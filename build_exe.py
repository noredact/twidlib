"""Build a standalone Windows Twiddler4Tools.exe with PyInstaller.

Usage:

    python build_exe.py

Requires PyInstaller and the project dependencies (PySide6-Essentials and
platformdirs) to be installed in the active Python environment. The output
is written to ``dist/Twiddler4Tools.exe``.
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


def main() -> int:
    _ensure_dependencies()

    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "_twiddler_entry.py"
        entry.write_text(_ENTRY_SOURCE, encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            APP_NAME,
            "--paths",
            str(root),
            str(entry),
        ]
        print("Running:", " ".join(cmd))
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            return result.returncode

    exe = root / "dist" / f"{APP_NAME}.exe"
    if exe.exists():
        print(f"\nBuilt {exe}")
        return 0
    print("\nBuild finished but the exe was not found in dist/.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
