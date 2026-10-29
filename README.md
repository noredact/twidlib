# TwidLib

A small desktop toolkit for the [TekGear Twiddler 4](https://www.mytwiddler.com/)
chording keyboard. It helps you look up what chords already type, queue up new
letter-pairing chords (like `ing`, `or`, `st`), and export a merged `.cfg` for
the official tuner — without plugging the Twiddler into USB every time you think
of a new pairing.

> The tool builds config files you upload to the tuner website. It does **not**
> flash the Twiddler directly.

## Features

- **Chord Lookup** — search by output text or by chord notation (`F2M 3R 4R`,
  `T12 F1LM 2MR`), or pick special keys/actions/mouse buttons from a dropdown.
  Click keys on the keymap to reverse-look up a chord. A mirror toggle flips the
  display for left-handed visualization.
- **Chord Editor** — click keys on the keymap to build a chord, type the text it
  should send, insert special keys, and see which outputs are already taken
  before adding to the queue.
- **Export Queue** — a persistent list of pending chords with status
  (`pending` / `exported` / `on device`). Merges pending chords into a base
  `.cfg` and marks them exported.
- **Config** — import your tuner `.cfg` or CSV export, export a custom-mapping
  JSON for the tutor site, and read the how-to instructions.

## Requirements

- Python 3.10+
- [PySide6-Essentials](https://pypi.org/project/PySide6-Essentials/)
- [platformdirs](https://pypi.org/project/platformdirs/)

Both Python packages are declared runtime dependencies and are installed
automatically by `pip install -e .`.

## Install & run

```sh
pip install -e .
twiddler-tools
```

Or run directly without installing:

```sh
python -m twiddler_tools.gui.app
```

## Development

```sh
pip install -e ".[dev]"
pytest
```

The test suite uses small synthetic CSV, JSON, and `.cfg` fixtures. Replace
them with your own tuner exports when testing against a personal configuration;
do not commit personal device configurations.


## Build the Windows .exe

A standalone `Twiddler4Tools.exe` can be produced with PyInstaller:

```sh
pip install -e ".[build]"
python build_exe.py
```

The executable is written to `dist/Twiddler4Tools.exe`. The build script
expects `PySide6-Essentials`, `platformdirs`, and `PyInstaller` to be
available in the active Python environment; the editable install above
installs the runtime dependencies and the `[build]` extra adds PyInstaller.

The resulting single-file exe has no console window (it is built with
PyInstaller's `--windowed` flag), so run it from a terminal if you need to
see startup errors.


## Known Issue

Once uploaded to the tuner, you have to open it in the tuner, save, then download. Directly downloading to twiddler without doing this step sometimes fails (gives a red led then auto-switches to next available configuration).

## License

TwidLib is released under the [MIT License](LICENSE).
