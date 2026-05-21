from openai import OpenAI

from app.config import get_secret
from app.llm.llm_client import LLMClient
from app.models.entry import Entry

_MODEL = "gpt-4o-mini"
_SYSTEM_PROMPT = (
    "You are a thoughtful personal journal assistant. "
    "Write a warm, reflective, first-person narrative paragraph summarizing the provided diary entries. "
    "Use the language of the entries. "
    "Write freely — no fixed structure. "
    "Speak as if the person is looking back at their own period. "
    "3–7 sentences."
)


class OpenAILLMClient(LLMClient):
    def __init__(self) -> None:
        self._client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))

    def generate_narrative(self, entries: list[Entry], period_label: str) -> str:
        if not entries:
            return "No entries this period."
        body = "\n\n".join(
            f"[{e.timestamp[:10]}] {e.entry}"
            for e in sorted(entries, key=lambda e: e.timestamp)
        )
        response = self._client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Period: {period_label}\n\n{body}"},
            ],
        )
        return response.choices[0].message.content or ""
