from __future__ import annotations

import json
import os
import re
from codecs import encode
from typing import Protocol

import httpx
from pypinyin import Style, pinyin

from .models import ConversationResponse, Sentence

SENTENCE_SPLIT_RE = re.compile(r"[^.!?]+[.!?]?", re.UNICODE)
WORD_RE = re.compile(r"[A-Za-z0-9']+")
PINYIN_TONE_RE = re.compile(r"[a-zv]+[1-5]")
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


class Rot13Translator:
    backend_name = "rot13"

    def translate(
        self,
        text: str,
        *,
        language: str = DEFAULT_LANGUAGE,
        language_code: str = DEFAULT_LANGUAGE_CODE,
    ) -> ConversationResponse:
        conversation = [
            self._translate_sentence(sentence, language=language, language_code=language_code)
            for sentence in self._split_sentences(text)
        ]
        return ConversationResponse(conversation=conversation)

    def _split_sentences(self, text: str) -> list[str]:
        return [match.group(0).strip() for match in SENTENCE_SPLIT_RE.finditer(text) if match.group(0).strip()]

    def _translate_sentence(self, sentence: str, *, language: str, language_code: str) -> Sentence:
        english_tokens = WORD_RE.findall(sentence.lower())
        transformed_tokens = [self._rot13_token(token) for token in english_tokens]
        return Sentence(
            language=language,
            language_code=language_code,
            english=english_tokens,
            phonetic=transformed_tokens,
            symbols=transformed_tokens,
        )

    def _rot13_token(self, token: str) -> str:
        return encode(token, "rot_13")

    def respond(self, prompt: str) -> str:
        # Deterministic fallback backend: echo prompt as the English response.
        return prompt.strip()


class OllamaTranslator:
    backend_name = "ollama"

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

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0,
                "top_p": 0.9,
            },
            "prompt": self._build_prompt(text=source_text, language=language, language_code=language_code),
        }
        try:
            response = self._client_or_default().post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TranslatorError(f"Ollama request failed: {exc}") from exc

        try:
            data = response.json()
            raw_content = data["response"]
        except (KeyError, json.JSONDecodeError, ValueError) as exc:
            raise TranslatorError("Ollama returned an invalid response envelope") from exc

        return self._parse_conversation_response(raw_content, source_text=source_text)

    def respond(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
            "prompt": (
                "You are a helpful assistant. Respond in natural English only. "
                "Do not include JSON, markdown, or role labels.\n\n"
                f"User prompt: {json.dumps(prompt)}"
            ),
        }
        try:
            response = self._client_or_default().post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            text = str(data.get("response", "")).strip()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise TranslatorError(f"Ollama request failed: {exc}") from exc

        if not text:
            raise TranslatorError("Ollama returned an empty response")
        return text

    def _client_or_default(self) -> httpx.Client:
        return self._client or httpx.Client()

    def _build_prompt(self, *, text: str, language: str, language_code: str) -> str:
        return (
            "You are a translation engine. Return one JSON object only with no markdown and no commentary. "
            "Translate the user input into the exact schema below. "
            "The response must be an object with a conversation key whose value is an array of sentence objects. "
            "Each sentence object must contain language, language_code, english, phonetic, and symbols. "
            "Use lowercase English word tokens in english. "
            "Use numbered pinyin syllables in phonetic, with no tone marks. "
            "Use simplified Chinese characters or character groups in symbols. "
            f"Set language to {json.dumps(language)} and language_code to {json.dumps(language_code)} for every sentence. "
            "Do not include extra keys. Do not echo instructions.\n\n"
            "Schema example:\n"
            '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["what","time","is","it"],"phonetic":["xian4","zai4","ji3","dian3"],"symbols":["现","在","几","点"]}]}\n\n'
            f"User input (literal string): {json.dumps(text)}"
        )

    def _parse_conversation_response(self, raw_content: str, *, source_text: str) -> ConversationResponse:
        try:
            parsed = json.loads(raw_content)
            response = ConversationResponse.model_validate(parsed)
            return self._normalize_response(response, source_text=source_text)
        except (json.JSONDecodeError, ValueError):
            extracted = self._extract_first_json_object(raw_content)
            if extracted is None:
                raise TranslatorError("Ollama did not return valid translator JSON")

            try:
                parsed = json.loads(extracted)
                response = ConversationResponse.model_validate(parsed)
                return self._normalize_response(response, source_text=source_text)
            except (json.JSONDecodeError, ValueError) as exc:
                raise TranslatorError("Ollama did not return valid translator JSON") from exc

    def _normalize_response(self, response: ConversationResponse, *, source_text: str) -> ConversationResponse:
        normalized_sentences: list[Sentence] = []
        source_english_tokens = [token.lower() for token in WORD_RE.findall(source_text)]

        for sentence in response.conversation:
            symbols = CJK_TOKEN_RE.findall(" ".join(sentence.symbols))

            english = [token.lower() for token in WORD_RE.findall(" ".join(sentence.english))]
            if source_english_tokens:
                # Keep source tokens stable for single-turn requests.
                english = source_english_tokens

            phonetic = self._symbols_to_pinyin(symbols)
            if not phonetic:
                phonetic = PINYIN_TONE_RE.findall(" ".join(sentence.phonetic).lower().replace("u:", "v").replace("ü", "v"))

            if not english:
                raise TranslatorError("Model returned empty or invalid english tokens")
            if not phonetic:
                raise TranslatorError("Model returned empty or invalid phonetic tokens")
            if not symbols:
                raise TranslatorError("Model returned empty or invalid symbol tokens")

            normalized_sentences.append(
                Sentence(
                    language=sentence.language,
                    language_code=sentence.language_code,
                    english=english,
                    phonetic=phonetic,
                    symbols=symbols,
                )
            )

        return ConversationResponse(conversation=normalized_sentences)

    def _symbols_to_pinyin(self, symbols: list[str]) -> list[str]:
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

    def _preprocess_user_text(self, text: str) -> str:
        extracted = extract_target_phrase_from_prompt(text)
        return extracted if extracted is not None else text.strip()

    def _extract_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for idx, ch in enumerate(text[start:], start=start):
            if in_string:
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
                    continue
                if ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]

        return None


def build_translator_from_env() -> Translator:
    backend = os.getenv("TRANSLATOR_BACKEND", "rot13").strip().lower()
    if backend == "rot13":
        return Rot13Translator()
    if backend == "ollama":
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
        return OllamaTranslator(model=model, base_url=base_url, timeout=timeout, keep_alive=keep_alive)
    raise TranslatorError(f"Unsupported translator backend: {backend}")