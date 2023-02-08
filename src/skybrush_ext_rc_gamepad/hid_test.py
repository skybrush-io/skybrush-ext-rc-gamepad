from contextlib import closing

import hid


def suppress_keyboardinterrupt(func):
    def decorated():
        try:
            return func()
        except KeyboardInterrupt:
            pass

    return decorated


@suppress_keyboardinterrupt
def main():
    while True:
        devices = [None]
        for device in hid.enumerate():
            if not device['vendor_id'] or not device['product_id']:
                continue

            if device.get("usage_page") not in (0, 1):
                continue

            index = len(devices)
            decoded_path = device['path'].decode("utf-8", "replace")
            print(f"{index:2}: 0x{device['vendor_id']:04x}:0x{device['product_id']:04x}\t{device['product_string']}  {decoded_path}")
            devices.append(device['path'])

        print()
        print("Please enter the index of the device you want to test, an empty string to re-scan, or anything else to exit:")
        selected = input()
        if not selected:
            continue

        try:
            selected = int(selected)
        except Exception:
            return
        else:
            break


    gamepad = hid.device()
    print("Opening device...")
    gamepad.open_path(devices[selected])
    print("Device opened successfully, reading input reports. Press ^C to abort.")
    with closing(gamepad):
        while True:
            report = gamepad.read(64)
            if report:
                print(bytes(report).hex(" "), end="\r")


if __name__ == "__main__":
    import sys
    sys.exit(main())

