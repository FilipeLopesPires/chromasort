"""Decide whether a rendered page contains a relevant colored picture.

Idea: mark strongly colored pixels, then erode the mask. Thin colored
structures (page borders, text strokes, checkbox outlines, outlined
letters) vanish under erosion; filled pictures (photos, clipart) survive.
If enough eroded "color mass" remains, the page is a color page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True)
class ClassifierSettings:
    dpi: int = 50
    # A pixel is "colored" when max(R,G,B) - min(R,G,B) >= chroma_min (0-255).
    # Chroma (not saturation) ignores pale tints such as light page backgrounds.
    # 25 is low enough to catch muted photos (brown bees, gray-blue dolphins).
    chroma_min: int = 25
    # Erosion radius in pixels at `dpi`: structures thinner than 2*r+1 px vanish.
    erode_radius: int = 3
    # Minimum surviving colored pixels (at `dpi`) for the page to count as color.
    # On the reference dataset, B&W pages score <= 29 and the faintest real
    # picture page scores 177.
    min_area: int = 100


def color_mass(png: Path, s: ClassifierSettings) -> int:
    """Number of strongly colored pixels that survive erosion."""
    rgb = np.asarray(Image.open(png).convert("RGB"), dtype=np.int16)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mask = Image.fromarray(((chroma >= s.chroma_min) * 255).astype(np.uint8))
    eroded = mask.filter(ImageFilter.MinFilter(2 * s.erode_radius + 1))
    return int(np.count_nonzero(np.asarray(eroded)))


def is_color(png: Path, s: ClassifierSettings) -> tuple[bool, int]:
    mass = color_mass(png, s)
    return mass >= s.min_area, mass
