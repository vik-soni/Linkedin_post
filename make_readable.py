#!/usr/bin/env python3
"""
Convert wide markdown table files to grouped, human-readable card format.

Usage:
    python make_readable.py                  # converts output.md
    python make_readable.py research         # converts research_output.md
"""

import re
import sys
from collections import OrderedDict

_PIPE = "\x00PIPE\x00"   # temp placeholder for escaped \|


# ── Shared helpers ────────────────────────────────────────────────────────────

def parse_row(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith("|"):
        return None
    line = line.replace("\\|", _PIPE)
    parts = [p.replace(_PIPE, "|").strip() for p in line.split("|")]
    return parts[1:-1] if len(parts) > 2 else None


def is_separator(cells: list[str]) -> bool:
    return all(re.match(r"^-+$", c.replace(" ", "")) for c in cells if c)


def extract_link(cell: str) -> tuple[str, str]:
    m = re.match(r'\[(.+?)\]\((.+?)\)', cell, re.DOTALL)
    if m:
        title = m.group(1)
        title = title.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')
        return title, m.group(2)
    return cell, ""


def fmt_post(raw: str) -> str:
    """Restore paragraph breaks from the double-space collapse used in table cells."""
    paragraphs = [p.strip() for p in raw.split("  ") if p.strip()]
    return "\n\n".join(paragraphs)


def write_post_blockquote(out, post_text: str) -> None:
    out.write("**LinkedIn post draft:**\n\n")
    for para in fmt_post(post_text).split("\n\n"):
        out.write(f"> {para}\n>\n")
    out.write("\n")


# ── output.md converter ───────────────────────────────────────────────────────
# Columns: Status | Video Title | Date | Reference | Who Said It |
#          What They Said | What It Means | Nate's Interpretation | LinkedIn Post Draft

def convert_output(input_file: str = "output.md", output_file: str = "output_readable.md") -> None:
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rows = []
    for line in lines:
        cells = parse_row(line)
        if not cells or len(cells) < 9:
            continue
        if is_separator(cells) or cells[1].strip() == "Video Title":
            continue
        rows.append(cells)

    videos: OrderedDict = OrderedDict()
    for cells in rows:
        status         = cells[0]
        title, url     = extract_link(cells[1])
        date           = cells[2]
        reference      = cells[3]
        who_said_it    = cells[4]
        what_they_said = cells[5]
        what_it_means  = cells[6]
        nate_interp    = cells[7]
        linkedin_post  = cells[8]

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

    with open(output_file, "w", encoding="utf-8") as out:
        out.write("# NateBJones Research — Readable View\n\n")
        out.write(f"_{len(videos)} videos · {total_refs} references_\n\n")

        for video in videos.values():
            out.write("---\n\n")
            ref_count = len(video["refs"])
            out.write(f"## [{video['title']}]({video['url']})\n\n")
            out.write(f"**Date:** {video['date']} &nbsp;|&nbsp; **{ref_count} reference{'s' if ref_count != 1 else ''}**\n\n")

            for i, ref in enumerate(video["refs"], 1):
                status = ref["status"] or "[ ]"
                out.write(f"### {status} {i}. {ref['reference']}\n\n")
                out.write(f"**Who:** {ref['who_said_it']}\n\n")
                out.write(f"**What they said:**\n{ref['what_they_said']}\n\n")
                out.write(f"**What it means:**\n{ref['what_it_means']}\n\n")
                out.write(f"**Nate's take:**\n{ref['nate_interpretation']}\n\n")
                write_post_blockquote(out, ref["linkedin_post"])

        out.write("---\n\n*End of report*\n")

    print(f"Written → {output_file}")


# ── research_output.md converter ─────────────────────────────────────────────
# Columns: Status | Theme | Source | Author | Date Published |
#          What They Said | What It Really Means | Short/Long Term Impact | LinkedIn Post Draft

def convert_research(input_file: str = "research_output.md", output_file: str = "research_readable.md") -> None:
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rows = []
    for line in lines:
        cells = parse_row(line)
        if not cells or len(cells) < 9:
            continue
        if is_separator(cells) or cells[1].strip() == "Theme":
            continue
        rows.append(cells)

    # Group by theme
    themes: OrderedDict = OrderedDict()
    for cells in rows:
        status        = cells[0]
        theme         = cells[1]
        source_title, source_url = extract_link(cells[2])
        author        = cells[3]
        date          = cells[4]
        what_said     = cells[5]
        what_means    = cells[6]
        impact_raw    = cells[7]
        linkedin_post = cells[8]

        # Split Short/Long term impact on the original | separator (was escaped as \|)
        if "|" in impact_raw:
            parts = impact_raw.split("|", 1)
            impact_short = parts[0].strip().removeprefix("Short:").strip()
            impact_long  = parts[1].strip().removeprefix("Long:").strip()
        else:
            impact_short = impact_raw.strip()
            impact_long  = ""

        if theme not in themes:
            themes[theme] = []
        themes[theme].append({
            "status":        status,
            "source_title":  source_title,
            "source_url":    source_url,
            "author":        author,
            "date":          date,
            "what_said":     what_said,
            "what_means":    what_means,
            "impact_short":  impact_short,
            "impact_long":   impact_long,
            "linkedin_post": linkedin_post,
        })

    total_entries = sum(len(v) for v in themes.values())
    print(f"Parsed: {len(themes)} theme(s), {total_entries} entries")

    with open(output_file, "w", encoding="utf-8") as out:
        out.write("# AI × Security × Psychology — Research Readable View\n\n")
        out.write(f"_{len(themes)} theme{'s' if len(themes) != 1 else ''} · {total_entries} entries_\n\n")

        for theme, entries in themes.items():
            out.write("---\n\n")
            out.write(f"# {theme}\n\n")

            for i, e in enumerate(entries, 1):
                status = e["status"] or "[ ]"
                out.write(f"## {status} {i}. [{e['source_title']}]({e['source_url']})\n\n")
                out.write(f"**Author:** {e['author']} &nbsp;|&nbsp; **Published:** {e['date']}\n\n")

                out.write(f"**What they said:**\n{e['what_said']}\n\n")
                out.write(f"**What it really means:**\n{e['what_means']}\n\n")

                if e["impact_short"]:
                    out.write(f"**Short-term impact:**\n{e['impact_short']}\n\n")
                if e["impact_long"]:
                    out.write(f"**Long-term impact:**\n{e['impact_long']}\n\n")

                write_post_blockquote(out, e["linkedin_post"])

        out.write("---\n\n*End of report*\n")

    print(f"Written → {output_file}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "output"
    if mode == "research":
        convert_research()
    else:
        convert_output()
