from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .export import OVERLAP_COLOR, SURFACE_COLORS, export_layout
from .model import CockpitFile, RttSurface


DEFAULT_FILE = r"C:\Falcon BMS 4.38 (Internal)\Data\Art\CkptArt\F-15C\3dCkpit.dat"
HANDLE_SIZE = 9
SNAP_PIXELS = 10
CANVAS_INTERNAL_GRID_COLOR = "#6f6f6f"
HUD_SKY_COLOR = "#2B3745"
HUD_GROUND_COLOR = "#2F4039"
HUD_HORIZON_FRACTION = 0.44
HUD_TFOV_COLOR = "#e6d24f"
HUD_DEPRESSION_COLOR = "#66c46f"


class RttLayoutApp(tk.Tk):
    def __init__(self, initial_file: str | None = None) -> None:
        super().__init__()
        self.title("RTTLayout2")
        self.minsize(980, 680)

        self.doc = CockpitFile()
        self.selected: RttSurface | None = None
        self.drag_mode: str | None = None
        self.drag_start: tuple[int, int, tuple[int, int, int, int]] | None = None
        self.pan_start: tuple[int, int, float, float] | None = None
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.canvas_items: dict[int, RttSurface] = {}
        self.entry_vars = {name: tk.StringVar() for name in ("left", "top", "width", "height", "right", "bottom", "blend", "alpha")}
        self.status_var = tk.StringVar(value="Open a 3dCkpit.dat file to begin.")
        self.warning_var = tk.StringVar()
        self.snap_var = tk.BooleanVar(value=True)
        self.grid_var = tk.BooleanVar(value=False)
        self.internal_grid_var = tk.BooleanVar(value=True)
        self.allow_resize_var = tk.BooleanVar(value=True)
        self.lock_ratio_var = tk.BooleanVar(value=True)
        self.allow_overlap_var = tk.BooleanVar(value=True)
        self.actual_size_var = tk.BooleanVar(value=False)
        self.zoom_var = tk.DoubleVar(value=1.0)

        self._build_ui()
        candidate = initial_file or (DEFAULT_FILE if Path(DEFAULT_FILE).exists() else None)
        if candidate:
            self.open_file(candidate)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=0, column=0, sticky="nsew")
        self.texture_tab = ttk.Frame(self.tabs)
        self.hud_tab = ttk.Frame(self.tabs)
        self.dat_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.texture_tab, text="Texture Definitions")
        self.tabs.add(self.hud_tab, text="HUD 3D Definition")
        self.tabs.add(self.dat_tab, text="3dckpit.dat")

        self._build_texture_tab()
        self._build_hud_tab()
        self._build_dat_tab()
        self.tabs.bind("<<NotebookTabChanged>>", lambda _event: self.refresh_secondary_tabs())

    def _build_texture_tab(self) -> None:
        self.texture_tab.columnconfigure(1, weight=1)
        self.texture_tab.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.texture_tab, padding=10)
        sidebar.grid(row=0, column=0, sticky="nw")

        file_row = ttk.Frame(sidebar)
        file_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(file_row, text="Open", command=self.ask_open).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(file_row, text="Save", command=self.save).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(file_row, text="Save As", command=self.save_as).grid(row=0, column=2)

        ttk.Label(sidebar, text="RTT Surfaces").grid(row=1, column=0, sticky="nw")
        self.surface_list = tk.Listbox(sidebar, height=12, exportselection=False)
        self.surface_list.grid(row=2, column=0, sticky="new", pady=(2, 10))
        self.surface_list.bind("<<ListboxSelect>>", self.on_list_select)

        details = ttk.LabelFrame(sidebar, text="Surface Definition", padding=10)
        details.grid(row=3, column=0, sticky="ew")
        for row, (label, key) in enumerate((("X", "left"), ("Y", "top"), ("Width", "width"), ("Height", "height"), ("Right", "right"), ("Bottom", "bottom"), ("Blend", "blend"), ("Alpha", "alpha"))):
            ttk.Label(details, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(details, textvariable=self.entry_vars[key], width=12)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            entry.bind("<Return>", self.apply_entries)
            entry.bind("<FocusOut>", self.apply_entries)
        ttk.Button(details, text="Apply", command=self.apply_entries).grid(row=8, column=0, columnspan=2, pady=(8, 0))
        ttk.Label(details, textvariable=self.warning_var, foreground="#c62828", wraplength=150).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))

        options = ttk.Frame(sidebar)
        options.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(options, text="Snap to Canvas", variable=self.snap_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(options, text="Canvas Grid", variable=self.grid_var, command=self.redraw).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(options, text="Internal Grid", variable=self.internal_grid_var, command=self.redraw).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(options, text="Allow Resize Handles", variable=self.allow_resize_var, command=self.redraw).grid(row=3, column=0, sticky="w")
        ttk.Checkbutton(options, text="Lock Ratio", variable=self.lock_ratio_var).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(options, text="Allow Overlap", variable=self.allow_overlap_var, command=self.redraw).grid(row=5, column=0, sticky="w")
        zoom_row = ttk.Frame(options)
        zoom_row.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(zoom_row, text="Zoom").grid(row=0, column=0, sticky="w")
        ttk.Scale(zoom_row, from_=0.25, to=4.0, variable=self.zoom_var, command=lambda _value: self.redraw()).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        zoom_row.columnconfigure(1, weight=1)
        ttk.Button(options, text="Set Actual Size", command=self.set_actual_size).grid(row=7, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(options, text="Export PNG", command=self.ask_export).grid(row=8, column=0, sticky="ew", pady=(6, 0))

        main = ttk.Frame(self.texture_tab, padding=(0, 10, 10, 10))
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(main, bg="#141414", highlightthickness=1, highlightbackground="#666666")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_down)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_up)
        self.canvas.bind("<ButtonPress-2>", self.on_canvas_pan_down)
        self.canvas.bind("<B2-Motion>", self.on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_canvas_pan_up)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel_zoom)
        self.canvas.bind("<Button-4>", self.on_mousewheel_zoom)
        self.canvas.bind("<Button-5>", self.on_mousewheel_zoom)

        ttk.Label(main, textvariable=self.status_var).grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def _build_hud_tab(self) -> None:
        self.hud_tab.columnconfigure(0, weight=1)
        self.hud_tab.rowconfigure(1, weight=1)

        self.hud_metric_vars = {
            key: tk.StringVar(value="")
            for key in (
                "depth",
                "width",
                "height",
                "center_y",
                "center_z",
                "tfov_h",
                "tfov_v",
                "half_h",
                "half_v",
                "deck_angle",
            )
        }
        self.hud_edit_vars = {
            key: tk.StringVar(value="")
            for key in ("tfov_h", "tfov_v", "center_angle", "depth")
        }
        self.updating_hud_fields = False

        metrics = ttk.Frame(self.hud_tab, padding=(10, 10, 10, 6))
        metrics.grid(row=0, column=0, sticky="ew")
        for column in range(4):
            metrics.columnconfigure(column, weight=1)

        angle_box = ttk.LabelFrame(metrics, text="Total Field Of View", padding=8)
        center_box = ttk.LabelFrame(metrics, text="Center Offset", padding=8)
        size_box = ttk.LabelFrame(metrics, text="Quad Size", padding=8)
        coord_box = ttk.LabelFrame(metrics, text="HUD Quad Coordinates", padding=8)
        angle_box.grid(row=0, column=0, sticky="new", padx=(0, 8))
        center_box.grid(row=0, column=1, sticky="new", padx=(0, 8))
        size_box.grid(row=0, column=2, sticky="new", padx=(0, 8))
        coord_box.grid(row=0, column=3, sticky="new")
        self.add_metric_rows(
            angle_box,
            (
                ("Horizontal TFOV", "tfov_h"),
                ("Horizontal Half-Angle", "half_h"),
                ("Vertical TFOV", "tfov_v"),
                ("Vertical Half-Angle", "half_v"),
            ),
        )
        self.add_metric_rows(center_box, (("Center Y", "center_y"), ("Center Z", "center_z"), ("Depression Angle", "deck_angle")))
        self.add_metric_rows(size_box, (("Depth", "depth"), ("Quad Width", "width"), ("Quad Height", "height")))
        edit_box = ttk.LabelFrame(metrics, text="Edit HUD Definition", padding=8)
        edit_box.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        edit_rows = (
            ("Horizontal TFOV °", "tfov_h"),
            ("Vertical TFOV °", "tfov_v"),
            ("Depression Angle °", "center_angle"),
            ("Depth", "depth"),
        )
        for column, (label, key) in enumerate(edit_rows):
            ttk.Label(edit_box, text=label).grid(row=0, column=column * 2, sticky="w", padx=(0, 6))
            entry = ttk.Entry(edit_box, textvariable=self.hud_edit_vars[key], width=10)
            entry.grid(row=0, column=column * 2 + 1, sticky="w", padx=(0, 14))
            entry.bind("<Return>", self.apply_hud_edits)
        ttk.Button(edit_box, text="Apply", command=self.apply_hud_edits).grid(row=0, column=8, sticky="e")
        edit_box.columnconfigure(8, weight=1)
        self.hud_quad_text = tk.Text(coord_box, wrap="none", font=("Consolas", 9), height=5, width=50)
        self.hud_quad_text.grid(row=0, column=0, sticky="ew")
        self.hud_quad_text.configure(state="disabled")
        coord_box.columnconfigure(0, weight=1)

        body = ttk.Frame(self.hud_tab, padding=(10, 0, 10, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.hud_canvas = tk.Canvas(body, bg="#101010", highlightthickness=1, highlightbackground="#666666")
        self.hud_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.hud_canvas.bind("<Configure>", lambda _event: self.update_hud_tab())

        self.hud_side_canvas = tk.Canvas(body, bg="#101010", highlightthickness=1, highlightbackground="#666666")
        self.hud_side_canvas.grid(row=0, column=1, sticky="nsew")
        self.hud_side_canvas.bind("<Configure>", lambda _event: self.update_hud_tab())

    def add_metric_rows(self, parent: ttk.LabelFrame, rows: tuple[tuple[str, str], ...]) -> None:
        for row, (label, key) in enumerate(rows):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(parent, textvariable=self.hud_metric_vars[key], width=18).grid(row=row, column=1, sticky="w", pady=2)

    def _build_dat_tab(self) -> None:
        self.dat_tab.columnconfigure(1, weight=1)
        self.dat_tab.rowconfigure(0, weight=1)
        self.line_numbers = tk.Text(self.dat_tab, width=6, padx=6, takefocus=False, borderwidth=0, background="#efefef", foreground="#666666", font=("Consolas", 10))
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.dat_preview = tk.Text(self.dat_tab, wrap="none", font=("Consolas", 10), undo=False)
        self.dat_preview.grid(row=0, column=1, sticky="nsew")
        self.dat_preview.tag_configure("editable", foreground="#000000")
        self.dat_preview.tag_configure("readonly", foreground="#8a8a8a")
        yscroll = ttk.Scrollbar(self.dat_tab, orient="vertical", command=self._scroll_dat_preview)
        yscroll.grid(row=0, column=2, sticky="ns")
        xscroll = ttk.Scrollbar(self.dat_tab, orient="horizontal", command=self.dat_preview.xview)
        xscroll.grid(row=1, column=1, sticky="ew")
        self.dat_preview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set, state="disabled")
        self.line_numbers.configure(state="disabled")
        self.dat_preview.bind("<MouseWheel>", self.on_dat_mousewheel)
        self.line_numbers.bind("<MouseWheel>", self.on_dat_mousewheel)

    def ask_open(self) -> None:
        path = filedialog.askopenfilename(title="Open 3dCkpit.dat", filetypes=[("Cockpit DAT", "*.dat"), ("All files", "*.*")])
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        try:
            self.doc = CockpitFile.load(path)
        except OSError as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.surface_list.delete(0, tk.END)
        for surface in self.doc.surfaces:
            prefix = "" if surface.enabled else "// "
            self.surface_list.insert(tk.END, f"{prefix}{surface.name}")
        self.selected = self.doc.surfaces[0] if self.doc.surfaces else None
        if self.selected:
            self.surface_list.selection_set(0)
        self.update_entries()
        self.redraw()
        self.update_status()
        self.refresh_secondary_tabs()

    def save(self) -> None:
        try:
            self.doc.save()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.update_status("Saved.")
        self.refresh_secondary_tabs()

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(title="Save 3dCkpit.dat", defaultextension=".dat", filetypes=[("Cockpit DAT", "*.dat"), ("All files", "*.*")])
        if path:
            try:
                self.doc.save(path)
            except Exception as exc:
                messagebox.showerror("Save failed", str(exc))
                return
            self.update_status("Saved.")
            self.refresh_secondary_tabs()

    def ask_export(self) -> None:
        if not self.doc.surfaces:
            return
        errors = self.doc.invalid_for_export()
        if errors:
            self.update_status()
            messagebox.showerror("Export blocked", errors[0])
            return
        dialog = ExportDialog(self, self.doc.rtt_width, self.doc.rtt_height)
        self.wait_window(dialog)
        if not dialog.result:
            return
        width, height = dialog.result
        path = filedialog.asksaveasfilename(title="Export RTT layout", defaultextension=".png", filetypes=[("PNG image", "*.png")])
        if path:
            try:
                export_layout(self.doc, path, width, height, self.internal_grid_var.get())
            except Exception as exc:
                messagebox.showerror("Export failed", str(exc))
                return
            self.update_status(f"Exported {width}x{height} PNG.")

    def on_list_select(self, _event: tk.Event) -> None:
        selection = self.surface_list.curselection()
        if selection:
            self.selected = self.doc.surfaces[selection[0]]
            self.update_entries()
            self.redraw()
            self.refresh_secondary_tabs()

    def update_entries(self) -> None:
        surface = self.selected
        if surface is None:
            for var in self.entry_vars.values():
                var.set("")
            return
        values = {
            "left": surface.left,
            "top": surface.top,
            "width": surface.width,
            "height": surface.height,
            "right": surface.right,
            "bottom": surface.bottom,
            "blend": surface.blend,
            "alpha": "" if surface.alpha is None else surface.alpha,
        }
        for key, value in values.items():
            self.entry_vars[key].set(str(value))
        self.update_definition_warning()

    def apply_entries(self, _event: tk.Event | None = None) -> None:
        surface = self.selected
        if surface is None:
            return
        try:
            left = int(float(self.entry_vars["left"].get()))
            top = int(float(self.entry_vars["top"].get()))
            width = int(float(self.entry_vars["width"].get()))
            height = int(float(self.entry_vars["height"].get()))
        except ValueError:
            self.update_entries()
            return
        old_rect = surface.rect()
        surface.set_rect(left, top, width, height)
        if not self.allow_overlap_var.get() and self.surface_overlaps_others(surface):
            surface.left, surface.top, surface.right, surface.bottom = old_rect
            self.update_entries()
            self.update_status()
            return
        blend = self.entry_vars["blend"].get().strip()
        if blend:
            surface.blend = blend[0]
        alpha_text = self.entry_vars["alpha"].get().strip()
        surface.alpha = float(alpha_text) if alpha_text else None
        self.update_entries()
        self.redraw()
        self.update_status()
        self.refresh_secondary_tabs()

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.canvas_items.clear()
        if not self.doc.surfaces:
            return
        ox, oy, scale = self.canvas_transform()
        width = self.doc.rtt_width * scale
        height = self.doc.rtt_height * scale
        self.canvas.create_rectangle(ox, oy, ox + width - 1, oy + height - 1, fill="#050505", outline="#777777", width=1)
        if self.grid_var.get():
            self.draw_grid(ox, oy, width, height, scale)
        overlaps = self.doc.overlapping_surface_names()
        for index, surface in enumerate(self.doc.surfaces):
            self.draw_surface(surface, index, ox, oy, scale, surface.name in overlaps)

    def draw_grid(self, ox: float, oy: float, width: float, height: float, scale: float) -> None:
        step = 100 if self.doc.rtt_width >= 1000 else 50
        for x in range(step, self.doc.rtt_width, step):
            px = ox + x * scale
            self.canvas.create_line(px, oy, px, oy + height, fill="#252525")
        for y in range(step, self.doc.rtt_height, step):
            py = oy + y * scale
            self.canvas.create_line(ox, py, ox + width, py, fill="#252525")

    def draw_surface(self, surface: RttSurface, index: int, ox: float, oy: float, scale: float, is_overlapping: bool) -> None:
        color = rgb_to_hex(OVERLAP_COLOR if is_overlapping else SURFACE_COLORS[index % len(SURFACE_COLORS)])
        outline = "#ffffff" if surface is self.selected else color
        x1 = ox + surface.left * scale
        y1 = oy + surface.top * scale
        x2 = ox + surface.right * scale - 1
        y2 = oy + surface.bottom * scale - 1
        rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline, width=1, stipple="gray50")
        text = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, anchor="center", text=surface.name.upper(), fill="#000000", font=("Segoe UI", max(10, int(21 * scale))))
        self.canvas_items[rect] = surface
        self.canvas_items[text] = surface
        if self.internal_grid_var.get():
            self.draw_internal_grid(x1, y1, x2, y2)
        if surface is self.selected and self.allow_resize_var.get():
            for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
                handle = self.canvas.create_rectangle(hx - HANDLE_SIZE / 2, hy - HANDLE_SIZE / 2, hx + HANDLE_SIZE / 2, hy + HANDLE_SIZE / 2, fill="#ffffff", outline="#111111", tags=("resize_handle",))
                self.canvas_items[handle] = surface

    def draw_internal_grid(self, x1: float, y1: float, x2: float, y2: float) -> None:
        width = x2 - x1 + 1
        height = y2 - y1 + 1
        if width < 10 or height < 10:
            return
        for step in range(1, 10):
            x = x1 + width * step / 10
            y = y1 + height * step / 10
            self.canvas.create_line(x, y1, x, y2, fill=CANVAS_INTERNAL_GRID_COLOR, width=1)
            self.canvas.create_line(x1, y, x2, y, fill=CANVAS_INTERNAL_GRID_COLOR, width=1)

    def canvas_transform(self) -> tuple[float, float, float]:
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        zoom = self.zoom_var.get()
        if self.actual_size_var.get():
            scale = zoom
            ox = max(0, (cw - self.doc.rtt_width * scale) / 2) + self.pan_x
            oy = max(0, (ch - self.doc.rtt_height * scale) / 2) + self.pan_y
            return ox, oy, scale
        scale = min((cw - 24) / self.doc.rtt_width, (ch - 24) / self.doc.rtt_height) * zoom
        scale = max(0.05, scale)
        ox = (cw - self.doc.rtt_width * scale) / 2 + self.pan_x
        oy = (ch - self.doc.rtt_height * scale) / 2 + self.pan_y
        return ox, oy, scale

    def canvas_to_rtt(self, x: int, y: int) -> tuple[int, int]:
        ox, oy, scale = self.canvas_transform()
        return round((x - ox) / scale), round((y - oy) / scale)

    def on_canvas_down(self, event: tk.Event) -> None:
        surface = self.surface_at(event.x, event.y)
        if surface:
            self.selected = surface
            self.select_in_list(surface)
            rtt_x, rtt_y = self.canvas_to_rtt(event.x, event.y)
            mode = self.resize_mode_for(surface, rtt_x, rtt_y) if self.allow_resize_var.get() else None
            self.drag_mode = mode
            self.drag_start = (rtt_x, rtt_y, surface.rect())
            self.update_entries()
            self.redraw()

    def surface_at(self, x: int, y: int) -> RttSurface | None:
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            surface = self.canvas_items.get(item)
            if surface:
                return surface
        return None

    def on_canvas_drag(self, event: tk.Event) -> None:
        if not self.selected or not self.drag_start:
            return
        start_x, start_y, rect = self.drag_start
        x, y = self.canvas_to_rtt(event.x, event.y)
        dx = x - start_x
        dy = y - start_y
        left, top, right, bottom = rect
        if self.drag_mode and self.drag_mode.startswith("resize_"):
            new_left, new_top, new_right, new_bottom = left, top, right, bottom
            if "w" in self.drag_mode:
                new_left = left + dx
            if "e" in self.drag_mode:
                new_right = right + dx
            if "n" in self.drag_mode:
                new_top = top + dy
            if "s" in self.drag_mode:
                new_bottom = bottom + dy
            new_left, new_top, new_right, new_bottom = normalize_rect(new_left, new_top, new_right, new_bottom)
            if self.lock_ratio_var.get():
                new_left, new_top, new_right, new_bottom = lock_rect_ratio(left, top, right, bottom, new_left, new_top, new_right, new_bottom, self.drag_mode)
            candidate = (new_left, new_top, new_right, new_bottom)
        else:
            candidate = (left + dx, top + dy, left + dx + right - left, top + dy + bottom - top)
        old_rect = self.selected.rect()
        self.selected.left, self.selected.top, self.selected.right, self.selected.bottom = candidate
        if self.snap_var.get():
            self.snap_selected()
        if not self.allow_overlap_var.get() and self.surface_overlaps_others(self.selected):
            self.selected.left, self.selected.top, self.selected.right, self.selected.bottom = old_rect
        self.update_entries()
        self.redraw()
        self.update_status()
        self.refresh_secondary_tabs()

    def on_canvas_up(self, _event: tk.Event) -> None:
        self.drag_mode = None
        self.drag_start = None

    def on_canvas_pan_down(self, event: tk.Event) -> str:
        self.pan_start = (event.x, event.y, self.pan_x, self.pan_y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def on_canvas_pan_drag(self, event: tk.Event) -> str:
        if self.pan_start is None:
            return "break"
        start_x, start_y, start_pan_x, start_pan_y = self.pan_start
        self.pan_x = start_pan_x + event.x - start_x
        self.pan_y = start_pan_y + event.y - start_y
        self.redraw()
        return "break"

    def on_canvas_pan_up(self, _event: tk.Event) -> str:
        self.pan_start = None
        self.canvas.configure(cursor="")
        return "break"

    def snap_selected(self) -> None:
        surface = self.selected
        if surface is None:
            return
        edges_x = [0, self.doc.rtt_width]
        edges_y = [0, self.doc.rtt_height]
        width, height = surface.width, surface.height
        left, top = surface.left, surface.top
        for edge in edges_x:
            if abs(surface.left - edge) <= SNAP_PIXELS:
                left = edge
            if abs(surface.right - edge) <= SNAP_PIXELS:
                left = edge - width
        for edge in edges_y:
            if abs(surface.top - edge) <= SNAP_PIXELS:
                top = edge
            if abs(surface.bottom - edge) <= SNAP_PIXELS:
                top = edge - height
        surface.set_rect(left, top, width, height)

    def surface_overlaps_others(self, surface: RttSurface) -> bool:
        from .model import rects_overlap

        if not surface.enabled:
            return False
        return any(
            other is not surface and other.enabled and rects_overlap(surface.rect(), other.rect())
            for other in self.doc.surfaces
        )

    def resize_mode_for(self, surface: RttSurface, x: int, y: int) -> str | None:
        close_left = abs(x - surface.left) <= SNAP_PIXELS
        close_right = abs(x - surface.right) <= SNAP_PIXELS
        close_top = abs(y - surface.top) <= SNAP_PIXELS
        close_bottom = abs(y - surface.bottom) <= SNAP_PIXELS
        if close_left and close_top:
            return "resize_nw"
        if close_right and close_top:
            return "resize_ne"
        if close_left and close_bottom:
            return "resize_sw"
        if close_right and close_bottom:
            return "resize_se"
        return None

    def select_in_list(self, surface: RttSurface) -> None:
        try:
            index = self.doc.surfaces.index(surface)
        except ValueError:
            return
        self.surface_list.selection_clear(0, tk.END)
        self.surface_list.selection_set(index)
        self.surface_list.see(index)

    def update_status(self, prefix: str | None = None) -> None:
        warnings = self.doc.validate()
        file_name = str(self.doc.path) if self.doc.path else "No file"
        status = f"{file_name} | RTT Texture Size: {self.doc.rtt_width}x{self.doc.rtt_height}"
        if warnings:
            status += f" | {len(warnings)} warning(s): " + warnings[0]
        if prefix:
            status = f"{prefix} {status}"
        self.status_var.set(status)
        self.update_definition_warning()

    def update_definition_warning(self) -> None:
        surface = self.selected
        if surface is None:
            self.warning_var.set("")
            return
        warnings = []
        if surface.left < 0 or surface.top < 0 or surface.right > self.doc.rtt_width or surface.bottom > self.doc.rtt_height:
            warnings.append("Outside RTT target; export will fail.")
        if surface.width <= 0 or surface.height <= 0:
            warnings.append("Invalid size; export will fail.")
        overlaps = self.doc.overlapping_surface_names()
        if surface.name in overlaps:
            warnings.append("Overlaps another surface.")
            if not self.allow_overlap_var.get():
                warnings.append("Overlap editing is disabled.")
        self.warning_var.set(" ".join(warnings))

    def set_actual_size(self) -> None:
        self.actual_size_var.set(True)
        self.zoom_var.set(1.0)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.canvas.configure(width=self.doc.rtt_width, height=self.doc.rtt_height)
        self.update_idletasks()
        sidebar_width = self.texture_tab.grid_slaves(row=0, column=0)[0].winfo_reqwidth()
        extra_w = sidebar_width + 42
        extra_h = 78
        self.geometry(f"{self.doc.rtt_width + extra_w}x{self.doc.rtt_height + extra_h}")
        self.redraw()

    def on_mousewheel_zoom(self, event: tk.Event) -> str:
        if getattr(event, "num", None) == 5 or getattr(event, "delta", 0) < 0:
            factor = 0.9
        else:
            factor = 1.1
        current = self.zoom_var.get()
        self.zoom_var.set(max(0.25, min(4.0, current * factor)))
        self.redraw()
        return "break"

    def refresh_secondary_tabs(self) -> None:
        self.update_hud_tab()
        self.update_dat_preview()

    def update_hud_tab(self) -> None:
        if not hasattr(self, "hud_canvas"):
            return
        hud = self.find_surface("hud")
        if hud is None:
            for var in self.hud_metric_vars.values():
                var.set("")
            for var in self.hud_edit_vars.values():
                var.set("")
            self.set_text(self.hud_quad_text, "No hud surface definition found.")
            self.hud_canvas.delete("all")
            if hasattr(self, "hud_side_canvas"):
                self.hud_side_canvas.delete("all")
            return

        metrics = hud_metrics(hud)
        values = {
            "depth": f"{metrics['depth']:.3f}",
            "width": f"{metrics['width']:.3f}",
            "height": f"{metrics['height']:.3f}",
            "center_y": f"{metrics['center_y']:.3f}",
            "center_z": f"{metrics['center_z']:.3f}",
            "tfov_h": f"{metrics['tfov_h']:.3f}°",
            "tfov_v": f"{metrics['tfov_v']:.3f}°",
            "half_h": f"{metrics['half_h']:.3f}°",
            "half_v": f"{metrics['half_v']:.3f}°",
            "deck_angle": f"{metrics['deck_angle']:.3f}°",
        }
        for key, value in values.items():
            self.hud_metric_vars[key].set(value)
        if not self.updating_hud_fields:
            self.updating_hud_fields = True
            self.hud_edit_vars["tfov_h"].set(f"{metrics['tfov_h']:.3f}")
            self.hud_edit_vars["tfov_v"].set(f"{metrics['tfov_v']:.3f}")
            self.hud_edit_vars["center_angle"].set(f"{metrics['deck_angle']:.3f}")
            self.hud_edit_vars["depth"].set(f"{metrics['depth']:.3f}")
            self.updating_hud_fields = False
        ul = hud.quad[0:3]
        ur = hud.quad[3:6]
        ll = hud.quad[6:9]
        quad_text = (
            f"UL.x {ul[0]:.3f}    UL.y {ul[1]:.3f}    UL.z {ul[2]:.3f}\n"
            f"UR.x {ur[0]:.3f}    UR.y {ur[1]:.3f}    UR.z {ur[2]:.3f}\n"
            f"LL.x {ll[0]:.3f}    LL.y {ll[1]:.3f}    LL.z {ll[2]:.3f}\n\n"
            f"RTT: L {hud.left}  T {hud.top}  R {hud.right}  B {hud.bottom}  Blend {hud.blend}"
        )
        self.set_text(self.hud_quad_text, quad_text)
        rear_scale = self.draw_hud_rear_preview(metrics["width"], metrics["height"], metrics["center_y"], metrics["center_z"], metrics["half_h"], metrics["half_v"])
        self.draw_hud_side_preview(metrics["depth"], metrics["height"], metrics["center_z"], metrics["half_v"], metrics["deck_angle"], rear_scale)

    def apply_hud_edits(self, _event: tk.Event | None = None) -> None:
        hud = self.find_surface("hud")
        if hud is None:
            return
        try:
            tfov_h = float(self.hud_edit_vars["tfov_h"].get())
            tfov_v = float(self.hud_edit_vars["tfov_v"].get())
            center_angle = float(self.hud_edit_vars["center_angle"].get())
            depth = float(self.hud_edit_vars["depth"].get())
        except ValueError:
            self.update_hud_tab()
            return
        if depth <= 0 or tfov_h <= 0 or tfov_v <= 0:
            self.update_hud_tab()
            return
        metrics = hud_metrics(hud)
        center_y = metrics["center_y"]
        center_z = -depth * math.tan(math.radians(center_angle))
        width = 2 * depth * math.tan(math.radians(tfov_h / 2))
        height = 2 * depth * math.tan(math.radians(tfov_v / 2))
        left_y = center_y - width / 2
        right_y = center_y + width / 2
        top_z = center_z - height / 2
        bottom_z = center_z + height / 2
        hud.quad = [
            depth,
            left_y,
            top_z,
            depth,
            right_y,
            top_z,
            depth,
            left_y,
            bottom_z,
        ]
        self.updating_hud_fields = True
        self.update_hud_tab()
        self.updating_hud_fields = False
        self.update_dat_preview()

    def draw_hud_rear_preview(self, width: float, height: float, center_y: float, center_z: float, half_h: float, half_v: float) -> float:
        self.hud_canvas.delete("all")
        cw = max(1, self.hud_canvas.winfo_width())
        ch = max(1, self.hud_canvas.winfo_height())
        pad = 70
        extent_w = max(abs(center_y) * 2 + width, width)
        extent_h = max(abs(center_z) * 2 + height, height)
        scale = min((cw - pad * 2) / max(1, extent_w), (ch - pad * 2) / max(1, extent_h))
        rect_w = width * scale
        rect_h = height * scale
        cx = cw / 2
        cy = ch * HUD_HORIZON_FRACTION
        quad_cx = cx + center_y * scale
        quad_cy = cy + center_z * scale
        x1 = quad_cx - rect_w / 2
        y1 = quad_cy - rect_h / 2
        x2 = quad_cx + rect_w / 2
        y2 = quad_cy + rect_h / 2
        self.draw_hud_background(self.hud_canvas, cw, ch, cy)
        self.draw_hud_axes(self.hud_canvas, cx, cy, cw, ch, pad)
        self.hud_canvas.create_text(cx, 24, text="REAR VIEW (FROM COCKPIT)", fill="#d7dde0", font=("Segoe UI", 10, "bold"))
        for corner in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
            self.hud_canvas.create_line(cx, cy, corner[0], corner[1], fill="#6b8fb5", width=1, dash=(4, 4))
        self.hud_canvas.create_rectangle(x1, y1, x2, y2, outline="#9db7c8", width=2)
        self.hud_canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="#e0b86d", outline="")
        self.hud_canvas.create_text((x1 + x2) / 2, y2 + 18, text=f"H TFOV {half_h * 2:.1f}°", fill=HUD_TFOV_COLOR, font=("Segoe UI", 10, "bold"))
        v_label_x = x2 + 12
        v_anchor = "w"
        if v_label_x + 105 > cw:
            v_label_x = x2 - 12
            v_anchor = "e"
        self.hud_canvas.create_text(v_label_x, (y1 + y2) / 2, text=f"V TFOV {half_v * 2:.1f}°", fill=HUD_TFOV_COLOR, anchor=v_anchor, font=("Segoe UI", 10, "bold"))
        return scale

    def draw_hud_side_preview(self, depth: float, height: float, center_z: float, half_v: float, deck_angle: float, rear_scale: float) -> None:
        if not hasattr(self, "hud_side_canvas"):
            return
        canvas = self.hud_side_canvas
        canvas.delete("all")
        cw = max(1, canvas.winfo_width())
        ch = max(1, canvas.winfo_height())
        pad_x = 58
        pad_y = 62
        eye_x = cw - pad_x
        plane_x = pad_x
        eye_y = ch * HUD_HORIZON_FRACTION
        z_top = center_z - height / 2
        z_bottom = center_z + height / 2
        top_y = eye_y + z_top * rear_scale
        bottom_y = eye_y + z_bottom * rear_scale
        center_y = eye_y + center_z * rear_scale
        self.draw_hud_background(canvas, cw, ch, eye_y)
        self.draw_hud_axes(canvas, eye_x, eye_y, cw, ch, pad_y)
        canvas.create_text(cw / 2, 24, text="SIDE VIEW", fill="#d7dde0", font=("Segoe UI", 10, "bold"))
        canvas.create_line(plane_x, top_y, plane_x, bottom_y, fill="#9db7c8", width=3)
        canvas.create_line(plane_x, top_y, eye_x, eye_y, fill="#9db7c8", width=2)
        canvas.create_line(plane_x, bottom_y, eye_x, eye_y, fill="#9db7c8", width=2)
        canvas.create_line(plane_x, center_y, eye_x, eye_y, fill="#d7dde0", dash=(5, 5), width=2)
        canvas.create_oval(eye_x - 4, eye_y - 4, eye_x + 4, eye_y + 4, fill="#e0b86d", outline="")
        self.draw_angle_arc(canvas, eye_x, eye_y, plane_x, top_y, bottom_y, HUD_TFOV_COLOR, 0.22)
        self.draw_depression_arc(canvas, eye_x, eye_y, plane_x, center_y, HUD_DEPRESSION_COLOR)
        canvas.create_text(eye_x - 18, eye_y - 30, text=f"V TFOV {half_v * 2:.1f}°", fill=HUD_TFOV_COLOR, anchor="e", font=("Segoe UI", 10, "bold"))
        canvas.create_text(eye_x - 150, eye_y + 20, text=f"{deck_angle:.3f}° Depression", fill=HUD_DEPRESSION_COLOR, anchor="e", font=("Segoe UI", 10, "bold"))

    def draw_angle_arc(self, canvas: tk.Canvas, eye_x: float, eye_y: float, plane_x: float, top_y: float, bottom_y: float, color: str, radius_fraction: float) -> None:
        top_angle = math.atan2(top_y - eye_y, plane_x - eye_x)
        bottom_angle = math.atan2(bottom_y - eye_y, plane_x - eye_x)
        delta = ((bottom_angle - top_angle + math.pi) % (math.tau)) - math.pi
        radius = min(82.0, max(42.0, abs(eye_x - plane_x) * radius_fraction))
        points = []
        steps = 28
        for index in range(steps + 1):
            angle = top_angle + delta * index / steps
            points.extend((eye_x + math.cos(angle) * radius, eye_y + math.sin(angle) * radius))
        canvas.create_line(*points, fill=color, width=3, smooth=True)

    def draw_depression_arc(self, canvas: tk.Canvas, eye_x: float, eye_y: float, plane_x: float, center_y: float, color: str) -> None:
        level_angle = math.pi
        center_angle = math.atan2(center_y - eye_y, plane_x - eye_x)
        delta = ((center_angle - level_angle + math.pi) % math.tau) - math.pi
        radius = min(116.0, max(74.0, abs(eye_x - plane_x) * 0.32))
        points = []
        steps = 20
        for index in range(steps + 1):
            angle = level_angle + delta * index / steps
            points.extend((eye_x + math.cos(angle) * radius, eye_y + math.sin(angle) * radius))
        canvas.create_line(*points, fill=color, width=3, smooth=True)

    def draw_hud_axes(self, canvas: tk.Canvas, cx: float, cy: float, width: int, height: int, pad: float) -> None:
        canvas.create_line(cx, pad / 2, cx, height - pad / 2, fill="#3b3f42")
        canvas.create_line(pad / 2, cy, width - pad / 2, cy, fill="#3b3f42")

    def draw_hud_background(self, canvas: tk.Canvas, width: int, height: int, horizon_y: float) -> None:
        canvas.create_rectangle(0, 0, width, horizon_y, fill=HUD_SKY_COLOR, outline="")
        canvas.create_rectangle(0, horizon_y, width, height, fill=HUD_GROUND_COLOR, outline="")

    def update_dat_preview(self) -> None:
        if not hasattr(self, "dat_preview"):
            return
        text = self.doc.render() if self.doc.lines or self.doc.surfaces else ""
        lines = text.splitlines()
        numbers = "\n".join(str(i) for i in range(1, len(lines) + 1))
        self.set_text(self.dat_preview, text)
        self.apply_dat_preview_tags(lines)
        self.set_text(self.line_numbers, numbers)

    def apply_dat_preview_tags(self, lines: list[str]) -> None:
        editable_names = {surface.name.lower() for surface in self.doc.surfaces}
        self.dat_preview.configure(state="normal")
        self.dat_preview.tag_remove("editable", "1.0", tk.END)
        self.dat_preview.tag_remove("readonly", "1.0", tk.END)
        for index, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            token = stripped.split(maxsplit=1)[0].rstrip(";").lower() if stripped else ""
            tag = "editable" if token in editable_names else "readonly"
            self.dat_preview.tag_add(tag, f"{index}.0", f"{index}.end")
        self.dat_preview.configure(state="disabled")

    def _scroll_dat_preview(self, *args: object) -> None:
        self.dat_preview.yview(*args)
        self.line_numbers.yview(*args)

    def on_dat_mousewheel(self, event: tk.Event) -> str:
        units = -1 if getattr(event, "delta", 0) > 0 else 1
        self.dat_preview.yview_scroll(units * 3, "units")
        self.line_numbers.yview_scroll(units * 3, "units")
        return "break"

    def set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def find_surface(self, name: str) -> RttSurface | None:
        name = name.lower()
        return next((surface for surface in self.doc.surfaces if surface.name.lower() == name), None)


class ExportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, width: int, height: int) -> None:
        super().__init__(parent)
        self.title("Export PNG")
        self.resizable(False, False)
        self.result: tuple[int, int] | None = None
        self.native_size = (width, height)
        self.width_var = tk.StringVar(value=str(width))
        self.height_var = tk.StringVar(value=str(height))
        self.preset_var = tk.StringVar(value="actual")
        frame = ttk.Frame(self, padding=14)
        frame.grid(sticky="nsew")
        presets = ttk.Frame(frame)
        presets.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for column, (label, value) in enumerate((("Actual Size", "actual"), ("1k", "1024"), ("2k", "2048"), ("4k", "4096"), ("8k", "8192"))):
            ttk.Radiobutton(presets, text=label, value=value, variable=self.preset_var, command=self.apply_preset).grid(row=0, column=column, padx=(0, 6))
        ttk.Label(frame, text="Width").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.width_var, width=12).grid(row=1, column=1, padx=(8, 0))
        ttk.Label(frame, text="Height").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.height_var, width=12).grid(row=2, column=1, padx=(8, 0), pady=(6, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(buttons, text="Export", command=self.accept).grid(row=0, column=1)
        self.transient(parent)
        self.grab_set()

    def apply_preset(self) -> None:
        value = self.preset_var.get()
        if value == "actual":
            width, height = self.native_size
        else:
            width = height = int(value)
        self.width_var.set(str(width))
        self.height_var.set(str(height))

    def accept(self) -> None:
        try:
            width = max(1, int(float(self.width_var.get())))
            height = max(1, int(float(self.height_var.get())))
        except ValueError:
            return
        self.result = (width, height)
        self.destroy()


def rgb_to_hex(color: tuple[int, int, int, int]) -> str:
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def normalize_rect(left: int, top: int, right: int, bottom: int) -> tuple[int, int, int, int]:
    if right <= left:
        right = left + 1
    if bottom <= top:
        bottom = top + 1
    return left, top, right, bottom


def lock_rect_ratio(
    original_left: int,
    original_top: int,
    original_right: int,
    original_bottom: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    mode: str,
) -> tuple[int, int, int, int]:
    original_width = max(1, original_right - original_left)
    original_height = max(1, original_bottom - original_top)
    ratio = original_width / original_height
    width = max(1, right - left)
    height = max(1, bottom - top)
    if width / height > ratio:
        width = round(height * ratio)
    else:
        height = round(width / ratio)

    if "w" in mode:
        left = right - width
    else:
        right = left + width
    if "n" in mode:
        top = bottom - height
    else:
        bottom = top + height
    return normalize_rect(left, top, right, bottom)


def hud_metrics(hud: RttSurface) -> dict[str, float]:
    ul = hud.quad[0:3]
    ur = hud.quad[3:6]
    ll = hud.quad[6:9]
    depth = abs((ul[0] + ur[0] + ll[0]) / 3)
    width = abs(ur[1] - ul[1])
    height = abs(ll[2] - ul[2])
    center_y = (ul[1] + ur[1]) / 2
    center_z = (ul[2] + ll[2]) / 2
    half_h = math.degrees(math.atan2(width / 2, depth)) if depth else 0
    half_v = math.degrees(math.atan2(height / 2, depth)) if depth else 0
    deck_angle = math.degrees(math.atan2(-center_z, depth)) if depth else 0
    return {
        "depth": depth,
        "width": width,
        "height": height,
        "center_y": center_y,
        "center_z": center_z,
        "half_h": half_h,
        "half_v": half_v,
        "tfov_h": half_h * 2,
        "tfov_v": half_v * 2,
        "deck_angle": deck_angle,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Edit Falcon BMS 3dCkpit.dat RTT texture coordinates.")
    parser.add_argument("file", nargs="?", help="Path to 3dCkpit.dat")
    args = parser.parse_args()
    app = RttLayoutApp(args.file)
    app.mainloop()


if __name__ == "__main__":
    main()
