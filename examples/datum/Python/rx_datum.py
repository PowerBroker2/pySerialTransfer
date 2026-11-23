"""Receive 32-bit float data from the matching Arduino sender example."""

import argparse
import sys
import time

from pySerialTransfer import pySerialTransfer as txfer
from pySerialTransfer.pySerialTransfer import Status


def main(argv=None):
    parser = argparse.ArgumentParser(description="Receive a float datum over UART.")
    parser.add_argument("--port", required=True, help="serial port, such as COM11 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default: 115200)")
    args = parser.parse_args(argv)
    link = None
    try:
        link = txfer.SerialTransfer(args.port, baud=args.baud, restrict_ports=False)
        if not link.open():
            raise RuntimeError("could not open serial port {!r}".format(args.port))
        while True:
            link.available()
            if link.status == Status.NEW_DATA:
                value = link.rx_obj(obj_type="f")
                if link.id_byte != 0 or link.bytes_read != 4 or value is None:
                    print("Received packet did not contain a complete float.", file=sys.stderr)
                else:
                    print(value)
            elif link.status in (Status.CRC_ERROR, Status.STALE_PACKET_ERROR):
                print("SerialTransfer parser reported {}".format(link.status.name), file=sys.stderr)
            else:
                time.sleep(0.001)
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
