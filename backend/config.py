import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

_chroma_dir_raw = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_PERSIST_DIR = (
    _chroma_dir_raw if os.path.isabs(_chroma_dir_raw) else str((BASE_DIR / _chroma_dir_raw).resolve())
)
CHROMA_COLLECTION_NAME = "finance_schemes"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Demo-only: a persona name/id substring (e.g. "kabir"). When set, compliance_agent
# forces a failing first attempt for that persona so the fail-then-retry loop is
# guaranteed to fire on demand, without altering the underlying rule logic.
DEMO_FORCE_FAIL_FOR = os.getenv("DEMO_FORCE_FAIL_FOR", "").strip().lower()

DOCUMENTS_DIR = Path(__file__).resolve().parent / "rag" / "documents"
