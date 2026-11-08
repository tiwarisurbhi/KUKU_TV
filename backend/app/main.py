"""Screening Room API + static frontend."""
import asyncio
import copy
import logging
import uuid
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, display, edits, keys, live, pipeline, tts, voices
from . import qwen_prompts as qp
from .llm import LLMError
from .models import Story

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = FastAPI(title="Screening Room")
_tasks = set()

PUBLIC = ("id", "status", "step", "trace", "error", "culture", "lang", "persona", "pace", "version", "audio", "words")


def _get(pid: str) -> dict:
    p = db.load(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def public(p: dict) -> dict:
    out = {k: p.get(k) for k in PUBLIC}
    out["live"] = live.LIVE.get(p["id"])         # what the model is writing right now (Adapt page only)
    if p.get("status") == "ready":
        if "story" not in p or "adaptation" not in p:   # project from before the qwen_prompts integration
            out.update(status="error", error="This project was made with an older version. Craft it again.")
            return out
        ls = display.lines(p)
        out.update(
            title=display.title(p), lines=ls, terms=display.terms(p), twists=display.twists(p, ls),
            glossary=p["adaptation"].get("glossary", []), story=p["story"],
            names={k: {f: v.get(f, "") for f in ("name_native", "name_short", "name_latin")}
                   for k, v in display.name_table(p["adaptation"]).items()},
            lint={k: len(v) for k, v in (p.get("lint") or {}).items()}, voice=p.get("voice"))
    return out


@app.exception_handler(LLMError)
async def _llm_err(_, e):
    return JSONResponse({"detail": f"The writing model failed: {e}"}, status_code=502)


@app.exception_handler(keys.NoLiveKey)
async def _nokey_err(_, e):
    return JSONResponse({"detail": str(e)}, status_code=502)


@app.exception_handler(tts.TTSError)
async def _tts_err(_, e):
    return JSONResponse({"detail": str(e)}, status_code=502)


# ---------- models ----------
class CreateReq(BaseModel):
    source: str = Field(min_length=20)
    culture: str = "IN"
    lang: str = "hi"


class EditReq(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    route: Literal["story", "persona"] = "story"        # UI hint only; chat_router decides
    quote: str = ""
    beat: str = ""


class TranslitReq(BaseModel):
    key: str
    value: str = Field(min_length=1, max_length=80)


class NameFields(BaseModel):
    name_native: str = ""
    name_short: str = ""
    name_latin: str = ""


class StateReq(BaseModel):
    story: Optional[dict] = None
    names: Optional[Dict[str, NameFields]] = None
    cues: Optional[Dict[str, Literal["none", "pause", "whisper", "rising", "shock"]]] = None   # sid -> cue
    persona: Optional[Literal["ott", "grandma", "radio", "trailer"]] = None
    pace: Optional[float] = None


class VoicePickReq(BaseModel):
    persona: Literal["ott", "grandma", "radio", "trailer"] = "ott"


class VoiceChooseReq(BaseModel):
    voice_id: str


class NarrateReq(BaseModel):
    persona: Literal["ott", "grandma", "radio", "trailer"] = "ott"
    pace: float = 1.0
    emotion_tags: str = ""                                # "", "all", "english", "off" (A/B test)


# ---------- routes ----------
@app.get("/api/config")
def get_config():
    return {"langs": {k: v[0] for k, v in config.LANGS.items()}, "cultures": config.CULTURES,
            "llm_ready": bool(keys.LLM.live()) or config.MOCK_LLM,
            "tts_ready": (bool(keys.TTS.live()) and bool(config.VOICE_DEFAULT or all(config.VOICES.values()))) or config.MOCK_TTS,
            "keys": {"llm": keys.LLM.summary(), "tts": keys.TTS.summary()},   # counts only, never the keys
            "mock": {"llm": config.MOCK_LLM, "tts": config.MOCK_TTS}, "model": config.LLM_MODEL,
            "tts_model": config.TTS_MODEL, "emotion_tags": config.TTS_EMOTION_TAGS}


@app.post("/api/projects")
async def create(req: CreateReq):
    if req.lang not in qp.LANGUAGE_PROFILES or req.lang not in config.LANGS:
        raise HTTPException(400, f"Unsupported language {req.lang}. Supported: {', '.join(qp.LANGUAGE_PROFILES)}")
    words = len(req.source.split())
    if words > config.MAX_SOURCE_WORDS:
        raise HTTPException(400, f"Source is {words:,} words; the limit is {config.MAX_SOURCE_WORDS:,}.")
    p = {"id": uuid.uuid4().hex[:12], "source": req.source, "culture": req.culture, "lang": req.lang,
         "status": "queued", "step": 0, "trace": [""] * 6, "persona": "ott", "pace": 1.0, "words": words}
    db.save(p)
    t = asyncio.create_task(pipeline.run(p))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
    return {"id": p["id"]}


@app.get("/api/projects/{pid}")
def read(pid: str):
    return public(_get(pid))


def _ready(pid: str) -> dict:
    p = _get(pid)
    if p.get("status") != "ready" or "story" not in p:
        raise HTTPException(409, "Story is not ready yet")
    return p


@app.post("/api/projects/{pid}/edit")
async def edit(pid: str, req: EditReq):
    p = _ready(pid)
    d = await edits.handle(p, req.instruction, req.quote, req.beat)
    db.save(p)                                            # keeps the short chat history for the router
    return d


@app.post("/api/projects/{pid}/transliterate")
async def translit(pid: str, req: TranslitReq):
    p = _ready(pid)
    if req.key not in display.name_table(p["adaptation"]):
        raise HTTPException(404, "Unknown name id")
    return await edits.transliterate(p, req.key, req.value)


@app.put("/api/projects/{pid}/state")
def put_state(pid: str, req: StateReq):
    """Keep / Undo / bible renames / cue changes / voice settings. Structure is validated; returns the new view."""
    p = _ready(pid)
    changed = False
    if req.story is not None:
        st = Story.model_validate(req.story).model_dump(exclude={"notes"})
        if [b["id"] for b in st["beats"]] != [b["id"] for b in p["story"]["beats"]]:
            raise HTTPException(400, "Beats must keep the same ids and order")
        p["story"], changed = st, True
    if req.names:
        known = display.name_table(p["adaptation"])
        if not set(req.names) <= set(known):
            raise HTTPException(400, "Unknown name id")
        p["adaptation"] = edits._with_names(p["adaptation"], {k: v.model_dump() for k, v in req.names.items()})
        changed = True
    if req.cues:
        st = copy.deepcopy(p["story"])
        for b in st["beats"]:
            for i, ln in enumerate(b["lines"]):
                c = req.cues.get(f"{b['id']}-{i}")
                if c and not (ln["twist_role"] == "reveal" and c != "shock"):   # a reveal stays a shock (lint rule)
                    ln["cue"] = c
        p["story"], changed = st, True
    if req.persona is not None:
        p["persona"] = req.persona
    if req.pace is not None:
        p["pace"] = min(1.2, max(0.8, req.pace))
    if changed:
        p["lint"] = qp.lint_story(p["story"], p["bible"], p["adaptation"], p["lang"])
        p["version"] = (p.get("version") or 1) + 1
        db.add_version(pid, p["version"], {"story": p["story"], "adaptation": p["adaptation"]})
    db.save(p)
    return public(p)


@app.post("/api/projects/{pid}/voice/pick")
async def voice_pick(pid: str, req: VoicePickReq):
    """Re-cast the narrator (persona switch, or 'pick again')."""
    p = _ready(pid)
    p["voice"] = await voices.pick(p, req.persona)
    p["persona"] = req.persona
    db.save(p)
    return p["voice"]


@app.post("/api/projects/{pid}/voice")
def voice_choose(pid: str, req: VoiceChooseReq):
    p = _ready(pid)
    try:
        p["voice"] = voices.choose(p, req.voice_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.save(p)
    return p["voice"]


@app.get("/api/voices/{voice_id}/preview")
async def voice_preview(voice_id: str):
    """Preview clip, fetched once from Cartesia (or synthesized in mock mode)