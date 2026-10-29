"""Build a standalone Twiddler4Tools app with PyInstaller.

Usage:

    python build_exe.py

Output depends on the host operating system:

    Windows  ->  dist/Twiddler4Tools.exe
    macOS    ->  dist/Twiddler4Tools.dmg  (plus a Twiddler4Tools.app bundle)
    Linux    ->  dist/Twiddler4Tools

Requires PyInstaller and the project dependencies (PySide6-Essentials and
platformdirs) to be installed in the active Python environment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

APP_NAME = "Twiddler4Tools"

_ENTRY_SOURCE = (
    "from twiddler_tools.gui.app import main\n"
    "raise SystemExit(main())\n"
)


def _ensure_dependencies() -> None:
    missing = []
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        missing.append("PyInstaller (pip install pyinstaller)")
    try:
        import PySide6  # noqa: F401
    except ImportError:
        missing.append("PySide6-Essentials (pip install PySide6-Essentials)")
    if missing:
        sys.exit(
            "Missing build dependencies:\n"
            + "\n".join(f"  - {name}" for name in missing)
            + "\nInstall them with:  pip install -e .[build]"
        )


def _pyinstaller_args(root: Path, entry: Path) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--paths",
        str(root),
        "--specpath",
        str(entry.parent),
        str(entry),
    ]
    # Windows/Linux use a single-file bundle; on macOS PyInstaller emits a
    # .app bundle when --windowed is used without --onefile.
    if sys.platform != "darwin":
        args.insert(args.index("--windowed"), "--onefile")
    return args


def _make_dmg(root: Path) -> Path:
    app = root / "dist" / f"{APP_NAME}.app"
    dmg = root / "dist" / f"{APP_NAME}.dmg"
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(app),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
        ],
        check=True,
    )
    return dmg


def main() -> int:
    _ensure_dependencies()

    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "_twiddler_entry.py"
        entry.write_text(_ENTRY_SOURCE, encoding="utf-8")
        cmd = _pyinstaller_args(root, entry)
        print("Running:", " ".join(cmd))
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            return result.returncode

    if sys.platform == "darwin":
        artifact = _make_dmg(root)
    elif sys.platform.startswith("win"):
        artifact = root / "dist" / f"{APP_NAME}.exe"
    else:
        artifact = root / "dist" / APP_NAME

    if artifact.exists():
        print(f"\nBuilt {artifact}")
        return 0
    print(f"\nBuild finished but {artifact.name} was not found in dist/.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
