# Project Context: AI-Automated YouTube Channel (Arabic Coding Tutorials)

> Use this file as development context. It defines the goal, constraints, architecture, stack, and build phases for the automated video pipeline.

## Goal

Fully automated YouTube content pipeline: **one prompt (or one queued topic) → published video**, with every asset AI-generated (script, voice, visuals, editing decisions, captions, thumbnail, metadata). Runs unattended on a daily schedule during working hours. Human involvement limited to ~5 min/day: reviewing a privately-uploaded draft on mobile and publishing or deleting it.

## Niche & Format

- **Niche:** Arabic-language coding tutorials (backend/web focus: JS/TS, NestJS, auth/OAuth, APIs). Underserved market; creator has real domain expertise.
- **Primary format (v1):** YouTube Shorts, 60–90s, vertical 1080×1920. Structure: hook → animated code concept → payoff.
- **Later format (v2):** long-form 8–12 min versions of the best-performing Shorts (long-form watch hours are what count toward monetization).

## Hard Constraints

1. **$0 running cost.** Free tiers and open tools only. No paid APIs, no paid rendering, no owned GPU (assume no usable local hardware — all execution in the cloud).
2. **Fully agent-drivable.** Every step must be callable from code (no web-only tools, no free tiers without API/CLI access).
3. **Minimal maintenance time.** Builder has a full-time job; pipeline must run on a cron schedule without supervision.
4. **YouTube policy compliance.** Content must have genuine educational value (not "inauthentic content"), and the AI-content disclosure must be set on uploads. Pure low-effort AI slop is demonetized under the July 2025 YPP rules.

## Architecture Overview

```
topics.yaml (queue, refilled monthly)
    │  cron: GitHub Actions, daily ~10:00
    ▼
[1] Script Agent (Gemini API, free tier)
    → outputs video-spec JSON: scenes[], VO text, code snippets,
      timings, edit decisions, title/description/tags
    ▼
[2] Voiceover (edge-tts, free)
    → Arabic neural TTS per scene (ar-EG-SalmaNeural / ar-SA-HamedNeural)
    → emits word-boundary timestamps → caption timing for free (no Whisper needed)
    ▼
[3] Visual Render (Remotion, CPU render on Actions runner)
    → one reusable Short template; LLM fills props only
      (hook text, code blocks, highlights, pacing)
    → NOTE: diffusion video models cannot render readable text/code.
      All code/diagram scenes are programmatic motion graphics.
    ▼
[4] Assembly (FFmpeg, preinstalled on runners)
    → executes edit-decision JSON: cuts, transitions,
      burned-in Arabic captions (RTL-safe), music bed
    ▼
[5] Thumbnail (v2+, long-form only; AI Horde free API or Flux on Kaggle)
    ▼
[6] Publish (YouTube Data API v3)
    → upload as PRIVATE + AI disclosure flag + metadata from spec
    → notify via Telegram bot with preview link
    → human flips to public from phone
```

## Stack (all free)

| Concern | Tool | Notes / Link |
|---|---|---|
| Orchestrator | GitHub Actions, **public repo** | Unlimited minutes on public repos. Cron-triggered daily workflow. |
| LLM | Gemini API free tier | https://aistudio.google.com — strong Arabic. (Fallback: Claude Haiku ≈ $1–2/mo if quality demands it.) |
| TTS | edge-tts | https://github.com/rany2/edge-tts — unlimited, Arabic voices, word-boundary events |
| Video render | Remotion | https://remotion.dev — free license for individuals; CLI render, React-based |
| Assembly | FFmpeg | Preinstalled on GitHub Actions runners |
| Captions | edge-tts word timings | Whisper (CPU) only as fallback |
| Images (v2) | AI Horde | https://stablehorde.net — free crowdsourced image-gen API |
| B-roll (v2) | Wan 2.1 on Kaggle free GPU | 30 GPU-hrs/week, triggered via Kaggle API: https://www.kaggle.com/docs/api |
| Upload | YouTube Data API v3 | OAuth refresh token in GitHub Secrets; upload = 1,600 quota units of 10,000/day |
| Dev environment | GitHub Codespaces | Free 60 hrs/month — no local hardware required |
| Topic queue | `topics.yaml` in repo | Editable from mobile via GitHub app |

## Video-Spec JSON (contract between all modules)

Single source of truth produced by the Script Agent. Every downstream module consumes it. Must include: scene list (type: `hook | code | diagram | payoff`), per-scene VO text (Arabic), code snippets + highlight ranges, target durations, transition types, title, description, tags, and disclosure flags. Design this schema first — everything depends on it.

## Build Phases

**Phase 0 — Accounts (1 evening):** YouTube channel (fresh Google account), Gemini API key, public GitHub repo, Google Cloud project with YouTube Data API v3 + OAuth credentials, secrets stored in GitHub Secrets.

**Phase 1 — MVP pipeline (2 weekends):**
- Weekend 1: script generator (topic → video-spec JSON) + voiceover module with word timings. Develop in Codespaces.
- Weekend 2: Remotion Short template + FFmpeg assembly + upload module + cron workflow. Fill `topics.yaml` with 30 topics.

**Phase 2 — after ~30 published videos:** diffusion b-roll hooks via Kaggle (Wan 2.1), thumbnail generation, long-form template, Telegram approval bot with one-tap publish.

**Phase 3 — after ~100 videos:** analytics feedback loop (YouTube Analytics API → topic/hook selection), approach true single-prompt operation.

## Known Gotchas

- **YouTube API audit:** unverified API projects have uploads locked as private until Google audits the app. Harmless here (flow uploads private anyway); request audit once the channel has traction.
- **Public repo = public code.** Accepted trade-off for unlimited Actions minutes; doubles as a portfolio piece. Keep all secrets in GitHub Secrets, never in code.
- **RTL rendering:** Arabic captions and UI text need RTL-aware layout in Remotion and FFmpeg drawtext/ASS subtitles. Test early.
- **Actions runner limits:** 6-hour max per job, ~7GB RAM, 2-core CPU. Keep renders short-form; long-form renders may need job splitting.
- **Monetization reality:** YPP requires 1,000 subs + 4,000 public long-form watch hours OR 10M Shorts views/90 days. Shorts watch time does not count toward the 4,000 hours. Expect first revenue month 4–6; affiliate links likely pay before AdSense.
- **Avoid** anything that reads as "inauthentic content": no reused clips with generic narration, no template spam. Educational specificity is the moat.

## Success Criteria (v1)

- Daily video produced and uploaded (private) with zero manual steps.
- Cost: $0.00/month across all services.
- Human time: ≤5 min/day review + ~30 min/month topic refill.
- Output quality: readable Arabic code animations, natural Arabic VO, correctly synced captions.
