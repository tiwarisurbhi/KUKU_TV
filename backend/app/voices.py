"""Narrator casting: pick the best Cartesia voice for a story.

1. Catalog   Cartesia GET /voices per language (paged, with preview URLs), cached in SQLite, refreshed daily.
2. Filter    in code, exact: the story's language, native speakers first, gender from the persona.
3. Rank      in code (native, gender, narration-ish descriptions up; support/IVR voices down) -> top 12 finalists.
4. Cast      Qwen (voice_prompts.VOICE_PICK) chooses among the finalists for the story's setting, tone and
             persona. Its id must be in the list; otherwise the top-ranked voice is used.
The result is stored on the project and shown in the Voice tab with previews and a "change voice" list.
"""
import logging
import time

import httpx

from . import config, db, keys, llm, persona_prompts, voice_prompts
from . import qwen_prompts as qp

log = logging.getLogger("voices")
TTL_S = 24 * 3600
FINALISTS = 12
PERSONA_GENDER = {"grandma": "feminine", "radio": None, "trailer": "masculine", "ott": None}   # None = either
GOOD = ("narrat", "story", "storytell", "drama", "audiobook", "broadcast", "host", "radio", "documentary",
        "expressive", "warm", "deep", "dramatic", "theatr", "rich", "mature", "intense")
BAD = ("customer", "support", "assistant", "ivr", "sales", "agent", "receptionist", "service", "virtual", "call center")
PERSONA_WORDS = {"grandma": ("warm", "mature", "elder", "gentle", "calm", "soft", "grand", "maternal", "story"),
                 "radio": ("clear", "expressive", "broadcast", "host", "theatr", "radio", "lively", "news"),
                 "trailer": ("deep", "intense", "dramatic", "bold", "trailer", "cinematic", "gravel", "authoritative"),
                 "ott": ("natural", "expressive", "engaging", "conversational", "story", "narrat", "clear", "modern", "warm")}


def _headers() -> dict:
    return keys.cartesia_headers(keys.TTS.current())


def _norm(v: dict, lang: str) -> dict:
    accents = v.get("accents") or []
    native = any(a.get("is_native") and str(a.get("locale", "")).lower().startswith(lang) for a in accents)
    if not accents and v.get("language") == lang:
        native = True
    acc = ", ".join(sorted({a.get("accent") or a.get("locale") or "" for a in accents
                            if str(a.get("locale", "")).lower().startswith(lang)} - {""})) or (v.get("country") or "")
    return {"id": v["id"], "name": v.get("name", ""), "tagline": v.get("tagline") or "", "description": (v.get("description") or "")[:300],
            "gender": v.get("gender") or "", "accent": acc, "native": native, "country": v.get("country") or "",
            "preview_url": v.get("preview_file_url") or ""}


def _mock_catalog(lang: str) -> list:
    base = [("m1", "Asha", "feminine", "Warm storyteller", "A warm, mature voice for bedtime stories and narration."),
            ("m2", "Kavya", "feminine", "Bright host", "Clear, expressive radio host with theatrical energy."),
            ("m3", "Veer", "masculine", "Trailer voice", "Deep, intense, dramatic voice for cinematic trailers."),
            ("m4", "Neel", "masculine", "Calm narrator", "Gentle documentary narrator with a steady pace."),
            ("m5", "Riya", "feminine", "Support agent", "Friendly customer support voice."),
            ("m6", "Dev", "masculine", "IVR voice", "Crisp voice for IVR menus.")]
    return [{"id": f"{lang}-{i}", "name": n, "tagline": t, "description": d, "gender": g, "accent": f"{lang}-IN",
             "native": True, "country": "IN", "preview_url": ""} for i, n, g, t, d in base]


async def catalog(lang: str, refresh: bool = False) -> list:
    """All Cartesia voices for a language (normalized), cached in SQLite for TTL_S."""
    cached, fetched = db.get_voices(lang)
    if cached is not None and not refresh and time.time() - fetched < TTL_S:
        return cached
    if config.MOCK_TTS or not config.CARTESIA_API_KEY:
        voices = _mock_catalog(lang)
        db.put_voices(lang, voices)
        return voices
    voices, after = [], None
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            for _ in range(20):                                  # paging guard
                params = {"language": lang, "limit": 100, "expand[]": "preview_file_url"}
                if after:
                    params["starting_after"] = after
                for _ in range(len(keys.TTS.keys) + 1):           # a dead key is retired, then the next one is tried
                    key = keys.TTS.current()
                    r = await c.get(f"{config.CARTESIA_BASE_URL}/voices", params=params, headers=keys.cartesia_headers(key))
                    if not keys.TTS.check(key, r.status_code, r.text):
                        break
                r.raise_for_status()
                data = r.json()
                page = data.get("data", [])
                voices += [_norm(v, lang) for v in page]
                if not data.get("has_more") or not page:
                    break
                after = data.get("next_page") or page[-1]["id"]
    except (httpx.HTTPError, keys.NoLiveKey) as e:
        log.warning("voice catalog fetch failed for %s: %s", lang, e)
        return cached or []
    voices = list({v["id"]: v for v in voices}.values())
    db.put_voices(lang, voices)
    log.info("voice catalog %s: %d voices (%d native)", lang, len(voices), sum(v["native"] for v in voices))
    return voices


def rank(voices: list, persona: str) -> list:
    """Exact filters + a simple score. Gender is a hard filter when the persona has one (falls back if empty)."""
    want = PERSONA_GENDER.get(persona)
    pool = [v for v in voices if not want or v["gender"] == want] or voices
    words = PERSONA_WORDS.get(persona, ())

    def score(v):
        d = f"{v['name']} {v['tagline']} {v['description']}".lower()
        return (v["native"] * 6 + sum(w in d for w in GOOD) * 1.5 + sum(w in d for w in words) * 2
                - sum(w in d for w in BAD) * 4)
    return sorted(pool, key=score, reverse=True)


def _setting_text(p: dict) -> str:
    s = (p.get("adaptation") or {}).get("setting") or {}
    return ", ".join(x for x in (s.get("era"), s.get("region"), s.get("social_world")) if x) or "contemporary India"


async def pick(p: dict, persona: str) -> dict:
    """Cast the narrator for this story + persona. Never raises: falls back to ranking, then to .env voices."""
    lang = config.LANGS[p["lang"]][1]
    base = {"persona": persona, "lang": lang}
    voices = await catalog(lang)
    if not voices:
        vid = config.voice_override(persona, lang) or config.VOICES.get(persona) or config.VOICE_DEFAULT
        return {**base, "voice_id": vid, "name": "", "reason": "No voices listed for this language; using the voice from settings.",
                "by": "settings", "backup_ids": [], "finalists": [], "pool": 0}
    ranked = rank(voices, persona)
    finalists = ranked[:FINALISTS]
    by_id = {v["id"]: v for v in finalists}
    chosen, reason, by, backups = finalists[0]["id"], "Best match on language, gender and narration style.", "ranked", []
    try:
        bible = p.get("bible") or {}
        table = "\n".join(f"{v['id']} | {v['name']} | {v['gender'] or '-'} | {v['accent'] or '-'} | "
                          f"{'yes' if v['native'] else 'no'} | {v['tagline'] or '-'} | {v['description'] or '-'}" for v in finalists)
        req = voice_prompts.build_voice_request(p["lang"], genre=bible.get("genre", ""), tone=bible.get("tone", ""),
                                                logline=bible.get("logline", ""), setting=_setting_text(p),
                                                persona_guide=persona_prompts.guide(persona, p["lang"])[:1800], voices=table)
        r = await llm.call_request("voice_pick", req, p["lang"])
        if r.voice_id in by_id:
            chosen, reason, by = r.voice_id, r.reason.strip() or reason, "qwen"
            backups = [b for b in r.backup_ids if b in by_id and b != chosen][:2]
        else:
            log.warning("voice_pick returned an id not in the finalists (%s); using top-ranked", r.voice_id)
    except Exception as e:                                   # casting must never block a story
        log.warning("voice_pick failed, using top-ranked voice: %s", e)
    v = by_id[chosen]
    return {**base, "voice_id": chosen, "name": v["name"], "gender": v["gender"], "accent": v["accent"],
            "native": v["native"], "tagline": v["tagline"], "reason": reason, "by": by, "backup_ids": backups,
            "pool": len(ranked), "native_count": sum(x["native"] for x in voices),
            "finalists": [{k: x[k] for k in ("id", "name", "gender", "accent", "native", "tagline")} for x in finalists]}


def choose(p: dict, voice_id: str) -> dict:
    """The writer picked a voice from the finalists."""
    cur = p.get("voice") or {}
    f = next((x for x in cur.get("finalists", []) if x["id"] == voice_id), None)
    if not f:
        raise ValueError("That voice is not in this story's list")
    return {**cur, "voice_id": voice_id, "name": f["name"], "gender": f["gender"], "accent": f["accent"],
            "native": f["native"], "tagline": f["tagline"], "reason": "Chosen by the writer.", "by": "writer"}


SAMPLE_LINE = {   # spoken when a voice has no catalog preview clip
    "hi": "नमस्ते, आज मैं आपको एक ऐसी कहानी सुनाऊँगी, जिसका अंत आप सोच भी नहीं सकते।",
    "bn": "নমস্কার, আজ তোমাদের এমন একটা গল্প শোনাব, যার শেষটা তোমরা ভাবতেও পারবে না।",
    "pa": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਅੱਜ ਮੈਂ ਤੁਹਾਨੂੰ ਇੱਕ ਅਜਿਹੀ ਕਹਾਣੀ ਸੁਣਾਵਾਂਗੀ, ਜਿਸਦਾ ਅੰਤ ਤੁਸੀਂ ਸੋਚ ਵੀ ਨਹੀਂ ਸਕਦੇ।",
    "mr": "नमस्कार, आज मी तुम्हाला अशी एक गोष्ट सांगणार आहे, जिचा शेवट तुम्ही विचारही करू शकणार नाही.",
    "gu": "નમસ્તે, આજે હું તમને એવી એક વાર્તા કહીશ, જેનો અંત તમે વિચારી પણ નહીં શકો.",
    "or": "ନମସ୍କାର, ଆଜି ମୁଁ ଆପଣଙ୍କୁ ଏମିତି ଏକ ଗଳ୍ପ ଶୁଣାଇବି, ଯାହାର ଶେଷ ଆପଣ ଭାବି ବି ପାରିବେନି।",
    "ta": "வணக்கம், இன்னைக்கு நான் உங்களுக்கு ஒரு கதை சொல்லப் போறேன், அதோட முடிவை நீங்க நினைச்சுக்கூட பார்க்க முடியாது.",
    "te": "నమస్కారం, ఈ రోజు నేను మీకు ఒక కథ చెప్పబోతున్నాను, దాని ముగింపు మీరు ఊహించను కూడా ఊహించలేరు.",
    "kn": "ನಮಸ್ಕಾರ, ಇವತ್ತು ನಾನು ನಿಮಗೆ ಒಂದು ಕಥೆ ಹೇಳ್ತೀನಿ, ಅದರ ಕೊನೆಯನ್ನು ನೀವು ಊಹಿಸೋಕೂ ಸಾಧ್ಯವಿಲ್ಲ.",
    "ml": "നമസ്കാരം, ഇന്ന് ഞാൻ നിങ്ങളോട് ഒരു കഥ പറയാം, അതിന്റെ അവസാനം നിങ്ങൾക്ക് ഊഹിക്കാൻ പോലും പറ്റില്ല.",
}


def lang_of(voice_id: str) -> str:
    for code in config.LANGS:
        cached, _ = db.get_voices(config.LANGS[code][1])
        if any(v["id"] == voice_id for v in cached or []):
            return config.LANGS[code][1]
    return ""


async def preview_url(voice_id: str) -> str:
    for lang in config.LANGS:
        cached, _ = db.get_voices(config.LANGS[lang][1])
        for v in cached or []:
            if v["id"] == voice_id:
                return v.get("preview_url") or ""
    return ""
