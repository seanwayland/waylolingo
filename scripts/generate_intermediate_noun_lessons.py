#!/usr/bin/env python3
"""Generate an intermediate English conversation dataset with practical nouns."""

from __future__ import annotations

import json
from pathlib import Path

TARGET_NOUNS = [
    "hospital",
    "school",
    "work",
    "airport",
    "Mary",
    "Hong Kong",
    "bag",
    "car",
]

TEMPLATES = [
    [
        "Mary, are you going to the hospital after work?",
        "Yes, I need to visit the hospital at six.",
        "Do you want me to drive the car?",
        "Yes, please. My bag is heavy today.",
        "Can we stop by the school first?",
        "Sure, the school is on the same road.",
        "Great, then we can go straight to the hospital.",
        "After that, I will drop you home by car.",
        "Thanks, Mary. That helps a lot.",
        "No problem. Lets leave work now.",
    ],
    [
        "What time is your flight to Hong Kong?",
        "My Hong Kong flight leaves from the airport at nine.",
        "Did you pack your bag already?",
        "Yes, but I still need my work laptop.",
        "Is your car ready for the airport drive?",
        "Yes, I parked the car near school.",
        "Why near school?",
        "Mary borrowed it after work and returned it there.",
        "Okay, lets pick it up and go to the airport.",
        "Perfect. Please remind me to take my bag.",
    ],
    [
        "How is your first week at the new school?",
        "The school is busy, but I like it.",
        "Do you go to work by car?",
        "Most days, yes. My car saves time.",
        "Did Mary start work there too?",
        "Yes, Mary works in the school office.",
        "Can you meet after work at the hospital cafe?",
        "Sure, I need to visit a friend in the hospital.",
        "Bring your bag. I have your airport documents.",
        "Thanks, I need them for my Hong Kong trip.",
    ],
    [
        "Where is Mary today?",
        "Mary is at work near the airport.",
        "Is she driving the car or taking a bus?",
        "She took the car because her bag is full.",
        "What is in the bag?",
        "School papers and hospital forms.",
        "That sounds like a long day.",
        "Yes, she has school meetings after work.",
        "Will she still travel to Hong Kong tomorrow?",
        "Yes, she will go to the airport at dawn.",
    ],
    [
        "Can you help me plan tomorrow?",
        "Sure. I start work at eight.",
        "I need to take Mary to the hospital first.",
        "Then we can drive to school by car.",
        "After school, I need to go to the airport.",
        "Is this for your Hong Kong meeting?",
        "Yes, and my bag is not packed yet.",
        "Pack your bag tonight after work.",
        "Good idea. Can you call me at seven?",
        "Of course. I will call before school.",
    ],
    [
        "Did you see my car keys?",
        "They are next to your bag on the chair.",
        "Thanks. I must drive Mary to work.",
        "Then are you going to school?",
        "Yes, school starts in thirty minutes.",
        "Dont forget the hospital report.",
        "Right, it is in my bag.",
        "And your airport ticket to Hong Kong?",
        "Also in my bag. I checked twice.",
        "Great. Your car trip should be smooth.",
    ],
    [
        "Why are you late for work today?",
        "The road to school was blocked.",
        "Did you still reach the hospital on time?",
        "Yes, Mary waited with my bag at the gate.",
        "That was helpful.",
        "Very. Then we drove the car to the airport.",
        "Was the airport crowded?",
        "Yes, many flights to Hong Kong were boarding.",
        "Did you finish work after that?",
        "Yes, I returned to work at noon.",
    ],
    [
        "What should we buy before the trip?",
        "A new bag and a phone charger.",
        "For the Hong Kong flight from the airport?",
        "Yes, and snacks for Mary.",
        "Will Mary meet us after work?",
        "She will meet us near school at five.",
        "Should we take your car?",
        "Yes, my car has more space for bags.",
        "Do we need to stop by the hospital?",
        "Only briefly to pick up medicine.",
    ],
    [
        "How far is your work from the airport?",
        "About twenty minutes by car.",
        "And from work to school?",
        "Around ten minutes if traffic is light.",
        "Can Mary carry this bag for you?",
        "Yes, Mary said she can help.",
        "Do you still need to visit the hospital?",
        "Yes, before my Hong Kong flight.",
        "That is a tight schedule.",
        "It is, but I planned it after work.",
    ],
    [
        "Lets review the plan one more time.",
        "Okay. First, school at eight.",
        "Second, work meeting at ten.",
        "Third, hospital visit at noon.",
        "Fourth, pick up Mary and her bag.",
        "Fifth, drive the car to the airport.",
        "Sixth, check in for the Hong Kong flight.",
        "Seventh, call work before boarding.",
        "Great plan. Anything else?",
        "Yes, keep your bag and passport ready.",
    ],
]


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
        "source": "generated_intermediate_nouns",
        "language": "en",
        "turn_count": 10,
        "turns": turns,
    }


def generate_dataset(target_count: int = 100) -> dict:
    conversations = []
    for idx in range(target_count):
        template = TEMPLATES[idx % len(TEMPLATES)]
        conversations.append(make_conversation(f"intermediate-nouns-{idx + 1:03d}", template))

    return {
        "level": "intermediate",
        "source": "generated",
        "focus_nouns": TARGET_NOUNS,
        "count": len(conversations),
        "turns_per_conversation": 10,
        "notes": "Generated intermediate dialogs with practical travel, work, and daily-life nouns.",
        "conversations": conversations,
    }


def main() -> None:
    out_path = Path("data/lessons/intermediate_nouns_100x10_en.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = generate_dataset(target_count=100)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {payload['count']} conversations to {out_path}")


if __name__ == "__main__":
    main()
