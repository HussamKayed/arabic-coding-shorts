# 🎬 Automated Arabic Coding Shorts

One queued topic → fully produced YouTube Short: script, Arabic voiceover, word-timed captions, render, and private upload — all automated, all on free tiers. Full design in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Status

| Stage | Module | Status |
|---|---|---|
| Video-spec schema (the contract) | `schema/video-spec.schema.json` | ✅ |
| Script agent (Gemini → spec JSON, validated + auto-retry) | `pipeline/script_agent.py` | ✅ |
| Voiceover + word timings + caption grouping (edge-tts) | `pipeline/tts.py` | ✅ |
| Remotion render | — | 🔜 weekend 2 |
| FFmpeg assembly + burned captions | — | 🔜 weekend 2 |
| YouTube upload (private + AI disclosure) | — | 🔜 weekend 2 |
| Daily cron | `.github/workflows/pipeline.yml` (commented out) | 🔜 weekend 2 |

## One-time setup

1. Create a **public** GitHub repo and push this code (public = unlimited Actions minutes):

   ```
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```

2. Get a free Gemini API key: https://aistudio.google.com/apikey
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**, name `GEMINI_API_KEY`.
4. Smoke test: **Actions tab → pipeline → Run workflow** (defaults are fine). When it finishes, download the `video-build-*` artifact and check:
   - `spec.json` — the generated video spec (scenes, Arabic VO text, code, metadata)
   - `audio/*.mp3` — one Arabic voiceover clip per scene
   - `timings.json` — per-word timestamps + grouped caption chunks

CI (`ci.yml`) runs the test suite on every push — no local Python needed.

## Running it

Via GitHub Actions (recommended — no local installs):

- **pipeline** workflow, `topic` empty → picks the next pending topic from `topics.yaml`
- `topic` = any free text → ad-hoc one-off video spec
- `until` = `script` → only generate the spec (cheapest way to iterate on prompt quality)

Locally or in Codespaces (optional):

```
pip install -r requirements.txt
cp .env.example .env            # then paste your GEMINI_API_KEY
python -m pipeline.run --until tts
python -m pipeline.run --topic "شرح الـ closures" --until script
pytest
```

## How it flows

```
topics.yaml ──► script_agent (Gemini, validate, retry)
                    │ out/<topic>/spec.json
                    ▼
                tts (edge-tts, word boundaries)
                    │ out/<topic>/audio/*.mp3 + timings.json
                    ▼
                render → assemble → upload   (weekend 2)
```

- `topics.yaml` is **human-edited only**; the pipeline records progress in `state/queue_state.json`, so your comments and mobile edits are never clobbered.
- `schema/video-spec.schema.json` is the single source of truth between modules. `tests/fixtures/sample_spec.json` is a golden example of it (and will double as the Remotion dev fixture).
- The script agent forces the untrusted fields (`privacy_status: private`, `ai_disclosure: true`) no matter what the LLM outputs.

## Repo layout

```
pipeline/          Python package: run.py (orchestrator), script_agent, tts,
                   validate_spec, topics, config
prompts/           Gemini prompt template for the script agent
schema/            video-spec JSON Schema (the inter-module contract)
state/             machine-owned queue state (committed by the bot later)
tests/             pytest suite + golden spec fixture
.github/workflows/ ci.yml (tests) + pipeline.yml (manual now, cron later)
```
