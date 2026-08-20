"""fapemu - run Flipper Zero .fap applications on a desktop computer.

A .fap is a relocatable ARM (Thumb-2) ELF object built for the Flipper's
Cortex-M4. It is not a standalone program: it imports the firmware's API
(furi_*, gui_*, canvas_*, ...) and the Flipper's loader resolves those imports
at load time.

fapemu does the same thing on your PC:

  1. parse and relocate the ELF into an emulated address space
  2. point every imported symbol at a trampoline address
  3. execute the app's real ARM code with the Unicorn CPU emulator
  4. when the code calls an imported function, trap it and run a Python
     implementation instead, drawing onto a real desktop window

So the application's own machine code runs unmodified; only the firmware
underneath it is substituted.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
