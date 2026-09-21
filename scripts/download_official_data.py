#!/usr/bin/env python3
"""Download the public men's basketball result and play-by-play feeds.

The official results API returns a zlib stream represented as Latin-1 code
points inside a UTF-8 response.  This script reverses that transport encoding
and saves ordinary UTF-8 JSON files.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import zlib
from pathlib import Path


API_ROOT = "https://back.results.asiangames2026.org"
ORIGIN = "https://results.asiangames2026.org"
EVENT_KEY = "M.TEAM5-------------"
TARGET_ORGS = {"CHN", "JPN", "KOR", "IRI"}


def fetch_json(path: str):
    request = urllib.request.Request(
        API_ROOT + path,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/",
            "User-Agent": "ag2026-basketball-analysis/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()

    compressed = body.decode("utf-8").encode("latin-1")
    return json.loads(zlib.decompress(compressed).decode("utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw", help="Raw-data directory")
    parser.add_argument(
        "--target-only",
        action="store_true",
        help="Download only games involving China, Japan, Korea or Iran",
    )
    args = parser.parse_args()

    output = Path(args.output)
    schedule_path = f"/s/AG2026/en/BKB/schedule/event/{EVENT_KEY}"
    schedule = fetch_json(schedule_path)
    write_json(output / "event_schedule.json", schedule)

    games = [row for row in schedule if not row.get("IsPhase") and row.get("Key")]
    if args.target_only:
        games = [row for row in games if TARGET_ORGS.intersection(row.get("Orgs", []))]

    for index, game in enumerate(games, start=1):
        key = game["Key"]
        result = fetch_json(f"/s/AG2026/en/BKB/results/{key}")
        actions = fetch_json(f"/s/AG2026/en/BKB/actions/Total/{key}")
        write_json(output / "games" / f"{key}.result.json", result)
        write_json(output / "games" / f"{key}.actions.json", actions)
        print(f"[{index:02d}/{len(games):02d}] {key}")
        time.sleep(0.1)


if __name__ == "__main__":
    main()
