"""Class that scans the USB bus for devices that we can treat as a USB gamepad."""

from trio import to_thread
from typing import Optional, Set, Tuple

from .devices import ChannelMap, HIDDescriptor, SupportedDeviceRules

__all__ = ("GamepadScanner",)


class GamepadScanner:
    """Class that scans the USB bus for devices that we can treat as a USB gamepad."""

    _rules: SupportedDeviceRules

    def __init__(self):
        self._rules = SupportedDeviceRules.create()

    @property
    def rules(self) -> SupportedDeviceRules:
        """Returns the ruleset used by this scanner to decide whether a particular
        USB HID is supported.
        """
        return self._rules

    async def scan(self) -> Optional[Tuple[HIDDescriptor, ChannelMap]]:
        result = await to_thread.run_sync(self._scan_sync, cancellable=True)
        return result  # type: ignore

    def _scan_sync(self) -> Optional[Tuple[HIDDescriptor, ChannelMap]]:
        """Blocking core of the ``scan()`` method. Must be run on a separate
        thread so we don't block the main Trio loop.
        """
        import hid

        seen: Set[HIDDescriptor] = set()
        for device in hid.enumerate():
            # Limit ourselves to generic HID devices only
            if device.get("usage_page") not in (0, 1):
                continue

            # Extract the vendor / product ID, the manufacturer, the product
            # and the serial number
            try:
                descriptor = HIDDescriptor.from_dict(device)
            except Exception:
                continue

            # Have we seen this device already (maybe with a different usage
            # page)?
            if descriptor in seen:
                continue

            seen.add(descriptor)

            # Can we handle this device?
            rule = self._rules.match(descriptor)
            if rule:
                return descriptor, rule.channels
