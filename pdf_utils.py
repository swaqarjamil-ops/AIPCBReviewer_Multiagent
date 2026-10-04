"""
pdf_utils.py
------------
Small helper module that turns an uploaded schematic PDF into a list of
PIL images (one per page). Schematics are visual documents, so every
agent that needs to "see" the design works from these page images
rather than raw PDF text.

Note: this uses `import pymupdf`, the current recommended import name
for the PyMuPDF package. Its older alias `import fitz` still works and
isn't going away, but new code should prefer `pymupdf`.

Token optimization: images are rendered at a moderate zoom, converted
to RGB, and capped to a max side length so vision calls stay cheaper
without losing readable reference designators.
"""

import io

import pymupdf
from PIL import Image


def render_pdf_pages_to_images(
    pdf_bytes: bytes,
    zoom: float = 1.4,
    max_side: int = 1400,
) -> list[Image.Image]:
    """Render every page of a PDF into a PIL Image (token-optimized).

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file.
        zoom: Scale factor applied to the default 72 DPI PDF resolution.
            Higher values give sharper images at the cost of more tokens.
            Default 1.4 balances readability vs token cost.
        max_side: Longest side (width or height) is capped at this many
            pixels after zoom. Prevents very large pages from exploding
            vision token usage.

    Returns:
        A list of RGB PIL Image objects, one per PDF page, in page order.
    """
    images = []
    matrix = pymupdf.Matrix(zoom, zoom)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix)
            png_bytes = pixmap.tobytes("png")
            img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > max_side:
                scale = max_side / longest
                img = img.resize(
                    (int(w * scale), int(h * scale)),
                    Image.Resampling.LANCZOS,
                )
            images.append(img)
    return images
