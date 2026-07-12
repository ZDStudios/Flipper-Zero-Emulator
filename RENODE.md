# Running real Flipper firmware in Renode (EXPERIMENTAL bring-up)

> **Read this first.** This is the "boot the actual Momentum/Unleashed/official
> firmware binary" track you asked for. It is a genuine bring-up effort, **not a
> finished VM**. Here's the honest state of it.

## The honest reality

- **Renode does not ship a platform for the STM32WB55** — the exact chip in the
  Flipper. Renode has STM32 F0/F1/F3/F4/F7/G0/H7/L0/L4/L5, `stm32wba52` (a
  different, newer WB**A** part) and `stm32w108`, but **no WB55**.
- **No public "Flipper in Renode" project exists.** (A GitHub search for
  `flipper renode` returns zero repositories.) Nobody has published one.

So there was nothing to install and point at a firmware. This directory is a
**hand-written STM32WB55 platform built from scratch** (from the RM0434 memory
map) so you have a real starting point. Getting a full firmware to boot cleanly
is an ongoing reverse-engineering task — the files here get you to the start
line and document the road.

## Why the radios still won't work (even here)

Even once the CPU boots, the Flipper's sub-GHz (CC1101) and NFC (ST25R3916) are
**external chips on SPI**, driven with microsecond / 13.56 MHz timing. Renode
doesn't model those chips, and you can't tunnel their raw SPI/RF timing out to an
ESP32 over USB (milliseconds of latency vs. microseconds of signal). So in
emulation the radio apps will hang or error. **Real RF needs a real Flipper.**
This track is for exploring/booting the firmware's UI and logic, not for RF.

## What's in this folder

| File | What it is |
|---|---|
| [`renode/stm32wb55.repl`](renode/stm32wb55.repl) | The STM32WB55 platform: CPU + NVIC + correct RAM/flash map + peripheral register blocks (stubbed as memory, with the real Renode model to swap in noted on each). |
| [`renode/flipper.resc`](renode/flipper.resc) | Loads a firmware image at `0x08000000`, sets the vector table, and starts. |
| [`tools/firmware_manager.py`](tools/firmware_manager.py) | The "VM manager": list images, show download sources, launch one in Renode. |

## Prerequisites

1. **Renode 1.15+** — <https://renode.io/> (or unzip the portable build into
   `./renode_bin/`). The Windows portable-dotnet build needs **.NET 8**.
2. **A firmware image** in `sdcard/firmware/<name>/` (e.g. `firmware.bin`).
   `python tools/firmware_manager.py sources` lists where to get official,
   Momentum, Unleashed and RogueMaster releases. A `.elf` from a source build
   boots most reliably; a `.bin`/`.dfu` from a release also works.

## Quick start

```bash
python tools/firmware_manager.py doctor          # check Renode + files
python tools/firmware_manager.py list            # installed images
python tools/firmware_manager.py run momentum    # boot it in Renode
# or drive Renode directly:
renode renode/flipper.resc -e '$bin=@sdcard/firmware/momentum/firmware.bin; start'
```

Inside Renode: `start` runs, `pause` stops, `cpu PC` shows the program counter,
`sysbus` prints the memory map, `logLevel 0` shows every peripheral access
(invaluable for finding the next register the firmware is waiting on).

## What works / what doesn't

| | Status |
|---|---|
| Platform loads, CPU starts fetching from flash | Target of this scaffold |
| Early boot / clock init | Needs RCC ready-bits (see checklist) |
| UART console output | After swapping `usart1` to a real UART model |
| Display / UI on screen | Needs a display-controller model (not done) |
| Sub-GHz / NFC / RF | **Not possible in emulation** (see above) |
| BLE / radio coprocessor (M0+) | Not emulated |

## Bring-up checklist (how to push it further)

1. **Console first.** Turn `usart1` into `UART.STM32F7_USART`, add
   `showAnalyzer sysbus.usart1`, and watch the firmware's boot log. Everything
   else is easier once you can see what it prints.
2. **Clocks.** Replace the `rcc` memory stub with a real model, or use
   `sysbus Tag` in `flipper.resc` to force the HSE/HSI/PLL "ready" bits so the
   `while(!(RCC->CR & …RDY))` loops fall through.
3. **Systick + timers.** Wire `TIM2`/`TIM16` as `Timers.STM32_Timer` so FreeRTOS
   ticks and the scheduler runs.
4. **GPIO.** `GPIOPort.STM32F4GPIOPort` for the buttons and chip-selects; inject
   button presses with `sysbus.gpioX.PressButton`-style commands.
5. **Display.** The hardest part — model the SPI display controller (ST756x) so
   the framebuffer renders. This is what gives you the actual Flipper UI.
6. **Leave the radios stubbed** — they can't be made real here.

Use `logLevel -1 sysbus` and `sysbus LogPeripheralAccess` to see exactly which
unmodelled register the firmware touches next, then model that one. Iterate.

## Verification status

Verified on Renode 1.16.1 (Windows portable-dotnet, .NET 8):

- `stm32wb55.repl` loads with no errors; all 39 defined components register
  (`cpu` as `CortexM`, `nvic` as `NVIC`, flash/SRAM/GPIO/USART/SPI/RCC/timers as
  memory), confirmed with Renode's `peripherals` command.
- `flipper.resc` loads a raw `.bin` at `0x08000000` and correctly sets the stack
  pointer and program counter from the firmware's vector table (checked with a
  crafted image: `cpu SP` read back `0x20030000` as encoded).
- `firmware_manager.py run <name>` launches Renode and loads the image end to end.
- Not there yet: a real Momentum/Unleashed image booting to its UI. That needs
  the bring-up checklist above (console UART, then clock ready-bits, timers, GPIO,
  and a display model). The radios stay impossible in emulation.

If a Renode build is unpacked in `./renode_bin/`, `firmware_manager.py doctor`
finds it automatically; otherwise install Renode from <https://renode.io/>.
