from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
RTT_TARGET_RE = re.compile(r"^\s*rttTarget\s+(\d+)\s+(\d+)\s*;", re.IGNORECASE)
SURFACE_RE = re.compile(rf"^\s*([A-Za-z_][\w]*)\s+(.+?)\s*;\s*(?://.*)?$")


HEADER_LINES = [
    "// RTT definition line:",
    "// [display]    [UL.x] [UL.y] [UL.z]    [UR.x] [UR.y] [UR.z]    [LL.x] [LL.y] [LL.z]    [RTT.L] [RTT.T] [RTT.R] [RTT.B] [BlendMode]",
    "// Quad coordinate convention: X = depth (larger = narrower)",
    "//                             Y = width",
    "//                             Z = height (only LL determines bottom edge height)",
    "// RTT coordinates define the pixel source from rttTarget size",
    "// BlendModes are a = alpha blending, c = color blending, g = texture gouraud, t = texture, default = g",
    "",
]


@dataclass
class RttSurface:
    name: str
    quad: list[float]
    left: int
    top: int
    right: int
    bottom: int
    blend: str = "g"
    alpha: float | None = None
    line_index: int | None = None
    enabled: bool = True

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def rect(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom

    def set_rect(self, left: int, top: int, width: int, height: int, max_w: int | None = None, max_h: int | None = None) -> None:
        width = max(1, int(width))
        height = max(1, int(height))
        left = int(left)
        top = int(top)
        self.left = left
        self.top = top
        self.right = left + width
        self.bottom = top + height

    def formatted(self) -> str:
        quad = "".join(f"{v:10.3f}" for v in self.quad)
        alpha = "" if self.alpha is None else f" {self.alpha:g}"
        return (
            f"{self.name:<10}{quad}"
            f"{self.left:7d}{self.top:6d}{self.right:6d}{self.bottom:6d}"
            f"  {self.blend}{alpha};"
        )


@dataclass
class CockpitFile:
    path: Path | None = None
    lines: list[str] = field(default_factory=list)
    rtt_width: int = 600
    rtt_height: int = 600
    target_line_index: int | None = None
    rtt_preamble: list[str] = field(default_factory=list)
    surfaces: list[RttSurface] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "CockpitFile":
        source = Path(path)
        text = source.read_text(encoding="utf-8", errors="replace")
        doc = cls(path=source, lines=text.splitlines())
        doc.parse()
        return doc

    def parse(self) -> None:
        self.surfaces.clear()
        self.rtt_preamble.clear()
        for index, line in enumerate(self.lines):
            target = RTT_TARGET_RE.match(line)
            if target:
                self.rtt_width = int(target.group(1))
                self.rtt_height = int(target.group(2))
                self.target_line_index = index
                continue

            stripped = line.lstrip()
            enabled = not stripped.startswith("//")
            candidate = stripped[2:].strip() if not enabled else line.strip()
            match = SURFACE_RE.match(candidate)
            if not match:
                continue
            parsed = parse_surface(match.group(1), match.group(2), index, enabled)
            if parsed:
                self.surfaces.append(parsed)
        self._capture_rtt_preamble()

    def validate(self) -> list[str]:
        warnings: list[str] = []
        for surface in self.surfaces:
            if surface.left < 0 or surface.top < 0 or surface.right > self.rtt_width or surface.bottom > self.rtt_height:
                warnings.append(f"{surface.name} extends outside the RTT target.")
            if surface.width <= 0 or surface.height <= 0:
                warnings.append(f"{surface.name} has zero or negative size.")
        for i, a in enumerate(self.surfaces):
            if not a.enabled:
                continue
            for b in self.surfaces[i + 1 :]:
                if b.enabled and rects_overlap(a.rect(), b.rect()):
                    warnings.append(f"{a.name} overlaps {b.name}.")
        return warnings

    def invalid_for_export(self) -> list[str]:
        return [
            warning
            for warning in self.validate()
            if "extends outside" in warning or "zero or negative" in warning
        ]

    def overlapping_surface_names(self) -> set[str]:
        names: set[str] = set()
        for i, a in enumerate(self.surfaces):
            if not a.enabled:
                continue
            for b in self.surfaces[i + 1 :]:
                if b.enabled and rects_overlap(a.rect(), b.rect()):
                    names.add(a.name)
                    names.add(b.name)
        return names

    def resize_rtt_target(self, width: int, height: int) -> None:
        width = int(width)
        height = int(height)
        if width < 1 or height < 1:
            raise ValueError("RTT target dimensions must be positive.")

        scale_x = width / max(1, self.rtt_width)
        scale_y = height / max(1, self.rtt_height)
        for surface in self.surfaces:
            left = round(surface.left * scale_x)
            top = round(surface.top * scale_y)
            right = round(surface.right * scale_x)
            bottom = round(surface.bottom * scale_y)
            surface.left = left
            surface.top = top
            surface.right = max(left + 1, right)
            surface.bottom = max(top + 1, bottom)

        self.rtt_width = width
        self.rtt_height = height

    def save(self, path: str | Path | None = None) -> Path:
        if path is None:
            if self.path is None:
                raise ValueError("No save path was provided.")
            path = self.path
        destination = Path(path)
        destination.write_text(self.render(), encoding="utf-8", newline="\n")
        self.path = destination
        self.lines = self.render().splitlines()
        self.parse()
        return destination

    def render(self) -> str:
        lines = list(self.lines)
        if self.target_line_index is None:
            block = self._render_rtt_block()
            return "\n".join(block + [""] + lines) + "\n"

        start, end = find_rtt_block(lines, self.target_line_index, self.surfaces)
        block = self._render_rtt_block()
        new_lines = lines[:start] + block + lines[end:]
        return "\n".join(new_lines).rstrip() + "\n"

    def _capture_rtt_preamble(self) -> None:
        if self.target_line_index is None or not self.surfaces:
            return
        first_surface_line = min(s.line_index for s in self.surfaces if s.line_index is not None)
        for line in self.lines[self.target_line_index + 1 : first_surface_line]:
            stripped = line.strip()
            if stripped and not stripped.startswith("//"):
                self.rtt_preamble.append(stripped)

    def _render_rtt_block(self) -> list[str]:
        block = HEADER_LINES + [f"rttTarget {self.rtt_width} {self.rtt_height};"]
        if self.rtt_preamble:
            block.extend(["", *self.rtt_preamble])
        block.extend(["", rtt_column_header()])
        block.extend(s.formatted() for s in self.surfaces)
        return block


def parse_surface(name: str, body: str, line_index: int, enabled: bool) -> RttSurface | None:
    tokens = body.replace("\t", " ").split()
    if len(tokens) < 14:
        return None
    try:
        quad = [float(value.rstrip("fF")) for value in tokens[:9]]
        left, top, right, bottom = [int(float(value)) for value in tokens[9:13]]
    except ValueError:
        return None
    blend = tokens[13].strip()
    if len(blend) != 1 or not blend.isalpha():
        return None
    alpha = None
    if len(tokens) > 14:
        try:
            alpha = float(tokens[14].rstrip("fF"))
        except ValueError:
            alpha = None
    return RttSurface(name, quad, left, top, right, bottom, blend, alpha, line_index, enabled)


def rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def find_rtt_block(lines: list[str], target_index: int, surfaces: list[RttSurface]) -> tuple[int, int]:
    start = target_index
    while start > 0 and (lines[start - 1].strip() == "" or lines[start - 1].lstrip().startswith("//")):
        start -= 1

    surface_indexes = [surface.line_index for surface in surfaces if surface.line_index is not None]
    if surface_indexes:
        end = max(surface_indexes) + 1
    else:
        end = target_index + 1

    while end < len(lines):
        line = lines[end]
        if line.strip() == "" or line.lstrip().startswith("//"):
            end += 1
            continue
        match = SURFACE_RE.match(line.strip())
        if match and parse_surface(match.group(1), match.group(2), end, True):
            end += 1
            continue
        break
    return start, end


def rtt_column_header() -> str:
    return (
        "//         /UL.x     /UL.y     /UL.z     /UR.x     /UR.y     /UR.z"
        "     /LL.x     /LL.y     /LL.z      /L    /T    /R    /B  /BLEND"
    )
