from flockwave.connections.base import TaskConnectionBase, ReadableConnection
from typing import Callable, List, Optional, TYPE_CHECKING

from trio import (
    CapacityLimiter,
    Event,
    Lock,
    from_thread,
    move_on_after,
    open_memory_channel,
    to_thread,
)
from trio.abc import ReceiveChannel, SendChannel

from .devices import HIDDescriptor

if TYPE_CHECKING:
    from hid import device as Device

__all__ = ("GamepadConnection",)


class GamepadConnection(TaskConnectionBase, ReadableConnection[List[int]]):
    """Class that represents a connection to a single gamepad device."""

    _descriptor: HIDDescriptor
    """The HID descriptor of the device that the connection will connect to."""

    _limiter: CapacityLimiter
    """Capacity limiter for spawning the worker thread so it does not use up
    the standard Trio thread pool.
    """

    _rx_queue: Optional[ReceiveChannel[List[int]]]
    """Queue that is used to receive the bytes read from the gamepad device
    in the worker thread.
    """

    def __init__(self, descriptor: HIDDescriptor):
        """Constructor.

        Parameters:
            descriptor: the Human Interface Device to connect to as a gamepad
        """
        super().__init__()
        self._descriptor = descriptor
        self._limiter = CapacityLimiter(16)
        self._lock = Lock()
        self._rx_queue = None
        self._request_stop_event = None
        self._stopped_event = None

    async def _run(self, started) -> None:
        import hid

        device = hid.device()
        await to_thread.run_sync(device.open_path, self._descriptor.path)

        tx_queue, rx_queue = open_memory_channel(0)
        request_stop, stopped = Event(), Event()

        self._rx_queue = rx_queue

        try:
            await to_thread.run_sync(
                self._worker,
                device,
                tx_queue,
                started,
                request_stop.is_set,
                stopped.set,
                abandon_on_cancel=True,
                limiter=self._limiter,
            )
        except OSError as ex:
            if ex.args == ("read error",):
                # Device was probably disconnected, this is okay, let's send
                # an empty list to indicate that the channel is now closed
                await tx_queue.send([])
            else:
                raise
        finally:
            request_stop.set()
            with move_on_after(3):
                await stopped.wait()
            self._rx_queue = None

    async def read(self) -> List[int]:
        assert self._rx_queue is not None
        return await self._rx_queue.receive()

    def _worker(
        self,
        device: "Device",
        tx_queue: SendChannel[bytes],
        started: Callable[[], None],
        is_stopped: Callable[[], bool],
        stopped: Callable[[], bool],
    ) -> None:
        """Main worker loop of the connection that is being executed on a
        separate thread.
        """
        from_thread.run_sync(started)
        try:
            while not is_stopped():
                data = device.read(256, 0.25)
                if data:
                    from_thread.run(tx_queue.send, data)
        finally:
            from_thread.run_sync(stopped)
