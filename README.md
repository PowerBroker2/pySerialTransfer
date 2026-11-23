# pySerialTransfer

Python package to transfer data in a fast, reliable, and packetized form over serial/UART.

If using this package to communicate with Arduinos, see [SerialTransfer](https://github.com/PowerBroker2/SerialTransfer) for the corresponding and compatible library (also available through the Arduino IDE's Libraries Manager).

Use Python to send and receive packets with an Arduino over a USB serial connection or a USB-to-UART adapter. Each packet carries up to 255 payload bytes and an application-defined ID. The package includes a Python API for two-way exchanges and the `pySerialTransfer` command for inspecting ports, sending a packet, and watching incoming traffic.

## Quick start: get an echo from your board

### 1. Install the matching libraries

This development checkout requires Python 3.8 or later.

In a terminal, change to this **pySerialTransfer** checkout and run:

```console
python -m pip install -e .
pySerialTransfer --help
```

This installs the checkout and its CLI into the active Python environment. If the command is missing from your shell's path, use `python -m pySerialTransfer` anywhere this guide uses `pySerialTransfer`.

On the board, use the version of [Arduino SerialTransfer](https://github.com/PowerBroker2/SerialTransfer) that documents `START | ID | LENGTH | PAYLOAD | CRC`. The older protocol with byte stuffing and a stop byte is incompatible. If the Arduino checkout is already in your sketchbook's `libraries/SerialTransfer` folder, the IDE can use it there. Otherwise, install its ZIP using **Sketch > Include Library > Add .ZIP Library**. [Arduino library installation guide](https://docs.arduino.cc/software/ide-v2/tutorials/ide-v2-installing-a-library/)

### 2. Upload the Arduino sketch

Connect the board to the computer with a USB data cable. The sketch below uses the board port exposed to the computer as `Serial`. Select the board and port in the Arduino IDE, paste the sketch into a new sketch window, and upload it. Close the IDE's Serial Monitor before opening the port in Python.

```cpp
#include <SerialTransfer.h>

SerialTransfer transfer;

void setup() {
  Serial.begin(115200);
  transfer.begin(Serial, false);
}

void loop() {
  if (transfer.tick()) {
    // Return the original payload and packet ID.
    memcpy(transfer.packet.txBuff, transfer.packet.rxBuff, transfer.bytesRead);
    transfer.sendData(transfer.bytesRead, transfer.currentPacketID());
  }
}
```

For a **USB-to-UART adapter**, use a board with an available hardware UART such as `Serial1`. Change both occurrences of `Serial` in `setup()` to that UART. Connect adapter TX to board RX1, adapter RX to board TX1, and GND to GND. Use an adapter with logic levels compatible with the board. Select the adapter's port in Python. On a direct USB connection, the USB cable handles both directions.

### 3. Send and receive on the same port

Run `pySerialTransfer ports` and find the port that appears when you plug in the board, for example `COM3` on Windows or `/dev/ttyACM0` on Linux.

Save the following as `echo.py`. It sends the word `hello` with packet ID 1, waits for its reply on the same open connection, then closes the port.

```python
import sys
import time
from pySerialTransfer import pySerialTransfer as txfer

port = sys.argv[1]
link = txfer.SerialTransfer(port, baud=115200)
try:
    if not link.open():
        raise OSError(f"Could not open {port}")
    time.sleep(2)  # Some boards restart when the port opens.
    size = link.tx_obj("hello")
    if size is None or not link.send(size, packet_id=1):
        raise OSError("Could not send hello")

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        link.available()
        if link.status == txfer.Status.NEW_DATA and link.id_byte == 1:
            print(bytes(link.rx_buff[:link.bytes_read]).decode("utf-8"))
            break
        time.sleep(0.001)
    else:
        raise TimeoutError("No echo within three seconds")
finally:
    link.close()
```

Run `python echo.py COM3` with the port you found earlier. On Linux or macOS, substitute the full device name. Printing `hello` confirms that the packet reached the board and the reply reached Python.

## Command line

Run `pySerialTransfer` or `pySerialTransfer --help` for an overview. Each command accepts `-h` or `--help` and lists its options and defaults.

| Command | Use it when |
| --- | --- |
| `pySerialTransfer ports` | You need the names of serial devices available to Python. |
| `pySerialTransfer send --port COM3 --text hello` | You want to send one UTF-8 message. The command prints the packet details and closes the connection. |
| `pySerialTransfer send --port COM3 --hex "00 7e ff" --packet-id 0x10` | You know the payload bytes and packet ID. Supply exactly one of `--hex` and `--text`. |
| `pySerialTransfer listen --port COM3 --count 1 --duration 5` | A device transmits on its own. Print the next packet as JSON and stop, or report an error if five seconds pass first. |

Substitute your device name for `COM3`. Sender and receiver must agree on `--baud` (115200 by default). Run `pySerialTransfer send --help` for write and startup timing. The separate `send` and `listen` commands each open the port anew. For request/reply exchanges, use the Python example above so the reply stays on the same connection.

### Troubleshooting your first packet

| Symptom | What to check |
| --- | --- |
| The port is missing or fails to open | Use a USB data cable, close the Serial Monitor and other port users, and check your account's serial-device permissions. |
| The port opens but the echo times out | Check the selected port, baud rate and sketch. A board that restarts on port open may need a longer startup delay. For adapters, check crossed TX/RX, ground and logic voltage. |
| CRC errors or unreadable packets | Confirm the protocol versions match and keep diagnostic text off the data stream. Use a separate debug port. |
| Payload bytes look right but decoded numbers are wrong | Check the byte order and width of each field on both ends. |

## Working with payloads

Packet IDs are numbers from 0 through 255. Give each message type an ID and decide its payload layout on both sides. To send opaque bytes, use `link.tx_struct_obj(data)` with at most 255 bytes, then pass its returned length to `link.send(length, packet_id=...)`. A successful send means the local serial connection accepted the frame. If the application needs delivery confirmation, have the receiver reply.

`tx_obj(value, start_pos=...)` packs a Python value and returns the next free byte offset. `rx_obj(type, start_pos=...)` reads a value from the current payload. The default byte order is little-endian. A Python `int` uses four signed bytes, a `float` uses four bytes, and a string uses UTF-8. For binary data containing zeros, use the raw bytes in `rx_buff[:bytes_read]`.

For example, message ID 7 can carry a two-byte unsigned channel followed by a four-byte signed count. On a little-endian Arduino, pack `uint16_t channel` and `int32_t count` separately with `txObj`. The six bytes for channel 3 and count -42 are `03 00 D6 FF FF FF`. After a completed Python receive:

```python
import struct

if link.status == txfer.Status.NEW_DATA and link.id_byte == 7:
    if link.bytes_read == 6:
        channel, count = struct.unpack_from("<Hi", link.rx_buff)
        print(channel, count)
```

With the library helpers the same fields are `link.rx_obj("H")` and `link.rx_obj("i", start_pos=2)`. For lists of fixed-width values, specify a byte count and a format, such as `link.rx_obj(list, obj_byte_size=8, list_format="i")` for two signed 32-bit integers. Arduino struct padding and the platform-dependent widths of `int` and `double` can affect the wire layout.

The `send` command waits two seconds after opening the port so boards that reset can finish booting. Set `--startup-delay 0` for a link that is already ready.

## Advanced: parsing, timeouts, and callbacks

`available()` polls for one completed packet and returns its payload length. Always use `status == Status.NEW_DATA` when an empty payload is meaningful. Both an empty packet and an idle poll return zero. Read or copy `rx_buff[:bytes_read]` before polling again. Extra buffered frames can be consumed on subsequent calls.

The OS read timeout (`timeout`) and parser timeout (`inter_byte_timeout`) are separate, both in seconds. The parser default is 0.05 seconds. It discards an incomplete packet when it observes a gap that long. Pass `inter_byte_timeout=None` in Python or `--inter-byte-timeout none` in the CLI to disable that check. Use an application deadline when waiting for a reply. `Status.CRC_ERROR` means the checksum failed, and `Status.STALE_PACKET_ERROR` reports an expired partial frame.

For dispatch by ID, use `set_callbacks()` and poll with `tick()`. Position zero in the callback list corresponds to packet ID zero. This snippet assumes `link` is open:

```python
def on_message():
    print(bytes(link.rx_buff[:link.bytes_read]))

link.set_callbacks([on_message])
while True:
    if not link.tick():
        time.sleep(0.001)
```

### Wire format

| Field | Bytes | Meaning |
| --- | ---: | --- |
| Start | 1 | Always `0x7E`. |
| ID | 1 | Application-defined message type, 0 to 255. |
| Length | 1 | Number of payload bytes, 0 to 255. |
| Payload | Length | Any bytes, including `0x00` and `0x7E`. |
| CRC | 1 | CRC-8 over ID, length, and payload, in that order. |

CRC calculation starts at zero, uses polynomial `0x9B`, processes the most significant bit first, and applies no final XOR. For example, ID 0 with payload `01 02 03 04` produces the eight wire bytes `7E 00 04 01 02 03 04 6A`. Once the parser knows the length, it can consume a literal `0x7E` inside the payload. There is no escaping or trailing delimiter.

### File transfers and paired examples

The USB examples pair one program on the computer with the opposite sketch on the board. Run the Python scripts from the repository root. For a float, use the [datum examples](examples/datum/). For a marker, float, and text in a single message, use the [data examples](examples/data/).

| Direction | Upload to the Arduino | Run on the computer |
| --- | --- | --- |
| Computer sends a file | [rx_file.ino](examples/file/Arduino/rx_file/rx_file.ino) | `python examples/file/Python/tx_file.py --port COM3 sample.bin` |
| Computer receives a file | [tx_file.ino](examples/file/Arduino/tx_file/tx_file.ino) | `python examples/file/Python/rx_file.py --port COM3 --output-dir received` |

These file sketches use USB `Serial` by default. To use a separate adapter on a board with `Serial1`, set `FILE_PORT` to `Serial1` in the selected sketch. The example accepts up to 4096 file bytes. Packet ID 0 carries the size, a 32-bit FNV-1a checksum, and filename. ID 1 carries a two-byte little-endian offset followed by up to 253 data bytes. ID 2 repeats the size and checksum. The receiver checks every offset and verifies the completed file. This one-way protocol detects incomplete transfers. The Arduino library's separate acknowledged file examples use different IDs and support retries.

On boards with `LED_BUILTIN`, the Arduino receiver lights it after a valid file arrives. The Python receiver saves verified files into the output directory and skips filenames that already exist.
