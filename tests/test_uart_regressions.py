import struct
from unittest.mock import Mock

import pytest
import serial
from typer.testing import CliRunner

from pySerialTransfer import cli
from pySerialTransfer.CRC import CRC
from pySerialTransfer.pySerialTransfer import SerialTransfer, Status


def link_with(port):
    link = SerialTransfer("test", restrict_ports=False)
    link.connection = port
    return link


def test_real_pyserial_loopback_all_lengths():
    with serial.serial_for_url("loop://", timeout=0) as port:
        link = link_with(port)
        for length in range(256):
            payload = bytes((i + length) % 256 for i in range(length))
            link.tx_struct_obj(payload)
            assert link.send(length, packet_id=255 - length)
            assert link.available() == length
            assert link.status == Status.NEW_DATA
            assert link.id_byte == 255 - length
            assert link.rx_obj(bytes) == payload


def test_reset_and_reconnect_discard_receive_state():
    with serial.serial_for_url("loop://", timeout=0) as port:
        link = link_with(port)
        for packet_id in (1, 2):
            assert link.send(0, packet_id)
        assert link.tick() and link.id_byte == 1
        link.close()
        assert link.open()
        assert not link.tick()
        assert link.id_byte == 0
        port.write(b"\x7e\x03")
        assert not link.tick()
        port.write(b"\x00")
        link.reset()
        assert port.in_waiting == 0
        assert link.send(0, 9)
        assert link.tick() and link.id_byte == 9


def test_partial_tail_expires_at_read_time(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("pySerialTransfer.pySerialTransfer.time.monotonic", lambda: now[0])
    with serial.serial_for_url("loop://", timeout=0) as port:
        link = link_with(port)
        port.write(b"\x7e\x00\x00\x00\x7e\x02")
        assert link.tick()
        now[0] = 3
        assert not link.tick()
        assert link.status == Status.STALE_PACKET_ERROR


def test_busy_noise_source_yields_from_each_poll():
    port = Mock(is_open=True, in_waiting=8192)
    port.read.side_effect = [bytes(4096), AssertionError("read twice in one poll")]
    link = link_with(port)
    assert not link.tick()
    port.read.assert_called_once_with(4096)


@pytest.mark.parametrize("obj", [2, "€", [0, 1], {"a": 1}])
def test_typed_write_requires_room_for_whole_value(obj):
    link = SerialTransfer("test", restrict_ports=False)
    original = link.tx_buff
    snapshot = bytes(original)
    assert link.tx_obj(obj, start_pos=254) is None
    assert original is link.tx_buff
    assert bytes(original) == snapshot


def test_list_pack_failure_preserves_alias_and_contents():
    link = SerialTransfer("test", restrict_ports=False)
    original = link.tx_buff
    assert link.tx_obj([1, object()]) is None
    assert link.tx_buff is original
    assert not any(original)


def test_invalid_decodes_are_bounded_by_field_and_packet():
    link = SerialTransfer("test", restrict_ports=False)
    link.rx_buff[:5] = b"abcde"
    link.bytes_read = 5
    assert link.rx_obj(str, obj_byte_size=6) is None
    assert link.rx_obj(int, obj_byte_size=2) is None
    assert link.rx_obj(list, obj_byte_size=6, list_format="B") is None
    assert link.rx_obj("4x") is None
    assert link.rx_obj("2H") == struct.unpack("<2H", b"abcd")
    link.rx_buff[:4] = b"null"
    assert link.rx_obj(dict, obj_byte_size=4) is None


def test_crc_polynomial_change_updates_table():
    crc = CRC()
    before = crc.calculate(b"123456789")
    crc.poly = 0x07
    assert crc.calculate(b"123456789") == 0xF4
    assert crc.calculate(b"123456789") != before


def test_no_args_is_successful_help():
    result = CliRunner().invoke(cli.app, [])
    assert result.exit_code == 0
    assert "Usage:" in result.stdout and "ports" in result.stdout


def test_listen_drains_queued_packets_without_poll_sleep(monkeypatch):
    with serial.serial_for_url("loop://", timeout=0) as port:
        link = link_with(port)
        assert link.send(0, 1)
        assert link.send(0, 2)
        monkeypatch.setattr(cli, "_open_link", lambda *args: link)
        monkeypatch.setattr(cli.time, "sleep", lambda *_: pytest.fail("slept with queued packets"))
        result = CliRunner().invoke(cli.app, ["listen", "--port", "test", "--count", "2"])
        assert result.exit_code == 0, result.exception
        assert len(result.stdout.splitlines()) == 2


def test_send_waits_for_board_then_preserves_empty_frame(monkeypatch):
    link = Mock()
    monkeypatch.setattr(cli, "_open_link", lambda *args: link)
    delay = Mock()
    monkeypatch.setattr(cli.time, "sleep", delay)
    result = CliRunner().invoke(cli.app, ["send", "--port", "test", "--hex", "", "--startup-delay", "0.01"])
    assert result.exit_code == 0, result.exception
    delay.assert_called_once_with(0.01)
    link.send.assert_called_once_with(0, packet_id=0)
    link.close.assert_called_once()

