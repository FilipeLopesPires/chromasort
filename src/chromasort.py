"""chromasort: merge all dataset PDFs into one file, converting pages without colored pictures to grayscale.

Usage:
    python src/chromasort.py [--dataset DIR] [--out DIR] [--overrides FILE] [--min-area N] ...

See docs/README.md for details.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from classify import ClassifierSettings, is_color
from ghostscript import convert_to_gray, ink_coverage, render_pages
from report import PageResult, write_report

ROOT = Path(__file__).resolve().parent.parent
# A gray page passes verification when its C, M and Y ink are (nearly) zero.
VERIFY_TOLERANCE = 1e-4


def natural_key(path: Path) -> list:
    """Sort 'Semana 10' after 'Semana 9'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def load_overrides(path: Path) -> dict[str, dict[str, set[int]]]:
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    overrides = {}
    for name, entry in data.items():
        color = set(entry.get("color", []))
        gray = set(entry.get("gray", []))
        if color & gray:
            raise ValueError(f"{path}: pages {sorted(color & gray)} of {name} are both color and gray")
        overrides[name] = {"color": color, "gray": gray}
    return overrides


def parse_args() -> argparse.Namespace:
    d = ClassifierSettings()
    p = argparse.ArgumentParser(prog="chromasort", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", type=Path, default=ROOT / "dataset", help="folder with input PDFs")
    p.add_argument("--out", type=Path, default=ROOT / "out", help="output folder")
    p.add_argument("--output-name", default="merged.pdf", help="merged PDF file name")
    p.add_argument("--overrides", type=Path, default=ROOT / "overrides.toml", help="per-page overrides file")
    p.add_argument("--no-cover", action="store_true", help="do not force page 1 of each file to color")
    p.add_argument("--dpi", type=int, default=d.dpi, help="classification render resolution")
    p.add_argument("--chroma-min", type=int, default=d.chroma_min, help="min chroma (0-255) of a colored pixel")
    p.add_argument("--erode-radius", type=int, default=d.erode_radius, help="erosion radius in pixels")
    p.add_argument("--min-area", type=int, default=d.min_area, help="min surviving pixels for a color page")
    p.add_argument("--jobs", type=int, default=4, help="parallel Ghostscript processes")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = ClassifierSettings(args.dpi, args.chroma_min, args.erode_radius, args.min_area)
    sources = sorted(args.dataset.glob("*.pdf"), key=natural_key)
    if not sources:
        print(f"No PDFs found in {args.dataset}", file=sys.stderr)
        return 1
    overrides = load_overrides(args.overrides)
    unknown = set(overrides) - {s.name for s in sources}
    if unknown:
        print(f"Warning: overrides for unknown files ignored: {sorted(unknown)}", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    with tempfile.TemporaryDirectory(prefix="chromasort-") as tmp_str:
        tmp = Path(tmp_str)

        # 1. Render (text hidden) for classification, and produce grayscale copies, in parallel.
        print(f"Rendering and converting {len(sources)} PDFs...")
        with ThreadPoolExecutor(args.jobs) as ex:
            renders = ex.map(lambda i_s: render_pages(i_s[1], tmp / f"r{i_s[0]}", settings.dpi, True),
                             enumerate(sources))
            gray_jobs = [ex.submit(convert_to_gray, s, tmp / f"gray{i}.pdf") for i, s in enumerate(sources)]
            renders = list(renders)
            for job in gray_jobs:
                job.result()

        # 2. Classify, then 3. merge.
        writer = PdfWriter()
        results: list[PageResult] = []
        for i, (src, pngs) in enumerate(zip(sources, renders)):
            orig = PdfReader(src)
            gray = PdfReader(tmp / f"gray{i}.pdf")
            if not (len(orig.pages) == len(gray.pages) == len(pngs)):
                raise RuntimeError(f"{src.name}: page count mismatch "
                                   f"(orig {len(orig.pages)}, gray {len(gray.pages)}, renders {len(pngs)})")
            ov = overrides.get(src.name, {"color": set(), "gray": set()})
            first_out = len(writer.pages)
            for n, png in enumerate(pngs, start=1):
                color, mass = is_color(png, settings)
                reason = "picture" if color else "no picture"
                if n == 1 and not args.no_cover:
                    color, reason = True, "cover"
                if n in ov["color"]:
                    color, reason = True, "override"
                elif n in ov["gray"]:
                    color, reason = False, "override"
                writer.add_page((orig if color else gray).pages[n - 1])
                results.append(PageResult(src.name, n, len(writer.pages), color, reason, mass, png))
            writer.add_outline_item(src.stem, first_out)
            print(f"  {src.name}: {sum(r.color for r in results if r.source == src.name)}"
                  f"/{len(pngs)} color pages")

        out_pdf = args.out / args.output_name
        writer.compress_identical_objects()
        with open(out_pdf, "wb") as f:
            writer.write(f)

        # 4. Verify: gray pages in the merged output must carry no C/M/Y ink.
        print("Verifying merged output...")
        coverage = ink_coverage(out_pdf)
        if len(coverage) != len(results):
            raise RuntimeError(f"inkcov returned {len(coverage)} pages, expected {len(results)}")
        for r, (c, m, y, _k) in zip(results, coverage):
            if not r.color and max(c, m, y) > VERIFY_TOLERANCE:
                r.verified = False

        report = args.out / "report.html"
        write_report(results, report,
                     f"dpi={settings.dpi}, chroma_min={settings.chroma_min}, "
                     f"erode_radius={settings.erode_radius}, min_area={settings.min_area}")

    n_color = sum(r.color for r in results)
    n_fail = sum(not r.verified for r in results)
    size_mb = out_pdf.stat().st_size / 1e6
    print(f"\nDone in {time.time() - t0:.0f}s: {len(results)} pages, {n_color} color, "
          f"{len(results) - n_color} gray.")
    print(f"  {out_pdf} ({size_mb:.1f} MB)")
    print(f"  {report}")
    if n_fail:
        print(f"WARNING: {n_fail} gray pages still contain color ink - see report.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
