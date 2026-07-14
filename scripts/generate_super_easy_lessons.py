#!/usr/bin/env python3
"""Generate a super-easy English conversation dataset.

Output schema matches the lesson JSON files used in this repository.
"""

from __future__ import annotations

import json
from pathlib import Path


def make_conversation(conversation_id: str, turns_text: list[str]) -> dict:
    turns = []
    for idx, text in enumerate(turns_text):
        turns.append(
            {
                "turn": idx + 1,
                "speaker": "A" if idx % 2 == 0 else "B",
                "english": text,
            }
        )

    return {
        "conversation_id": conversation_id,
        "source": "generated_super_easy",
        "language": "en",
        "turn_count": 10,
        "turns": turns,
    }


def build_templates() -> list[list[str]]:
    return [
        [
            "Hi.",
            "Hi.",
            "How are you?",
            "I am good.",
            "Are you okay?",
            "Yes, I am okay.",
            "Great.",
            "Great.",
            "See you.",
            "See you.",
        ],
        [
            "Good morning.",
            "Good morning.",
            "Did you sleep well?",
            "Yes, very well.",
            "Are you ready?",
            "Yes, I am ready.",
            "Lets go.",
            "Okay, lets go.",
            "Have a nice day.",
            "You too.",
        ],
        [
            "Hello.",
            "Hello.",
            "What is your name?",
            "My name is Sam.",
            "Nice to meet you.",
            "Nice to meet you too.",
            "Are you new here?",
            "Yes, I am new.",
            "Welcome.",
            "Thank you.",
        ],
        [
            "Do you want water?",
            "Yes, please.",
            "Cold or warm?",
            "Warm water, please.",
            "Here you go.",
            "Thank you.",
            "Do you need more?",
            "No, I am fine.",
            "Okay.",
            "Thanks again.",
        ],
        [
            "Are you hungry?",
            "Yes, a little.",
            "Lets eat now.",
            "Good idea.",
            "Rice or noodles?",
            "Rice, please.",
            "Do you want tea?",
            "Yes, please.",
            "Enjoy your meal.",
            "Thank you.",
        ],
        [
            "Can we go now?",
            "Yes, we can.",
            "Where are we going?",
            "To the store.",
            "Is it far?",
            "No, it is close.",
            "Lets walk.",
            "Okay, lets walk.",
            "We are here.",
            "Great.",
        ],
        [
            "What time is it?",
            "It is seven.",
            "Are we late?",
            "No, we are early.",
            "Class starts at eight.",
            "Okay, good.",
            "Lets wait here.",
            "Sure.",
            "Do you have a pen?",
            "Yes, here.",
        ],
        [
            "Can you help me?",
            "Yes, of course.",
            "I lost my phone.",
            "Where did you see it?",
            "On the table.",
            "Lets check now.",
            "I found it.",
            "Great news.",
            "Thank you so much.",
            "You are welcome.",
        ],
        [
            "Are you tired?",
            "Yes, very tired.",
            "You should rest.",
            "I will rest now.",
            "Do you need tea?",
            "No, just water.",
            "Okay, here is water.",
            "Thank you.",
            "Sleep well.",
            "I will.",
        ],
        [
            "Do you like music?",
            "Yes, I do.",
            "What music do you like?",
            "I like pop music.",
            "Do you sing?",
            "A little.",
            "Lets sing together.",
            "Okay, sounds fun.",
            "That was nice.",
            "Yes, very nice.",
        ],
    ]


def generate_dataset(target_count: int = 100) -> dict:
    templates = build_templates()
    conversations = []

    for idx in range(target_count):
        template = templates[idx % len(templates)]
        conv_id = f"super-easy-{idx + 1:03d}"
        conversations.append(make_conversation(conv_id, template))

    return {
        "level": "super_easy",
        "source": "generated",
        "count": len(conversations),
        "turns_per_conversation": 10,
        "notes": "Generated simple lesson dialogs with very short everyday phrases.",
        "conversations": conversations,
    }


def main() -> None:
    out_path = Path("data/lessons/super_easy_100x10_en.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = generate_dataset(target_count=100)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {payload['count']} conversations to {out_path}")


if __name__ == "__main__":
    main()
