#!/usr/bin/env python3
"""
Pipeline: YouTube @NateBJones → Transcript → Claude extraction → Google Search → LinkedIn post
Appends new rows to output.md; skips videos already tracked by video ID.
"""

import os
import re
import json
import time
from dotenv import load_dotenv
import anthropic
import requests
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

_ytt = YouTubeTranscriptApi()

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID   = os.getenv("GOOGLE_CSE_ID")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY")

CLAUDE_MODEL   = "claude-sonnet-4-6"
CHANNEL_HANDLE = "NateBJones"
OUTPUT_FILE    = "output.md"
MAX_TRANSCRIPT = 15_000  # chars sent to Claude — keeps cost manageable

TABLE_HEADER = (
    "| Status | Video Title | Date | Reference | Who Said It "
    "| What They Said | What It Means | Nate's Interpretation | LinkedIn Post Draft |\n"
    "|--------|-------------|------|-----------|-------------|"
    "----------------|---------------|----------------------|---------------------|\n"
)


# ── output.md helpers ─────────────────────────────────────────────────────────

def init_output_file() -> None:
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("# NateBJones Video Research Tracker\n\n")
            f.write(TABLE_HEADER)


def load_processed_video_ids() -> set:
    """Extract video IDs already present in output.md so we can skip them."""
    if not os.path.exists(OUTPUT_FILE):
        return set()
    ids = set()
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            match = re.search(r"youtube\.com/watch\?v=([\w-]+)", line)
            if match:
                ids.add(match.group(1))
    return ids


def _cell(value: str) -> str:
    """Escape pipe characters and collapse newlines for a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def append_row(row: dict) -> None:
    line = (
        f"| {_cell(row.get('status', ''))} "
        f"| [{_cell(row['title'])}](https://youtube.com/watch?v={row['video_id']}) "
        f"| {_cell(row['date'])} "
        f"| {_cell(row['reference'])} "
        f"| {_cell(row['who_said_it'])} "
        f"| {_cell(row['what_they_said'])} "
        f"| {_cell(row['what_it_means'])} "
        f"| {_cell(row['nate_interpretation'])} "
        f"| {_cell(row['linkedin_post'])} |\n"
    )
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line)


# ── YouTube ───────────────────────────────────────────────────────────────────

def get_channel_id(youtube) -> str:
    resp = youtube.channels().list(part="id", forHandle=CHANNEL_HANDLE).execute()
    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel @{CHANNEL_HANDLE} not found.")
    return items[0]["id"]


def get_all_videos(youtube, channel_id: str) -> list:
    """Return all videos sorted newest → oldest via pagination."""
    videos = []
    next_page = None
    while True:
        resp = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            type="video",
            order="date",
            maxResults=50,
            pageToken=next_page,
        ).execute()
        for item in resp.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title":    item["snippet"]["title"],
                "date":     item["snippet"]["publishedAt"][:10],
            })
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
        time.sleep(0.3)
    return videos


def get_transcript(video_id: str) -> tuple[str | None, str]:
    time.sleep(2)  # avoid rate limiting
    try:
        transcript_list = _ytt.list(video_id)

        # Skip manual entirely — go straight to auto-generated
        try:
            transcript = transcript_list.find_generated_transcript(["en"])
        except NoTranscriptFound:
            # Fall back to any available language
            for t in transcript_list:
                transcript = t
                break
            else:
                return None, "no_transcript"

        text = " ".join(entry.text for entry in transcript.fetch())
        return text, "auto-generated"

    except TranscriptsDisabled:
        return None, "disabled"
    except Exception as e:
        return None, str(e)


# ── Claude ────────────────────────────────────────────────────────────────────

def extract_references(client: anthropic.Anthropic, title: str, transcript: str) -> list:
    prompt = f"""Video title: {title}

Transcript (timestamps in seconds):
{transcript[:MAX_TRANSCRIPT]}

Extract ALL named references — people, papers, companies, tools, and studies mentioned.

Return a raw JSON array (no markdown fences, no extra text) where each object has:
  "reference"          – the name of the person / paper / company / tool / study
  "who_said_it"        – who is being referenced (not the host)
  "what_they_said"     – direct quote or close paraphrase attributed to them
  "what_it_means"      – plain-English explanation of the concept or finding
  "nate_interpretation"– how Nate frames or interprets this reference
  "timestamp_context"  – approximate timestamp + one-sentence surrounding context

Return ONLY valid JSON. No explanation, no commentary."""

    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"    [warn] Could not parse references JSON — first 300 chars:\n{raw[:300]}")
        return []


def write_linkedin_post(
    client: anthropic.Anthropic,
    ref: dict,
    search_result: dict | None,
) -> str:
    source_ctx = ""
    if search_result:
        source_ctx = (
            f"\nSource: {search_result.get('title', '')} — "
            f"{search_result.get('snippet', '')}"
        )

    prompt = f"""Write a LinkedIn post (7 lines max) inspired by this reference:

Reference: {ref.get('reference', '')}
What they said / contributed: {ref.get('what_they_said', '')}
Why it matters: {ref.get('what_it_means', '')}{source_ctx}

Hard rules:
- Casual, thinking-out-loud tone — a practitioner who just discovered something interesting
- Do NOT mention Nate B Jones, any YouTube video, or that you watched/heard this somewhere
- Reference the person, paper, tool, or company directly and naturally
- No hashtags, no bullet points, no "excited to share", no corporate speak
- 7 lines maximum
- Sound human, not like a press release

Return only the post text — nothing else."""

    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


# ── Google Custom Search ──────────────────────────────────────────────────────

def search_reference(query: str) -> dict | None:
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": GOOGLE_API_KEY,
                "cx":  GOOGLE_CSE_ID,
                "q":   query,
                "num": 1,
            },
            timeout=10,
        )
        data = resp.json()
        if "items" in data:
            item = data["items"][0]
            return {
                "url":     item.get("link"),
                "title":   item.get("title"),
                "snippet": item.get("snippet"),
            }
    except Exception as exc:
        print(f"    [warn] Google search failed for '{query}': {exc}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_output_file()
    processed = load_processed_video_ids()
    print(f"Already processed: {len(processed)} video(s)\n")

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    client  = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    print(f"Resolving channel ID for @{CHANNEL_HANDLE}...")
    channel_id = get_channel_id(youtube)
    print(f"Channel ID: {channel_id}\n")

    print("Fetching full video list...")
    all_videos = get_all_videos(youtube, channel_id)
    new_videos = [v for v in all_videos if v["video_id"] not in processed]
    print(f"Total videos: {len(all_videos)}  |  New to process: {len(new_videos)}\n")

    for idx, video in enumerate(new_videos, 1):
        vid_id = video["video_id"]
        title  = video["title"]
        date   = video["date"]

        print(f"[{idx}/{len(new_videos)}] {title}  ({date})")

        transcript, transcript_status = get_transcript(vid_id)
        if not transcript:
            print(f"  → No transcript ({transcript_status}) — skipping\n")
            continue
        print(f"  → Transcript: {transcript_status}")

        print("  → Extracting references via Claude...")
        refs = extract_references(client, title, transcript)
        print(f"  → {len(refs)} reference(s) found")

        if not refs:
            print()
            continue

        for ref in refs:
            ref_name = ref.get("reference", "").strip()
            if not ref_name:
                continue
            print(f"    · {ref_name}")

            search_result = search_reference(ref_name)
            time.sleep(0.3)

            post = write_linkedin_post(client, ref, search_result)

            append_row({
                "status":              "",
                "video_id":            vid_id,
                "title":               title,
                "date":                date,
                "reference":           ref_name,
                "who_said_it":         ref.get("who_said_it", ""),
                "what_they_said":      ref.get("what_they_said", ""),
                "what_it_means":       ref.get("what_it_means", ""),
                "nate_interpretation": ref.get("nate_interpretation", ""),
                "linkedin_post":       post,
            })
            time.sleep(1)

        print()
        time.sleep(1)

    print(f"Done. Output → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
