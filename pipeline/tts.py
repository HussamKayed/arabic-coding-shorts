"""Voiceover: edge-tts per scene, capturing word-boundary timestamps.

The WordBoundary events give caption timing for free — no Whisper needed.
Offsets arrive in 100-nanosecond ticks; everything is emitted in seconds.

Output layout (under the build dir):
    audio/<scene_id>.mp3
    timings.json  — per scene: duration_s, words[], captions[] (grouped for Shorts)
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import edge_tts

TICKS_PER_SECOND = 10_000_000
CAPTION_MAX_WORDS = 3
CAPTION_GAP_S = 0.6
SYNTH_RETRIES = 3


async def _synth_scene(text: str, voice: str, rate: str, pitch: str, out_path: Path) -> list[dict]:
    words: list[dict] = []
    # edge-tts 7.2 defaults to SentenceBoundary metadata. Captions require the
    # per-word mode explicitly; otherwise audio succeeds but `words` stays empty.
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, pitch=pitch, boundary="WordBoundary"
    )
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_s = chunk["offset"] / TICKS_PER_SECOND
                words.append({
                    "text": chunk["text"],
                    "start_s": round(start_s, 3),
                    "end_s": round(start_s + chunk["duration"] / TICKS_PER_SECOND, 3),
                })
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("edge-tts produced no audio")
    if not words:
        raise RuntimeError(
            f"edge-tts produced {out_path.stat().st_size} audio bytes but no word events"
        )
    return words


def synth_scene(text: str, voice: str, rate: str, pitch: str, out_path: Path) -> list[dict]:
    last_exc: Exception | None = None
    for attempt in range(1, SYNTH_RETRIES + 1):
        try:
            return asyncio.run(_synth_scene(text, voice, rate, pitch, out_path))
        except Exception as exc:
            last_exc = exc
            print(f"[tts] attempt {attempt} failed: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"TTS failed after {SYNTH_RETRIES} attempts: {last_exc}")


def audio_duration_s(path: Path, words: list[dict]) -> float:
    try:
        from mutagen.mp3 import MP3
        return round(MP3(path).info.length, 3)
    except Exception:
        # fall back to last word end + breathing room
        return round((words[-1]["end_s"] + 0.3) if words else 0.0, 3)


def group_captions(words: list[dict], max_words: int = CAPTION_MAX_WORDS,
                   gap_s: float = CAPTION_GAP_S) -> list[dict]:
    """Group word timestamps into short Shorts-style caption chunks.

    A new chunk starts when the current one is full or after a speech pause.
    Text order is preserved; RTL shaping is the renderer's job.
    """
    groups: list[list[dict]] = []
    current: list[dict] = []
    for word in words:
        if current and (len(current) >= max_words or word["start_s"] - current[-1]["end_s"] > gap_s):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return [
        {
            "text": " ".join(w["text"] for w in group),
            "start_s": group[0]["start_s"],
            "end_s": group[-1]["end_s"],
        }
        for group in groups
    ]


def run_tts(spec: dict, out_dir: Path) -> dict:
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    voice = spec["voice"]
    voice_id = voice["voice_id"]
    rate = voice.get("rate", "+8%")
    pitch = voice.get("pitch", "+0Hz")

    scenes_out = []
    total = 0.0
    for scene in spec["scenes"]:
        sid = scene["id"]
        mp3_path = audio_dir / f"{sid}.mp3"
        print(f"[tts] {sid}: synthesizing {len(scene['vo_text'].split())} words with {voice_id}")
        words = synth_scene(scene["vo_text"], voice_id, rate, pitch, mp3_path)
        duration = audio_duration_s(mp3_path, words)
        total += duration
        scenes_out.append({
            "scene_id": sid,
            "audio_file": f"audio/{sid}.mp3",
            "duration_s": duration,
            "words": words,
            "captions": group_captions(words),
        })
        print(f"[tts] {sid}: {duration:.2f}s audio, {len(words)} word events")

    timings = {
        "topic_id": spec["topic_id"],
        "voice_id": voice_id,
        "total_duration_s": round(total, 3),
        "scenes": scenes_out,
    }
    timings_path = out_dir / "timings.json"
    timings_path.write_text(json.dumps(timings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[tts] wrote {timings_path} (total voiceover {total:.1f}s)")
    return timings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize voiceover + word timings from a spec.json")
    parser.add_argument("--spec", required=True, help="path to spec.json")
    parser.add_argument("--out", help="output directory (default: alongside the spec)")
    args = parser.parse_args(argv)

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    out_dir = Path(args.out) if args.out else spec_path.parent
    run_tts(spec, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
