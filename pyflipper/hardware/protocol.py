"""The PyFlipper Bridge serial protocol (v1).

A simple newline-delimited ASCII protocol so it is trivial to implement on an
Arduino/ESP32.  The host (this emulator) sends a command line; the device
replies with one or more lines terminated by a final status line.

Handshake
    ->  PING
    <-  PONG PyFlipperBridge 1 caps=SUBGHZ,NFC,IR,RFID,GPIO,IBUTTON

Sub-GHz
    ->  SUBGHZ RX <freq_hz> <preset>          start receiving
    <-  EVT SUBGHZ <freq> <rssi> <hex...>     (streamed, 0+ times)
    ->  SUBGHZ STOP
    ->  SUBGHZ TX <freq> <preset> <protocol> <bits> <te> <hexkey>
    <-  OK | ERR <msg>
    ->  SUBGHZ RAWTX <freq> <preset> <t0> <t1> ...   (signed us; + = high)
    <-  OK | ERR <msg>

NFC
    ->  NFC POLL
    <-  NFC <type> <uidhex> <atqahex> <sak> | NFC NONE
    ->  NFC EMU <uidhex> <atqahex> <sak>
    <-  OK | ERR
    ->  NFC STOP

125 kHz RFID
    ->  RFID READ
    <-  RFID <type> <datahex> | RFID NONE
    ->  RFID WRITE <type> <datahex>
    ->  RFID EMU <type> <datahex>
    ->  RFID STOP

Infrared
    ->  IR RX
    <-  IR <protocol> <address> <command> | IR RAW <freq> <t0> <t1> ... | IR NONE
    ->  IR TX <protocol> <address> <command>
    ->  IR RAWTX <freq> <duty> <t0> <t1> ...

iButton / 1-Wire
    ->  IBTN READ
    <-  IBTN <type> <datahex> | IBTN NONE
    ->  IBTN EMU <type> <datahex>

GPIO
    ->  GPIO MODE <pin> <in|out>
    ->  GPIO SET <pin> <0|1>
    ->  GPIO GET <pin>
    <-  GPIO <pin> <0|1>

Generic replies: 'OK', 'ERR <msg>', and asynchronous 'EVT ...' lines.
"""
from __future__ import annotations

PROTOCOL_VERSION = 1
GREETING = "PyFlipperBridge"

# Presets shared by both sides.
PRESETS = ["AM270", "AM650", "FM238", "FM476"]

# Command verbs
PING = "PING"
PONG = "PONG"
OK = "OK"
ERR = "ERR"
EVT = "EVT"


def encode(*parts) -> bytes:
    """Join command parts into a newline-terminated line."""
    return (" ".join(str(p) for p in parts) + "\n").encode("ascii", "replace")


def parse_caps(pong_line: str):
    """Extract the capability set from a PONG line."""
    caps = set()
    for tok in pong_line.split():
        if tok.startswith("caps="):
            caps = {c.strip().upper() for c in tok[5:].split(",") if c.strip()}
    return caps
