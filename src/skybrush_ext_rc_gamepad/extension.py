from aio_usb_hotplug import HotplugEvent, HotplugEventType
from contextlib import ExitStack
from functools import partial
from typing import Callable, List

from trio import open_nursery
from trio_util import RepeatedEvent

from flockwave.server.ext.base import Extension

from .connection import GamepadConnection
from .devices import HIDDescriptor, ChannelMap
from .scanner import GamepadScanner

__all__ = ("RCGamepadExtension",)


class RCGamepadExtension(Extension):
    """Extension that adds support for handling USB gamepad devices as virtual
    remote controllers.
    """

    async def run(self, app, configuration, logger):
        assert self.app is not None

        hotplug_event = self.app.import_api("signals").get("hotplug:event")
        scan_trigger = RepeatedEvent()

        with ExitStack() as stack:
            stack.enter_context(
                hotplug_event.connected_to(
                    partial(self._on_hotplug_event, scan_trigger)
                )
            )

            scanner = GamepadScanner()

            if "devices" in configuration:
                num_rules = len(scanner.rules)
                scanner.rules.extend_from_json(configuration["devices"], prepend=True)
                num_rules = len(scanner.rules) - num_rules
                if num_rules == 1:
                    logger.info("Loaded 1 custom device rule from configuration")
                elif num_rules > 1:
                    logger.info(
                        f"Loaded {num_rules} custom device rules from configuration"
                    )

            while True:
                maybe_result = await scanner.scan()
                if maybe_result:
                    device, channel_map = maybe_result
                    try:
                        await self._handle_gamepad(device, channel_map)
                    except Exception:
                        logger.exception(
                            "Unexpected exception caught from gamepad handler task"
                        )

                await scan_trigger.wait()

    async def _handle_gamepad(
        self, gamepad: HIDDescriptor, channel_map: ChannelMap
    ) -> None:
        assert self.app is not None
        assert self.log is not None

        notify = self.app.import_api("rc").notify
        notify_lost = self.app.import_api("rc").notify_lost

        formatted_name = gamepad.format()
        self.log.info(f"Using {formatted_name!r} as virtual RC")
        try:
            connection = GamepadConnection(gamepad)
            async with open_nursery() as nursery:
                connection.assign_nursery(nursery)
                with self.app.connection_registry.use(
                    connection, name="Gamepad RC input"
                ):
                    await connection.open()
                    try:
                        await self._handle_gamepad_connection(
                            connection, channel_map, notify
                        )
                    finally:
                        await connection.close()
        finally:
            notify_lost()
            self.log.info(f"{formatted_name!r} disconnected")

    async def _handle_gamepad_connection(
        self,
        conn: GamepadConnection,
        channel_map: ChannelMap,
        notify: Callable[[List[int]], None],
    ) -> None:
        if self.app is None:
            return

        num_channels = max((spec.channel + 1 for spec in channel_map), default=0)
        channels = [0] * num_channels

        while True:
            data = await conn.read()
            if not data:
                break

            for spec in channel_map:
                spec.update_channels_from_hid_report(channels, data)

            notify(channels)

    def _on_hotplug_event(
        self, scan_trigger: RepeatedEvent, sender, event: HotplugEvent
    ) -> None:
        """Handler called for hotplug events. Used to re-scan the USB bus to detect
        devices that look like gamepads.
        """
        if event.type is HotplugEventType.ADDED:
            scan_trigger.set()
