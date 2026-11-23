"""Send a file to the SerialTransfer.h UART file receiver example."""

import argparse
import math
from pathlib import Path
import sys
import time

from file_transfer import FILE_BUFFER_SIZE, iter_file_chunks, make_file_header, make_file_trailer
from pySerialTransfer import pySerialTransfer as txfer


def send_payload(link, payload, packet_id):
    link.tx_buff[:len(payload)] = payload
    if not link.send(len(payload), packet_id=packet_id):
        raise RuntimeError("serial write did not send the complete packet")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Transfer one file to the SerialTransfer.h UART file receiver example."
    )
    parser.add_argument("file", type=Path, help="file to send (maximum 4096 bytes)")
    parser.add_argument("--port", required=True, help="serial port, such as COM11 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud rate (default: 115200)")
    parser.add_argument("--startup-delay", type=float, default=2.0,
                        help="seconds after opening the port for the board to reset (default: 2)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.startup_delay) or args.startup_delay < 0:
        parser.error("--startup-delay must be finite and non-negative")

    link = None
    try:
        with args.file.open("rb") as source:
            data = source.read(FILE_BUFFER_SIZE + 1)
        name = args.file.name
        header = make_file_header(name, data)
        trailer = make_file_trailer(data)
        link = txfer.SerialTransfer(args.port, baud=args.baud, restrict_ports=False)
        if not link.open():
            raise RuntimeError("could not open serial port {!r}".format(args.port))
        time.sleep(args.startup_delay)
        send_payload(link, header, 0)
        time.sleep(0.1)
        for chunk in iter_file_chunks(data):
            send_payload(link, chunk, 1)
            # Give small MCU UART receive buffers time to drain between frames.
            time.sleep(0.1)
        send_payload(link, trailer, 2)
        print("Sent {!r} ({} bytes). The Arduino receiver validates its checksum.".format(name, len(data)))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        if link is not None:
            link.close()


if __name__ == "__main__":
    raise SystemExit(main())
