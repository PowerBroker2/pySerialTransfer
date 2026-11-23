#include "SerialTransfer.h"


SerialTransfer myTransfer;

struct __attribute__((packed)) STRUCT {
  char z;
  float y;
} testStruct;

char arr[6];


void setup()
{
  Serial.begin(115200);
  myTransfer.begin(Serial);
}


void loop()
{
  if (myTransfer.available() == sizeof(testStruct) + sizeof(arr) - 1 && myTransfer.currentPacketID() == 0)
  {
    // use this variable to keep track of how many
    // bytes we've processed from the receive buffer
    uint16_t recSize = 0;

    recSize = myTransfer.rxObj(testStruct, recSize);
    myTransfer.rxObj(arr, recSize, sizeof(arr) - 1);
    arr[sizeof(arr) - 1] = '\0';
  }
}
