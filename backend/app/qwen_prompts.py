"""
qwen_prompts.py — every LLM prompt in the Kuku Adaptation Studio (Screening Room)
backend, tuned for SiliconFlow `Qwen/Qwen3.8-27B`.
English source show -> conversational Indian-language story (Hindi default; Bengali,
Punjabi, Marathi, Gujarati supported through LANGUAGE_PROFILES).

v2 (2026-11-07) — after reviewing real Hindi output:
  * Register is now SPOKEN, CODE-MIXED, NATIVE SCRIPT: Hinglish written in Devanagari,
    Benglish in Bengali script, etc. Everyday English words are welcome (प्लान, क्रू,
    प्रपोज़); formal / Sanskritized words are banned with explicit swap lists.
  * Language is a parameter (lang="hi" | "bn" | "pa" | "mr" | "gu"); each profile carries
    its script, punctuation, gender rule, case-ending style, swaps and sample lines.
  * Adaptation now returns a short spoken name per character (मीरा, सैंडी) plus a
    glossary of recurring terms (crew -> क्रू, never कर्नल) that the story must use.
  * No Western name may survive adaptation; anything unnamed in the cast sheet is
    described generically instead of transliterated (no "टोर्टुगा", "HMS इंटरसेप्टर").
  * swap_names(): first mention = full name, later mentions = short name, and fixes
    fused case endings for Bengali / Gujarati after insertion.
  * lint_story(): checks the target script (any other script = error), digits, heavy
    words, sentence enders, raw names, placeholders and twist setup/reveal.

WHERE THE LLM IS CALLED (one section per call site below)
    1. CHUNK_NOTES     each ~8k-word slice of the season -> English story notes   (parallel)
    2. BIBLE           all chunk notes -> one canonical bible (C/E ids, 8-14 beats, twists)
    3. ADAPTATION      bible -> Indian names (full + short), places, setting, glossary
    4. STORY           bible + adaptation -> spoken-language story, {C1}/{E1} placeholders
    5. TWIST_REWRITE   deterministic twist check failed -> rewrite only the failing beats (1 try)
    6. STORY_EDIT      chat / comment edit -> regenerate all beats, ids locked, copy the rest verbatim
    7. CHAT_ROUTER     writer's chat message -> rename / persona / pace / story_edit / question
    8. TRANSLITERATE   name typed in Latin (bible inline rename) -> target script
    9. JSON_REPAIR     Pydantic validation failed -> one repair turn (follow-up message)
    Narration has no LLM step (story lines go straight to Cartesia).

DESIGN RULES APPLIED TO EVERY PROMPT
  * Instructions in English; the target language appears only as examples of the output.
  * Analysis steps (1-3) work in English; the target language is written once, in step 4.
  * System = role, numbered rules, JSON shape, tiny example. User = inputs in <tags>,
    then a REMINDER repeating the rules most likely to be forgotten in a long context.
  * Strict-mode-friendly schemas: all fields required, no null/anyOf; "" / [] = none.
  * `notes` field in every schema as a pressure valve; the backend discards it.
  * CJK characters banned explicitly (Qwen sometimes leaks them).
  * Dialogue in curly single quotes ‘ ’ so the model never escapes " inside JSON.

TEMPLATE SYNTAX: <<name>> slots, filled by render(). Not str.format, because prompts
contain {C1} placeholders and JSON braces.

FIELD NAMES are the contract these prompts assume; reconcile with the built Pydantic
models (line-level `cue` / `twist_id` / `twist_role`, `name_native` / `name_short`).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

MODEL = "Qwen/Qwen3.8-27B"

# If <think> blocks ever come back despite enable_thinking=false, try " /no_think"
# (Qwen3 soft switch) — verify on a real call first.
NO_THINK_SUFFIX = ""

# ---------------------------------------------------------------------------
# Sampling per step (Qwen non-thinking guidance ~ temp 0.7 / top_p 0.8 / top_k 20).
# presence_penalty <= 1.0: higher values can cause language mixing in Qwen.
# Indic scripts cost more tokens per word than English, so story steps get room.
# ---------------------------------------------------------------------------
SAMPLING: dict[str, dict[str, Any]] = {
    "chunk_notes":   {"temperature": 0.2, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.0, "max_tokens": 4000},
    "bible":         {"temperature": 0.3, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.0, "max_tokens": 6000},
    "adaptation":    {"temperature": 0.6, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.0, "max_tokens": 5000},
    "story":         {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.5, "max_tokens": 14000},
    "twist_rewrite": {"temperature": 0.5, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.3, "max_tokens": 6000},
    "story_edit":    {"temperature": 0.4, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.0, "max_tokens": 14000},
    "chat_router":   {"temperature": 0.0, "top_p": 1.0, "top_k": 1,  "presence_penalty": 0.0, "max_tokens": 600},
    "transliterate": {"temperature": 0.0, "top_p": 1.0, "top_k": 1,  "presence_penalty": 0.0, "max_tokens": 160},
    "json_repair":   {"temperature": 0.0, "top_p": 1.0, "top_k": 1,  "presence_penalty": 0.0, "max_tokens": 14000},
}


def render(template: str, **kw: Any) -> str:
    """Fill <<name>> slots. Dicts/lists are dumped as compact JSON. Missing slot = error."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in kw:
            raise KeyError(f"missing prompt variable: {key}")
        v = kw[key]
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        return "None" if v in (None, "") else str(v)
    return re.sub(r"<<(\w+)>>", sub, template)


# ===========================================================================
# LANGUAGE PROFILES
# Everything language-specific lives here, so adding a language = adding a profile.
#   case_style "separate": postpositions are separate words  ({C1} ने)      — hi, pa
#   case_style "attached": case endings fuse with the noun   ({C1}কে, {C1}এর) — bn, mr, gu
# Sample lines are what the model imitates: have a native speaker review a new profile
# before shipping it. ta/te/kn/ml are not included yet for that reason (spoken and
# written Tamil in particular differ a lot, and the samples must be right).
# ===========================================================================
LANGUAGE_PROFILES: dict[str, dict[str, Any]] = {
    "hi": {
        "name": "Hindi", "mix_name": "Hinglish", "script": "Devanagari",
        "script_re": r"ऀ-ॿ", "native_digits": r"०-९",
        "enders": "।?!", "end_char": "।",
        "register": ("Conversational Hinglish exactly as people talk in Indian cities and on popular Hindi "
                     "audio shows: Hindi grammar, everyday Hindi-Urdu words, and common English words mixed in "
                     "naturally (roughly one English word every sentence or two — mostly nouns and set phrases). "
                     "Spoken forms: वो (not वह), ये (not यह), तुम/तू/आप to show the relationship."),
        "loanwords": "प्लान, डील, सॉरी, प्लीज़, क्रू, कैप्टन, सिग्नल, टेंशन, प्रपोज़, पाइरेट, मिशन, ट्रैप",
        "swaps": {"स्वर्ण मुद्रा": "सोने का सिक्का", "प्रस्ताव रखा": "प्रपोज़ किया", "ध्वस्त कर दिया": "उड़ा दिया",
                  "प्रतीक्षा": "इंतज़ार", "क्रोध": "गुस्सा", "हृदय": "दिल", "विवाह": "शादी", "अश्रु": "आँसू",
                  "किंतु": "लेकिन / पर", "तत्पश्चात": "उसके बाद", "अत्यंत": "बहुत", "सम्मुख": "सामने",
                  "ज्ञात": "पता", "समुद्र": "समंदर", "अनिवा�