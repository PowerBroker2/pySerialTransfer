#include "SerialTransfer.h"

// Use Serial for USB, or change to Serial1 for a USB-to-UART adapter.
#define FILE_PORT Serial
const char fileName[] = "sample.bin";
const uint16_t fileSize = 512;
SerialTransfer transfer;

// A generated binary file spans multiple packets without using 512 bytes of RAM.
uint8_t fileByte(uint16_t offset)
{
  return uint8_t(offset);
}

void put16(uint8_t* p, uint16_t value)
{
  p[0] = uint8_t(value);
  p[1] = uint8_t(value >> 8);
}

void putMetadata(uint32_t hash)
{
  uint8_t* p = transfer.packet.txBuff;
  put16(p, fileSize);
  put16(p + 2, uint16_t(hash));
  put16(p + 4, uint16_t(hash >> 16));
}

bool sendFile()
{
  uint32_t hash = 2166136261UL;
  for (uint16_t i = 0; i < fileSize; ++i)
    hash = (hash ^ fileByte(i)) * 16777619UL;

  putMetadata(hash);
  memcpy(transfer.packet.txBuff + 6, fileName, sizeof(fileName) - 1);
  transfer.sendData(6 + sizeof(fileName) - 1, 0);
  if (transfer.transmissionStatus)
    return false;
  for (uint16_t offset = 0; offset < fileSize;)
  {
    const uint16_t remaining = fileSize - offset;
    const uint16_t count = remaining < MAX_PACKET_SIZE - 2 ? remaining : MAX_PACKET_SIZE - 2;
    put16(transfer.packet.txBuff, offset);
    for (uint16_t i = 0; i < count; ++i)
      transfer.packet.txBuff[2 + i] = fileByte(offset + i);
    transfer.sendData(2 + count, 1);
    if (transfer.transmissionStatus)
      return false;
    offset += count;
    delay(100);
  }
  putMetadata(hash);
  transfer.sendData(6, 2);
  return transfer.transmissionStatus == 0;
}

void setup()
{
#ifdef LED_BUILTIN
  pinMode(LED_BUILTIN, OUTPUT);
#endif
  FILE_PORT.begin(115200);
  transfer.begin(FILE_PORT, false);
}

void loop()
{
  const bool sent = sendFile();
#ifdef LED_BUILTIN
  digitalWrite(LED_BUILTIN, sent ? HIGH : LOW);
#endif
  delay(sent ? 10000 : 120);
}
