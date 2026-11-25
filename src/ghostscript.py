"""Thin wrappers around the Ghostscript command-line tool."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def gs_executable() -> str:
    """Locate the Ghostscript console executable (env GS overrides)."""
    env = os.environ.get("GS")
    if env:
        return env
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            return found
    # Default Windows install location, newest version first.
    candidates = sorted(glob.glob(r"C:\Program Files*\gs\gs*\bin\gswin*c.exe"), reverse=True)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "Ghostscript not found. Install it (https://ghostscript.com) or set the GS environment variable."
    )


def _run(args: list[str]) -> str:
    result = subprocess.run(
        [gs_executable(), "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def render_pages(pdf: Path, out_dir: Path, dpi: int, filter_text: bool = False) -> list[Path]:
    """Render every page of `pdf` to RGB PNGs in `out_dir`; return them in page order.

    With `filter_text`, text objects are not drawn (Ghostscript -dFILTERTEXT), so
    colored words cannot be mistaken for pictures.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    _run([
        "-sDEVICE=png16m",
        f"-r{dpi}",
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        *(["-dFILTERTEXT"] if filter_text else []),
        f"-sOutputFile={out_dir / 'page-%04d.png'}",
        str(pdf),
    ])
    return sorted(out_dir.glob("page-*.png"))


def convert_to_gray(pdf: Path, out_pdf: Path) -> None:
    """Rewrite `pdf` with every color converted to DeviceGray.

    Text and vector graphics stay vector; images are converted but not downsampled.
    """
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-sColorConversionStrategy=Gray",
        "-dProcessColorModel=/DeviceGray",
        "-dOverrideICC",
        "-dAutoRotatePages=/None",
        "-dDownsampleColorImages=false",
        "-dDownsampleGrayImages=false",
        "-dDownsampleMonoImages=false",
        f"-sOutputFile={out_pdf}",
        str(pdf),
    ])


def ink_coverage(pdf: Path, dpi: int = 20) -> list[tuple[float, float, float, float]]:
    """Return per-page (C, M, Y, K) ink coverage fractions using the inkcov device."""
    out = _run(["-sDEVICE=inkcov", f"-r{dpi}", "-o", "-", str(pdf)])
    pages = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and "CMYK" in parts:
            pages.append(tuple(float(v) for v in parts[:4]))
    return pages
