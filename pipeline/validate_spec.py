"""Schema + business-rule validation for video-spec JSON.

Schema errors are returned first (structure must be right before content checks
make sense). Business rules encode what the schema can't express: pacing,
readable code on a vertical phone screen, YouTube limits, disclosure.
"""

import json

from jsonschema import Draft202012Validator

from . import config

MAX_CODE_LINES = 14
MAX_CODE_COLS = 46
WORDS_PER_SECOND = 2.3
TOTAL_DURATION_RANGE = (50, 100)
MAX_TAGS_TOTAL_CHARS = 400
DISCLOSURE_SUBSTRING = "الذكاء الاصطناعي"

_schema_cache: dict | None = None


def load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(config.SCHEMA_FILE.read_text(encoding="utf-8"))
    return _schema_cache


def validate_spec(spec: object) -> list[str]:
    """Return a list of human-readable errors; empty list means the spec is valid."""
    validator = Draft202012Validator(load_schema())
    errors = [
        f"schema: {err.json_path}: {err.message}"
        for err in sorted(validator.iter_errors(spec), key=lambda e: e.json_path)
    ]
    if errors:
        return errors
    return _business_errors(spec)


def _business_errors(spec: dict) -> list[str]:
    errors: list[str] = []
    scenes = spec["scenes"]

    ids = [s["id"] for s in scenes]
    if len(ids) != len(set(ids)):
        errors.append("scene ids must be unique")

    if scenes[0]["type"] != "hook":
        errors.append("first scene must be type 'hook'")
    if scenes[-1]["type"] != "payoff":
        errors.append("last scene must be type 'payoff'")
    if not any(s["type"] in ("code", "diagram") for s in scenes):
        errors.append("need at least one 'code' or 'diagram' scene")

    total = sum(s["target_duration_s"] for s in scenes)
    lo, hi = TOTAL_DURATION_RANGE
    if not lo <= total <= hi:
        errors.append(f"total target duration {total:.0f}s is outside {lo}-{hi}s")

    for scene in scenes:
        sid = scene["id"]
        target = scene["target_duration_s"]
        word_count = len(scene["vo_text"].split())
        spoken_s = word_count / WORDS_PER_SECOND
        if spoken_s > target * 1.6:
            errors.append(
                f"{sid}: vo_text too long ({word_count} words ≈ {spoken_s:.0f}s spoken) "
                f"for target {target}s — shorten the text or raise target_duration_s"
            )
        elif spoken_s < target * 0.35:
            errors.append(
                f"{sid}: vo_text too short ({word_count} words) for target {target}s"
            )

        code = scene.get("code")
        if code:
            lines = code["content"].split("\n")
            if len(lines) > MAX_CODE_LINES:
                errors.append(f"{sid}: code has {len(lines)} lines (max {MAX_CODE_LINES})")
            too_long = [i + 1 for i, line in enumerate(lines) if len(line) > MAX_CODE_COLS]
            if too_long:
                errors.append(
                    f"{sid}: code lines {too_long} exceed {MAX_CODE_COLS} chars "
                    "(unreadable on a vertical phone screen)"
                )
            for h in code.get("highlights", []):
                if h["end_line"] < h["start_line"] or h["end_line"] > len(lines):
                    errors.append(
                        f"{sid}: highlight {h['start_line']}-{h['end_line']} is out of "
                        f"range for {len(lines)} code lines"
                    )

        diagram = scene.get("diagram")
        if diagram:
            node_ids = {n["id"] for n in diagram["nodes"]}
            for edge in diagram["edges"]:
                if edge["from"] not in node_ids or edge["to"] not in node_ids:
                    errors.append(
                        f"{sid}: diagram edge {edge['from']}->{edge['to']} references an unknown node"
                    )

    meta = spec["metadata"]
    if DISCLOSURE_SUBSTRING not in meta["description"]:
        errors.append(
            f"description must contain the AI disclosure line (mention '{DISCLOSURE_SUBSTRING}')"
        )
    if sum(len(t) for t in meta["tags"]) > MAX_TAGS_TOTAL_CHARS:
        errors.append(f"tags exceed {MAX_TAGS_TOTAL_CHARS} total characters (YouTube limit is 500)")

    return errors
