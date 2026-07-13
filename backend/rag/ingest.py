"""Loads WealthLoop's scheme documents into ChromaDB, chunked by numbered section."""

import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

try:
    from backend.config import (
        CHROMA_COLLECTION_NAME,
        CHROMA_PERSIST_DIR,
        DOCUMENTS_DIR,
        EMBEDDING_MODEL_NAME,
    )
except ImportError:  # allows running as `python ingest.py` from within backend/rag/
    from config import (
        CHROMA_COLLECTION_NAME,
        CHROMA_PERSIST_DIR,
        DOCUMENTS_DIR,
        EMBEDDING_MODEL_NAME,
    )

# Matches numbered section headers like "1. OVERVIEW" or "4. TAX BENEFITS"
SECTION_HEADER_RE = re.compile(r"^(\d+)\.\s+(.+?)\s*$", re.MULTILINE)

# .title() mangles all-caps acronyms (e.g. "Fd", "Nps") -> fix the common ones back up.
ACRONYMS = {
    "Fd": "FD",
    "Fds": "FDs",
    "Sip": "SIP",
    "Nps": "NPS",
    "Ppf": "PPF",
    "Elss": "ELSS",
    "Ltcg": "LTCG",
    "Rbi": "RBI",
    "Sebi": "SEBI",
    "Dicgc": "DICGC",
    "Kyc": "KYC",
    "Tds": "TDS",
}


def humanize_section_title(raw_title: str) -> str:
    titled = raw_title.title()
    for wrong, right in ACRONYMS.items():
        titled = re.sub(rf"\b{wrong}\b", right, titled)
    return titled


def chunk_document(text: str, filename: str) -> list[dict]:
    """Split one document into section-level chunks using its numbered headers as boundaries.

    Each chunk keeps its source filename and (human-readable) section title as metadata.
    The trailing "Source: ..." citation paragraph is split off into its own chunk too,
    since it isn't part of the section it trails but is still a natural boundary.
    """
    matches = list(SECTION_HEADER_RE.finditer(text))
    chunks = []

    preamble = text[: matches[0].start()].strip() if matches else text.strip()
    if preamble:
        chunks.append({"text": preamble, "source": filename, "section": "Header"})

    for i, match in enumerate(matches):
        section_title = humanize_section_title(match.group(2).strip())
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        source_match = re.search(r"\n\s*(Source:.*)\Z", body, re.DOTALL)
        if source_match:
            source_text = source_match.group(1).strip()
            body = body[: source_match.start()].strip()
        else:
            source_text = None

        chunk_text = f"{section_title}\n\n{body}" if body else section_title
        chunks.append({"text": chunk_text, "source": filename, "section": section_title})

        if source_text:
            chunks.append({"text": source_text, "source": filename, "section": "Source"})

    return chunks


def load_and_chunk_documents(documents_dir: Path = DOCUMENTS_DIR) -> list[dict]:
    all_chunks = []
    for path in sorted(documents_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        all_chunks.extend(chunk_document(text, path.name))
    return all_chunks


def ingest() -> int:
    """Embed all chunked documents and (re)persist them into ChromaDB.

    Returns the number of chunks ingested.
    """
    chunks = load_and_chunk_documents()
    if not chunks:
        print(f"No .txt documents found in {DOCUMENTS_DIR}")
        return 0

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = model.encode([c["text"] for c in chunks], show_progress_bar=False).tolist()

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass  # collection didn't exist yet on first run
    collection = client.create_collection(CHROMA_COLLECTION_NAME)

    collection.add(
        ids=[f"{c['source']}::{c['section']}::{i}" for i, c in enumerate(chunks)],
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[{"source": c["source"], "section": c["section"]} for c in chunks],
    )

    print(
        f"Ingested {len(chunks)} chunks from {DOCUMENTS_DIR} "
        f"into collection '{CHROMA_COLLECTION_NAME}' at {CHROMA_PERSIST_DIR}"
    )
    return len(chunks)


if __name__ == "__main__":
    ingest()
