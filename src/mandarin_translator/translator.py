from __future__ import annotations

import json
import os
import re
from typing import Protocol

import httpx
from pypinyin import Style, pinyin

from .models import ConversationResponse, Sentence

SENTENCE_SPLIT_RE = re.compile(r"[^.!?]+[.!?]?", re.UNICODE)
WORD_RE = re.compile(r"[A-Za-z0-9']+")
CJK_TOKEN_RE = re.compile(r"[\u3400-\u9FFF]+")

DEFAULT_LANGUAGE = "mandarin"
DEFAULT_LANGUAGE_CODE = "zh-CN"
HOW_DO_I_SAY_RE = re.compile(r"^how\s+do\s+i\s+say\s+(.+?)\s+in\s+(mandarin|chinese)\??$", re.IGNORECASE)


def extract_target_phrase_from_prompt(text: str) -> str | None:
    stripped = text.strip()
    match = HOW_DO_I_SAY_RE.match(stripped)
    if not match:
        return None
    return match.group(1).strip(" \"'")


class TranslatorError(RuntimeError):
    pass


def _symbols_to_pinyin(symbols: list[str]) -> list[str]:
    if not symbols:
        return []

    joined = "".join(symbols)
    py = pinyin(
        joined,
        style=Style.TONE3,
        heteronym=False,
        neutral_tone_with_five=True,
        strict=False,
        errors="ignore",
    )
    return [item[0].lower().replace("u:", "v").replace("ü", "v") for item in py if item and item[0]]


class Translator(Protocol):
    backend_name: str

    def translate(
        self,
        text: str,
        *,
        language: str = DEFAULT_LANGUAGE,
        language_code: str = DEFAULT_LANGUAGE_CODE,
    ) -> ConversationResponse: ...

    def respond(self, prompt: str) -> str: ...


class TranslateGemmaTranslator:
    backend_name = "translategemma"

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 60.0,
        keep_alive: str = "30m",
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._client = client

    def translate(
        self,
        text: str,
        *,
        language: str = DEFAULT_LANGUAGE,
        language_code: str = DEFAULT_LANGUAGE_CODE,
    ) -> ConversationResponse:
        source_text = self._preprocess_user_text(text)
        sentences = self._split_sentences(source_text) or [source_text]

        conversation = [
            self._translate_sentence(sentence, language=language, language_code=language_code)
            for sentence in sentences
        ]
        return ConversationResponse(conversation=conversation)

    def respond(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "You are a helpful assistant. Respond in natural English only. "
                        "Do not include JSON, markdown, or role labels.\n\n"
                        f"User prompt: {prompt}"
                    ),
                }
            ],
        }
        try:
            response = self._client_or_default().post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            text = str(data.get("message", {}).get("content", "")).strip()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise TranslatorError(f"TranslateGemma request failed: {exc}") from exc

        if not text:
            raise TranslatorError("TranslateGemma returned an empty response")
        return text

    def _translate_sentence(self, sentence: str, *, language: str, language_code: str) -> Sentence:
        english = [token.lower() for token in WORD_RE.findall(sentence)]
        symbols = CJK_TOKEN_RE.findall(self._translate_to_mandarin(sentence))
        phonetic = _symbols_to_pinyin(symbols)

        if not english:
            raise TranslatorError("Source sentence contained no English tokens")
        if not symbols:
            raise TranslatorError("TranslateGemma did not return Mandarin characters")

        return Sentence(
            language=language,
            language_code=language_code,
            english=english,
            phonetic=phonetic,
            symbols=symbols,
        )

    def _translate_to_mandarin(self, sentence: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0,
                "top_p": 0.9,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional English (en) to Mandarin Chinese (zh-CN) translator. "
                        "Your goal is to accurately convey the meaning and nuances of the original "
                        "English text while adhering to Mandarin Chinese grammar, vocabulary, and "
                        "cultural sensitivities."
                    ),
                },
                {"role": "user", "content": sentence},
            ],
        }
        try:
            response = self._client_or_default().post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("message", {}).get("content", ""))
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise TranslatorError(f"TranslateGemma request failed: {exc}") from exc

    def _client_or_default(self) -> httpx.Client:
        return self._client or httpx.Client()

    def _split_sentences(self, text: str) -> list[str]:
        return [match.group(0).strip() for match in SENTENCE_SPLIT_RE.finditer(text) if match.group(0).strip()]

    def _preprocess_user_text(self, text: str) -> str:
        extracted = extract_target_phrase_from_prompt(text)
        return extracted if extracted is not None else text.strip()


def build_translator_from_env() -> Translator:
    backend = os.getenv("TRANSLATOR_BACKEND", "translategemma").strip().lower()
    if backend != "translategemma":
        raise TranslatorError(f"Unsupported translator backend: {backend}")

    model = os.getenv("OLLAMA_MODEL", "translategemma:4b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
    return TranslateGemmaTranslator(model=model, base_url=base_url, timeout=timeout, keep_alive=keep_alive)
