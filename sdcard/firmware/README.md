# sdcard/firmware/

Drop Flipper firmware images here, one folder per firmware:

```
sdcard/firmware/
├── official/    firmware.bin   (or .elf)
├── momentum/    firmware.bin
└── unleashed/   firmware.bin
```

Then:

```
python tools/firmware_manager.py list          # see what's installed
python tools/firmware_manager.py run official   # boot it in Renode
```

Where to get images: `python tools/firmware_manager.py sources`.

**This is experimental** — the ARM firmware runs on a hand-written STM32WB55
Renode platform, but the radios, BLE and display controller are not emulated
yet. Read [`../../RENODE.md`](../../RENODE.md) for exactly what works and what
doesn't, and the bring-up checklist.
