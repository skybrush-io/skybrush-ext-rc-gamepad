from ast import literal_eval
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch
from typing import cast, Any, Dict, Iterable, List, Optional, Tuple, Union

from .utils import Scaler

__all__ = (
    "HIDDescriptor",
    "ChannelDefinition",
    "ChannelMap",
    "ChannelMappingType",
    "Rule",
    "SupportedDeviceRules",
)


@dataclass(frozen=True)
class HIDDescriptor:
    """Main properties of a USB Human Interface Device that can be used to
    decide whether we support this device or not.
    """

    path: bytes
    """The path of the device, used to identify it uniquely in the system"""

    vid: int
    """The vendor ID of the device"""

    pid: int
    """The product ID of the device"""

    manufacturer: str = ""
    """The manufacturer of the device"""

    product: str = ""
    """The product name of the device"""

    serial_number: str = ""
    """The serial number of the device"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Constructs a Human Interface Device descriptor from a dictionary
        representation that typically appears in the result of
        ``hid.enumerate()``.
        """
        return cls(
            path=data["path"],
            vid=int(data["vendor_id"]),
            pid=int(data["product_id"]),
            manufacturer=data["manufacturer_string"] or "",
            product=data["product_string"] or "",
            serial_number=data["serial_number"] or "",
        )

    def format(self) -> str:
        """Returns a nicely formatted, human-readable string representation
        of the descriptor.
        """
        parts: List[str] = []
        if self.manufacturer:
            parts.append(self.manufacturer)
        if self.product:
            parts.append(self.product)
        if self.serial_number:
            parts.append(f"(S/N: {self.serial_number})")
        return " ".join(parts) if parts else "unknown HID device"


class ChannelMappingType(Enum):
    AXIS = "axis"
    BUTTON = "button"
    MULTI_BUTTON = "multibutton"
    HAT = "hat"


# N NE E SE S SW W NW
_hat_to_value: Dict[str, List[int]] = {
    "x": [0, 1, 1, 1, 0, -1, -1, -1] + [0] * 8,
    "y": [-1, -1, 0, 1, 1, 1, 0, -1] + [0] * 8,
}


@dataclass
class ChannelDefinition:
    """Definition of a single mapping from one or more gamepad axes or buttons
    to an RC channel.
    """

    channel: int
    """Index of the channel (0-based)"""

    type: ChannelMappingType
    """Specifies how the channel value is determined from the gamepad axes
    and buttons.

    See https://github.com/ArduPilot/MAVProxy/blob/master/docs/JOYSTICKS.md
    for more details.
    """

    offset: int = 0
    """Byte offset in the HID report that corresponds to this entry."""

    bit: int = 0
    """Index of the bit to look at in the byte pointed to by the offset. The
    LSB is bit 0, the MSB is bit 7. Used only when the type is
    `ChannelMappingType.BUTTON` or `ChannelMappingType.HAT`. When the type is
    `ChannelMappingType.HAT`, the bit must point to the _least_ significant
    bit of four consecutive bits in the report that encode the status of the
    hat in standard gamepad conventions (8 = released, 0 = North, 1 = Northeast,
    2 = East and so on).
    """

    axis: str = "x"
    """Specifies which axis of a hat switch to look at; used only when the
    type is `ChannelMappingType.HAT`.
    """

    buttons: List[Tuple[int, int, int]] = field(default_factory=list)
    """A list of offset-bit-value triplets, one for each possible state of a
    multi-button mapping.
    """

    in_range: Tuple[int, int] = (0, 255)
    """Input range coming from the gamepad that is to be mapped to the output
    range of the RC channel. Closed from both ends.
    """

    out_range: Tuple[int, int] = (0, 65535)
    """Output range of the RC channel being mapped. Closed from both ends.
    Note that Skybrush Server uses 16 bits to represent an RC channel; these
    will be mapped to a more conventional [1000; 2000] range in drone-specific
    extensions if needed.
    """

    invert: bool = False
    """Whether to invert the in-range when mapping a value from the gamepad to
    the corresponding RC channel.
    """

    signed: bool = False
    """Whether to treat the in-range as a signed byte when mapping a value from
    the gamepad to the corresponding RC channel; used only when the type is
    `ChannelMappingType.AXIS`.
     """

    _scaler: Optional[Scaler] = None

    @classmethod
    def from_json(cls, obj: Dict[str, Any]):
        if not isinstance(obj, dict):
            raise TypeError(f"control definition must be an object, got {type(obj)!r}")

        # Extract channel index
        channel = obj.get("channel")
        if not isinstance(channel, int):
            raise TypeError("channel index must be an integer")
        if channel < 1:
            raise ValueError("channel indices must be positive")
        channel -= 1

        # Extract channel type
        channel_type = ChannelMappingType(obj.get("type"))

        # Parse offset and bit index
        offset = int(obj.get("offset", 0))
        bit = int(obj.get("bit", 0))

        # Extract axis
        if "axis" in obj:
            axis = str(obj["axis"]).lower()
            if axis != "x" and axis != "y":
                raise ValueError("axis must be 'x' or 'y', got {axis!r}")
        else:
            axis = "x"

        # TODO(ntamas): parse buttons
        if "buttons" in obj:
            buttons = obj["buttons"]
            if not isinstance(buttons, (list, tuple)):
                raise TypeError(
                    f"button list for multi-button entries must be a list, got {type(buttons)!r}"
                )

            buttons = [cls._process_button_spec(spec) for spec in buttons]
        else:
            buttons = []

        # Parse whether input is signed
        signed = bool(obj.get("signed"))

        # Parse input range
        if "in_range" in obj:
            in_range = obj["in_range"]
            if not isinstance(in_range, (list, tuple)) or len(in_range) != 2:
                raise TypeError("in_range must be a list of length 2")

            in_range = int(in_range[0]), int(in_range[1])
        else:
            if signed:
                in_range = (-128, 127)
            else:
                in_range = (0, 255)

        # Parse output range
        if "out_range" in obj:
            out_range = obj["out_range"]
            if not isinstance(out_range, (list, tuple)) or len(out_range) != 2:
                raise TypeError("out_range must be a list of length 2")

            out_range = int(out_range[0]), int(out_range[1])
        else:
            out_range = (0, 65535)

        return cls(
            channel=channel,
            type=channel_type,
            offset=offset,
            bit=bit,
            axis=axis,
            buttons=buttons,
            in_range=in_range,
            out_range=out_range,
            invert=bool(obj.get("invert")),
            signed=signed,
        )

    @staticmethod
    def _process_button_spec(spec: Any) -> Tuple[int, int, int]:
        """Helper function for `from_json()` that parses a single button
        specification from a multi-button entry.
        """
        if not isinstance(spec, dict):
            raise TypeError(
                f"entry in multi-button specification must be an object, got {type(spec)!r}"
            )

        offset = int(spec.get("offset", 0))
        bit = int(spec.get("bit", 0))
        value = int(spec.get("value", 0))

        return offset, bit, value

    def update_channels_from_hid_report(
        self, channels: List[int], data: List[int]
    ) -> None:
        """Updates the list of channel values from the given HID status report."""
        if self.type is ChannelMappingType.AXIS:
            # bit is ignored, just take the byte at the given offset
            if self._scaler is None:
                self._scaler = Scaler(self.in_range, self.out_range, self.invert)
            if self.signed:
                value = (data[self.offset] & 0x7F) - (data[self.offset] & 0x80)
            else:
                value = data[self.offset]
            value = self._scaler(value)
            channels[self.channel] = int(round(value))

        elif self.type is ChannelMappingType.BUTTON:
            pressed = bool(data[self.offset] & (1 << self.bit))
            if self.invert:
                pressed = not pressed
            value = self.out_range[1] if pressed else self.out_range[0]
            channels[self.channel] = value

        elif self.type is ChannelMappingType.HAT:
            x = (data[self.offset] >> self.bit) & 0x0F
            value = _hat_to_value[self.axis][x]
            if value:
                if self.invert:
                    value = -value
                value = self.out_range[1] if value > 0 else self.out_range[0]
                channels[self.channel] = value

        elif self.type is ChannelMappingType.MULTI_BUTTON:
            # self.invert is intentionally ignored here
            for offset, bit, value in self.buttons:
                bit = data[offset] & (1 << bit)
                if bit:
                    channels[self.channel] = value
                    break


ChannelMap = List[ChannelDefinition]


@dataclass(frozen=True)
class Rule:
    """A single entry that describes a device and the mapping from its
    HID report to RC channels.

    The structure of this object is designed to be compatible with the
    joystick definitions found in MAVProxy.
    """

    conditions: List[Dict[str, Union[int, str]]]
    """List of conditions that define when the rule should be applied. The
    rule is applied if it matches at least one entry from the condition list.

    Each entry is a mapping of HID descriptor keys to the expected values. A
    device must match all the items in the mapping to match the entry.
    """

    channels: ChannelMap

    @classmethod
    def from_json(cls, obj: Dict[str, Any]):
        """Creates a rule from a JSON representation that is used in the
        `supported_devices.json` file that comes with the extension.
        """
        conditions = obj.get("match")
        if conditions is None:
            conditions = []

        if not isinstance(conditions, (list, tuple)):
            conditions = [conditions]

        conditions = [cls._process_condition(cond) for cond in conditions]

        channel_map = obj.get("controls")
        if not isinstance(channel_map, list):
            raise TypeError(f"channel map must be a list, got {type(channel_map)!r}")

        return cls(
            conditions,
            [ChannelDefinition.from_json(cast(Any, spec)) for spec in channel_map],
        )

    @staticmethod
    def _process_condition(cond: Any):
        if isinstance(cond, str):
            cond = {"product": cond}
        elif not isinstance(cond, dict):
            raise TypeError(f"rule conditions must be objects, got {type(cond)!r}")

        cond = cast(Dict[str, Any], cond)

        if "vid" in cond:
            if isinstance(cond["vid"], str):
                cond["vid"] = literal_eval(cond["vid"])
            if not isinstance(cond["vid"], int):
                raise TypeError("vendor ID must be an integer")

        if "pid" in cond:
            if isinstance(cond["pid"], str):
                cond["pid"] = literal_eval(cond["pid"])
            if not isinstance(cond["pid"], int):
                raise TypeError("product ID must be an integer")

        if "description" in cond:
            if not isinstance(cond["description"], str):
                raise TypeError("condition description must be a string")

        return cond

    def match(self, descriptor: HIDDescriptor) -> bool:
        """Returns whether the rule matches the given HID descriptor."""
        return any(self._match_entry(descriptor, entry) for entry in self.conditions)

    def _match_entry(
        self, descriptor: HIDDescriptor, entry: Dict[str, Union[int, str]]
    ) -> bool:
        for key in ("vid", "pid"):
            if key in entry and getattr(descriptor, key) != entry[key]:
                return False

        for key in ("manufacturer", "product", "serial_number"):
            if key in entry:
                pattern = entry[key]
                value = getattr(descriptor, key)
                if isinstance(pattern, str):
                    if not fnmatch(value, pattern):
                        return False
                else:
                    if value != pattern:
                        return False

        return True


class SupportedDeviceRules(Sequence[Rule]):
    """Class that holds a list of rules that determine which devices are
    supported and how their HID reports are mapped to RC channels.
    """

    _rules: List[Rule]

    @classmethod
    def create(cls, builtins: bool = True):
        """Creates a new ruleset.

        Parameters:
            builtins: whether to load the built-in rules into the ruleset.
        """
        result = cls()
        if builtins:
            result.extend_with_builtins()
        return result

    def __init__(self):
        """Constructor.

        Creates an empty ruleset.
        """
        self._rules = []

    def append(self, rule: Rule) -> None:
        """Adds the given rule to the end of the ruleset."""
        self._rules.append(rule)

    def clear(self) -> None:
        """Removes all rules from the ruleset."""
        self._rules.clear()

    def extend_from_json(self, obj: Any, *, prepend: bool = False) -> None:
        """Extends the ruleset from a JSON representation that is used in
        the ``supported_devices.json`` file.

        Parameters:
            prepend: whether to prepend the newly loaded rules to the existing
                list of rules
        """
        if not isinstance(obj, dict):
            raise TypeError(f"expected dict, got {type(obj)!r}")

        version = obj.get("version")
        if version != 1:
            raise ValueError("only version 1 objects are supported")

        rules = obj.get("rules")
        if not hasattr(rules, "__iter__"):
            raise TypeError(f"rules must be iterable, got {type(obj)!r}")

        for rule in cast(Iterable[Rule], rules):
            if isinstance(rule, dict):
                rule = Rule.from_json(rule)
                if prepend:
                    self.prepend(rule)
                else:
                    self.append(rule)

    def extend_with_builtins(self, *, prepend: bool = False) -> None:
        """Extends the ruleset with the built-in rules from the extension.

        Parameters:
            prepend: whether to prepend the newly loaded rules to the existing
                list of rules
        """
        from importlib.resources import open_text
        from json import load

        # open_text() is deprecated, but the new files() API breaks PyOxidizer
        # as of 2023-02-08. Migrate to files() only when this issue is fixed:
        # https://github.com/indygreg/PyOxidizer/issues/529
        # with files(__package__).joinpath("supported_devices.json").open("r") as fp:
        with open_text(__package__, "supported_devices.json") as fp:
            self.extend_from_json(load(fp), prepend=prepend)

    def match(self, descriptor: HIDDescriptor) -> Optional[Rule]:
        """Returns the first rule in the ruleset that matches the given HID
        descriptor, or ``None`` if no rule matches the HID descriptor.
        """
        for rule in self:
            if rule.match(descriptor):
                return rule

    def prepend(self, rule: Rule) -> None:
        """Prepends the given rule to the start of the ruleset."""
        self._rules.insert(0, rule)

    def __getitem__(self, index: int) -> Rule:
        return self._rules[index]

    def __len__(self):
        return len(self._rules)
