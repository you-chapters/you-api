import json

from openai import OpenAI

from app.config import get_secret
from app.models.entry_tags import EntryTags
from app.tag_extraction.tag_extraction_port import TagExtractionClient

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """Extract structured metadata from a journal entry. Return a JSON object with exactly these fields:
- "people": array of full names mentioned (use most complete consistent form, e.g. "Alice Smith" not "Alice")
- "locations": array of places mentioned or referenced; include user_location if provided and not already present
- "topics": array of topics covered; each topic must be a single lowercase word (e.g. "work", "sleep", "health", "travel", etc.)
- "mood": one of "positive", "negative", "neutral", "mixed", "anxious", "excited", or null
- "time_markers": array of references to events at a different time than the entry date (e.g. "last week", "in June")

Return only valid JSON. No explanation or extra fields."""


def _user_prompt(text: str, timestamp: str, user_location: str | None) -> str:
    parts = [f"Entry date: {timestamp}"]
    if user_location:
        parts.append(f"User location: {user_location}")
    parts.append(f"Entry:\n{text}")
    return "\n".join(parts)


class OpenAITagExtractionClient(TagExtractionClient):
    def __init__(self) -> None:
        self._client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))

    def extract(self, text: str, timestamp: str, user_location: str | None) -> EntryTags:
        response = self._client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(text, timestamp, user_location)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        try:
            data = json.loads(content)
            return EntryTags.model_validate(data)
        except Exception as e:
            raise ValueError(f"Tag extraction failed ({_MODEL}): {e}. Response: {(content or '')[:200]!r}") from e
