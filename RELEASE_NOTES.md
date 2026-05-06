# RTTLayout2 Windows Release

## Contents

- `RTTLayout2.exe` - standalone Windows executable.
- `README.md` - project overview, usage, and packaging notes.
- `RELEASE_NOTES.md` - this file.

## Run

Double-click `RTTLayout2.exe`, or launch it from a terminal:

```powershell
.\RTTLayout2.exe
```

The app can open a Falcon BMS `3dCkpit.dat` file from the File/Open control.

## Notes

- The executable is built with PyInstaller on `windows-latest`.
- No separate Python install is required for normal use.
- Windows may show a SmartScreen warning for unsigned local builds.
