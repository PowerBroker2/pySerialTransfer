#include "SerialTransfer.h"

// Use Serial for USB, or change to Serial1 for a USB-to-UART adapter.
#define FILE_PORT Serial
const uint16_t FILE_LIMIT = 4096;
const uint32_t FNV_BASIS = 2166136261UL;
SerialTransfer transfer;
bool receiving = false;
uint16_t expectedSize, nextOffset;
uint32_t expectedHash, runningHash;

uint16_t read16(const uint8_t* p)
{
  return uint16_t(p[0]) | (uint16_t(p[1]) << 8);
}

uint32_t read32(const uint8_t* p)
{
  return uint32_t(read16(p)) | (uint32_t(read16(p + 2)) << 16);
}

void showResult(bool valid)
{
#ifdef LED_BUILTIN
  digitalWrite(LED_BUILTIN, valid ? HIGH : LOW);
#else
  (void)valid;
#endif
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
  if (!transfer.tick())
    return;

  const uint8_t* p = transfer.packet.rxBuff;
  const uint8_t n = transfer.bytesRead;
  switch (transfer.currentPacketID())
  {
    case 0: // Size, checksum, filename (1..31 bytes).
      showResult(false);
      receiving = false;
      if (n < 7 || n > 37 || read16(p) > FILE_LIMIT)
        return;
      expectedSize = read16(p);
      expectedHash = read32(p + 2);
      nextOffset = 0;
      runningHash = FNV_BASIS;
      receiving = true;
      break;

    case 1: // Offset followed by file bytes.
      if (!receiving)
        return;
      if (n <= 2 || read16(p) != nextOffset || uint16_t(n - 2) > expectedSize - nextOffset)
      {
        receiving = false;
        return;
      }
      // This example verifies the stream without storing the whole file in RAM.
      // To save it, write p + 2 through p + n to a temporary file here.
      for (uint16_t i = 2; i < n; ++i)
        runningHash = (runningHash ^ p[i]) * 16777619UL;
      nextOffset += n - 2;
      break;

    case 2: // Publish success only after both size and checksum match.
      if (receiving && n == 6 && read16(p) == expectedSize
          && nextOffset == expectedSize && read32(p + 2) == expectedHash
          && runningHash == expectedHash)
        showResult(true);
      receiving = false;
      break;
  }
}
