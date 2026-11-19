#!/usr/bin/env python3
"""Publish the committed poster to the make.fun output directory.

The repository ships a single 1024x1024 image at ``entry.png`` (a lossless RGB
PNG). This script accepts a PNG or a JPEG container, validates the structure and
exact dimensions, and then copies the bytes atomically to
``$MAKEFUN_OUTPUT_DIR/entry.png`` (default ``/output/entry.png``).

Standard library only. Safe under ``python3 -P -s``: it never imports from the
working directory, never uses site packages, never touches the network, and
resolves ``entry.png`` next to this file rather than from the cwd.
"""

from __future__ import annotations

import os
import sys
import tempfile
import zlib
from pathlib import Path

SIDE = 1024
MAX_BYTES = 1024 * 1024
MIN_BYTES = 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_CRITICAL_BEFORE_IDAT = {b"IHDR", b"PLTE"}
JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


class EntryError(Exception):
    """The committed entry is missing, truncated, or not a valid image."""


def _fail(message: str) -> None:
    raise EntryError(message)


def _png_size(data: bytes) -> tuple[int, int]:
    if not data.startswith(PNG_SIGNATURE):
        _fail("bad PNG signature")
    pos = len(PNG_SIGNATURE)
    index = 0
    width = height = 0
    idat_bytes = 0
    seen_idat = False
    while pos < len(data):
        if pos + 8 > len(data):
            _fail("truncated PNG chunk header")
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        if length > 0x7FFFFFFF:
            _fail("PNG chunk length out of range")
        end = pos + 8 + length
        if end + 4 > len(data):
            _fail("truncated PNG chunk body")
        payload = data[pos + 8:end]
        stored_crc = int.from_bytes(data[end:end + 4], "big")
        if zlib.crc32(ctype + payload) & 0xFFFFFFFF != stored_crc:
            _fail("PNG chunk CRC mismatch")

        if index == 0:
            if ctype != b"IHDR" or length != 13:
                _fail("PNG does not begin with a 13-byte IHDR")
            width = int.from_bytes(payload[0:4], "big")
            height = int.from_bytes(payload[4:8], "big")
            if width == 0 or height == 0:
                _fail("PNG has zero dimensions")
            depth, color = payload[8], payload[9]
            if depth not in (1, 2, 4, 8, 16):
                _fail("invalid PNG bit depth")
            if color not in (0, 2, 3, 4, 6):
                _fail("invalid PNG colour type")
            if payload[10] != 0 or payload[11] != 0:
                _fail("unsupported PNG compression or filter method")
            if payload[12] not in (0, 1):
                _fail("invalid PNG interlace method")
        elif ctype == b"IDAT":
            seen_idat = True
            idat_bytes += length
        elif ctype == b"IEND":
            if length != 0:
                _fail("PNG IEND chunk is not empty")
            if not seen_idat or idat_bytes == 0:
                _fail("PNG has no image data")
            if end + 4 != len(data):
                _fail("trailing bytes after PNG IEND")
            return width, height
        elif not seen_idat and not (ctype[0] & 0x20):
            if ctype not in PNG_CRITICAL_BEFORE_IDAT:
                _fail("unexpected critical PNG chunk before image data")
        elif seen_idat and not (ctype[0] & 0x20):
            _fail("unexpected critical PNG chunk after image data")

        pos = end + 4
        index += 1
        if index > 4096:
            _fail("implausible number of PNG chunks")
    _fail("PNG has no IEND")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    if data[:2] != b"\xff\xd8":
        _fail("bad JPEG start-of-image marker")
    if not data.endswith(b"\xff\xd9"):
        _fail("JPEG has no end-of-image marker")
    pos = 2
    size: tuple[int, int] | None = None
    seen_sos = False
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            _fail("JPEG marker expected")
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker == 0x00:
            continue
        if marker == 0xD9:
            break
        if 0xD0 <= marker <= 0xD8:
            continue
        if pos + 2 > len(data):
            _fail("truncated JPEG segment")
        seglen = int.from_bytes(data[pos:pos + 2], "big")
        if seglen < 2 or pos + seglen > len(data):
            _fail("invalid JPEG segment length")
        if marker in JPEG_SOF:
            payload = data[pos + 2:pos + seglen]
            if len(payload) < 5:
                _fail("truncated JPEG frame header")
            height = int.from_bytes(payload[1:3], "big")
            width = int.from_bytes(payload[3:5], "big")
            if width == 0 or height == 0:
                _fail("JPEG frame has zero dimensions")
            size = (width, height)
        if marker == 0xDA:
            seen_sos = True
            break
        pos += seglen
    if not seen_sos:
        _fail("JPEG has no scan data")
    if size is None:
        _fail("JPEG has no frame header")
    return size


def inspect_entry(data: bytes) -> tuple[str, int, int]:
    """Return (kind, width, height) after structural validation."""
    if len(data) < MIN_BYTES:
        _fail(f"image is only {len(data)} bytes")
    if len(data) > MAX_BYTES:
        _fail(f"image is {len(data)} bytes, over the 1 MiB limit")
    if data.startswith(PNG_SIGNATURE):
        kind = "PNG"
        width, height = _png_size(data)
    elif data.startswith(b"\xff\xd8"):
        kind = "JPEG"
        width, height = _jpeg_size(data)
    else:
        _fail("entry.png is neither PNG nor JPEG")
    if (width, height) != (SIDE, SIDE):
        _fail(f"image is {width}x{height}, expected {SIDE}x{SIDE}")
    return kind, width, height


def resolve_source() -> Path:
    return Path(__file__).resolve().parent / "entry.png"


def resolve_destination() -> Path:
    raw = os.environ.get("MAKEFUN_OUTPUT_DIR", "").strip()
    directory = Path(raw).expanduser() if raw else Path("/output")
    return directory / "entry.png"


def publish(destination: Path, payload: bytes) -> None:
    """Write the exact payload atomically and verify the bytes landed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=".entry-", suffix=".tmp",
        delete=False,
    )
    tmp = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(tmp, destination)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    if destination.read_bytes() != payload:
        raise OSError("written entry.png does not match the source bytes")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in args):
        print("usage: python3 -P -s main.py  "
              "(writes $MAKEFUN_OUTPUT_DIR/entry.png or /output/entry.png)")
        return 0
    if args:
        print(f"main.py: unexpected argument {args[0]!r}", file=sys.stderr)
        return 1

    source = resolve_source()
    try:
        payload = source.read_bytes()
    except OSError as exc:
        print(f"main.py: cannot read {source}: {exc}", file=sys.stderr)
        return 1
    try:
        kind, width, height = inspect_entry(payload)
    except EntryError as exc:
        print(f"main.py: {source.name} rejected: {exc}", file=sys.stderr)
        return 1

    destination = resolve_destination()
    try:
        publish(destination, payload)
    except OSError as exc:
        print(f"main.py: cannot write {destination}: {exc}", file=sys.stderr)
        return 1

    print(f"main.py: wrote {destination} "
          f"({kind} {width}x{height}, {len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
