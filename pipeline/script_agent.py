"""Script Agent: topic -> validated video-spec JSON via the Gemini API (free tier).

Strategy: ask for raw JSON (responseMimeType), validate locally against the
schema + business rules, and feed validation errors back for up to two retries.
This is more robust than Gemini's responseSchema subset for a nested spec.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

from . import config
from .topics import resolve_topic
from .validate_spec import load_schema, validate_spec

# Text generation is available on the stable API. Avoid tying the production
# workflow to v1beta, whose model availability can differ by API key/project.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
MAX_VALIDATION_ATTEMPTS = 3
MAX_HTTP_ATTEMPTS = 5


def build_prompt(topic: dict) -> str:
    template = config.PROMPT_FILE.read_text(encoding="utf-8")
    schema_json = json.dumps(load_schema(), ensure_ascii=False, indent=2)
    return (
        template
        .replace("{{TOPIC_ID}}", topic["id"])
        .replace("{{TOPIC_TITLE}}", topic.get("title", ""))
        .replace("{{TOPIC_ANGLE}}", topic.get("angle", ""))
        .replace("{{TOPIC_NOTES}}", topic.get("notes", ""))
        .replace("{{SCHEMA_JSON}}", schema_json)
    )


def call_gemini(prompt: str, *, api_key: str | None = None, model: str | None = None,
                temperature: float = 0.8) -> str:
    api_key = api_key or config.GEMINI_API_KEY
    model = model or config.GEMINI_MODEL
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (add it to the environment or a .env file)")

    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": 16384,
    }
    # responseMimeType and thinkingConfig are not accepted by the stable v1
    # GenerateContent endpoint for every API project. The prompt still requires
    # raw JSON, and parse_spec_text + validate_spec enforce it locally.

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }

    last_error = "no attempts made"
    for attempt in range(MAX_HTTP_ATTEMPTS):
        if attempt:
            time.sleep(min(60, 5 * 2 ** attempt))
        resp = requests.post(
            GEMINI_URL.format(model=model),
            params={"key": api_key},
            json=body,
            timeout=180,
        )
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"[script] transient Gemini error, retrying: {last_error}", file=sys.stderr)
            continue
        if not resp.ok:
            # requests' default HTTPError only includes the URL/status. Gemini's
            # JSON body contains the useful reason (unknown model, disabled API,
            # key restriction, etc.), so preserve a safe excerpt in Actions logs.
            try:
                detail = (resp.json().get("error") or {}).get("message", "")
            except (ValueError, AttributeError):
                detail = resp.text
            detail = " ".join(detail.split())[:500]
            raise RuntimeError(
                f"Gemini API HTTP {resp.status_code} for model {model!r}: "
                f"{detail or 'no error detail returned'}"
            )
        data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates (safety block?): {json.dumps(data)[:400]}")
        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(
                f"Gemini candidate had no text (finishReason={finish_reason}): {json.dumps(data)[:400]}"
            )
        if finish_reason not in ("STOP", "MAX_TOKENS"):
            raise RuntimeError(f"Gemini stopped abnormally: finishReason={finish_reason}")
        return text

    raise RuntimeError(f"Gemini API unavailable after {MAX_HTTP_ATTEMPTS} attempts: {last_error}")


def parse_spec_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("top-level JSON must be an object")
    return obj


def normalize_spec(spec: dict, topic: dict) -> dict:
    """Force the fields the LLM must not be trusted with."""
    spec["spec_version"] = "1.0"
    spec["topic_id"] = topic["id"]
    spec["language"] = "ar"
    spec["voice"] = {
        "voice_id": "ar-EG-SalmaNeural",
        "rate": "+8%",
        "pitch": "+0Hz",
    }
    meta = spec.get("metadata")
    if isinstance(meta, dict):
        meta["ai_disclosure"] = True
        meta["privacy_status"] = "private"
        meta["default_language"] = "ar"
    return spec


def generate_spec(topic: dict, **gemini_kwargs) -> dict:
    prompt = build_prompt(topic)
    feedback = ""
    text = ""
    last_errors: list[str] = []
    for attempt in range(1, MAX_VALIDATION_ATTEMPTS + 1):
        text = call_gemini(prompt + feedback, **gemini_kwargs)
        try:
            spec = normalize_spec(parse_spec_text(text), topic)
        except ValueError as exc:  # includes json.JSONDecodeError
            last_errors = [f"output was not valid JSON: {exc}"]
        else:
            last_errors = validate_spec(spec)
            if not last_errors:
                print(f"[script] spec valid on attempt {attempt}")
                return spec
        print(f"[script] attempt {attempt}: {len(last_errors)} validation error(s)", file=sys.stderr)
        feedback = (
            "\n\n---\nYour previous attempt was:\n" + text[:6000]
            + "\n\nIt failed validation with these errors:\n- " + "\n- ".join(last_errors)
            + "\n\nRegenerate the FULL corrected JSON, fixing every error. Output raw JSON only."
        )
    raise RuntimeError(
        f"Script generation failed validation after {MAX_VALIDATION_ATTEMPTS} attempts:\n- "
        + "\n- ".join(last_errors)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a video-spec JSON from a topic")
    parser.add_argument("--topic-id", help="id of a topic in topics.yaml")
    parser.add_argument("--topic", help="ad-hoc topic title (bypasses the queue)")
    parser.add_argument("--out", help="output directory (default: out/<topic_id>)")
    args = parser.parse_args(argv)

    topic = resolve_topic(topic_id=args.topic_id, adhoc_title=args.topic)
    if topic is None:
        print("Topic queue is empty — add entries to topics.yaml", file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else config.OUT_DIR / topic["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = generate_spec(topic)
    spec_path = out_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[script] wrote {spec_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
