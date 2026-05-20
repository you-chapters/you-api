from app.models.entry_tags import EntryTags
from app.tag_extraction.tag_extraction_port import TagExtractionClient


class InMemoryTagExtractionClient(TagExtractionClient):
    def extract(self, text: str, timestamp: str, user_location: str | None) -> EntryTags:
        return EntryTags()
