import sys
from pathlib import Path

import pytest

EXAMPLE_DIR = (Path(__file__).resolve().parents[1] / "examples" / "file" / "Python")
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from file_transfer import (  # noqa: E402
    FILE_BUFFER_SIZE,
    FileReceiver,
    file_hash,
    iter_file_chunks,
    make_file_header,
    make_file_trailer,
)


def test_file_hash_matches_32_bit_fnv1a():
    assert file_hash(b"") == 0x811C9DC5
    assert file_hash(b"hello") == 0x4F9F2CAB


def test_file_transfer_helpers_round_trip_data():
    data = bytes(range(256)) * 3 + b"tail"
    header = make_file_header("sample.bin", data)
    receiver = FileReceiver()
    assert receiver.process(0, header) is None
    chunks = list(iter_file_chunks(data))
    assert [len(chunk) - 2 for chunk in chunks] == [253, 253, 253, 13]
    for chunk in chunks:
        assert receiver.process(1, chunk) is None
    assert receiver.process(2, make_file_trailer(data)) == ("sample.bin", data)


@pytest.mark.parametrize(
    "name",
    ["../escape.bin", "folder\\escape.bin", "", ".", "..", "CON.txt", "NUL .txt", "CONIN$", "COM¹.txt", "bad:name.txt"],
)
def test_file_header_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        make_file_header(name, b"data")


def test_file_header_rejects_size_above_receiver_capacity():
    with pytest.raises(ValueError):
        make_file_header("large.bin", bytes(FILE_BUFFER_SIZE + 1))


def test_receiver_rejects_out_of_order_and_corrupt_trailer():
    data = b"abcdef"
    receiver = FileReceiver()
    receiver.process(0, make_file_header("x.bin", data))
    with pytest.raises(ValueError, match="out of order"):
        receiver.process(1, b"\x01\x00abc")
    assert receiver.active is False

    receiver.process(0, make_file_header("x.bin", data))
    for chunk in iter_file_chunks(data):
        receiver.process(1, chunk)
    with pytest.raises(ValueError, match="checksum"):
        receiver.process(2, b"\x06\x00\x00\x00\x00\x00")


def test_empty_file_round_trips():
    receiver = FileReceiver()
    receiver.process(0, make_file_header("empty.txt", b""))
    assert receiver.process(2, make_file_trailer(b"")) == ("empty.txt", b"")


def test_receiver_accepts_null_terminated_arduino_filename():
    data = b"from Arduino"
    receiver = FileReceiver()
    receiver.process(0, make_file_header("arduino.txt", data) + b"\x00")
    for chunk in iter_file_chunks(data):
        receiver.process(1, chunk)
    assert receiver.process(2, make_file_trailer(data)) == ("arduino.txt", data)
