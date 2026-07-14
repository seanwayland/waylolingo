from fastapi.testclient import TestClient

from mandarin_translator import api
from mandarin_translator.api import app
from mandarin_translator.models import ConversationResponse, Sentence


client = TestClient(app)


def test_root_reports_backend() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["backend"] == "rot13"
    assert response.json()["app"] == "/app"
    assert response.json()["prompt_translate"] == "/prompt-translate"


def test_frontend_route_serves_html() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "WayloLingo Prompt Studio" in response.text


def test_translate_returns_structured_rot13_response() -> None:
    response = client.post(
        "/translate",
        json={"text": "What time is it?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversation": [
            {
                "language": "mandarin",
                "language_code": "zh-CN",
                "english": ["what", "time", "is", "it"],
                "phonetic": ["jung", "gvzr", "vf", "vg"],
                "symbols": ["jung", "gvzr", "vf", "vg"],
            }
        ]
    }


def test_translate_splits_multiple_sentences() -> None:
    response = client.post(
        "/translate",
        json={"text": "Hello there. General Kenobi!"},
    )

    assert response.status_code == 200
    assert response.json()["conversation"] == [
        {
            "language": "mandarin",
            "language_code": "zh-CN",
            "english": ["hello", "there"],
            "phonetic": ["uryyb", "gurer"],
            "symbols": ["uryyb", "gurer"],
        },
        {
            "language": "mandarin",
            "language_code": "zh-CN",
            "english": ["general", "kenobi"],
            "phonetic": ["trareny", "xrabov"],
            "symbols": ["trareny", "xrabov"],
        },
    ]


def test_translate_returns_503_when_translator_fails(monkeypatch) -> None:
    class FailingTranslator:
        backend_name = "ollama"

        def translate(self, text: str) -> ConversationResponse:
            raise api.TranslatorError("Ollama request failed")

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: FailingTranslator())

    response = client.post("/translate", json={"text": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Ollama request failed"}


def test_prompt_translate_returns_llm_response_and_translation() -> None:
    response = client.post(
        "/prompt-translate",
        json={"prompt": "How do I say piano in Mandarin?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prompt"] == "How do I say piano in Mandarin?"
    assert body["english_response"] == "How do I say piano in Mandarin? Target word(s): cvnab"
    assert body["translation"]["conversation"]
    assert body["translation"]["conversation"][0]["english"] == ["piano"]
    assert body["target_words"] == ["cvnab"]


def test_prompt_translate_uses_mandarin_phrase_from_english_response(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "ollama"

        def respond(self, prompt: str) -> str:
            return (
                'To say "let\'s go downstairs" in Mandarin, use "我们下去吧" '
                "(wǒmen xiàqù ba)."
            )

        def translate(self, text: str) -> ConversationResponse:
            return ConversationResponse(
                conversation=[
                    Sentence(
                        language="mandarin",
                        language_code="zh-CN",
                        english=["lets", "do", "downstairs"],
                        phonetic=["rang4", "wo3", "men5", "xia4", "qu4"],
                        symbols=["让", "我们", "下去"],
                    )
                ]
            )

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

    response = client.post(
        "/prompt-translate",
        json={"prompt": "Can you translate lets do downstairs to Mandarin?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translation"]["conversation"][0]["symbols"] == ["我们下去吧"]
    assert body["translation"]["conversation"][0]["phonetic"] == ["wo3", "men5", "xia4", "qu4", "ba5"]
    assert body["target_words"] == ["我们下去吧"]


def test_prompt_translate_normalizes_wrong_pinyin_in_english_response(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "ollama"

        def respond(self, prompt: str) -> str:
            return 'In Mandarin, you would say "钢琴" (pínggān) for "piano."'

        def translate(self, text: str) -> ConversationResponse:
            return ConversationResponse(
                conversation=[
                    Sentence(
                        language="mandarin",
                        language_code="zh-CN",
                        english=["piano"],
                        phonetic=["gang1", "qin2"],
                        symbols=["钢琴"],
                    )
                ]
            )

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

    response = client.post(
        "/prompt-translate",
        json={"prompt": "Please translate this to Mandarin: piano"},
    )

    assert response.status_code == 200
    body = response.json()
    assert '"钢琴" (gāng qín)' in body["english_response"]
    assert "pínggān" not in body["english_response"]


def test_prompt_translate_ollama_fast_path_skips_freeform_response(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "ollama"

        def respond(self, prompt: str) -> str:
            raise AssertionError("respond should not be called in fast path")

        def translate(self, text: str) -> ConversationResponse:
            assert text == "piano"
            return ConversationResponse(
                conversation=[
                    Sentence(
                        language="mandarin",
                        language_code="zh-CN",
                        english=["piano"],
                        phonetic=["gang1", "qin2"],
                        symbols=["钢", "琴"],
                    )
                ]
            )

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

    response = client.post(
        "/prompt-translate",
        json={"prompt": "How do I say piano in Mandarin?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["english_response"] == 'In Mandarin, you would say "钢琴" (gāng qín) for "piano".'