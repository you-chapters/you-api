import os

from pinecone import Pinecone, ServerlessSpec

_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "you-entries")
_DIMS = 1536


def main() -> None:
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    existing = [idx.name for idx in pc.list_indexes()]
    if _INDEX_NAME not in existing:
        pc.create_index(
            name=_INDEX_NAME,
            dimension=_DIMS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Created index '{_INDEX_NAME}'")
    else:
        print(f"Index '{_INDEX_NAME}' already exists")

    desc = pc.describe_index(_INDEX_NAME)
    print(f"PINECONE_INDEX_HOST={desc.host}")


if __name__ == "__main__":
    main()
