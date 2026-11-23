"""Send a 32-bit float datum to the matching Arduino receiver example."""

import argparse
import sys
import time

from pySerialTransfer import pySerialTransfer as txfer


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send one float repeatedly over UART.")
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
            send_size = link.tx_obj(4.5)
            if send_size is None or not link.send(send_size):
                raise RuntimeError("could not send the complete float packet")
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
