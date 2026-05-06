from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import CockpitFile, RttSurface


SURFACE_COLORS = [
    (126, 83, 74, 130),
    (148, 132, 77, 130),
    (76, 132, 132, 130),
    (128, 122, 63, 130),
    (73, 86, 143, 130),
    (72, 125, 84, 130),
    (126, 86, 126, 130),
    (145, 103, 73, 130),
]

OVERLAP_COLOR = (210, 45, 45, 165)
INTERNAL_GRID_COLOR = (235, 235, 235, 70)
LABEL_COLOR = (0, 0, 0, 210)


def export_layout(doc: CockpitFile, path: str | Path, width: int | None = None, height: int | None = None, internal_grid: bool = True) -> Path:
    errors = doc.invalid_for_export()
    if errors:
        raise ValueError("Export blocked: " + errors[0])
    target_w = int(width or doc.rtt_width)
    target_h = int(height or doc.rtt_height)
    scale_x = target_w / max(1, doc.rtt_width)
    scale_y = target_h / max(1, doc.rtt_height)
    image = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    font = load_font(max(10, min(36, target_w // 32)))

    overlaps = doc.overlapping_surface_names()
    for index, surface in enumerate(doc.surfaces):
        draw_surface(draw, surface, index, scale_x, scale_y, font, surface.name in overlaps, internal_grid)

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return destination


def draw_surface(
    draw: ImageDraw.ImageDraw,
    surface: RttSurface,
    index: int,
    sx: float,
    sy: float,
    font: ImageFont.ImageFont,
    is_overlapping: bool,
    internal_grid: bool,
) -> None:
    x1 = round(surface.left * sx)
    y1 = round(surface.top * sy)
    x2 = round(surface.right * sx) - 1
    y2 = round(surface.bottom * sy) - 1
    fill = OVERLAP_COLOR if is_overlapping else SURFACE_COLORS[index % len(SURFACE_COLORS)]
    outline = fill[:3] + (255,)
    draw.rectangle((x1, y1, x2, y2), fill=fill, outline=outline, width=1)
    draw_centered_text(draw, (x1, y1, x2, y2), surface.name.upper(), font)
    if internal_grid:
        draw_internal_grid(draw, x1, y1, x2, y2)


def draw_centered_text(draw: ImageDraw.ImageDraw, bounds: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont) -> None:
    x1, y1, x2, y2 = bounds
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = x1 + ((x2 - x1 + 1) - text_w) / 2
    y = y1 + ((y2 - y1 + 1) - text_h) / 2 - bbox[1]
    draw.text((x, y), text, fill=LABEL_COLOR, font=font)


def draw_internal_grid(draw: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int) -> None:
    width = x2 - x1 + 1
    height = y2 - y1 + 1
    if width < 10 or height < 10:
        return
    for step in range(1, 10):
        x = round(x1 + width * step / 10)
        y = round(y1 + height * step / 10)
        draw.line((x, y1, x, y2), fill=INTERNAL_GRID_COLOR, width=1)
        draw.line((x1, y, x2, y), fill=INTERNAL_GRID_COLOR, width=1)


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()
