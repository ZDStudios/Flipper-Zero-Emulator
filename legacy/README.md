# legacy/

These are the files from the **original** state of this repo — a fork of the
["flippulator"](https://github.com/Milk-Cool/flippulator) skeleton, which tried
to reimplement the Flipper firmware in C and compile real apps with SDL.

In this repo that approach was never finished: the `Makefile` references
`flipper_hal/`, `helpers/` and `lib/` directories that don't exist, and it only
builds on Linux (`-m32`, `-lbsd`, `termios`). It does **not** run.

The project was rewritten from scratch in Python (+ C++ for the hardware
bridge). See the top-level `README.md`. These files are kept only for history.
