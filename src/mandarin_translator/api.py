from functools import lru_cache
import re

from fastapi import FastAPI, HTTPException
from pypinyin import Style, pinyin

from .models import ConversationResponse, PromptTranslateRequest, PromptTranslateResponse, TranslateRequest
from .translator import TranslatorError, build_translator_from_env, extract_target_phrase_from_prompt

app = FastAPI(title="Mandarin Translator Prototype", version="0.1.0")

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


@lru_cache
def get_translator():
    return build_translator_from_env()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Mandarin Translator Prototype",
        "backend": get_translator().backend_name,
        "docs": "/docs",
        "health": "/health",
        "translate": "/translate",
        "prompt_translate": "/prompt-translate",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": get_translator().backend_name}


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
        english_response = translator.respond(request.prompt)
        translation_source = extract_target_phrase_from_prompt(request.prompt) or english_response
        translation = translator.translate(translation_source)

        mandarin_phrase = _extract_longest_cjk_phrase(english_response)
        if mandarin_phrase and translation.conversation:
            first_sentence = translation.conversation[0]
            first_sentence.symbols = [mandarin_phrase]
            mandarin_phonetic = _phrase_to_pinyin_tokens(mandarin_phrase)
            if mandarin_phonetic:
                first_sentence.phonetic = mandarin_phonetic

        target_words = [symbol for sentence in translation.conversation for symbol in sentence.symbols]
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