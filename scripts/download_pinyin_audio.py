#!/usr/bin/env python3
"""Download pinyin syllable audio files from AllSet Learning PronWiki.

This script reads data/pinyin_syllables.csv and tries to download every
non-empty tone token (e.g. ma1, ma2, ...). It skips files that already exist
unless --force is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://resources.allsetlearning.com/pronwiki/resources/pinyin-audio"
TONE_COLUMNS = ["tone1", "tone2", "tone3", "tone4", "tone5"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download pinyin syllable audio set")
    parser.add_argument(
        "--csv",
        default="data/pinyin_syllables.csv",
        help="Path to pinyin syllables CSV",
    )
    parser.add_argument(
        "--output-dir",
        default="data/audio/pinyin_full",
        help="Directory to save MP3 files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of tokens to attempt (0 means no limit)",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=75,
        help="Delay between requests in milliseconds",
    )
    return parser.parse_args()


def build_tokens(csv_path: Path) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in TONE_COLUMNS:
                token = (row.get(key) or "").strip().lower()
                if not token:
                    continue
                # PronWiki filenames use v for umlaut sounds, which matches repo CSV.
                token = token.replace("ü", "v")
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
    return tokens


def download_file(url: str, out_path: Path) -> bool:
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
        # Keep a small sanity threshold to avoid HTML error bodies.
        if len(data) < 1024:
            return False
        out_path.write_bytes(data)
        return True
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError:
        return False


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    tokens = build_tokens(csv_path)
    if args.limit and args.limit > 0:
        tokens = tokens[: args.limit]

    attempted = 0
    downloaded = 0
    skipped_existing = 0
    missing = 0
    missing_tokens: list[str] = []

    for token in tokens:
        attempted += 1
        out_path = out_dir / f"{token}.mp3"

        if out_path.exists() and not args.force:
            skipped_existing += 1
            continue

        url = f"{BASE_URL}/{token}.mp3"
        ok = download_file(url, out_path)
        if ok:
            downloaded += 1
        else:
            missing += 1
            missing_tokens.append(token)
            out_path.unlink(missing_ok=True)

        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000)

    report = {
        "source": BASE_URL,
        "csv": str(csv_path),
        "output_dir": str(out_dir),
        "attempted": attempted,
        "downloaded": downloaded,
        "skipped_existing": skipped_existing,
        "missing": missing,
        "missing_tokens": missing_tokens,
    }

    report_path = out_dir / "download_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Attempted: {attempted}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Missing: {missing}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
