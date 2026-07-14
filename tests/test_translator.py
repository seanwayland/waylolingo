from mandarin_translator.models import ConversationResponse
from mandarin_translator.translator import TranslateGemmaTranslator, build_translator_from_env


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)
        self.requests: list[dict] = []

    def post(self, url: str, json: dict, timeout: float) -> FakeResponse:
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        content = self._contents.pop(0)
        return FakeResponse({"message": {"role": "assistant", "content": content}})

    @property
    def last_request(self) -> dict | None:
        return self.requests[-1] if self.requests else None


def test_translategemma_translator_translates_single_sentence() -> None:
    client = FakeClient(["现在几点"])
    translator = TranslateGemmaTranslator(model="translategemma:4b", client=client)

    response = translator.translate("What time is it?")

    assert response == ConversationResponse.model_validate(
        {
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
    )
    assert client.last_request is not None
    assert client.last_request["json"]["model"] == "translategemma:4b"
    assert client.last_request["url"].endswith("/api/chat")


def test_translategemma_translator_splits_multiple_sentences() -> None:
    client = FakeClient(["你好。", "你好吗？"])
    translator = TranslateGemmaTranslator(model="translategemma:4b", client=client)

    response = translator.translate("Hello. How are you?")

    assert [sentence.english for sentence in response.conversation] == [
        ["hello"],
        ["how", "are", "you"],
    ]
    assert response.conversation[0].symbols == ["你好"]
    assert response.conversation[1].symbols == ["你好吗"]


def test_build_translator_from_env_uses_translategemma(monkeypatch) -> None:
    monkeypatch.setenv("TRANSLATOR_BACKEND", "translategemma")
    monkeypatch.setenv("OLLAMA_MODEL", "translategemma:4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    translator = build_translator_from_env()

    assert translator.backend_name == "translategemma"
    assert translator.model == "translategemma:4b"
    assert translator.base_url == "http://localhost:11434"


def test_translategemma_translator_extracts_target_phrase_from_how_do_i_say_prompt() -> None:
    client = FakeClient(["钢琴"])
    translator = TranslateGemmaTranslator(model="translategemma:4b", client=client)

    response = translator.translate("how do i say piano in mandarin")

    assert response.conversation[0].english == ["piano"]
    assert response.conversation[0].symbols == ["钢琴"]
    assert response.conversation[0].phonetic == ["gang1", "qin2"]
