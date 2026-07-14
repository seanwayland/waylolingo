#!/usr/bin/env python3
"""Split conversation lessons into beginner and intermediate sets.

This uses a lightweight lexical complexity score so the split is deterministic
and easy to tune without model dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

WORD_RE = re.compile(r"[A-Za-z']+")


def turn_score(text: str) -> float:
    words = WORD_RE.findall(text)
    if not words:
        return 0.0

    token_count = len(words)
    long_words = sum(1 for w in words if len(w) >= 8)
    avg_word_len = sum(len(w) for w in words) / token_count
    punctuation_bonus = 0.3 if any(ch in text for ch in [",", ";", ":"]) else 0.0
    question_bonus = 0.2 if "?" in text else 0.0

    return token_count + (0.8 * long_words) + (0.5 * avg_word_len) + punctuation_bonus + question_bonus


def conversation_score(conversation: dict) -> float:
    turns = conversation.get("turns", [])
    if not turns:
        return 0.0
    return sum(turn_score(str(turn.get("english", ""))) for turn in turns) / len(turns)


def with_metadata(conversations: list[dict], level: str, source_file: Path) -> dict:
    return {
        "level": level,
        "source_file": str(source_file),
        "count": len(conversations),
        "turns_per_conversation": 10,
        "conversations": conversations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Split lessons JSON by difficulty")
    parser.add_argument("--input", required=True, help="Input conversations JSON path")
    parser.add_argument("--beginner-output", required=True, help="Beginner output JSON path")
    parser.add_argument("--intermediate-output", required=True, help="Intermediate output JSON path")
    parser.add_argument("--beginner-count", type=int, default=50, help="Number of beginner conversations")
    parser.add_argument("--intermediate-count", type=int, default=50, help="Number of intermediate conversations")
    args = parser.parse_args()

    input_path = Path(args.input)
    beginner_output = Path(args.beginner_output)
    intermediate_output = Path(args.intermediate_output)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    conversations = data.get("conversations", [])
    if not conversations:
        raise ValueError("No conversations found in input file")

    scored = sorted(conversations, key=conversation_score)

    beginner = scored[: args.beginner_count]
    intermediate_start = args.beginner_count
    intermediate_end = intermediate_start + args.intermediate_count
    intermediate = scored[intermediate_start:intermediate_end]

    if len(beginner) < args.beginner_count or len(intermediate) < args.intermediate_count:
        raise ValueError(
            "Not enough conversations for requested split: "
            f"have={len(scored)}, beginner={args.beginner_count}, intermediate={args.intermediate_count}"
        )

    beginner_output.parent.mkdir(parents=True, exist_ok=True)
    intermediate_output.parent.mkdir(parents=True, exist_ok=True)

    beginner_output.write_text(
        json.dumps(with_metadata(beginner, "beginner", input_path), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    intermediate_output.write_text(
        json.dumps(with_metadata(intermediate, "intermediate", input_path), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote beginner set: {beginner_output} ({len(beginner)} conversations)")
    print(f"Wrote intermediate set: {intermediate_output} ({len(intermediate)} conversations)")


if __name__ == "__main__":
    main()
