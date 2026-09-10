"""
pdf_builder.py — Convert a list of images into a PDF at maximum quality.

Each image is placed on its own page (default A4, 210 × 297 mm) at 300 DPI,
centered with white padding to preserve the original aspect ratio.

Supported page sizes: A5, A4, A3, Letter, Legal.
Supported orientations: portrait, landscape.
"""

import io
import os
from PIL import Image

DPI = 300

# Page sizes in millimetres: (width, height) in portrait orientation.
PAGE_SIZES_MM = {
    "a5": (148, 210),
    "a4": (210, 297),
    "a3": (297, 420),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
}

# Backwards compatibility
A4_WIDTH_PX = 2480
A4_HEIGHT_PX = 3508


def get_page_size_px(page_size: str = "a4", orientation: str = "portrait") -> tuple[int, int]:
    """
    Return (width_px, height_px) for the given page size + orientation at 300 DPI.

    Args:
        page_size: one of PAGE_SIZES_MM keys (case-insensitive).
        orientation: "portrait" or "landscape" (case-insensitive).
    """
    key = (page_size or "a4").strip().lower()
    if key not in PAGE_SIZES_MM:
        raise ValueError(f"Unsupported page size: {page_size!r}. Choose from: {', '.join(sorted(PAGE_SIZES_MM))}")
    w_mm, h_mm = PAGE_SIZES_MM[key]
    w_px = round(w_mm / 25.4 * DPI)
    h_px = round(h_mm / 25.4 * DPI)

    ori = (orientation or "portrait").strip().lower()
    if ori not in ("portrait", "landscape"):
        raise ValueError(f"Unsupported orientation: {orientation!r}. Choose 'portrait' or 'landscape'.")
    if ori == "landscape":
        w_px, h_px = h_px, w_px
    return w_px, h_px


def _fit_image_to_page(img: Image.Image, page_w_px: int, page_h_px: int) -> Image.Image:
    """
    Scale *img* to fit inside a page and center it on a white background.
    """
    img = img.convert("RGB")
    w, h = img.size

    # Scale factor to fit inside the page while preserving aspect ratio
    scale = min(page_w_px / w, page_h_px / h)
    # For music sheets we DO want to upscale to fill the page
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Center on white canvas
    canvas = Image.new("RGB", (page_w_px, page_h_px), (255, 255, 255))
    x_offset = (page_w_px - new_w) // 2
    y_offset = (page_h_px - new_h) // 2
    canvas.paste(resized, (x_offset, y_offset))
    return canvas


def _fit_image_to_a4(img: Image.Image) -> Image.Image:
    """Backwards-compatible A4 portrait fitting."""
    return _fit_image_to_page(img, A4_WIDTH_PX, A4_HEIGHT_PX)


def build_pdf(
    image_paths: list[str],
    page_size: str = "a4",
    orientation: str = "portrait",
) -> bytes:
    """
    Build a PDF from an ordered list of image file paths.

    Args:
        image_paths: ordered list of image file paths.
        page_size: "a5" | "a4" | "a3" | "letter" | "legal".
        orientation: "portrait" | "landscape".

    Returns:
        The PDF file content as bytes.
    """
    if not image_paths:
        raise ValueError("No images provided")

    page_w_px, page_h_px = get_page_size_px(page_size, orientation)

    pages: list[Image.Image] = []
    for path in image_paths:
        img = Image.open(path)
        pages.append(_fit_image_to_page(img, page_w_px, page_h_px))

    buf = io.BytesIO()
    pages[0].save(
        buf,
        format="PDF",
        resolution=DPI,
        save_all=True,
        append_images=pages[1:],
    )
    buf.seek(0)
    return buf.read()


def build_pdf_to_file(
    image_paths: list[str],
    output_path: str,
    page_size: str = "a4",
    orientation: str = "portrait",
) -> str:
    """Build a PDF and write it to *output_path*. Returns the path."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    data = build_pdf(image_paths, page_size=page_size, orientation=orientation)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build a PDF from images.")
    parser.add_argument("output", help="Output PDF path")
    parser.add_argument("images", nargs="+", help="Input image paths")
    parser.add_argument(
        "--page-size",
        default="a4",
        choices=sorted(PAGE_SIZES_MM),
        help="Page size (default: a4)",
    )
    parser.add_argument(
        "--orientation",
        default="portrait",
        choices=["portrait", "landscape"],
        help="Page orientation (default: portrait)",
    )
    # Legacy positional usage still works: python pdf_builder.py out.pdf img1 img2
    # (options default to A4 portrait in that case).
    args = parser.parse_args()
    build_pdf_to_file(
        args.images, args.output,
        page_size=args.page_size, orientation=args.orientation,
    )
    print(f"PDF saved to {args.output} ({args.page_size} {args.orientation})")

