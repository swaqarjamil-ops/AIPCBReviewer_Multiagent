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
"""

import io

import pymupdf
from PIL import Image


def render_pdf_pages_to_images(pdf_bytes: bytes, zoom: float = 2.0) -> list[Image.Image]:
    """Render every page of a PDF into a PIL Image.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file.
        zoom: Scale factor applied to the default 72 DPI PDF resolution.
            Higher values give sharper images (better for reading small
            reference designators / values) at the cost of more tokens.

    Returns:
        A list of PIL Image objects, one per PDF page, in page order.
    """
    images = []
    matrix = pymupdf.Matrix(zoom, zoom)
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix)
            png_bytes = pixmap.tobytes("png")
            images.append(Image.open(io.BytesIO(png_bytes)))
    return images
