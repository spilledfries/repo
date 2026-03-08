# path: tools/montage.py
from __future__ import annotations

import argparse
import os
import re
from math import ceil, sqrt
from typing import Iterable, List, Tuple

from PIL import Image, ImageOps, ImageDraw, ImageFont

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def natural_key(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_images_in_dir(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        raise ValueError(f"Input directory not found: {directory}")
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
    ]
    return sorted(files, key=lambda p: natural_key(os.path.basename(p)))


def load_images(paths: Iterable[str]) -> List[Image.Image]:
    images: List[Image.Image] = []
    try:
        for p in paths:
            im = Image.open(p)
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            images.append(im)
        return images
    except Exception:
        for im in images:
            try:
                im.close()
            except Exception:
                pass
        raise


def compute_grid(n: int, cols: int | None, rows: int | None) -> Tuple[int, int]:
    if cols and rows:
        if cols * rows < n:
            raise ValueError("Provided rows*cols cannot fit all images.")
        return cols, rows
    if cols:
        return cols, ceil(n / cols)
    if rows:
        return ceil(n / rows), rows
    cols = ceil(sqrt(n))
    return cols, ceil(n / cols)


def compute_cell_size(images: List[Image.Image]) -> Tuple[int, int]:
    return max(im.width for im in images), max(im.height for im in images)


def resize_to_fit(im: Image.Image, cell_w: int, cell_h: int) -> Image.Image:
    w, h = im.size
    scale = min(cell_w / w, cell_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return im if (new_w, new_h) == (w, h) else im.resize((new_w, new_h), Image.Resampling.LANCZOS)


def parse_color(color: str, allow_transparent: bool = True) -> Tuple[int, int, int, int]:
    s = color.strip()
    if allow_transparent and s.lower() == "transparent":
        return (0, 0, 0, 0)
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 6:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
        return (r, g, b, 255)
    if len(s) == 8:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16); a = int(s[6:8], 16)
        return (r, g, b, a)
    raise ValueError("Invalid color. Use 'transparent' or #RRGGBB[#AA].")


def parse_offset_pair(s: str) -> Tuple[int, int]:
    parts = s.replace(",", " ").split()
    if len(parts) != 2:
        raise ValueError("Offset must be two integers, e.g. '2,2' or '2 2'.")
    return int(parts[0]), int(parts[1])


def infer_format(output_path: str, fmt_opt: str | None) -> str:
    if fmt_opt:
        return fmt_opt.upper()
    ext = os.path.splitext(output_path)[1].lower()
    mapping = {
        ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG",
        ".webp": "WEBP", ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
    }
    return mapping.get(ext, "PNG")


def load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        return ImageFont.truetype(path, size=size)
    for candidate in (
        "arial.ttf", "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def measure_label_height(font: ImageFont.ImageFont, lines: int, pad: int) -> int:
    ascent, descent = getattr(font, "getmetrics", lambda: (getattr(font, "size", 12), 0))()
    line_h = ascent + descent
    return max(1, lines * line_h + 2 * pad)


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font, stroke_width: int) -> Tuple[int,int,int,int]:
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)


def text_width(draw: ImageDraw.ImageDraw, text: str, font, stroke_width: int) -> int:
    b = text_bbox(draw, text, font, stroke_width); return b[2] - b[0]


def text_height(draw: ImageDraw.ImageDraw, text: str, font, stroke_width: int) -> int:
    b = text_bbox(draw, text, font, stroke_width); return b[3] - b[1]


def wrap_text_to_width(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
    draw: ImageDraw.ImageDraw,
    stroke_width: int,
) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        if text_width(draw, trial, font, stroke_width) <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur)); cur = [w]
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and cur:
        lines.append(" ".join(cur))
    used_words = " ".join(lines).split()
    if len(used_words) < len(words):
        last = lines[-1] if lines else ""
        while last and text_width(draw, last + "…", font, stroke_width) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + "…") if last else "…"
    return lines[:max_lines]


def build_label(name: str, mode: str) -> str:
    root = os.path.splitext(os.path.basename(name))[0]
    if mode == "lower": return root.lower()
    if mode == "upper": return root.upper()
    return root


def clamp_radius(w: int, h: int, r: int) -> int:
    return int(max(0, min(r, min(w, h) // 2)))


def draw_rounded_rect(draw: ImageDraw.ImageDraw, bbox: Tuple[int,int,int,int], radius: int,
                      fill=None, outline=None, width: int = 1) -> None:
    radius = clamp_radius(bbox[2]-bbox[0], bbox[3]-bbox[1], radius)
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def rounded_mask(size: Tuple[int,int], radius: int) -> Image.Image:
    w, h = size
    r = clamp_radius(w, h, radius)
    if r <= 0:
        return Image.new("L", size, 255)
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, w, h), radius=r, fill=255)
    return m


def create_montage(
    input_files: List[str],
    output_path: str,
    max_size: int = 2048,
    gap: int = 0,
    bg: str = "transparent",
    cols: int | None = None,
    rows: int | None = None,
    out_format: str | None = None,
    # label options
    label: bool = False,
    label_size: int = 20,
    label_color: str = "#000000",
    label_bg: str = "transparent",
    label_pad: int = 6,
    label_lines: int = 1,
    label_font: str | None = None,
    label_case: str = "original",
    # legibility
    label_stroke_width: int = 0,
    label_stroke_color: str = "#000000",
    label_shadow_offset: str = "0,0",
    label_shadow_color: str = "#00000080",
    # borders & corners
    cell_border_width: int = 0,
    cell_border_color: str = "#000000",
    cell_corner_radius: int = 0,
    img_corner_radius: int = 0,
) -> None:
    if not input_files:
        raise ValueError("At least one input image is required.")
    images = load_images(input_files)

    try:
        n = len(images)
        grid_cols, grid_rows = compute_grid(n, cols, rows)

        cell_w, base_cell_h = compute_cell_size(images)

        font = load_font(label_font, label_size) if label else None

        label_bg_rgba = parse_color(label_bg) if label else (0, 0, 0, 0)
        label_color_rgba = parse_color(label_color, allow_transparent=False) if label else (0, 0, 0, 255)
        stroke_w = max(0, int(label_stroke_width))
        stroke_rgba = parse_color(label_stroke_color, allow_transparent=False)
        shadow_dx, shadow_dy = parse_offset_pair(label_shadow_offset)
        shadow_rgba = parse_color(label_shadow_color, allow_transparent=True)

        cell_border_w = max(0, int(cell_border_width))
        cell_border_rgba = parse_color(cell_border_color, allow_transparent=True)

        label_h = measure_label_height(font, label_lines, label_pad) if label and font else 0
        cell_h = base_cell_h + (label_h if label else 0)

        grid_w = grid_cols * cell_w + (grid_cols - 1) * gap
        grid_h = grid_rows * cell_h + (grid_rows - 1) * gap

        bg_rgba = parse_color(bg)
        canvas_mode = "RGBA" if (bg_rgba[3] < 255 or (label and label_bg_rgba[3] < 255)) else "RGB"
        grid_image = Image.new("RGBA", (grid_w, grid_h), bg_rgba)
        draw = ImageDraw.Draw(grid_image)

        for idx, im in enumerate(images):
            col = idx % grid_cols
            row = idx // grid_cols

            cell_x = col * (cell_w + gap)
            cell_y = row * (cell_h + gap)
            cell_bbox = (cell_x, cell_y, cell_x + cell_w, cell_y + cell_h)

            # Image area (exclude label area)
            img_area_h = base_cell_h
            fitted = resize_to_fit(im, cell_w, img_area_h)
            ox = cell_x + (cell_w - fitted.width) // 2
            oy = cell_y + (img_area_h - fitted.height) // 2

            # Rounded corners for the image
            if img_corner_radius > 0:
                mask = rounded_mask((fitted.width, fitted.height), img_corner_radius)
                grid_image.paste(fitted, (ox, oy), mask)
            else:
                grid_image.paste(fitted, (ox, oy), fitted if fitted.mode == "RGBA" else None)

            # Label background + text
            if label and font:
                label_y0 = cell_y + img_area_h
                if label_bg_rgba[3] > 0:
                    draw.rectangle([cell_x, label_y0, cell_x + cell_w, label_y0 + label_h], fill=label_bg_rgba)

                text = build_label(input_files[idx], label_case)
                max_text_w = cell_w - 2 * label_pad
                lines = wrap_text_to_width(text, font, max_text_w, label_lines, draw, stroke_w)

                total_text_h = sum(text_height(draw, ln, font, stroke_w) for ln in lines)
                avail = label_h - 2 * label_pad
                y = label_y0 + label_pad + max(0, (avail - total_text_h) // 2)

                for ln in lines:
                    lw = text_width(draw, ln, font, stroke_w)
                    x = cell_x + (cell_w - lw) // 2
                    if (shadow_dx != 0 or shadow_dy != 0) and shadow_rgba[3] > 0:
                        draw.text((x + shadow_dx, y + shadow_dy), ln, font=font, fill=shadow_rgba, stroke_width=0)
                    draw.text(
                        (x, y),
                        ln,
                        font=font,
                        fill=label_color_rgba,
                        stroke_width=stroke_w,
                        stroke_fill=stroke_rgba if stroke_w > 0 else None,
                    )
                    y += text_height(draw, ln, font, stroke_w)

            # Cell border (around entire cell incl. label area)
            if cell_border_w > 0 and cell_border_rgba[3] > 0:
                draw_rounded_rect(
                    draw,
                    cell_bbox,
                    radius=cell_corner_radius,
                    fill=None,
                    outline=cell_border_rgba,
                    width=cell_border_w,
                )

        # Downscale if needed
        max_dim = max(grid_w, grid_h)
        if max_dim > max_size:
            scale = max_size / max_dim
            new_w = max(1, int(grid_w * scale))
            new_h = max(1, int(grid_h * scale))
            grid_image = grid_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Format/flatten
        fmt = infer_format(output_path, out_format)
        if fmt in ("JPEG", "BMP", "TIFF") and canvas_mode == "RGB":
            grid_image = grid_image.convert("RGB")
        elif fmt in ("JPEG",) and canvas_mode != "RGB":
            opaque_bg = (bg_rgba[0], bg_rgba[1], bg_rgba[2])  # JPEG can't do alpha
            rgb = Image.new("RGB", grid_image.size, opaque_bg)
            rgb.paste(grid_image, mask=grid_image.split()[-1])
            grid_image = rgb

        grid_image.save(output_path, format=fmt)
    finally:
        for im in images:
            try:
                im.close()
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create an image montage.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--input_files", nargs="+", help="List of input image file paths")
    g.add_argument("--input_dir", help="Directory containing input images")
    p.add_argument("--output", required=True, help="Path to save the output montage")
    p.add_argument("--max_size", type=int, default=2048, help="Longest side cap")
    p.add_argument("--gap", type=int, default=0, help="Pixel gap between cells")
    p.add_argument("--bg", default="transparent", help="Background: 'transparent' or #RRGGBB[#AA]")
    p.add_argument("--cols", type=int, help="Force number of columns")
    p.add_argument("--rows", type=int, help="Force number of rows")
    p.add_argument("--format", dest="out_format", help="Override output format (PNG, JPEG, WEBP, ...)")

    # Label options
    p.add_argument("--label", action="store_true", help="Draw filename labels under each cell")
    p.add_argument("--label_size", type=int, default=20, help="Label font size")
    p.add_argument("--label_color", default="#000000", help="Label text color (#RRGGBB[#AA])")
    p.add_argument("--label_bg", default="transparent", help="Label background (#RRGGBB[#AA] or 'transparent')")
    p.add_argument("--label_pad", type=int, default=6, help="Padding inside the label area")
    p.add_argument("--label_lines", type=int, default=1, help="Max lines for label wrap (>=1)")
    p.add_argument("--label_font", help="Path to a .ttf/.otf font file")
    p.add_argument("--label_case", choices=("original", "lower", "upper"), default="original")

    # Legibility
    p.add_argument("--label_stroke_width", type=int, default=0, help="Outline width in pixels (0 to disable)")
    p.add_argument("--label_stroke_color", default="#000000", help="Outline color (#RRGGBB[#AA])")
    p.add_argument("--label_shadow_offset", default="0,0", help="Shadow offset 'dx,dy'")
    p.add_argument("--label_shadow_color", default="#00000080", help="Shadow color (#RRGGBB[#AA])")

    # Borders & corners
    p.add_argument("--cell_border_width", type=int, default=0, help="Per-cell border width (px)")
    p.add_argument("--cell_border_color", default="#000000", help="Per-cell border color")
    p.add_argument("--cell_corner_radius", type=int, default=0, help="Corner radius for cell border")
    p.add_argument("--img_corner_radius", type=int, default=0, help="Corner radius for the image itself")

    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.input_files:
        input_files = args.input_files
    else:
        input_files = list_images_in_dir(args.input_dir)
        if not input_files:
            raise ValueError("No images found in the specified directory.")

    create_montage(
        input_files=input_files,
        output_path=args.output,
        max_size=args.max_size,
        gap=args.gap,
        bg=args.bg,
        cols=args.cols,
        rows=args.rows,
        out_format=args.out_format,
        label=args.label,
        label_size=args.label_size,
        label_color=args.label_color,
        label_bg=args.label_bg,
        label_pad=args.label_pad,
        label_lines=max(1, args.label_lines),
        label_font=args.label_font,
        label_case=args.label_case,
        label_stroke_width=args.label_stroke_width,
        label_stroke_color=args.label_stroke_color,
        label_shadow_offset=args.label_shadow_offset,
        label_shadow_color=args.label_shadow_color,
        cell_border_width=args.cell_border_width,
        cell_border_color=args.cell_border_color,
        cell_corner_radius=args.cell_corner_radius,
        img_corner_radius=args.img_corner_radius,
    )


if __name__ == "__main__":
    main()
