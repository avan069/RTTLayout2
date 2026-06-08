# RTTLayout2

RTTLayout2 is an editor for Falcon BMS `3dCkpit.dat` RTT texture coordinate blocks.

## What it does

- Opens a `3dCkpit.dat` and display/edit RTT (Real-Time Texture) layout.
- For any RTT surface: select, drag, resize from corner handles, snap to the canvas edge, or manually edit dimensions.
- Detect and display collisions or out-of-bounds surfaces.
- Pan and zoom the canvas with middle mouse.
- Changes the `rttTarget` texture resolution and proportionally scales all RTT surface rectangles.
- Draws precise 1px inclusive borders so the preview matches the declared pixel extent.
- Can draw internal grids inside each surface to guide modelers/coders in accurate symbology placement.
- Allows surfaces to be moved outside the RTT target while editing, but blocks export until they are brought back inside.
- Can prevent overlap while editing when `Allow Overlap` is unchecked.
- Saves a clean, aligned RTT block back to `3dCkpit.dat` if desired
- Exports the layout as PNG at native, 1k, 2k, 4k, 8k, or custom resolution for accurate UV map application.
- View HUD projection metrics and adjust multiple parameters to achieve accurate HUD field of view

## Run

```powershell
python RTTLayout2.py
python RTTLayout2.py "C:\Falcon BMS 4.38 (Internal)\Data\Art\CkptArt\F-15C\3dCkpit.dat"
```

The app only needs Python with Tkinter and Pillow.

## Package As A Windows EXE

```powershell
python -m pip install pyinstaller -r requirements.txt
python -m PyInstaller --noconsole --onefile --name RTTLayout2 RTTLayout2.py
```

## Next Extension Points
- A future `3dButtons.dat` editor should get its own parser/model module and a new UI tab, reusing the same validation and export patterns.
- Sound table support should be implemented as a separate resolver service so button editing can remain independent of audio playback.
