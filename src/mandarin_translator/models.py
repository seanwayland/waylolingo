from pydantic import BaseModel, Field


class Sentence(BaseModel):
    language: str = Field(default="mandarin", examples=["mandarin"])
    language_code: str = Field(default="zh-CN", examples=["zh-CN"])
    english: list[str]
    phonetic: list[str]
    symbols: list[str]


class ConversationResponse(BaseModel):
    conversation: list[Sentence]


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, examples=["What time is it?"])


class PromptTranslateRequest(BaseModel):
    prompt: str = Field(min_length=1, examples=["How do I ask for coffee in Mandarin?"])


class PromptTranslateResponse(BaseModel):
    prompt: str
    english_response: str
    translation: ConversationResponse
    target_words: list[str]