# Gamepad-as-simulated-RC extension for Skybrush Server

This repository contains an experimental extension module to Skybrush Server
that allows any gamepad that appears as a USB Human Interface Device to be
used as a simulated RC transmitter. Skybrush Server will take care of
periodically reading the HID input report bytes from the gamepad and converting
them to RC channel values according to a descriptor file that specifies which
bytes of the HID input report should be mapped to which RC channels.

## Installation

1. Check out this repository using git.

2. Install [`poetry`](https://python-poetry.org) if you haven't done so yet;
   `poetry` is a tool that allows you to install Skybrush Server and the
   extension you are working on in a completely isolated virtual environment.

3. Run `poetry install`; this will create a virtual environment and install
   Skybrush Server with all required dependencies in it, as well as the code
   of the extension.

4. Run `poetry shell` to open a shell associated to the virtual environment
   that you have just created.

5. In the shell prompt, type `skybrushd -c skybrushd.jsonc` to start the server
   with a configuration file that loads the extension.

## Adding support for a new gamepad

See [`src/skybrush_ext_rc_gamepad/supported_devices.json`][1]; this is the file
that contains the descriptors for all the gamepads that we currently support.
If you want to add a new one, you will typically need the USB vendor and
product ID of the gamepad so we can identify it uniquely in the USB device
list, and you will also need the documentation of how the HID input report
looks like.

Many gamepads out there provide data in the same format as the PlayStation 4
gamepad; the Horipad mini4 (which we support) is an example. If your gamepad
is compatible with the Horipad mini4, chances are that you can simply add its
USB vendor and product ID to the appropriate section of the device descriptor
file to implement support for your gamepad.

If you managed to make this extension work for one of your gamepads and we
do not support it officially yet, [open an issue][2] or send us a pull request
so we can add support for it in the next release.

[1]: https://github.com/skybrush-io/skybrush-ext-rc-gamepad/blob/main/src/skybrush_ext_rc_gamepad/supported_devices.json
[2]: https://github.com/skybrush-io/skybrush-ext-rc-gamepad/issues/new
