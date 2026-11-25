"""Self-contained HTML report with one thumbnail per page of the merged output."""

from __future__ import annotations

import base64
import html
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class PageResult:
    source: str          # source PDF file name
    page: int            # 1-based page number within the source
    out_page: int        # 1-based page number in the merged output
    color: bool          # final decision
    reason: str          # "cover", "picture", "no picture", "override"
    mass: int            # classifier score
    thumb: Path          # rendered page used for the thumbnail
    verified: bool = True  # False if the merged page still carries color ink while marked gray


def _thumb_data_uri(png: Path, color: bool) -> str:
    img = Image.open(png).convert("RGB")
    if not color:
        img = img.convert("L")
    img.thumbnail((160, 230))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def write_report(results: list[PageResult], out_html: Path, settings_desc: str) -> None:
    n_color = sum(r.color for r in results)
    n_fail = sum(not r.verified for r in results)
    sections: list[str] = []
    current = None
    for r in results:
        if r.source != current:
            if current is not None:
                sections.append("</div>")
            current = r.source
            sections.append(f"<h2>{html.escape(r.source)}</h2><div class='grid'>")
        cls = "color" if r.color else "gray"
        warn = "" if r.verified else "<div class='warn'>still has color ink!</div>"
        sections.append(
            f"<figure class='{cls}'><img src='{_thumb_data_uri(r.thumb, r.color)}' alt=''>"
            f"<figcaption><b>p{r.page}</b> &rarr; out {r.out_page}<br>"
            f"<span class='tag'>{cls.upper()}</span> {html.escape(r.reason)} ({r.mass}){warn}</figcaption></figure>"
        )
    if current is not None:
        sections.append("</div>")

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>chromasort report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, sans-serif; margin: 16px; background: #fafafa; color: #222; }}
.grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
figure {{ margin: 0; padding: 6px; background: #fff; border: 3px solid #bbb; border-radius: 6px; width: 170px; }}
figure.color {{ border-color: #2e8b57; }}
figure img {{ display: block; max-width: 160px; margin: 0 auto 4px; }}
figcaption {{ font-size: 12px; }}
.tag {{ font-weight: bold; }}
.color .tag {{ color: #2e8b57; }}
.gray .tag {{ color: #666; }}
.warn {{ color: #c00; font-weight: bold; }}
</style></head><body>
<h1>chromasort report</h1>
<p>{len(results)} pages: <b>{n_color} color</b>, <b>{len(results) - n_color} gray</b>.
Verification failures: <b>{n_fail}</b>.</p>
<p>Score in parentheses = colored pixels surviving erosion ({html.escape(settings_desc)}).
To fix a page, add it to <code>overrides.toml</code> and re-run.</p>
{''.join(sections)}
</body></html>"""
    out_html.write_text(doc, encoding="utf-8")
