# chromasort

Merges every PDF in `dataset/` into one PDF and converts every page **without a
relevant colored picture** to true grayscale. Printers and print drivers decide
color vs. mono per page by checking whether the page actually uses color, so the
gray pages are billed and printed as black-and-white while picture pages stay in color.

## Requirements

- Python 3.11+ with `pypdf`, `numpy`, `Pillow` (`pip install -r requirements.txt`)
- [Ghostscript](https://ghostscript.com) 9.50+ (found on `PATH`, in
  `C:\Program Files\gs\...`, or via the `GS` environment variable)

## Usage

```
python src/chromasort.py
```

Outputs:

| File | Content |
|------|---------|
| `out/merged.pdf` | All dataset PDFs in natural name order ("Semana 10" after "Semana 9"), one bookmark per source file |
| `out/report.html` | Thumbnail of every page with its decision, reason and score |

Exit code `0` = success, `1` = no input PDFs, `2` = a gray page still contains color ink (see report).

Options (all optional):

| Option | Default | Meaning |
|--------|---------|---------|
| `--dataset DIR` | `dataset/` | Input folder |
| `--out DIR` | `out/` | Output folder |
| `--output-name NAME` | `merged.pdf` | Merged file name |
| `--overrides FILE` | `overrides.toml` | Per-page corrections |
| `--no-cover` | off | Don't force page 1 of each file to color |
| `--chroma-min N` | 25 | How strongly colored a pixel must be (0-255) |
| `--erode-radius N` | 3 | Thin-structure removal radius, pixels at 50 DPI |
| `--min-area N` | 100 | Colored pixels needed for a color page |
| `--dpi N` | 50 | Classification render resolution (rescale the two pixel settings if changed) |
| `--jobs N` | 4 | Parallel Ghostscript processes |

## How a page is classified

1. **Cover rule**: page 1 of every source PDF stays in color.
2. **Picture detection**: the page is rendered at 50 DPI with text hidden
   (Ghostscript `-dFILTERTEXT`). Pixels whose chroma (`max(R,G,B) - min(R,G,B)`)
   is at least 25 are marked as colored. The mask is then eroded with a 7x7 minimum
   filter, which removes anything thinner than ~7 px (≈3.5 mm): page borders, checkbox
   outlines, colored strokes. Filled pictures survive. If ≥ 100 pixels remain, the
   page is a **color** page.
3. **Overrides** in `overrides.toml` take precedence over both rules.

Consequences:

- Colored photos, paintings and clipart, including small icons, keep the page in color.
- Borders, checkboxes, colored text, outlined letters and black-and-white line art
  become gray.
- Pictures that are already (almost) gray, e.g. gray seal clipart, become gray. Nothing is lost.
- Pale decorative titles become light gray.

## Fixing a wrong decision

Open `out/report.html`, find the page (green frame = color, gray frame = gray), and
add its source file and page number to `overrides.toml`:

```toml
["Semana--3-----Cachorros.pdf"]
color = [12]     # keep in color
gray  = [5, 18]  # force grayscale
```

Then re-run `python src/chromasort.py`. Known limitation: large letters drawn as
colored shapes rather than text (e.g. the "find the letter" grids in weeks 6 and 7)
look like pictures to the detector. They are handled by overrides.

## Gray conversion and verification

Gray pages come from a Ghostscript `pdfwrite` copy of the source with
`ColorConversionStrategy=Gray`. Text and vector art stay vector, and images are not
downsampled. Color pages are copied unchanged from the original. After merging,
Ghostscript's `inkcov` device measures every page, and each gray page must use zero
cyan, magenta and yellow ink. Pages that fail are flagged in the report.

## Code layout

| File | Role |
|------|------|
| `src/chromasort.py` | CLI entry point: orchestration, merge, verification |
| `src/classify.py` | Color-picture detector (`ClassifierSettings`, `is_color`) |
| `src/ghostscript.py` | Ghostscript wrappers: render, gray conversion, ink coverage |
| `src/report.py` | HTML report |
| `overrides.toml` | Manual per-page corrections |

Design rationale: [design.md](design.md).
