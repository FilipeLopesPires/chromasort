# chromasort design: per-page color/gray PDF merge

Date: 2026-11-25

## Goal

Produce one PDF from all dataset PDFs (natural name order) in which pages with
relevant colored pictures stay in color and every other page is true grayscale,
so printers automatically count those pages as mono.

## Decisions

- **Small colored pictures count as color.** Activities may depend on color (for
  example "which ball is blue?"), so any real colored picture keeps the page in color,
  however small.
- **Review + overrides.** Every run writes a thumbnail report, and `overrides.toml`
  fixes individual pages on later runs.
- **Covers.** Page 1 of each source PDF is always kept in color.

## Approaches considered

1. **Render, measure, and convert with Ghostscript (chosen).** Classification works
   on the rendered appearance, so it doesn't matter how the PDF was built (images,
   vectors, transparency). Gray pages come from a Ghostscript gray conversion, so
   text and vectors stay sharp.
2. **Inspect PDF objects** (image color spaces, fill colors). Rejected as fragile:
   borders can be images and clipart can be vectors.
3. **Rasterize gray pages.** Rejected: text loses sharpness and files get bigger.

## Classifier

Render at 50 DPI with text hidden. Mark a pixel as colored when its chroma is at
least 25. Erode the mask with a 7x7 minimum filter. Count the surviving pixels and
compare the count with a minimum area of 100.

- Chroma rather than saturation, so pale tints (near-white backgrounds) don't count.
- The threshold of 25 is low enough to catch muted photos: on the dataset, brown
  bees scored 177-2600 and B&W pages scored at most 29. At 60, real photo pages
  were missed.
- Erosion separates thin decoration (borders, outlines) from filled pictures.
- Hiding text costs nothing and keeps colored words out of the count.

Tuning results on the reference dataset (273 pages): the highest B&W page scores 29
and the lowest real picture page scores 177. The two colored-letter grid pages
(Semana 6 p14, Semana 7 p14) are vector letters that look like pictures, so they
are set to gray in `overrides.toml`.

## Output and verification

pypdf merges the pages, taking each one from either the original or the gray copy,
and adds one bookmark per source. Afterwards `inkcov` checks that every gray page
uses no C/M/Y ink; if one does, the page is flagged and the exit code is 2.

## Result (reference dataset)

273 pages: 111 color, 162 gray. 0 verification failures. About 35 s to run;
output 187 MB (input 205 MB).
