#!/usr/bin/env python3
"""
Fetch the first 3 video IDs from @NateBJones and print ALL available
transcript types (manual, auto-generated, every language variant).
"""

import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

ytt = YouTubeTranscriptApi()

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_HANDLE  = "NateBJones"


def get_first_n_videos(n: int = 3) -> list:
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    channel_resp = youtube.channels().list(
        part="id", forHandle=CHANNEL_HANDLE
    ).execute()
    channel_id = channel_resp["items"][0]["id"]
    print(f"Channel ID : {channel_id}\n")

    search_resp = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        type="video",
        order="date",
        maxResults=n,
    ).execute()

    videos = []
    for item in search_resp["items"]:
        videos.append({
            "video_id": item["id"]["videoId"],
            "title":    item["snippet"]["title"],
            "date":     item["snippet"]["publishedAt"][:10],
        })
    return videos


def main() -> None:
    videos = get_first_n_videos(3)

    for video in videos:
        vid_id = video["video_id"]
        print("=" * 70)
        print(f"Title    : {video['title']}")
        print(f"Date     : {video['date']}")
        print(f"Video ID : {vid_id}")
        print(f"URL      : https://youtube.com/watch?v={vid_id}")
        print()

        try:
            transcript_list = ytt.list(vid_id)

            print("--- Raw TranscriptList object ---")
            print(repr(transcript_list))
            print()

            print("--- All available transcripts (iterated) ---")
            for t in transcript_list:
                print(
                    f"  video_id={t.video_id}"
                    f"  language={t.language!r}"
                    f"  language_code={t.language_code!r}"
                    f"  is_generated={t.is_generated}"
                    f"  translation_languages={t.translation_languages[:3]}{'...' if len(t.translation_languages) > 3 else ''}"
                )
            print()

            print("--- Manual transcripts (find_manually_created_transcript) ---")
            try:
                all_codes = [t.language_code for t in ytt.list(vid_id)]
                manual = transcript_list.find_manually_created_transcript(all_codes)
                print(f"  Found: [{manual.language_code}] {manual.language}")
            except Exception as e:
                print(f"  (none found: {e})")

            print("--- Auto-generated transcripts (find_generated_transcript) ---")
            try:
                all_codes = [t.language_code for t in ytt.list(vid_id)]
                generated = transcript_list.find_generated_transcript(all_codes)
                print(f"  Found: [{generated.language_code}] {generated.language}")
            except Exception as e:
                print(f"  (none found: {e})")

        except Exception as exc:
            print(f"  ERROR: {exc}")

        print()


if __name__ == "__main__":
    main()
