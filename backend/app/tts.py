"""Narration: story sentences -> Cartesia -> one stitched WAV + a timing manifest.

One request per sentence lets us (a) time the read-along exactly from sample counts,
(b) apply twist cues per sentence, and (c) cache sentences, so re-narrating after a
small edit only re-synthesises the lines that changed.
"""
import array
import asyncio
import hashlib
import logging
import math
import random
import time
import wave

import httpx

from . import config, keys
from . import display

SR = config.TTS_SAMPLE_RATE

# Persona baseline: speed, volume, and the Cartesia emotion used on un-cued lines.
PERSONAS = {
    "grandma": {"speed": 0.92, "volume": 1.0, "emotion": "calm"},
    "ott":     {"speed": 1.0,  "volume": 1.05, "emotion": "content"},   # natural, engaging, not over-dramatic
    "radio":   {"speed": 1.0,  "volume": 1.1, "emotion": "enthusiastic"},
    "trailer": {"speed": 0.95, "volume": 1.0, "emotion": "mysterious"},
}
# Line cues (from the story's `cue` field). Built to be FELT, not just measured:
#   pre/post  silence around the line (ms)   speed/volume  multipliers on the persona
#   emotion   Cartesia generation_config.emotion (sent per TTS_EMOTION_TAGS)
CUES = {
    # held breath: the line lands slowly, then the room goes quiet before the next one
    "pause":   {"pre": 350,  "post": 1100, "speed": 0.86, "volume": 0.95, "emotion": "anticipation"},
    # a secret: noticeably softer and slower, set apart by short silences
    "whisper": {"pre": 300,  "post": 450,  "speed": 0.84, "volume": 0.55, "emotion": "mysterious"},
    # tension climbing: each consecutive rising line gets faster and louder (see RISE_STEP)
    "rising":  {"pre": 60,   "post": 90,   "speed": 1.08, "volume": 1.22, "emotion": "anxious"},
    # the reveal: a long beat of silence, then a loud, deliberate line, then let it ring
    "shock":   {"pre": 1000, "post": 950,  "speed": 0.92, "volume": 1.6,  "emotion": "surprised"},
}
RISE_STEP = {"speed": 0.06, "volume": 0.12}          # added per consecutive rising line (max 3 steps)
GAP_SENT_MS, GAP_BEAT_MS = 220, 480


def emotion_mode(override: str = "") -> str:
    """all = send emotions in every language (experiment); english = English only; off = never."""
    m = (override or config.TTS_EMOTION_TAGS or "all").lower()
    return m if m in ("all", "english", "off") else "all"


class TTSError(RuntimeError):
    pass


_sem = asyncio.Semaphore(config.TTS_CONCURRENCY)   # shared across all requests


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


async def _synth(client: httpx.AsyncClient, text: str, voice: str, lang: str, speed: float, volume: float, emotion):
    key = hashlib.sha1(f"{config.TTS_MODEL}|{voice}|{lang}|{speed:.3f}|{volume:.3f}|{emotion}|{SR}|{text}".encode()).hexdigest()
    path = config.CACHE_DIR / f"{key}.pcm"
    if path.exists():
        return path.read_bytes()
    if config.MOCK_TTS:
        pcm = _fake_speech(text, speed, volume)
    else:
        body = {
            "model_id": config.TTS_MODEL, "transcript": text, "voice": {"id": voice}, "language": lang,
            "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": SR},
            "generation_config": {"speed": round(speed, 3), "volume": round(volume, 3)},
        }
        if emotion:                            # caller decides per TTS_EMOTION_TAGS (docs: English-only, beta)
            body["generation_config"]["emotion"] = emotion
        pcm, last, attempt = None, None, 0
        while attempt < 8:
            try:
                key = keys.TTS.current()
            except keys.NoLiveKey as e:
                raise TTSError(str(e))
            try:
                r = await client.post(f"{config.CARTESIA_BASE_URL}/tts/bytes", json=body, headers=keys.cartesia_headers(key))
            except httpx.HTTPError as e:
                last = str(e)
            else:
                if r.status_code == 200:
                    pcm = r.content
                    break
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if keys.TTS.check(key, r.status_code, r.text):
                    continue                                # key out of credit / invalid: retired, next key now
                if r.status_code < 500 and r.status_code != 429:
                    break                                   # bad request / bad voice: retrying won't help
            attempt += 1
            # 429 (plan concurrency or rate limit) and 5xx: back off and try again
            await asyncio.sleep(min(12.0, 0.8 * 2 ** attempt) + random.uniform(0, 0.5))
        if pcm is None:
            raise TTSError(f"Cartesia failed: {last}")
    path.write_bytes(pcm)
    return pcm


def _fake_speech(text: str, speed: float, volume: float) -> bytes:
    """Speech-shaped noise for MOCK_TTS so the player, waveform and read-along can be tested offline."""
    secs = max(0.8, len(text) * 0.055 / speed)
    n = int(secs * SR)
    rnd = random.Random(hash(text))
    a = array.array("h")
    syl = rnd.uniform(3.5, 5.0)
    for i in range(n):
        t = i / SR
        env = max(0.0, math.sin(math.pi * syl * t)) ** 2 * (0.6 + 0.4 * math.sin(2 * math.pi * 0.7 * t))
        s = env * (0.5 * math.sin(2 * math.pi * 170 * t) + 0.3 * math.sin(2 * math.pi * 340 * t) + 0.2 * rnd.uniform(-1, 1))
        a.append(int(_clamp(s * 9000 * volume, -32767, 32767)))
    return a.tobytes()


def _silence(ms: int) -> bytes:
    return b"\x00\x00" * int(SR * ms / 1000)


def _levels(pcm: bytes, buckets: int):
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if not a:
        return [0.0] * buckets
    step = max(1, len(a) // buckets)
    out = []
    for i in range(buckets):
        seg = a[i * step:(i + 1) * step:4]
        out.append(math.sqrt(sum(x * x for x in seg) / len(seg)) if seg else 0.0)
    peak = max(out) or 1.0
    return [round(x / peak, 3) for x in out]


_PERSONA_GENDER = {"grandma": "feminine", "radio": "feminine", "trailer": "masculine", "ott": "feminine"}
_lang_voices: dict = {}            # (lang, persona) -> voice id, found once per server run


async def voice_for(persona: str, lang: str) -> str:
    """The voice for this persona in this language.

    1. VOICE_<PERSONA>_<LANG> in .env (e.g. VOICE_GRANDMA_BN) if you set one
    2. Hindi: the persona voices from .env (Siya / Nisha / Anuj by default)
    3. Other languages: a native voice from Cartesia's library for that language,
       matched on gender and preferring narrator/storyteller voices
    4. Fallback: the Hindi persona voice (Sonic 3.6 can speak other languages with it)
    """
    base = config.VOICES.get(persona) or config.VOICE_DEFAULT
    override = config.voice_override(persona, lang)
    if override:
        return override
    if lang == "hi" or config.MOCK_TTS or not config.CARTESIA_API_KEY:
        return base
    key = (lang, persona)
    if key not in _lang_voices:
        _lang_voices[key] = base
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(f"{config.CARTESIA_BASE_URL}/voices", params={"language": lang, "limit": 100},
                                headers=keys.cartesia_headers(keys.TTS.current()))
            voices = r.json().get("data", []) if r.status_code == 200 else []
            taken = {v for (l, p_), v in _lang_voices.items() if l == lang and p_ != persona}

            def score(v):
                d = f"{v.get('name', '')} {v.get('description', '')} {v.get('tagline', '')}".lower()
                return ((v.get("gender") == _PERSONA_GENDER.get(persona)) * 4 + any(w in d for w in ("narrat", "story")) * 3
                        + any(w in d for w in ("warm", "calm")) * (persona == "grandma")
                        + any(w in d for w in ("broadcast", "host", "news")) * (persona == "radio")
                        + any(w in d for w in ("deep", "dramatic", "intense")) * (persona == "trailer")
                        - (v["id"] in taken) * 2)
            if voices:
                best = max(voices, key=score)
                _lang_voices[key] = best["id"]
                logging.getLogger("tts").info("voice for %s/%s: %s (%s)", lang, persona, best.get