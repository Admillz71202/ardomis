# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Ardomis is a voice-first personal AI assistant designed to run on a Raspberry Pi (Linux). It listens via microphone, transcribes speech with OpenAI Whisper, sends replies through DeepSeek, and speaks back using ElevenLabs TTS played via `aplay`. The audio stack (`aplay`, `amixer`, `ffmpeg`, `sounddevice`) is Linux-specific — it will not work on Windows.

## Running

```bash
# Production (activates .venv first)
./start_ardomis.sh

# Direct (inside venv)
python -m ardomis_app.app.main
# or
python ardomis.py
```

## Setup

1. Create a virtualenv and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy the env template to `~/ardomis/ardomis.env` and fill in API keys:
   ```bash
   cp ardomis.env.example ~/ardomis/ardomis.env
   ```
   Required keys: `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.
   Optional: `SPOTIFY_ACCESS_TOKEN`, `YOUTUBE_API_KEY`.

3. System dependencies required: `ffmpeg`, `aplay` (alsa-utils), `amixer`, `curl`.

## Configuration

All config is loaded from `~/ardomis/ardomis.env` (not from the repo) by `ardomis_app/config/settings.py`, which exposes every setting as a module-level constant. The `settings.py` module loads the env file at import time — never read env vars directly; always import from `settings`.

Runtime data lives in `~/ardomis/`:
- `memory.db` — SQLite database (chat history, notes, todos, schedule items)
- `state.json` — Persisted `EmotionState`

## Architecture

### Two-Mode FSM (main.py)
The `main()` loop runs a state machine with two modes:

- **`presence`** — Ambient background mode. Polls the mic in short windows (`PRESENCE_LISTEN_POLL_SEC`). Fires periodic chimes via `_presence_interrupt()` on a randomized timer (shortened by boredom/loneliness, lengthened by annoyance/sass). Wakes to chat on hearing a wake word.
- **`chat`** — Active conversation mode. Full listen→reply cycle. Times out back to presence after `CHAT_IDLE_TO_PRESENCE_SEC` seconds of silence.

**Presence chime categories** (selected by weighted random using emotion state): `random_thought`, `check_in`, `question`, `tease`, `observation`, `callback`, `introspect`. Each maps to a distinct DeepSeek prompt template; category weights are driven by `playfulness`, `loneliness`, `curiosity`, `sass`, `warmth`, `boredom`.

### Layer Breakdown

| Layer | Path | Responsibility |
|---|---|---|
| Config | `ardomis_app/config/settings.py` | Loads `~/ardomis/ardomis.env`, exposes constants |
| Core | `ardomis_app/core/emotion.py` | `EmotionState` dataclass, `drift()` (time-based decay toward baselines), `on_interaction()` |
| Core | `ardomis_app/core/memory.py` | `ChatMemory` — 24-message in-RAM deque backed by SQLite, survives restarts |
| Core | `ardomis_app/core/profile.py` | `PersonaProfile` frozen dataclass — Ardomis's persona, speaking style, family context |
| App | `ardomis_app/app/main.py` | Main loop, mode FSM, top-level orchestration |
| App | `ardomis_app/app/runtime.py` | `AudioRuntime` — mic listening, TTS speak+cooldown, dedup |
| App | `ardomis_app/app/prompting.py` | Builds the full DeepSeek system prompt from state + profile |
| App | `ardomis_app/app/prompt_profiles.py` | Rich psychological prompt template (`RICH_PSYCH_PROMPT_V32`) |
| App | `ardomis_app/app/humanizer.py` | Post-processes LLM replies (contractions, strip parens, mood-based vocalizations) |
| App | `ardomis_app/app/text_utils.py` | Text normalization (`norm()`), wake-word detection, garbage/filler filtering |
| App | `ardomis_app/app/constants.py` | Timing constants and phrase lists (wake words, stop/sleep phrases) |
| Services | `ardomis_app/services/audio_io.py` | Mic recording (sounddevice, VAD), ElevenLabs TTS (curl → ffmpeg → aplay), volume control (amixer) |
| Services | `ardomis_app/services/stt_openai.py` | OpenAI Whisper STT (`gpt-4o-transcribe`) |
| Services | `ardomis_app/services/llm_deepseek.py` | DeepSeek chat via OpenAI-compatible SDK; `deep=True` uses `deepseek-reasoner` |
| Services | `ardomis_app/services/command_center.py` | Regex-based intent dispatch for all built-in commands (time, volume, calc, notes, todos, timers, alarms, Spotify, YouTube, weather, maps) |
| Services | `ardomis_app/services/knowledge_vault.py` | SQLite notes + todos store |
| Services | `ardomis_app/services/scheduler_service.py` | SQLite durable timers/alarms/reminders; `due_items()` polled every loop tick |
| Services | `ardomis_app/services/vision_cam.py` | Captures image from Pi camera |
| Services | `ardomis_app/services/vision_openai.py` | Describes captured image via `gpt-4.1-mini` |
| Services | `ardomis_app/services/integration_service.py` | Spotify (Web API search), YouTube (Data API or browser launch), weather, maps |

### Emotion System

`EmotionState` (17 integer fields, 0–100) is loaded from `state.json` at startup and persisted every loop iteration. `drift()` slowly pulls each field back toward its baseline over time — **boredom and loneliness drift toward high baselines** (they grow when idle), while all others drift toward moderate baselines. `on_interaction()` adjusts energy, mood, excitement, etc. on each chat turn and cuts boredom/loneliness sharply. The current state is injected into every system prompt via `mood_line()` and `emotion_meter()`.

New fields added (on top of original 12): `warmth`, `curiosity`, `excitement`, `boredom`, `loneliness`. `build_system_prompt()` in `prompting.py` derives behavioral nudge strings from these fields (e.g. high boredom → flat/impatient tone nudge).

### SQLite Database Tables
All in `~/ardomis/memory.db`:
- `messages` — Chat history (role, content, ts)
- `notes` — Named notes
- `todos` — Task list with done flag
- `schedule_items` — Timers/alarms/reminders with `delivered` flag

### DeepSeek Modes
- **Fast** (`deepseek-chat`, 180 tokens) — Standard replies
- **Deep** (`deepseek-reasoner`, 450 tokens) — Triggered by voice phrases "deep mode", "big brain", or "use reasoner"

## Testing

There are no automated tests. There is a manual scheduler test harness:
```bash
python ardomis_app/scheduler_test_harness.py
# or
python scripts/scheduler_test_harness.py
```

### Wake Word Detection

`said_wake()` in `text_utils.py` uses a 5-stage pipeline: exact token match → substring match → curated `WAKE_VARIANTS` list (common STT misrecognitions like "art miss", "art oh", "arda", "ardoh") → fuzzy single-token Levenshtein match (≤2 distance, tokens ≥5 chars) → fuzzy bigram match (two adjacent tokens merged). Adding new STT misrecognition variants: update `WAKE_VARIANTS` in `constants.py`.

### Extended Command Phrases

Beyond the original patterns, `command_center.py` now handles: `put on / throw on / blast` → Spotify; `pull up / look up on youtube` → YouTube; `jot down / write down / make a note` → notes; `add task / add to list` → todos; `mute / unmute`; `turn up / turn down the volume`.

## Key Design Constraints

- **Text normalization**: All command matching uses `norm()` (lowercased, alphanumeric-only, collapsed spaces). Never compare raw STT text to command strings — always use `norm()` or the helpers in `text_utils.py`.
- **Persona integrity**: The persona definition lives exclusively in `ardomis_app/core/profile.py`. Changes to Ardomis's personality, speaking style, family context, or boundaries belong there.
- **Prompt construction**: The system prompt is always assembled via `build_system_prompt()` in `prompting.py` — never construct ad-hoc system prompts in services.
- **No direct env reads**: All configuration must be imported from `ardomis_app/config/settings.py`, not from `os.getenv()` directly in service files.
