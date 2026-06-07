# RTTLayout2

RTTLayout2 is a Python/Tkinter editor for Falcon BMS `3dCkpit.dat` RTT texture coordinate blocks.

## Current MVP

- Opens a required `3dCkpit.dat`.
- Parses `rttTarget` and RTT surface lines such as `hud`, `pfl`, `ded`, `rwr`, `mfdleft`, `mfdright`, and `hms`.
- Shows a resizable RTT canvas at the real target aspect ratio.
- Uses tabs for texture definitions, HUD 3D definition metrics/diagrams, and a read-only `3dCkpit.dat` output preview.
- Lets surfaces be selected, dragged, resized from corner handles, snapped to the RTT canvas edge, and edited by pixel fields.
- Supports optional corner resize handles, locked-ratio resizing, and exact 1:1 canvas sizing.
- Provides slider and mousewheel canvas zoom for inspecting native-size layouts.
- Changes the `rttTarget` texture resolution and proportionally scales all RTT surface rectangles.
- Draws precise 1px inclusive borders so the preview matches the declared pixel extent.
- Allows surfaces to be moved outside the RTT target while editing, but blocks export until they are brought back inside.
- Snaps only to the RTT canvas edge when `Snap to Canvas` is enabled.
- Can prevent overlap while editing when `Allow Overlap` is unchecked.
- Can draw internal 0.1 interval grids inside each surface in the editor and exported PNG.
- Displays the active definition values in real time.
- Warns when enabled surfaces overlap or fall outside the RTT target, and colors overlapping surfaces red.
- Saves a clean, aligned RTT block back to `3dCkpit.dat`.
- Exports the layout as PNG at native, 1k, 2k, 4k, 8k, or custom resolution.

## Run

```powershell
python RTTLayout2.py
python RTTLayout2.py "C:\Falcon BMS 4.38 (Internal)\Data\Art\CkptArt\F-15C\3dCkpit.dat"
```

The app only needs Python with Tkinter and Pillow. Tkinter is included with most Windows Python installs.

## Package As A Windows EXE

```powershell
python -m pip install pyinstaller -r requirements.txt
python -m PyInstaller --noconsole --onefile --name RTTLayout2 RTTLayout2.py
```

## Next Extension Points

- HUD quad metrics include editable TFOV, center angle, and depth fields that update the HUD 3D quad symmetrically around the current center.
- A future `3dButtons.dat` editor should get its own parser/model module and a new UI tab, reusing the same validation and export patterns.
- Soundtable support should be implemented as a separate resolver service so button editing can remain independent of audio playback.
