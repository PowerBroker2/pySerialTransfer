"""Receive and decode a marker, 32-bit float, and UTF-8 text payload."""

import argparse
import sys
import time

from pySerialTransfer import pySerialTransfer as txfer
from pySerialTransfer.pySerialTransfer import Status


def main(argv=None):
    parser = argparse.ArgumentParser(description="Receive and decode a packed data packet over UART.")
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
                marker = link.rx_obj(obj_type="c", start_pos=0)
                value = link.rx_obj(obj_type="f", start_pos=1)
                text = link.rx_obj(obj_type=str, start_pos=5, obj_byte_size=5)
                if link.id_byte != 0 or link.bytes_read != 10 or marker != b"$" or value is None or text is None:
                    print("Received packet did not match the expected 10-byte layout.", file=sys.stderr)
                else:
                    print("${} | {}".format(value, text))
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
