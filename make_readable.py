#!/usr/bin/env python3
"""
Convert output.md (wide markdown table) → output_readable.md (grouped card format).
Grouped by video, one card per reference.
"""

import re
from collections import OrderedDict

INPUT_FILE  = "output.md"
OUTPUT_FILE = "output_readable.md"
_PIPE       = "\x00PIPE\x00"   # temp placeholder for escaped \|


def parse_row(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith("|"):
        return None
    line = line.replace("\\|", _PIPE)
    parts = [p.replace(_PIPE, "|").strip() for p in line.split("|")]
    return parts[1:-1] if len(parts) > 2 else None


def extract_link(cell: str) -> tuple[str, str]:
    m = re.match(r'\[(.+?)\]\((.+?)\)', cell, re.DOTALL)
    if m:
        # Unescape HTML entities in title
        title = m.group(1)
        title = title.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')
        return title, m.group(2)
    return cell, ""


def fmt_post(raw: str) -> str:
    """Turn the flattened LinkedIn post back into readable paragraphs."""
    # Double-space was used as paragraph break when collapsing newlines
    paragraphs = [p.strip() for p in raw.split("  ") if p.strip()]
    return "\n\n".join(paragraphs)


def is_separator(cells: list[str]) -> bool:
    return all(re.match(r"^-+$", c.replace(" ", "")) for c in cells if c)


def is_header(cells: list[str]) -> bool:
    return cells[0].strip() in ("Status", "status") or cells[1].strip() == "Video Title"


def main() -> None:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rows = []
    for line in lines:
        cells = parse_row(line)
        if not cells or len(cells) < 9:
            continue
        if is_separator(cells) or is_header(cells):
            continue
        rows.append(cells)

    # Group by video URL (preserves insertion order = newest first)
    videos: OrderedDict = OrderedDict()
    for cells in rows:
        status        = cells[0]
        title, url    = extract_link(cells[1])
        date          = cells[2]
        reference     = cells[3]
        who_said_it   = cells[4]
        what_they_said= cells[5]
        what_it_means = cells[6]
        nate_interp   = cells[7]
        linkedin_post = cells[8]

        key = url or title
        if key not in videos:
            videos[key] = {"title": title, "url": url, "date": date, "refs": []}
        videos[key]["refs"].append({
            "status":              status,
            "reference":           reference,
            "who_said_it":         who_said_it,
            "what_they_said":      what_they_said,
            "what_it_means":       what_it_means,
            "nate_interpretation": nate_interp,
            "linkedin_post":       linkedin_post,
        })

    total_refs = sum(len(v["refs"]) for v in videos.values())
    print(f"Parsed: {len(videos)} videos, {total_refs} references")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# NateBJones Research — Readable View\n\n")
        out.write(f"_{len(videos)} videos · {total_refs} references_\n\n")

        for video in videos.values():
            out.write("---\n\n")
            ref_count = len(video["refs"])
            out.write(f"## [{video['title']}]({video['url']})\n\n")
            out.write(f"**Date:** {video['date']} &nbsp;|&nbsp; **{ref_count} reference{'s' if ref_count != 1 else ''}**\n\n")

            for i, ref in enumerate(video["refs"], 1):
                status  = ref["status"] or "[ ]"
                ref_num = f"{i}."
                out.write(f"### {status} {ref_num} {ref['reference']}\n\n")

                out.write(f"**Who:** {ref['who_said_it']}\n\n")
                out.write(f"**What they said:**\n{ref['what_they_said']}\n\n")
                out.write(f"**What it means:**\n{ref['what_it_means']}\n\n")
                out.write(f"**Nate's take:**\n{ref['nate_interpretation']}\n\n")

                post_text = fmt_post(ref["linkedin_post"])
                out.write("**LinkedIn post draft:**\n\n")
                for para in post_text.split("\n\n"):
                    out.write(f"> {para}\n>\n")
                out.write("\n")

        out.write("---\n\n*End of report*\n")

    print(f"Written → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
