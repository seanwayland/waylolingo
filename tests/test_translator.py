import httpx

from mandarin_translator.models import ConversationResponse
from mandarin_translator.translator import OllamaTranslator, build_translator_from_env


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.last_request: dict | None = None

    def post(self, url: str, json: dict, timeout: float) -> FakeResponse:
        self.last_request = {"url": url, "json": json, "timeout": timeout}
        return FakeResponse(self.payload)


def test_ollama_translator_parses_structured_json() -> None:
    client = FakeClient(
        {
            "response": '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["what","time","is","it"],"phonetic":["xian4","zai4","ji3","dian3"],"symbols":["现","在","几","点"]}]}'
        }
    )
    translator = OllamaTranslator(model="qwen2.5:7b-instruct", client=client)

    response = translator.translate("What time is it?")

    assert response == ConversationResponse.model_validate(
        {
            "conversation": [
                {
                    "language": "mandarin",
                    "language_code": "zh-CN",
                    "english": ["what", "time", "is", "it"],
                    "phonetic": ["xian4", "zai4", "ji3", "dian3"],
                    "symbols": ["现", "在", "几", "点"],
                }
            ]
        }
    )
    assert client.last_request is not None
    assert client.last_request["json"]["model"] == "qwen2.5:7b-instruct"
    assert client.last_request["json"]["format"] == "json"


def test_build_translator_from_env_uses_ollama(monkeypatch) -> None:
    monkeypatch.setenv("TRANSLATOR_BACKEND", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    translator = build_translator_from_env()

    assert translator.backend_name == "ollama"
    assert translator.model == "qwen2.5:3b"
    assert translator.base_url == "http://localhost:11434"


def test_ollama_translator_extracts_json_when_trailing_text_exists() -> None:
    client = FakeClient(
        {
            "response": '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["how","do","i","say","piano","in","mandarin"],"phonetic":["zen3","me","shuo1","gang1","qin2"],"symbols":["怎么","说","钢琴"]}]} user: fix this now'
        }
    )
    translator = OllamaTranslator(model="qwen2.5:7b-instruct", client=client)

    response = translator.translate("how do i say piano in mandarin")

    assert response.conversation[0].language == "mandarin"
    assert response.conversation[0].language_code == "zh-CN"
    assert response.conversation[0].symbols == ["怎么", "说", "钢琴"]


def test_ollama_translator_normalizes_junk_tokens() -> None:
    client = FakeClient(
        {
            "response": '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["How do I say piano in Mandarin??"],"phonetic":["ne4","bu2","wo3","shuo1","qian1","ne5",""] ,"symbols":["怎么","说`,`钢琴`","在`,`中文`中`"]}]} note: trailing noise'
        }
    )
    translator = OllamaTranslator(model="qwen2.5:7b-instruct", client=client)

    response = translator.translate("how do i say piano in mandarin")

    assert response.conversation[0].english == ["piano"]
    assert response.conversation[0].phonetic == ["zen3", "me5", "shuo1", "gang1", "qin2", "zai4", "zhong1", "wen2", "zhong1"]
    assert response.conversation[0].symbols == ["怎么", "说", "钢琴", "在", "中文", "中"]


def test_ollama_translator_extracts_target_phrase_from_how_do_i_say_prompt() -> None:
    client = FakeClient(
        {
            "response": '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["piano"],"phonetic":["gang1","qin2"],"symbols":["钢琴"]}]}'
        }
    )
    translator = OllamaTranslator(model="qwen2.5:7b-instruct", client=client)

    response = translator.translate("how do i say piano in mandarin")

    assert response.conversation[0].english == ["piano"]
    assert response.conversation[0].phonetic == ["gang1", "qin2"]
    assert response.conversation[0].symbols == ["钢琴"]


def test_ollama_translator_falls_back_when_symbols_missing() -> None:
    client = FakeClient(
        {
            "response": '{"conversation":[{"language":"mandarin","language_code":"zh-CN","english":["let","us","start"],"phonetic":["wo3","men5","kai1","shi3"],"symbols":[]}]} '
        }
    )
    translator = OllamaTranslator(model="qwen2.5:3b", client=client)

    response = translator.translate("let us start")

    assert response.conversation[0].english == ["let", "us", "start"]
    assert response.conversation[0].phonetic == ["wo3", "men5", "kai1", "shi3"]
    assert response.conversation[0].symbols == ["?"]