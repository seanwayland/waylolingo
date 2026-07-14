from functools import lru_cache
from pathlib import Path
import json
import random
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pypinyin import Style, pinyin

from .models import ConversationResponse, PromptTranslateRequest, PromptTranslateResponse, Sentence, TranslateRequest
from .translator import TranslatorError, build_translator_from_env, extract_target_phrase_from_prompt

app = FastAPI(title="Mandarin Translator Prototype", version="0.1.0")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = PROJECT_ROOT / "data" / "audio"
FRONTEND_FILE = PROJECT_ROOT / "src" / "mandarin_translator" / "static" / "app.html"

LESSON_FILES: dict[str, Path] = {
    "super_easy": PROJECT_ROOT / "data" / "lessons" / "super_easy_100x10_en.json",
    "beginner": PROJECT_ROOT / "data" / "lessons" / "dailydialog_beginner_50x10_en.json",
    "intermediate": PROJECT_ROOT / "data" / "lessons" / "dailydialog_intermediate_50x10_en.json",
    "intermediate_nouns": PROJECT_ROOT / "data" / "lessons" / "intermediate_nouns_100x10_en.json",
}

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

CJK_PHRASE_RE = re.compile(r"[\u3400-\u9FFF]+")


def _extract_longest_cjk_phrase(text: str) -> str | None:
    phrases = CJK_PHRASE_RE.findall(text)
    if not phrases:
        return None
    return max(phrases, key=len)


def _phrase_to_pinyin_tokens(phrase: str) -> list[str]:
    converted = pinyin(
        phrase,
        style=Style.TONE3,
        heteronym=False,
        neutral_tone_with_five=True,
        strict=False,
        errors="ignore",
    )
    return [item[0].lower().replace("u:", "v").replace("ü", "v") for item in converted if item and item[0]]


def _phrase_to_pinyin_tone_marks(phrase: str) -> str:
    converted = pinyin(
        phrase,
        style=Style.TONE,
        heteronym=False,
        strict=False,
        errors="ignore",
    )
    return " ".join(item[0].lower() for item in converted if item and item[0])


def _normalize_phrase_pinyin_in_english_response(text: str, phrase: str, pinyin_display: str) -> str:
    normalized = text
    phrase_variants = [f'"{phrase}"', f'“{phrase}”', phrase]

    for variant in phrase_variants:
        pattern = re.compile(rf"({re.escape(variant)}\s*\()([^)]*)(\))")
        updated, count = pattern.subn(rf"\1{pinyin_display}\3", normalized, count=1)
        if count:
            return updated

    if phrase in normalized:
        return f"{normalized}\n\nStandard pinyin: {phrase} ({pinyin_display})."

    return normalized


def _build_conversation_from_cjk_phrases(phrases: list[str]) -> ConversationResponse | None:
    conversation: list[Sentence] = []
    for phrase in phrases:
        normalized = phrase.strip()
        if not normalized:
            continue
        phonetic = _phrase_to_pinyin_tokens(normalized)
        if not phonetic:
            continue
        conversation.append(
            Sentence(
                language="mandarin",
                language_code="zh-CN",
                english=[],
                phonetic=phonetic,
                symbols=[normalized],
            )
        )

    if not conversation:
        return None
    return ConversationResponse(conversation=conversation)


@lru_cache
def get_translator():
    return build_translator_from_env()


@lru_cache
def _load_lesson_conversations(level: str) -> list[dict]:
    lesson_path = LESSON_FILES.get(level)
    if lesson_path is None:
        raise ValueError(f"Unsupported lesson level: {level}")
    if not lesson_path.exists():
        raise ValueError(f"Lesson file missing for level '{level}': {lesson_path}")

    payload = json.loads(lesson_path.read_text(encoding="utf-8"))
    conversations = payload.get("conversations", [])
    if not conversations:
        raise ValueError(f"No conversations found in lesson file: {lesson_path}")
    return conversations


def _build_lesson_prompt(conversation: dict, *, max_turns: int) -> tuple[str, int, int]:
    all_turns = conversation.get("turns", [])
    turns = all_turns[:max_turns]
    rendered_turns = "\n".join(
        f"{turn.get('turn', idx + 1)} {turn.get('speaker', 'A')}: {turn.get('english', '').strip()}"
        for idx, turn in enumerate(turns)
        if str(turn.get("english", "")).strip()
    )

    prompt = (
        "Translate this conversation into Mandarin Chinese and provide helpful pinyin-ready wording. "
        "Keep your response concise and learner-friendly.\n\n"
        f"Conversation:\n{rendered_turns}"
    )
    return prompt, len(turns), len(all_turns)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Mandarin Translator Prototype",
        "backend": get_translator().backend_name,
        "app": "/app",
        "docs": "/docs",
        "health": "/health",
        "translate": "/translate",
        "prompt_translate": "/prompt-translate",
        "lesson_random": "/lesson-random",
    }


@app.get("/app")
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": get_translator().backend_name}


@app.get("/lesson-random")
def lesson_random(level: str = "beginner", max_turns: int = 4) -> dict:
    try:
        conversations = _load_lesson_conversations(level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if max_turns < 1 or max_turns > 10:
        raise HTTPException(status_code=400, detail="max_turns must be between 1 and 10")

    selected = random.choice(conversations)
    prompt, prompt_turn_count, source_turn_count = _build_lesson_prompt(selected, max_turns=max_turns)
    return {
        "level": level,
        "conversation_id": selected.get("conversation_id", ""),
        "turn_count": prompt_turn_count,
        "source_turn_count": source_turn_count,
        "prompt": prompt,
        "turns": selected.get("turns", [])[:max_turns],
    }


@app.post("/translate", response_model=ConversationResponse)
def translate(request: TranslateRequest) -> ConversationResponse:
    try:
        return get_translator().translate(request.text)
    except TranslatorError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/prompt-translate", response_model=PromptTranslateResponse)
def prompt_translate(request: PromptTranslateRequest) -> PromptTranslateResponse:
    try:
        translator = get_translator()
        target_phrase = extract_target_phrase_from_prompt(request.prompt)

        # Fast path: for common "How do I say ... in Mandarin?" prompts,
        # skip the separate free-form response call to reduce end-to-end latency.
        if target_phrase:
            try:
                translation = translator.translate(target_phrase)
            except TranslatorError:
                translation = ConversationResponse(
                    conversation=[
                        Sentence(
                            language="mandarin",
                            language_code="zh-CN",
                            english=[target_phrase],
                            phonetic=[],
                            symbols=[],
                        )
                    ]
                )
            english_response = ""
        else:
            english_response = translator.respond(request.prompt)
            translation = None

            # For lesson prompts, a single LLM call is often enough if Chinese text
            # appears in the response. Build structured pinyin data locally.
            cjk_phrases = CJK_PHRASE_RE.findall(english_response)
            if cjk_phrases:
                translation = _build_conversation_from_cjk_phrases(cjk_phrases)

            if translation is None:
                translation_source = target_phrase or english_response
                try:
                    translation = translator.translate(translation_source)
                except TranslatorError:
                    translation = _build_conversation_from_cjk_phrases(cjk_phrases)
                    if translation is None:
                        translation = ConversationResponse(
                            conversation=[
                                Sentence(
                                    language="mandarin",
                                    language_code="zh-CN",
                                    english=[],
                                    phonetic=[],
                                    symbols=[],
                                )
                            ]
                        )

        mandarin_phrase = _extract_longest_cjk_phrase(english_response)
        if not mandarin_phrase and translation.conversation:
            mandarin_phrase = "".join(translation.conversation[0].symbols)
        if mandarin_phrase and translation.conversation:
            first_sentence = translation.conversation[0]
            first_sentence.symbols = [mandarin_phrase]
            mandarin_phonetic = _phrase_to_pinyin_tokens(mandarin_phrase)
            if mandarin_phonetic:
                first_sentence.phonetic = mandarin_phonetic
            mandarin_display = _phrase_to_pinyin_tone_marks(mandarin_phrase)
            if mandarin_display:
                if english_response:
                    english_response = _normalize_phrase_pinyin_in_english_response(
                        english_response,
                        mandarin_phrase,
                        mandarin_display,
                    )
                elif target_phrase:
                    english_response = (
                        f'In Mandarin, you would say "{mandarin_phrase}" '
                        f'({mandarin_display}) for "{target_phrase}".'
                    )

        if not english_response:
            english_response = request.prompt

        target_words = [symbol for sentence in translation.conversation for symbol in sentence.symbols]
        if not target_words and target_phrase:
            english_response = f'{english_response} Target phrase: {target_phrase}'.strip()
        if target_words and not any(word in english_response for word in target_words):
            english_response = f"{english_response} Target word(s): {' '.join(target_words)}"
        return PromptTranslateResponse(
            prompt=request.prompt,
            english_response=english_response,
            translation=translation,
            target_words=target_words,
        )
    except TranslatorError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc