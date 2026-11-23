"""Send a packed marker, float, and UTF-8 text payload over UART."""

import argparse
import sys
import time

from pySerialTransfer import pySerialTransfer as txfer


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send a marker, float, and text packet repeatedly.")
    parser.add_argument("--port", required=True, help="serial port, such as COM11 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default: 115200)")
    args = parser.parse_args(argv)
    link = None
    try:
        link = txfer.SerialTransfer(args.port, baud=args.baud, restrict_ports=False)
        if not link.open():
            raise RuntimeError("could not open serial port {!r}".format(args.port))
        time.sleep(2)  # allow boards that reset on serial open to restart
        while True:
            send_size = link.tx_obj("$", val_type_override="c")
            if send_size is None:
                raise RuntimeError("could not pack the marker byte")
            send_size = link.tx_obj(4.5, start_pos=send_size)
            if send_size is None:
                raise RuntimeError("could not pack the float value")
            send_size = link.tx_obj("hello", start_pos=send_size)
            if send_size is None or not link.send(send_size):
                raise RuntimeError("could not send the complete data packet")
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    raise SystemExit(main())
