"""Central paths and environment configuration for the pipeline."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Tiny optional .env loader so local/Codespaces dev needs no extra dependency."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

OUT_DIR = Path(os.environ.get("PIPELINE_OUT", ROOT / "out"))
TOPICS_FILE = ROOT / "topics.yaml"
STATE_FILE = ROOT / "state" / "queue_state.json"
SCHEMA_FILE = ROOT / "schema" / "video-spec.schema.json"
PROMPT_FILE = ROOT / "prompts" / "script_agent.md"
