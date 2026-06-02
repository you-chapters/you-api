import json

from openai import OpenAI

from app.config import get_secret
from app.llm.llm_client import LLMClient
from app.models.entry import Entry

_NARRATIVE_MODEL = "gpt-4o-mini"
_PHASE_MODEL = "gpt-4o"
_NARRATIVE_SYSTEM = (
    "Write a warm, reflective, first-person narrative paragraph summarizing the provided diary entries. "
    "Detect the language of the entries and write in that same language. "
    "Write freely — no fixed structure. "
    "Do not open with time markers like 'This week' or 'This month'. "
    "3–7 sentences."
)
_PHASE_SYSTEM = (
    "Given diary entries from a coherent life chapter, produce two outputs:\n"
    "1. title: A 2–5 word evocative chapter heading (e.g. 'The Quiet Rebuilding', 'Summer in Motion'). "
    "No vague labels like 'Period 1' or corporate language.\n"
    "2. description: 4–7 sentences of warm reflective prose describing the chapter's character, "
    "emotional tone, who/what was prominent, and how it felt to live through it. "
    "Detect the language of the diary entries and write both the title and description in that same language. "
    "Do not open with time markers like 'This week' or 'This month'.\n"
    'Respond with JSON: {"title": "...", "description": "..."}'
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
            model=_NARRATIVE_MODEL,
            messages=[
                {"role": "system", "content": _NARRATIVE_SYSTEM},
                {"role": "user", "content": f"Period: {period_label}\n\n{body}"},
            ],
        )
        return response.choices[0].message.content or ""

    def generate_phase(self, entries: list[Entry], signals_summary: str, hint: str) -> tuple[str, str]:
        if not entries:
            return "Quiet Chapter", "No entries recorded during this phase."
        body = "\n\n".join(
            f"[{e.timestamp[:10]}] {e.entry}"
            for e in sorted(entries, key=lambda e: e.timestamp)
        )
        user_content = f"Signals: {signals_summary}\nCharacter hint: {hint}\n\n{body}"
        response = self._client.chat.completions.create(
            model=_PHASE_MODEL,
            messages=[
                {"role": "system", "content": _PHASE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return data.get("title", "Unnamed Chapter"), data.get("description", "")
