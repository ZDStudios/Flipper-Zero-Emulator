# PyFlipper Bridge firmware (ESP32 / Arduino)

This is the **radio side** of the emulator. Flash it to an ESP32 (recommended)
or an Arduino, plug it into USB, and the PyFlipper desktop app relays Sub-GHz,
NFC, IR, RFID, iButton and GPIO operations to the real hardware wired to it.

## Quick start (no radio modules needed)

1. Open `pyflipper_bridge/pyflipper_bridge.ino` in the Arduino IDE.
2. Select your board (e.g. *ESP32 Dev Module*) and port, then **Upload**.
3. With every `USE_*` flag left at `0`, the board still speaks the protocol and
   returns *simulated* data — so you can confirm the USB link first.
4. In the emulator: **Settings → Hardware → Rescan**. It should switch from
   `Simulation` to `HW COMx` and list the capabilities the firmware advertises.

Then enable modules one at a time by setting the matching flag to `1` at the top
of the sketch and wiring the module as below.

## Modules & wiring

### Sub-GHz — CC1101 (`#define USE_CC1101 1`)
Libraries: **SmartRC-CC1101-Driver-Lib** (`ELECHOUSE_CC1101`) and **RCSwitch**.

| CC1101 | ESP32 | Arduino Uno |
|--------|-------|-------------|
| VCC    | 3V3   | 3V3 (NOT 5V)|
| GND    | GND   | GND         |
| CSN    | GPIO5 | D10         |
| SCK    | GPIO18| D13         |
| MOSI   | GPIO23| D11         |
| MISO   | GPIO19| D12         |
| GDO0   | GPIO2 | D2          |

### NFC — PN532 (`#define USE_PN532 1`)
Library: **Adafruit PN532**. Put the module in **I2C** mode (DIP switches).

| PN532 | ESP32  | Arduino Uno |
|-------|--------|-------------|
| VCC   | 3V3    | 5V          |
| GND   | GND    | GND         |
| SDA   | GPIO21 | A4          |
| SCL   | GPIO22 | A5          |

### Infrared (`#define USE_IR 1`)
Library: **IRremote** (v3+). IR LED (through a transistor + resistor) on the TX
pin, a TSOP38238-style receiver on the RX pin (ESP32: TX=GPIO4, RX=GPIO15).

### GPIO / iButton
Always available. GPIO pin numbers in the protocol map directly to board pins.
For iButton, a DS9092 probe on a 1-Wire pin with a 2.2k pull-up.

## Legal / safety

Only transmit on frequencies and with power levels you are licensed/allowed to
use in your country, and only interact with devices you own or are authorised to
test. Sub-GHz TX with `USE_CC1101` transmits real RF. This project is for
learning, interoperability and authorised testing.

## Protocol

The full command/response grammar lives in
[`pyflipper/hardware/protocol.py`](../pyflipper/hardware/protocol.py). It is
plain ASCII lines at 115200 baud, so you can also drive the board by hand from
any serial monitor (type `PING` and press enter).
