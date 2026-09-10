"""
pdf_builder.py — Convert a list of images into an A4 PDF at maximum quality.

Each image is placed on its own A4 page (210 × 297 mm) at 300 DPI,
centered with white padding to preserve the original aspect ratio.
"""

import io
import os
from PIL import Image

# A4 at 300 DPI  →  2480 × 3508 px
A4_WIDTH_PX = 2480
A4_HEIGHT_PX = 3508
DPI = 300


def _fit_image_to_a4(img: Image.Image) -> Image.Image:
    """
    Scale *img* to fit inside an A4 page and center it on a white background.
    """
    img = img.convert("RGB")
    w, h = img.size

    # Scale factor to fit inside A4 while preserving aspect ratio
    scale = min(A4_WIDTH_PX / w, A4_HEIGHT_PX / h)
    # Don't upscale if the image is already smaller than A4
    # Actually, for music sheets we DO want to upscale to fill the page
    new_w = int(w * scale)
    new_h = int(h * scale)

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Center on white A4 canvas
    canvas = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), (255, 255, 255))
    x_offset = (A4_WIDTH_PX - new_w) // 2
    y_offset = (A4_HEIGHT_PX - new_h) // 2
    canvas.paste(resized, (x_offset, y_offset))
    return canvas


def build_pdf(image_paths: list[str]) -> bytes:
    """
    Build a PDF from an ordered list of image file paths.

    Returns:
        The PDF file content as bytes.
    """
    if not image_paths:
        raise ValueError("No images provided")

    pages: list[Image.Image] = []
    for path in image_paths:
        img = Image.open(path)
        pages.append(_fit_image_to_a4(img))

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


def build_pdf_to_file(image_paths: list[str], output_path: str) -> str:
    """Build a PDF and write it to *output_path*. Returns the path."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    data = build_pdf(image_paths)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python pdf_builder.py output.pdf img1.png img2.png ...")
        sys.exit(1)
    out = sys.argv[1]
    imgs = sys.argv[2:]
    build_pdf_to_file(imgs, out)
    print(f"PDF saved to {out}")

