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

## Install & run (from source)

The app needs Python 3.10+ plus the project's runtime dependencies, which are
installed automatically by the steps below. Pick your operating system.

### Windows

Use the standard [python.org](https://www.python.org/downloads/windows/)
installer (not the Microsoft Store alias or an MSYS2/mingw build). In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m twiddler_tools.gui.app
```

### macOS

Use the [python.org](https://www.python.org/downloads/macos/) installer or
Homebrew (`brew install python`). In Terminal:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
twiddler-tools
```

### Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
twiddler-tools
```

You can also run without activating the environment by replacing
`twiddler-tools` with `python -m twiddler_tools.gui.app`.

## Development

```sh
pip install -e ".[dev]"
pytest
```

The test suite uses small synthetic CSV, JSON, and `.cfg` fixtures. Replace
them with your own tuner exports when testing against a personal configuration;
do not commit personal device configurations.


## Build a standalone app

`build_exe.py` bundles the app with PyInstaller:

```sh
pip install -e ".[build]"
python build_exe.py
```

Output depends on your operating system:

| OS      | Output                                               |
|---------|------------------------------------------------------|
| Windows | `dist/Twiddler4Tools.exe`                             |
| macOS   | `dist/Twiddler4Tools.dmg` (plus `Twiddler4Tools.app`) |
| Linux   | `dist/Twiddler4Tools`                                 |

On macOS the `.dmg` is created from the `.app` bundle and can be dragged into
`/Applications`. The build uses PyInstaller's `--windowed` flag, so the
Windows exe has no console window; run it from a terminal if you need to see
startup errors.

The GitHub Actions `build-macos` workflow builds and verifies the macOS app on
every push and uploads the resulting `.dmg` as a workflow artifact.


## Troubleshooting

- **`pip install PySide6-Essentials` reports "No matching distribution found"** —
  you are using a non-standard Python (for example an MSYS2/mingw build).
  PySide6 only publishes standard platform wheels, so install the standard
  CPython from python.org and create a fresh virtual environment with it.
- **macOS: the app won't open because of an "unidentified developer"** —
  right-click the app in Finder and choose **Open**, or clear the quarantine
  flag:
  ```sh
  xattr -dr com.apple.quarantine /Applications/Twiddler4Tools.app
  ```
- **The window doesn't appear** — confirm PySide6 is installed in the same
  environment you are launching from:
  ```sh
  pip show PySide6-Essentials
  ```

## Known Issue

Once uploaded to the tuner, you have to open it in the tuner, save, then download. Directly downloading to twiddler without doing this step sometimes fails (gives a red led then auto-switches to next available configuration).

## License

TwidLib is released under the [MIT License](LICENSE).
