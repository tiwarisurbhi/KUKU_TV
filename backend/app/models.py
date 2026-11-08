"""Pydantic mirrors of the JSON schemas in qwen_prompts.py.

The schema SENT to the model is always qwen_prompts' own (every field required, strict).
These models only VALIDATE what comes back. Fields the app needs to work are required;
cosmetic ones default, so one forgotten field never fails a whole run.
"""
from typing import List, Literal

from pydantic import BaseModel

Cue = Literal["none", "pause", "whisper", "rising", "shock"]
Role = Literal["none", "setup", "reveal"]
Gender = Literal["female", "male", "unknown"]


class _M(BaseModel):
    model_config = {"extra": "ignore"}


# 1 chunk_notes
class Rel(_M):
    to: str = ""
    relation: str = ""


class NoteChar(_M):
    name: str
    aliases: List[str] = []
    gender: Gender = "unknown"
    role: str = ""
    description: str = ""
    relationships: List[Rel] = []


class NoteEntity(_M):
    name: str
    type: str = "other"
    significance: str = ""


class NoteEvent(_M):
    episode: int = 0
    summary: str
    characters: List[str] = []
    is_reveal: bool = False


class Secret(_M):
    setup: str = ""
    setup_episode: int = 0
    payoff: str = ""
    payoff_episode: int = 0


class ChunkNotes(_M):
    chunk_index: int = 0
    characters: List[NoteChar] = []
    entities: List[NoteEntity] = []
    events: List[NoteEvent] = []
    secrets: List[Secret] = []
    open_threads: List[str] = []
    notes: str = ""


# 2 bible
class BibleChar(_M):
    id: str
    name: str
    aliases: List[str] = []
    gender: Gender = "unknown"
    role: str = ""
    arc: str = ""
    traits: List[str] = []


class BibleEntity(_M):
    id: str
    name: str
    type: str = "other"
    significance: str = ""


class BibleBeat(_M):
    id: str
    title: str = ""
    summary: str
    episodes: str = ""
    character_ids: List[str] = []
    entity_ids: List[str] = []
    twist_ids: List[str] = []


class BibleTwist(_M):
    id: str
    setup: str = ""
    reveal: str = ""
    setup_beat: str
    reveal_beat: str
    impact: str = ""
    kind: str = ""


class Bible(_M):
    title: str = ""
    logline: str = ""
    genre: str = ""
    tone: str = ""
    characters: List[BibleChar]
    entities: List[BibleEntity] = []
    beats: List[BibleBeat]
    twists: List[BibleTwist] = []
    core_must_keep: List[str] = []
    notes: str = ""


# 3 adaptation
class Setting(_M):
    era: str = ""
    region: str = ""
    social_world: str = ""
    why: str = ""


class AdaptChar(_M):
    id: str
    source_name: str = ""
    name_native: str
    name_short: str = ""
    name_latin: str = ""
    gender: Gender = "unknown"
    adapted_role: str = ""
    speech_style: str = ""
    why: str = ""


class AdaptEntity(_M):
    id: str
    source_name: str = ""
    name_native: str
    name_short: str = ""
    name_latin: str = ""
    type: str = "other"
    why: str = ""


class GlossaryItem(_M):
    source_term: str
    target_term: str


class PlotAdj(_M):
    source_detail: str = ""
    adapted_detail: str = ""
    beat_ids: List[str] = []
    why: str = ""


class Adaptation(_M):
    setting: Setting = Setting()
    characters: List[AdaptChar]
    entities: List[AdaptEntity] = []
    glossary: List[GlossaryItem] = []
    plot_adjustments: List[PlotAdj] = []
    keep_unchanged: List[str] = []
    notes: str = ""


# 4/6 story + story_edit, 5 twist_rewrite
class Line(_M):
    text: str
    cue: Cue = "none"
    twist_id: str = ""
    twist_role: Role = "none"


class Beat(_M):
    id: str
    lines: List[Line]


class Story(_M):
    title: str = ""
    beats: List[Beat]
    notes: str = ""


class TwistRewrite(_M):
    beats: List[Beat] = []
    notes: str = ""


# 7 chat_router
class Action(_M):
    type: Literal["rename", "persona", "pace", "story_edit", "question", "unclear"]
    target_id: str = ""
    new_name_native: str = ""
    new_name_latin: str = ""
    persona: Literal["", "ott", "grandma", "radio", "trailer"] = ""
    pace: Literal["", "slower", "faster"] = ""
    instruction: str = ""


class Router(_M):
    actions: List[Action] = []
    reply: str = ""
    notes: str = ""


# 8 transliterate
class Translit(_M):
    name_native: str
    name_short: str = ""
    name_latin: str = ""
    notes: str = ""


# voice_pick (voice_prompts.py)
class VoicePick(_M):
    voice_id: str
    backup_ids: List[str] = []
    reason: str = ""
    notes: str = ""


STEP_MODELS = {"chunk_notes": ChunkNotes, "bible": Bible, "adaptation": Adaptation, "story": Story,
               "twist_rewrite": TwistRewrite, "story_edit": Story, "chat_router": Router, "transliterate": Translit,
               "voice_pick": VoicePick}
