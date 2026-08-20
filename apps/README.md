# apps/

Put `.fap` files here and run them with:

    python -m fapemu run apps/snake.fap

List what's here:

    python -m fapemu list

## Where to get .fap files

They are not included in this repo (they are other people's software, each with
its own licence). Two easy sources:

- The official app catalog at <https://lab.flipper.net/apps> — download any app
  and you get a `.fap`.
- Your own Flipper's SD card, under `/ext/apps/<category>/`.

Apps built for API version **87.1** (firmware 1.4.x / Momentum mntm-012) are
what fapemu targets. `python -m fapemu info <file>` prints the API version a
`.fap` was built against, and lists anything it imports that is not implemented.
