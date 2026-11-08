"""All tunables in one place. Keys and IDs come from environment / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # screening-room/
load_dotenv(ROOT / "backend" / ".env")


def _f(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _keys(prefix: str, slots: int = 9) -> list:
    """Ordered key list: PREFIX_1..PREFIX_9, then legacy PREFIX, then comma-separated PREFIXS. Duplicates dropped."""
    found = [_f(f"{prefix}_{i}", "") for i in range(1, slots + 1)] + [_f(prefix, "")]
    found += [k.strip() for k in _f(prefix + "S", "").replace("\n", ",").split(",")]
    return list(dict.fromkeys(k for k in found if k))


# ---------- LLM (SiliconFlow, OpenAI-compatible) ----------
SILICONFLOW_API_KEYS = _keys("SILICONFLOW_API_KEY")          # tried in order; see app/keys.py
SILICONFLOW_API_KEY = SILICONFLOW_API_KEYS[0] if SILICONFLOW_API_KEYS else ""   # "is any key set?"
SILICONFLOW_BASE_URL = _f("SILICONFLOW_BASE_URL", "https://api.siliconflow.com/v1")
LLM_MODEL = _f("LLM_MODEL", "Qwen/Qwen3.8-27B")
LLM_TIMEOUT_S = float(_f("LLM_TIMEOUT_S", "240"))
LLM_CONCURRENCY = int(_f("LLM_CONCURRENCY", "6"))
# "json_schema" (strict structured output) or "json_object" (JSON mode + schema in prompt).
# The client falls back to json_object automatically if the provider rejects json_schema.
LLM_RESPONSE_MODE = _f("LLM_RESPONSE_MODE", "json_schema")
# Stream model output so the Adapt page can show it being written (set 0 to disable)
LLM_STREAM = _f("LLM_STREAM", "1") == "1"

# ---------- TTS (Cartesia) ----------
CARTESIA_API_KEYS = _keys("CARTESIA_API_KEY")
CARTESIA_API_KEY = CARTESIA_API_KEYS[0] if CARTESIA_API_KEYS else ""
CARTESIA_BASE_URL = _f("CARTESIA_BASE_URL", "https://api.cartesia.ai")
CARTESIA_VERSION = _f("CARTESIA_VERSION", "2026-08-14")
TTS_MODEL = _f("TTS_MODEL", "sonic-3.6")
TTS_SAMPLE_RATE = int(_f("TTS_SAMPLE_RATE", "24000"))
TTS_CONCURRENCY = int(_f("TTS_CONCURRENCY", "2"))   # Cartesia free/starter plans allow 2 at once
# Cartesia emotion tags: all = every language (experiment), english = English only (Cartesia docs), off
TTS_EMOTION_TAGS = _f("TTS_EMOTION_TAGS", "all")
# One voice per narrator persona; VOICE_DEFAULT is used when a persona voice is blank.
VOICE_DEFAULT = _f("VOICE_DEFAULT", "")
VOICES = {
    "grandma": _f("VOICE_GRANDMA", ""),
    "radio": _f("VOICE_RADIO", ""),
    "trailer": _f("VOICE_TRAILER", ""),
}



def voice_override(persona: str, lang: str) -> str:
    """Optional per-language voice, e.g. VOICE_GRANDMA_BN=<id> or VOICE_DEFAULT_TA=<id>."""
    return _f(f"VOICE_{persona.upper()}_{lang.upper()}", "") or _f(f"VOICE_DEFAULT_{lang.upper()}", "")


# ---------- Pipeline ----------
CHUNK_WORDS = int(_f("CHUNK_WORDS", "8000"))
CHUNK_OVERLAP_WORDS = int(_f("CHUNK_OVERLAP_WORDS", "300"))
MAX_SOURCE_WORDS = int(_f("MAX_SOURCE_WORDS", "160000"))

# ---------- Dev switches ----------
# MOCK_LLM=1 / MOCK_TTS=1 run the whole app without keys (canned story, synthetic audio).
MOCK_LLM = _f("MOCK_LLM", "0") == "1"
MOCK_TTS = _f("MOCK_TTS", "0") == "1"

DATA_DIR = Path(_f("DATA_DIR", str(ROOT / "backend" / "data")))
AUDIO_DIR = DATA_DIR / "audio"
CACHE_DIR = DATA_DIR / "tts_cache"
DB_PATH = DATA_DIR / "screening_room.db"
FRONTEND_DIR = ROOT / "frontend"
for d in (DATA_DIR, AUDIO_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------- Languages ----------
# code -> display name, Cartesia language code. Script fonts are handled in the frontend.
LANGS = {   # code -> display name, Cartesia language code. Must match qwen_prompts.LANGUAGE_PROFILES.
    "hi": ("Hindi", "hi"), "bn": ("Bengali", "bn"), "pa": ("Punjabi", "pa"),
    "mr": ("Marathi", "mr"), "gu": ("Gujarati", "gu"), "or": ("Odia", "or"), "ta": ("Tamil", "ta"),
    "te": ("Telugu", "te"), "kn": ("Kannada", "kn"), "ml": ("Malayalam", "ml"),
}
CULTURES = {"IN": "India"}
