"""Emulated address space layout.

Regions are far apart so a stray pointer lands in unmapped space and is
reported, instead of silently corrupting something else.

    0x00000000  (unmapped)   null-pointer trap
    0x10000000  APP    16M   relocated .text/.rodata/.data/.bss, followed by
                             the import trampolines
    0x20000000  HEAP   32M   malloc/free arena
    0x30000000  STACK   1M   app stack (grows down from the top)
    0x60000000  OBJ     1M   opaque handles for host-side objects
    0x70000000  RET     4K   magic return address: entry point returning here
                             means the app finished

The trampolines deliberately sit just past the app's own sections rather than
in a region of their own. Some apps call imports with a direct ``bl``, whose
Thumb-2 range is only +/-16 MB, so the stubs have to be near the code that
branches to them.
"""

APP_BASE = 0x10000000
APP_SIZE = 0x01000000

HEAP_BASE = 0x20000000
HEAP_SIZE = 0x02000000

STACK_BASE = 0x30000000
STACK_SIZE = 0x00100000
STACK_TOP = STACK_BASE + STACK_SIZE - 16   # initial SP (16-byte aligned headroom)

API_SLOT = 4
API_MAX_IMPORTS = 8192

OBJ_BASE = 0x60000000
OBJ_SIZE = 0x00100000
OBJ_SLOT = 16                  # spacing between handles

RET_MAGIC = 0x70000000
RET_SIZE = 0x1000

PAGE = 0x1000


def align_up(value: int, alignment: int) -> int:
    if alignment <= 1:
        return value
    return (value + alignment - 1) & ~(alignment - 1)

# ARM Cortex-M System Control Space (SCB, SysTick, NVIC registers).
SCS_BASE = 0xE0000000
SCS_SIZE = 0x00100000
CPACR = 0xE000ED88          # coprocessor access control (FPU enable)
