from fastapi.testclient import TestClient

from mandarin_translator import api
from mandarin_translator.api import app
from mandarin_translator.models import ConversationResponse, Sentence


client = TestClient(app)


def test_root_reports_backend() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["backend"] == "translategemma"
    assert response.json()["app"] == "/app"
    assert response.json()["prompt_translate"] == "/prompt-translate"
    assert response.json()["lesson_random"] == "/lesson-random"


def test_frontend_route_serves_html() -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "WayloLingo Prompt Studio" in response.text


def test_lesson_random_returns_prompt_and_turns() -> None:
    response = client.get("/lesson-random?level=beginner&max_turns=4")

    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "beginner"
    assert body["conversation_id"]
    assert body["turn_count"] == 4
    assert body["source_turn_count"] >= 4
    assert "Conversation:" in body["prompt"]
    assert isinstance(body["turns"], list)
    assert len(body["turns"]) == 4


def test_lesson_random_rejects_invalid_level() -> None:
    response = client.get("/lesson-random?level=unknown")

    assert response.status_code == 400
    assert "Unsupported lesson level" in response.json()["detail"]


def test_lesson_random_rejects_invalid_max_turns() -> None:
    response = client.get("/lesson-random?level=beginner&max_turns=0")

    assert response.status_code == 400
    assert "max_turns must be between 1 and 10" in response.json()["detail"]


def test_translate_returns_structured_translation(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

        def translate(self, text: str) -> ConversationResponse:
            assert text == "What time is it?"
            return ConversationResponse(
                conversation=[
                    Sentence(
                        language="mandarin",
                        language_code="zh-CN",
                        english=["what", "time", "is", "it"],
                        phonetic=["xian4", "zai4", "ji3", "dian3"],
                        symbols=["现在几点"],
                    )
                ]
            )

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

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
                "phonetic": ["xian4", "zai4", "ji3", "dian3"],
                "symbols": ["现在几点"],
            }
        ]
    }


def test_translate_returns_503_when_translator_fails(monkeypatch) -> None:
    class FailingTranslator:
        backend_name = "translategemma"

        def translate(self, text: str) -> ConversationResponse:
            raise api.TranslatorError("TranslateGemma request failed")

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: FailingTranslator())

    response = client.post("/translate", json={"text": "Hello"})

    assert response.status_code == 503
    assert response.json() == {"detail": "TranslateGemma request failed"}


def test_prompt_translate_returns_llm_response_and_translation(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

        def translate(self, text: str) -> ConversationResponse:
            assert text == "piano"
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
        json={"prompt": "How do I say piano in Mandarin?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prompt"] == "How do I say piano in Mandarin?"
    assert body["translation"]["conversation"]
    assert body["translation"]["conversation"][0]["english"] == ["piano"]
    assert body["target_words"] == ["钢琴"]


def test_prompt_translate_uses_mandarin_phrase_from_english_response(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

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
        backend_name = "translategemma"

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


def test_prompt_translate_fast_path_skips_freeform_response(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

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


def test_prompt_translate_builds_from_cjk_response_without_translate_call(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

        def respond(self, prompt: str) -> str:
            return 'Use "我们下去吧" (wǒmen xiàqù ba) and "现在走" (xiànzài zǒu).'

        def translate(self, text: str) -> ConversationResponse:
            raise AssertionError("translate should not be called when CJK is already present")

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

    response = client.post(
        "/prompt-translate",
        json={"prompt": "Translate this mini lesson to Mandarin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["translation"]["conversation"]
    assert body["translation"]["conversation"][0]["symbols"] == ["我们下去吧"]
    assert body["translation"]["conversation"][1]["symbols"] == ["现在走"]


def test_prompt_translate_falls_back_when_translate_fails(monkeypatch) -> None:
    class StubTranslator:
        backend_name = "translategemma"

        def respond(self, prompt: str) -> str:
            return "Here is a concise explanation without Chinese symbols."

        def translate(self, text: str) -> ConversationResponse:
            raise api.TranslatorError("TranslateGemma did not return valid translator JSON")

    api.get_translator.cache_clear()
    monkeypatch.setattr(api, "get_translator", lambda: StubTranslator())

    response = client.post(
        "/prompt-translate",
        json={"prompt": "Translate this lesson"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["english_response"].startswith("Here is a concise explanation")
    assert body["translation"]["conversation"]
