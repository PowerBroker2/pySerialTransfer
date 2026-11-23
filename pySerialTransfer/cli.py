"""Typer command line for the pySerialTransfer UART library."""

import json
import math
import time
from typing import Optional

import typer

from .pySerialTransfer import (
    DEFAULT_TIMEOUT,
    MAX_PACKET_SIZE,
    SerialTransfer,
    Status,
    serial_ports,
)


HELP_CONTEXT = {"help_option_names": ["-h", "--help"]}
OVERVIEW = """pySerialTransfer is the PC-side UART companion to the Arduino SerialTransfer library.

It sends and receives packetized bytes over a serial port, either through a
USB serial connection or a USB-to-UART adapter. The UART frame is
START (0x7E), packet ID, payload length, payload, and CRC-8 (polynomial 0x9B).
Payloads can contain 0 to 255 bytes. The Python library also provides helpers
for packing and unpacking common Python values; those payload bytes should be
laid out to match the Arduino program.

Commands:
  ports   List detected serial ports.
  send    Send one text or hexadecimal payload.
  listen  Print received packets as JSON lines.

Examples:
  pySerialTransfer ports
  pySerialTransfer send --port COM3 --text hello
  pySerialTransfer send --port COM3 --hex "00 7e ff" --packet-id 0x10
  pySerialTransfer listen --port COM3 --count 1

Run pySerialTransfer COMMAND --help for every command's options and examples."""

app = typer.Typer(
    name="pySerialTransfer",
    help=OVERVIEW,
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
    context_settings=HELP_CONTEXT,
)


@app.callback()
def overview(ctx: typer.Context) -> None:
    """Show the overview when the command is run without arguments."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def parse_packet_id(value: str) -> int:
    """Parse a decimal or prefixed hexadecimal/octal/binary packet ID."""
    try:
        base = 0 if value.lower().startswith(("0x", "0o", "0b")) else 10
        packet_id = int(value, base)
    except ValueError as exc:
        raise typer.BadParameter("packet ID must be an integer") from exc
    if not 0 <= packet_id <= 255:
        raise typer.BadParameter("packet ID must be between 0 and 255")
    return packet_id


def parse_inter_byte_timeout(value: str) -> Optional[float]:
    """Parse an inter-byte timeout in seconds, or none/off to disable it."""
    if value.lower() in ("none", "off", "disabled"):
        return None
    try:
        timeout = float(value)
    except ValueError as exc:
        raise typer.BadParameter("timeout must be seconds or none") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise typer.BadParameter("timeout must be finite and positive; use none to disable it")
    return timeout


def parse_payload(hex_text: Optional[str] = None, text: Optional[str] = None) -> bytes:
    """Convert the selected CLI payload option to bytes."""
    if (hex_text is None) == (text is None):
        raise ValueError("provide exactly one of --hex or --text")
    if hex_text is not None:
        try:
            return bytes.fromhex(hex_text)
        except ValueError as exc:
            raise ValueError("hex payload must contain hexadecimal byte pairs") from exc
    return text.encode("utf-8")


def _validate_serial_timeouts(timeout: float, write_timeout: Optional[float]) -> None:
    if not math.isfinite(timeout) or timeout < 0:
        raise typer.BadParameter("--timeout must be finite and non-negative")
    if write_timeout is not None and (not math.isfinite(write_timeout) or write_timeout < 0):
        raise typer.BadParameter("--write-timeout must be finite and non-negative")


def _open_link(
    port: str,
    baud: int,
    timeout: float,
    write_timeout: Optional[float],
    inter_byte_timeout: Optional[float],
) -> SerialTransfer:
    link = SerialTransfer(
        port,
        baud=baud,
        restrict_ports=False,
        debug=False,
        timeout=timeout,
        write_timeout=write_timeout,
        inter_byte_timeout=inter_byte_timeout,
    )
    if not link.open():
        raise RuntimeError("could not open serial port %s" % port)
    return link


@app.command(
    "ports",
    context_settings=HELP_CONTEXT,
)
def ports() -> None:
    """List available serial port names, sorted for easy selection."""
    found_ports = sorted(serial_ports())
    if not found_ports:
        typer.echo("No serial ports found", err=True)
        raise typer.Exit(code=1)
    for port in found_ports:
        typer.echo(port)


@app.command(
    "send",
    context_settings=HELP_CONTEXT,
)
def send(
    port: str = typer.Option(..., help="Serial port, such as COM3 or /dev/ttyUSB0."),
    baud: int = typer.Option(115200, help="UART baud rate; must match the Arduino sketch."),
    timeout: float = typer.Option(0.05, help="Serial read timeout in seconds."),
    startup_delay: float = typer.Option(
        2.0, help="Seconds to wait for a board that resets when opened. Use 0 for an always-ready UART."
    ),
    write_timeout: Optional[float] = typer.Option(
        None, help="Serial write timeout in seconds; omit to wait without a write timeout."
    ),
    inter_byte_timeout: str = typer.Option(
        str(DEFAULT_TIMEOUT),
        help="Maximum positive gap between frame bytes in seconds; use none to disable stale-frame checks.",
    ),
    packet_id: str = typer.Option(
        "0", help="Application packet ID from 0 to 255; decimal or 0x-prefixed hexadecimal."
    ),
    hex_payload: Optional[str] = typer.Option(
        None, "--hex", help="Payload as hexadecimal byte pairs, for example: 00 7e ff."
    ),
    text: Optional[str] = typer.Option(
        None, "--text", help="Payload as UTF-8 text. Choose this or --hex."
    ),
) -> None:
    """Send one packet. Exactly one of --hex or --text is required.

    Examples:
      pySerialTransfer send --port COM3 --text hello
      pySerialTransfer send --port COM3 --hex "00 7e ff" --packet-id 0x10
    """
    if baud <= 0:
        raise typer.BadParameter("--baud must be positive")
    if not math.isfinite(startup_delay) or startup_delay < 0:
        raise typer.BadParameter('--startup-delay must be finite and non-negative')
    _validate_serial_timeouts(timeout, write_timeout)
    try:
        inter_timeout = parse_inter_byte_timeout(inter_byte_timeout)
        packet_id_value = parse_packet_id(packet_id)
        payload = parse_payload(hex_payload, text)
    except (typer.BadParameter, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if len(payload) > MAX_PACKET_SIZE:
        raise typer.BadParameter("payload exceeds %d bytes" % MAX_PACKET_SIZE)

    link = None
    try:
        link = _open_link(port, baud, timeout, write_timeout, inter_timeout)
        if startup_delay:
            time.sleep(startup_delay)
        link.tx_struct_obj(payload)
        if not link.send(len(payload), packet_id=packet_id_value):
            raise RuntimeError("serial write did not complete")
        typer.echo(json.dumps({
            "sent": True,
            "packet_id": packet_id_value,
            "length": len(payload),
            "payload_hex": payload.hex(),
        }))
    except Exception as exc:
        typer.echo("error: %s" % exc, err=True)
        raise typer.Exit(code=1) from exc
    finally:
        if link is not None:
            link.close()


@app.command(
    "listen",
    context_settings=HELP_CONTEXT,
)
def listen(
    port: str = typer.Option(..., help="Serial port, such as COM3 or /dev/ttyUSB0."),
    baud: int = typer.Option(115200, help="UART baud rate; must match the Arduino sketch."),
    timeout: float = typer.Option(0.05, help="Serial read timeout in seconds."),
    inter_byte_timeout: str = typer.Option(
        str(DEFAULT_TIMEOUT),
        help="Maximum positive gap between frame bytes in seconds; use none to disable stale-frame checks.",
    ),
    count: Optional[int] = typer.Option(
        None, help="Stop after this many valid packets; omit to continue until interrupted."
    ),
    duration: Optional[float] = typer.Option(
        None, help="Stop after this many seconds; omit to listen until interrupted."
    ),
    poll_interval: float = typer.Option(
        0.005, help="Seconds to sleep between receive polls when no packet is ready."
    ),
) -> None:
    """Listen for packets and print JSON lines containing their ID and payload.

    Examples:
      pySerialTransfer listen --port COM3 --count 1
      pySerialTransfer listen --port /dev/ttyUSB0 --duration 10
    """
    if baud <= 0:
        raise typer.BadParameter("--baud must be positive")
    _validate_serial_timeouts(timeout, None)
    if count is not None and count <= 0:
        raise typer.BadParameter("--count must be positive")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise typer.BadParameter("--duration must be finite and positive")
    if not math.isfinite(poll_interval) or poll_interval <= 0:
        raise typer.BadParameter("--poll-interval must be finite and positive")
    inter_timeout = parse_inter_byte_timeout(inter_byte_timeout)

    link = None
    received = 0
    try:
        link = _open_link(port, baud, timeout, None, inter_timeout)
        deadline = None if duration is None else time.monotonic() + duration
        while deadline is None or time.monotonic() < deadline:
            link.available()
            if link.status == Status.NEW_DATA:
                payload = bytes(link.rx_buff[:link.bytes_read])
                try:
                    decoded_text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    decoded_text = None
                typer.echo(json.dumps({
                    "packet_id": link.id_byte,
                    "length": link.bytes_read,
                    "payload_hex": payload.hex(),
                    "text": decoded_text,
                }))
                received += 1
                if count is not None and received >= count:
                    return
                continue
            elif link.status in (Status.CRC_ERROR, Status.STALE_PACKET_ERROR):
                typer.echo("error: %s" % link.status.name, err=True)
            delay = poll_interval if deadline is None else min(poll_interval, deadline - time.monotonic())
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt as exc:
        raise typer.Exit(code=130) from exc
    except Exception as exc:
        typer.echo("error: %s" % exc, err=True)
        raise typer.Exit(code=1) from exc
    finally:
        if link is not None:
            link.close()

    if count is not None and received < count:
        typer.echo("error: received %d of %d requested packets" % (received, count), err=True)
        raise typer.Exit(code=1)


def main() -> None:
    """Run the installed pySerialTransfer command."""
    app(prog_name="pySerialTransfer")
