# chromasort

Merge PDFs and turn pages without color pictures into true grayscale, so printers bill them as black-and-white.

chromasort takes a folder of PDFs, merges them into a single file in natural name
order, and decides page by page whether color is actually needed:

- **Kept in color:** covers (page 1 of each file) and pages with real colored
  pictures (photos, paintings, clipart), even small ones.
- **Converted to grayscale:** pages whose only color is decorative: borders,
  checkboxes, colored text, outlined letters, or black-and-white drawings.

Gray pages are converted to true grayscale (no cyan, magenta or yellow ink), so
printers and print drivers automatically count them as mono pages. Text and vector
art stay sharp, because pages are not flattened into images.

## Quick start

Requirements: Python 3.11+ and [Ghostscript](https://ghostscript.com) 9.50+.

```
pip install -r requirements.txt
# put your PDFs in dataset/
python src/chromasort.py
```

Output:

- `out/merged.pdf`: the merged document, with one bookmark per source file
- `out/report.html`: a thumbnail of every page with its color/gray decision and the reason

If a page is misclassified, list it in [overrides.toml](overrides.toml) and run again:

```toml
["my-file.pdf"]
color = [12]     # keep page 12 in color
gray  = [5, 18]  # force pages 5 and 18 to grayscale
```

## How it works

1. Each page is rendered at low resolution with text hidden.
2. Strongly colored pixels are marked, and thin shapes such as borders and outlines
   are removed by shrinking the marked areas (erosion).
3. If enough colored area remains, the page has a colored picture and stays in color.
4. Gray pages are taken from a Ghostscript grayscale copy of the source. Color pages
   are copied unchanged.
5. The merged file is checked with Ghostscript's `inkcov` device. Any gray page
   that still uses color ink is flagged in the report.

## Documentation

- [docs/README.md](docs/README.md): full usage, command-line options, tuning and code layout
- [docs/design.md](docs/design.md): design decisions and the tuning results

## License

[MIT](LICENSE)

## Credits

Made with <3 by Filipe Pires.
