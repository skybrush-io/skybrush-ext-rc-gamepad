"""Extension that adds support for handling USB gamepad devices as virtual
remote controllers.
"""

from .extension import RCGamepadExtension as construct

__all__ = ("construct",)

description = "RC input source using USB gamepads"
dependencies = ("hotplug", "rc", "signals")
tags = ("experimental",)
schema = {}
