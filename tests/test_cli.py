import pytest
import typer
from typer.testing import CliRunner

from pySerialTransfer.cli import app, parse_inter_byte_timeout, parse_packet_id, parse_payload


runner = CliRunner()


def test_root_help_has_overview_commands_and_examples():
    result = runner.invoke(app, ["--help"], prog_name="pySerialTransfer")
    assert result.exit_code == 0
    assert "PC-side UART companion" in result.stdout
    assert "USB-to-UART adapter" in result.stdout
    assert "START (0x7E)" in result.stdout
    assert "ports" in result.stdout
    assert "send" in result.stdout
    assert "listen" in result.stdout
    assert "pySerialTransfer send --port COM3 --text hello" in result.stdout


def test_help_short_option_is_available():
    result = runner.invoke(app, ["-h"], prog_name="pySerialTransfer")
    assert result.exit_code == 0
    assert "Commands:" in result.stdout


def test_ports_help_explains_command():
    result = runner.invoke(app, ["ports", "--help"], prog_name="pySerialTransfer")
    assert result.exit_code == 0
    assert "List available serial port names" in result.stdout


def test_send_help_documents_every_option_and_payload_choice():
    result = runner.invoke(app, ["send", "--help"], prog_name="pySerialTransfer")
    assert result.exit_code == 0
    for option in (
        "--port", "--baud", "--timeout", "--write-timeout",
        "--inter-byte-timeout", "--packet-id", "--hex", "--text",
    ):
        assert option in result.stdout
    assert "Exactly one of --hex or --text is required" in result.stdout
    assert "0x10" in result.stdout


def test_listen_help_documents_every_option_and_examples():
    result = runner.invoke(app, ["listen", "--help"], prog_name="pySerialTransfer")
    assert result.exit_code == 0
    for option in (
        "--port", "--baud", "--timeout", "--inter-byte-timeout",
        "--count", "--duration", "--poll-interval",
    ):
        assert option in result.stdout
    assert "JSON lines" in result.stdout
    assert "--duration 10" in result.stdout


def test_parse_inter_byte_timeout():
    assert parse_inter_byte_timeout("50") == 50.0
    assert parse_inter_byte_timeout("none") is None


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "invalid"])
def test_reject_invalid_inter_byte_timeout(value):
    with pytest.raises(typer.BadParameter):
        parse_inter_byte_timeout(value)


def test_parse_hex_payload():
    assert parse_payload(hex_text="00 ff 7e") == bytes((0, 255, 126))


def test_parse_text_payload():
    assert parse_payload(text="hello") == b"hello"


def test_parse_packet_id_decimal_and_prefixed_integer():
    assert parse_packet_id("0") == 0
    assert parse_packet_id("0xff") == 255
    assert parse_packet_id("017") == 17


@pytest.mark.parametrize("value", ["256", "-1", "garbage"])
def test_reject_invalid_packet_id(value):
    with pytest.raises(typer.BadParameter):
        parse_packet_id(value)




def test_parse_inter_byte_timeout_rejects_zero():
    with pytest.raises(typer.BadParameter):
        parse_inter_byte_timeout('0')
