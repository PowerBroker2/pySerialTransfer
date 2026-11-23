"""Receive verified files from the SerialTransfer.h UART file sender example."""

import argparse
from pathlib import Path
import sys
import time

from file_transfer import FileReceiver
from pySerialTransfer import pySerialTransfer as txfer
from pySerialTransfer.pySerialTransfer import Status


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Receive files from the SerialTransfer.h UART file sender example."
    )
    parser.add_argument("--port", required=True, help="serial port, such as COM11 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default: 115200)")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(), help="directory for verified files")
    args = parser.parse_args(argv)

    receiver = FileReceiver()
    link = None
    try:
        link = txfer.SerialTransfer(args.port, baud=args.baud, restrict_ports=False)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if not link.open():
            raise RuntimeError("could not open serial port {!r}".format(args.port))
        print("Listening on {} at {} baud.".format(args.port, args.baud))
        while True:
            link.available()
            if link.status == Status.NEW_DATA:
                payload = bytes(link.rx_buff[:link.bytes_read])
                try:
                    completed = receiver.process(link.id_byte, payload)
                except ValueError as exc:
                    print("Rejected file packet: {}".format(exc), file=sys.stderr)
                    continue
                if completed is not None:
                    name, data = completed
                    destination = args.output_dir / name
                    try:
                        with destination.open("xb") as output:
                            output.write(data)
                    except FileExistsError:
                        print("Skipped existing file: {}".format(destination), file=sys.stderr)
                        continue
                    print("Saved {} ({} bytes) to {}".format(name, len(data), destination))
            elif link.status in (Status.CRC_ERROR, Status.STALE_PACKET_ERROR):
                print("SerialTransfer parser reported {}".format(link.status.name), file=sys.stderr)
            else:
                time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nStopped listening.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    raise SystemExit(main())
