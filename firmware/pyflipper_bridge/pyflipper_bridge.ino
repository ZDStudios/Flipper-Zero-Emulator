/*
 * PyFlipper Bridge firmware
 * -------------------------
 * Turns an ESP32 (or Arduino) into the "radio side" of the PyFlipper emulator.
 * The PC emulator sends newline-delimited ASCII commands over USB serial and
 * this firmware drives the real hardware: a CC1101 for Sub-GHz, a PN532 for
 * NFC, an IR LED/receiver for infrared, plus GPIO and 1-Wire.
 *
 * Protocol (see pyflipper/hardware/protocol.py for the authoritative spec):
 *   ->  PING
 *   <-  PONG PyFlipperBridge 1 caps=SUBGHZ,IR,GPIO,...
 *   ->  SUBGHZ RX <freq> <preset>      (device streams: EVT SUBGHZ <freq> <rssi> <hex>)
 *   ->  SUBGHZ TX <freq> <preset> <protocol> <bits> <te> <hexkey>
 *   ->  IR TX <protocol> <address> <command>
 *   ->  GPIO SET <pin> <0|1> ...        etc.
 *
 * IMPORTANT: everything is gated behind USE_* flags.  With every flag off the
 * firmware still speaks the protocol and returns simulated data, so you can
 * verify the USB link on a bare board first, then enable modules as you wire
 * them.  Only operate radios you are legally allowed to on your local bands.
 *
 * Libraries (install only for the modules you enable):
 *   CC1101 : "SmartRC-CC1101-Driver-Lib" (ELECHOUSE_CC1101) + optional RCSwitch
 *   PN532  : "Adafruit PN532"
 *   IR     : "IRremote" (v3+)
 */

// ---------------------------------------------------------------------------
// Feature flags - turn these on as you wire each module.
// ---------------------------------------------------------------------------
#define USE_CC1101 0     // Sub-GHz radio on SPI
#define USE_PN532  0     // NFC reader on I2C
#define USE_IR     0     // IR LED (TX) + receiver (RX)
// GPIO and the protocol core are always available.

#define FW_VERSION 1
#define BAUD 115200

// ---------------------------------------------------------------------------
// Pin map (ESP32 defaults; change for your board / an Arduino Uno).
// ---------------------------------------------------------------------------
#if defined(ESP32)
  #define CC1101_CS   5
  #define CC1101_GDO0 2
  #define IR_TX_PIN   4
  #define IR_RX_PIN   15
#else
  #define CC1101_CS   10
  #define CC1101_GDO0 2
  #define IR_TX_PIN   3
  #define IR_RX_PIN   2
#endif

#if USE_CC1101
  #include <ELECHOUSE_CC1101_SRC_DRV.h>
  #include <RCSwitch.h>
  RCSwitch rc = RCSwitch();
#endif
#if USE_PN532
  #include <Wire.h>
  #include <Adafruit_PN532.h>
  Adafruit_PN532 nfc(-1, -1);   // I2C
#endif
#if USE_IR
  #include <IRremote.hpp>
#endif

// ---------------------------------------------------------------------------
// Serial line reader
// ---------------------------------------------------------------------------
static char lineBuf[256];
static uint8_t lineLen = 0;

bool subghzRx = false;
long subghzFreq = 433920000;

void setup() {
  Serial.begin(BAUD);
  pinMode(LED_BUILTIN, OUTPUT);

#if USE_CC1101
  ELECHOUSE_cc1101.Init();
  ELECHOUSE_cc1101.setMHZ(433.92);
  rc.enableReceive(CC1101_GDO0);
#endif
#if USE_PN532
  nfc.begin();
  nfc.SAMConfig();
#endif
#if USE_IR
  IrSender.begin(IR_TX_PIN);
  IrReceiver.begin(IR_RX_PIN, ENABLE_LED_FEEDBACK);
#endif

  Serial.println("READY PyFlipperBridge");
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
void ok()               { Serial.println("OK"); }
void err(const char* m) { Serial.print("ERR "); Serial.println(m); }

int splitTokens(char* s, char** out, int maxTok) {
  int n = 0;
  char* p = strtok(s, " ");
  while (p && n < maxTok) { out[n++] = p; p = strtok(NULL, " "); }
  return n;
}

// Parse a contiguous hex string ("0CF938") into bytes; returns count.
int hexToBytes(const char* hex, uint8_t* out, int maxLen) {
  int len = strlen(hex), n = 0;
  for (int i = 0; i + 1 < len && n < maxLen; i += 2) {
    char b[3] = { hex[i], hex[i + 1], 0 };
    out[n++] = (uint8_t) strtol(b, NULL, 16);
  }
  return n;
}

// ---------------------------------------------------------------------------
// Command handlers
// ---------------------------------------------------------------------------
void handlePing() {
  Serial.print("PONG PyFlipperBridge ");
  Serial.print(FW_VERSION);
  Serial.print(" caps=");
  // Advertise only what is compiled in (GPIO always).
  String caps = "GPIO";
#if USE_CC1101
  caps += ",SUBGHZ";
#endif
#if USE_PN532
  caps += ",NFC";
#endif
#if USE_IR
  caps += ",IR";
#endif
  Serial.println(caps);
}

void handleSubghz(char** t, int n) {
  if (n < 2) { err("subghz args"); return; }
  if (!strcmp(t[1], "RX")) {
    subghzRx = true;
    if (n >= 3) subghzFreq = atol(t[2]);
#if USE_CC1101
    ELECHOUSE_cc1101.setMHZ(subghzFreq / 1000000.0);
    rc.enableReceive(CC1101_GDO0);
#endif
    // no immediate reply; captures arrive as EVT lines
  } else if (!strcmp(t[1], "STOP")) {
    subghzRx = false;
  } else if (!strcmp(t[1], "TX")) {
    // SUBGHZ TX <freq> <preset> <protocol> <bits> <te> <hexkey>
    if (n < 7) { err("tx args"); return; }
#if USE_CC1101
    long freq = atol(t[2]);
    int bits = atoi(t[4]);
    long code = strtol(t[6], NULL, 16);
    ELECHOUSE_cc1101.setMHZ(freq / 1000000.0);
    rc.disableReceive();
    rc.enableTransmit(CC1101_GDO0);
    rc.setProtocol(1);
    rc.send(code, bits);
    rc.disableTransmit();
    rc.enableReceive(CC1101_GDO0);
    ok();
#else
    ok();  // simulated
#endif
  } else if (!strcmp(t[1], "RAWTX")) {
#if USE_CC1101
    // SUBGHZ RAWTX <freq> <preset> <t0> <t1> ...  (signed us; + = high)
    long freq = atol(t[2]);
    ELECHOUSE_cc1101.setMHZ(freq / 1000000.0);
    ELECHOUSE_cc1101.SetTx();
    pinMode(CC1101_GDO0, OUTPUT);
    for (int i = 4; i < n; i++) {
      long us = atol(t[i]);
      digitalWrite(CC1101_GDO0, us > 0 ? HIGH : LOW);
      delayMicroseconds(abs(us));
    }
    digitalWrite(CC1101_GDO0, LOW);
    ELECHOUSE_cc1101.SetRx();
    ok();
#else
    ok();
#endif
  } else {
    err("subghz cmd");
  }
}

void pollSubghz() {
  if (!subghzRx) return;
#if USE_CC1101
  if (rc.available()) {
    unsigned long v = rc.getReceivedValue();
    int bits = rc.getReceivedBitlength();
    rc.resetAvailable();
    if (v) {
      Serial.print("EVT SUBGHZ ");
      Serial.print(subghzFreq);
      Serial.print(" -60 ");
      // print value as hex bytes, MSB first
      int nbytes = (bits + 7) / 8;
      for (int i = nbytes - 1; i >= 0; i--) {
        uint8_t b = (v >> (i * 8)) & 0xFF;
        if (b < 16) Serial.print('0');
        Serial.print(b, HEX);
        if (i) Serial.print(' ');
      }
      Serial.println();
    }
  }
#endif
}

void handleNfc(char** t, int n) {
  if (n < 2) { err("nfc args"); return; }
  if (!strcmp(t[1], "POLL")) {
#if USE_PN532
    uint8_t uid[7], uidLen;
    if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen, 100)) {
      Serial.print("NFC MIFARE ");
      for (int i = 0; i < uidLen; i++) {
        if (uid[i] < 16) Serial.print('0');
        Serial.print(uid[i], HEX);
      }
      Serial.println(" 0004 08");
    } else {
      Serial.println("NFC NONE");
    }
#else
    Serial.println("NFC NONE");
#endif
  } else if (!strcmp(t[1], "EMU") || !strcmp(t[1], "STOP")) {
    ok();
  } else {
    err("nfc cmd");
  }
}

void handleIr(char** t, int n) {
  if (n < 2) { err("ir args"); return; }
  if (!strcmp(t[1], "TX")) {
    // IR TX <protocol> <address> <command>
    if (n < 4) { err("ir tx args"); return; }
#if USE_IR
    uint16_t addr = strtol(t[2], NULL, 0);
    uint8_t cmd = strtol(t[3], NULL, 0);
    IrSender.sendNEC(addr, cmd, 0);
    ok();
#else
    ok();
#endif
  } else if (!strcmp(t[1], "RX") || !strcmp(t[1], "STOP")) {
    ok();
  } else {
    err("ir cmd");
  }
}

void handleGpio(char** t, int n) {
  if (n < 3) { err("gpio args"); return; }
  int pin = atoi(t[2]);
  if (!strcmp(t[1], "MODE") && n >= 4) {
    pinMode(pin, !strcmp(t[3], "out") ? OUTPUT : INPUT);
    ok();
  } else if (!strcmp(t[1], "SET") && n >= 4) {
    digitalWrite(pin, atoi(t[3]) ? HIGH : LOW);
    ok();
  } else if (!strcmp(t[1], "GET")) {
    Serial.print("GPIO ");
    Serial.print(pin);
    Serial.print(' ');
    Serial.println(digitalRead(pin) ? 1 : 0);
  } else {
    err("gpio cmd");
  }
}

void dispatch(char* line) {
  char* t[40];
  int n = splitTokens(line, t, 40);
  if (n == 0) return;
  if      (!strcmp(t[0], "PING"))   handlePing();
  else if (!strcmp(t[0], "SUBGHZ")) handleSubghz(t, n);
  else if (!strcmp(t[0], "NFC"))    handleNfc(t, n);
  else if (!strcmp(t[0], "IR"))     handleIr(t, n);
  else if (!strcmp(t[0], "RFID"))   { if (n>=2 && !strcmp(t[1],"READ")) Serial.println("RFID NONE"); else ok(); }
  else if (!strcmp(t[0], "IBTN"))   { if (n>=2 && !strcmp(t[1],"READ")) Serial.println("IBTN NONE"); else ok(); }
  else if (!strcmp(t[0], "GPIO"))   handleGpio(t, n);
  else                              err("unknown");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen) { lineBuf[lineLen] = 0; dispatch(lineBuf); lineLen = 0; }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    }
  }
  pollSubghz();
}
