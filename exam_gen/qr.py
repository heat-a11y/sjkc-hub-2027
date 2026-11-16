"""Pupil-ID QR codes for exam papers (pure stdlib).

Thin wrapper around the vendored Nayuki QR generator (:mod:`qrcodegen`) that
turns a short text payload (pupil / set ID) into:

  * ``qr_mat``  — the module matrix (for custom output),
  * ``qr_svg``  — crisp inline SVG (embedded directly into the HTML preview),
  * ``qr_png``  — a small grayscale PNG (embedded into the .docx).

No image library is needed: PNG is written by hand (zlib + crc32 from the
standard library).  Payloads that exceed a QR code's byte capacity raise
``ValueError`` so the caller can fall back to printing the ID as text.
"""

from __future__ import annotations

import base64
import struct
import zlib

from . import qrcodegen


def qr_mat(text: str):
    """Encode ``text`` (byte mode, error-correction LOW) to a module matrix.

    Returns ``(size, rows)`` where ``rows`` is a list of ``size`` bool lists
    (True = dark module), **including** the quiet-zone-free symbol area only.
    Raises ``ValueError`` when the payload is too long for any QR code.
    """
    qr = qrcodegen.QrCode.encode_text(str(text), qrcodegen.QrCode.Ecc.LOW)
    size = qr.get_size()
    rows = [[qr.get_module(x, y) for x in range(size)] for y in range(size)]
    return size, rows


def qr_svg(text: str, scale: int = 8, border: int = 2) -> str:
    """Return an inline SVG string rendering the QR code (white border
    included).  ``scale`` is the number of SVG px per module."""
    size, rows = qr_mat(text)
    dim = size + 2 * border
    rects = []
    for y, row in enumerate(rows):
        for x, dark in enumerate(row):
            if dark:
                rects.append(f"<rect x='{(x + border) * scale}' "
                             f"y='{(y + border) * scale}' width='{scale}' "
                             f"height='{scale}'/>")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{dim * scale}' "
            f"height='{dim * scale}' viewBox='0 0 {dim * scale} {dim * scale}'>"
            f"<rect width='100%' height='100%' fill='#fff'/>"
            f"{''.join(rects)}</svg>")


def qr_png(text: str, scale: int = 6, border: int = 3) -> bytes:
    """Return PNG bytes for the QR code (grayscale, boolean alpha)."""
    size, rows = qr_mat(text)
    dim = (size + 2 * border) * scale

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    raw = bytearray()
    for y in range(dim):
        raw.append(0)                       # filter: none
        my = y // scale - border
        for x in range(dim):
            mx = x // scale - border
            on = 0 <= mx < size and 0 <= my < size and rows[my][mx]
            raw.append(0 if on else 255)
    ihdr = struct.pack(">IIBBBBB", dim, dim, 8, 0, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    return (b"\x89PNG\r\n\x1a\n" +
            _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", idat) +
            _chunk(b"IEND", b""))


def qr_svg_data_uri(text: str, scale: int = 8) -> str:
    """Data-URI form of :func:`qr_svg` (smaller than PNG for typical IDs)."""
    return ("data:image/svg+xml;base64," +
            base64.b64encode(qr_svg(text, scale=scale).encode("utf-8"))
            .decode("ascii"))