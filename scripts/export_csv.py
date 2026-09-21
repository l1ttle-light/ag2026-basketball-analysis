#!/usr/bin/env python3
"""Export the prepared JSON tables as UTF-8 CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


TABLES = ["summary", "team_games", "key_games", "player_games", "games", "pbp"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/prepared.json")
    parser.add_argument("--output", default="analysis")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    for table in TABLES:
        rows = payload[table]
        if not rows:
            continue
        path = output / f"{table}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{path}: {len(rows)} rows")


if __name__ == "__main__":
    main()
