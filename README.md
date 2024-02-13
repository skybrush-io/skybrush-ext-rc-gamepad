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

## Known Issues

### Accessing USB devices without sudo permissions on Ubuntu

When attempting to use USB devices with applications on Ubuntu, users might encounter permission issues that prevent the application from accessing the device without elevated privileges.

**Solution: Creating a custon udev rule for USB devices**

To solve this issue, you can create a udev rule to set the appropriate permissions for your USB device, allowing non-root users to access it.

1. **Identify the vendor and product ID of your USB device**:
   - Connect your USB device to your Ubuntu machine.
   - Open a Terminal (`Ctrl + Alt + T`) and run the command `lsusb`. This lists all connected USB devices.
   - Locate your device in the list and note the `ID` part, which is formatted as `idVendor:idProduct`. For example, `054c:05c4`.

2. **Create a udev rule file**:
   - Use a text editor in the Terminal to create a new udev rule file in the `/etc/udev/rules.d/` directory. For instance, using `nano`:
     ```
     sudo nano /etc/udev/rules.d/99-usbdevices.rules
     ```

3. **Add a custom udev rule**:
   - In the editor, add the following line, substituting `your_idVendor_here` and `your_idProduct_here` with your device's actual vendor and product IDs from the `lsusb` output:
     ```
     SUBSYSTEM=="usb", ATTRS{idVendor}=="your_idVendor_here", ATTRS{idProduct}=="your_idProduct_here", MODE="0666"
     ```
   - This rule adjusts the permissions for your specific USB device, allowing all users read/write access.

4. **Save and close the file**:
   - If using `nano`, press `Ctrl + O` to save, followed by `Ctrl + X` to exit.

5. **Reload udev rules**:
   - To apply the new rule, reload the udev rules with the following command:
     ```
     sudo udevadm control --reload-rules && sudo udevadm trigger
     ```

6. **Test your device**:
   - Disconnect and reconnect your USB device, then test it with your application to ensure it operates correctly without needing sudo permissions.

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
