# Screening Room

Paste a foreign story → get one crisp, culturally adapted story (Hindi by default) with every twist kept in order → edit it with comments, chat or the bible → hear it narrated.

## Run

```bash
python3 setup_keys.py   # asks for your keys (hidden), tests them, saves backend/.env
./run.sh                # installs deps, builds the page, serves http://localhost:8000
```

`./run.sh` starts the key setup by itself if the keys are still blank. You can also edit `backend/.env` by hand.

Try it without keys first: set `MOCK_LLM=1` and `MOCK_TTS=1` in `backend/.env`. You get the sample story and synthetic audio, and every screen works.

## Keys to fill in (`backend/.env`)

| Key | What |
|---|---|
| `SILICONFLOW_API_KEY` | Writing model. Model id is `LLM_MODEL` (default `Qwen/Qwen3.8-27B`). |
| `CARTESIA_API_KEY` | Narration. Model is `TTS_MODEL` (default `sonic-3.6`). |
| `VOICE_GRANDMA`, `VOICE_RADIO`, `VOICE_TRAILER`, `VOICE_DEFAULT` | Preset Hindi voices: Siya (warm storyteller, the default), Nisha (broadcast) and Anuj (male narrator). `setup_keys.py` checks they exist on your account and swaps in another Hindi voice if not. To list every Hindi voice: `python3 backend/scripts/list_voices.py hi`. |

If you have a China-region SiliconFlow key, also set `SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1`.

## How it works

```
frontend/   design/Main.dc.html  (design export, untouched)
            logic.js             (live app logic; replaces the prototype's simulation)
            build.py             -> index.html (design template + a few live bindings + logic.js)
backend/app/
  main.py      API + serves the page and audio
  pipeline.py  6 steps shown in the UI: read (chunked) → beats → twists → culture map → write → twist check
  edits.py     chat / comment / bible edits → drafts (Keep / Undo)
  tts.py       per-sentence Cartesia calls → one WAV + exact read-along timings + waveform
  llm.py       SiliconFlow client: structured output only
  schemas.py   the JSON shape of every model call
  prompts.py   prompt text (tune here)
  mock.py      offline demo answers
```

**No thought leakage.** Every model call uses `response_format: json_schema` with `enable_thinking: false`. Any `reasoning_content` is dropped, and stray `<think>` blocks or code fences are stripped. The reply is validated against the schema and retried once if it fails. Each schema has a `notes` field where the model can plan; the backend discards it. Only validated fields reach the page or the voice.

**Long sources.** Sources over 8,000 words are read in parallel chunks, then merged into a story bible, so a full season (up to about 160k words) works.

**Renames are instant.** The story is stored with `{C1}`-style placeholders. Renaming a character or place swaps a dictionary entry; no rewrite is needed.

**Narration.** Each sentence is one Cartesia call, cached on disk. That gives exact read-along timing and per-twist cues: pause, whisper, rising and shock map to silence, speed and volume. Cartesia's emotion tags only work in English. Re-narrating after a small edit only re-synthesises the lines that changed.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/config` | languages, whether keys are set |
| POST | `/api/projects` | `{source, culture, lang}` → `{id}`; starts the pipeline |
| GET | `/api/projects/{id}` | status, step, trace, terms, beats, twists, audio |
| POST | `/api/projects/{id}/edit` | `{instruction, route: story/persona, quote?, beat?}` → draft |
| POST | `/api/projects/{id}/transliterate` | bible rename typed in Latin → target script |
| PUT | `/api/projects/{id}/state` | save on Keep / Undo / bible / voice changes |
| POST | `/api/projects/{id}/narrate` | `{persona, pace, emotions}` → audio URL + timings |

Data (SQLite plus WAVs) is stored in `backend/data/`. Projects resume from the URL (`#p=<id>`).

