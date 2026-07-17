"""Pipeline orchestrator: topic -> spec -> voiceover -> (render -> assemble -> upload).

Render/assemble/upload land in Phase 1 weekend 2; requesting them exits with
code 2 so a misconfigured scheduled run fails loudly instead of pretending.
"""

import argparse
import json
import sys

from . import config
from .script_agent import generate_spec
from .topics import mark_done, mark_failed, resolve_topic
from .tts import run_tts

STAGES = ["script", "tts", "render", "assemble", "upload"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the video production pipeline")
    parser.add_argument("--topic-id", help="id of a topic in topics.yaml")
    parser.add_argument("--topic", help="ad-hoc topic title (bypasses the queue)")
    parser.add_argument("--until", choices=STAGES, default="tts",
                        help="run up to and including this stage (default: tts)")
    parser.add_argument("--mark-state", action="store_true",
                        help="record success/failure in state/queue_state.json "
                             "(used by the scheduled daily run, not by tests)")
    args = parser.parse_args(argv)

    # Windows consoles default to a legacy codepage; Arabic output needs UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    topic = resolve_topic(topic_id=args.topic_id, adhoc_title=args.topic)
    if topic is None:
        print("Topic queue is empty — add entries to topics.yaml", file=sys.stderr)
        return 1
    print(f"[run] topic: {topic['id']} — {topic.get('title', '')}")

    out_dir = config.OUT_DIR / topic["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    until_idx = STAGES.index(args.until)

    try:
        spec = generate_spec(topic)
        spec_path = out_dir / "spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[run] script stage done -> {spec_path}")

        if until_idx >= STAGES.index("tts"):
            run_tts(spec, out_dir)

        if until_idx >= STAGES.index("render"):
            raise NotImplementedError(
                f"stage '{STAGES[2]}' onwards is not implemented yet (Phase 1, weekend 2)"
            )
    except NotImplementedError as exc:
        print(f"[run] stopped: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if args.mark_state:
            mark_failed(topic["id"], exc)
        raise

    if args.until == "upload" and args.mark_state:
        mark_done(topic["id"])

    print(f"[run] completed through '{args.until}'. Artifacts in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
