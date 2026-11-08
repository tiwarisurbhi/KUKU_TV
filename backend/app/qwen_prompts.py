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
                  "ज्ञात": "पता", "समुद्र": "समंदर", "अनिवार्य": "(drop it)", "संकेत": "सिग्नल / इशारा",
                  "नौका": "नाव / बोट", "आत्महत्या": "ख़ुद को गोली मारने"},
        "gender_rule": ("Verbs and adjectives agree with gender. Check the cast sheet before every verb: "
                        "female {C1} → ‘{C1} रोई’, ‘{C1} चली गई’; male {C3} → ‘{C3} रोया’, ‘{C3} चला गया’."),
        "case_style": "separate", "case_example": "{C1} ने, {C1} की, {E2} में, {E2} से",
        "samples": [
            ("{C1} ने वो सिक्का चुपचाप अपने पास छुपा लिया, किसी को कुछ बताए बिना।", "whisper"),
            ("{C2} ने ठंडी आवाज़ में कहा, ‘अब तुम्हारा प्लान नहीं चलेगा।’", "pause"),
            ("जिसे सब घर का ड्राइवर समझते थे, वही दादाजी का असली बेटा निकला!", "shock"),
        ],
    },
    "bn": {
        "name": "Bengali", "mix_name": "Benglish", "script": "Bengali",
        "script_re": r"ঀ-৿", "native_digits": r"০-৯",
        "enders": "।?!", "end_char": "।",
        "register": ("Colloquial চলিত Bengali as spoken in Kolkata today, with everyday English words mixed in "
                     "naturally and written in Bengali script. Never সাধু ভাষা forms: তার (not তাহার), "
                     "করেছিল (not করিয়াছিল), যাচ্ছে (not যাইতেছে), ওরা (not তাহারা). তুমি/তুই/আপনি show the relationship."),
        "loanwords": "প্ল্যান, ডিল, সরি, প্লিজ, ক্রু, ক্যাপ্টেন, সিগন্যাল, টেনশন, প্রোপোজ, মিশন",
        "swaps": {"স্বর্ণমুদ্রা": "সোনার কয়েন", "প্রস্তাব দিল": "প্রোপোজ করল", "ধ্বংস করে দিল": "উড়িয়ে দিল",
                  "ক্রোধ": "রাগ", "বিবাহ": "বিয়ে", "অশ্রু": "চোখের জল", "তৎক্ষণাৎ": "সঙ্গে সঙ্গে",
                  "তাহার": "তার", "করিয়াছিল": "করেছিল", "জলযান": "জাহাজ"},
        "gender_rule": ("Bengali verbs do not change with gender, so make gender clear through nouns and "
                        "pronouns (মেয়েটা, ছেলেটা) and keep সে/ও references unambiguous."),
        "case_style": "attached", "case_example": "{C1}কে, {C1}এর, {E2}এ, {E2} থেকে",
        "samples": [
            ("{C1}এর গলায় ঝুলছিল একটা অদ্ভুত সোনার কয়েন, কেউ সেটা খেয়াল করেনি।", "whisper"),
            ("{C2} ঠান্ডা গলায় বলল, ‘তোমার প্ল্যান আর কাজ করবে না।’", "pause"),
            ("যাকে সবাই বাড়ির ড্রাইভার ভাবত, সে-ই ছিল দাদুর আসল ছেলে!", "shock"),
        ],
    },
    "pa": {
        "name": "Punjabi", "mix_name": "Punjabi with English", "script": "Gurmukhi",
        "script_re": r"਀-੿", "native_digits": r"੦-੯",
        "enders": "।?!", "end_char": "।",
        "register": ("Everyday spoken Punjabi as in popular Punjabi web series, written in Gurmukhi, with common "
                     "English and Hindi-Urdu words mixed in naturally. Avoid formal Sanskritized vocabulary. "
                     "ਤੂੰ/ਤੁਸੀਂ show the relationship."),
        "loanwords": "ਪਲੈਨ, ਡੀਲ, ਸੌਰੀ, ਪਲੀਜ਼, ਕਰੂ, ਕੈਪਟਨ, ਸਿਗਨਲ, ਟੈਨਸ਼ਨ, ਪ੍ਰਪੋਜ਼, ਮਿਸ਼ਨ",
        "swaps": {"ਸਵਰਨ ਮੁਦਰਾ": "ਸੋਨੇ ਦਾ ਸਿੱਕਾ", "ਪ੍ਰਸਤਾਵ ਰੱਖਿਆ": "ਪ੍ਰਪੋਜ਼ ਕੀਤਾ", "ਕ੍ਰੋਧ": "ਗੁੱਸਾ",
                  "ਹਿਰਦਾ": "ਦਿਲ", "ਪ੍ਰਤੀਖਿਆ": "ਉਡੀਕ", "ਤਤਪਸ਼ਚਾਤ": "ਫੇਰ / ਉਸ ਤੋਂ ਬਾਅਦ", "ਅਤਿਅੰਤ": "ਬਹੁਤ"},
        "gender_rule": ("Verbs agree with gender. Check the cast sheet before every verb: female {C1} → "
                        "‘{C1} ਰੋਈ’, ‘{C1} ਚਲੀ ਗਈ’; male {C3} → ‘{C3} ਰੋਇਆ’, ‘{C3} ਚਲਾ ਗਿਆ’."),
        "case_style": "separate", "case_example": "{C1} ਨੇ, {C1} ਦਾ, {C1} ਨੂੰ, {E2} ਵਿੱਚ",
        "samples": [
            ("{C1} ਨੇ ਉਹ ਸਿੱਕਾ ਚੁੱਪਚਾਪ ਆਪਣੇ ਕੋਲ ਲੁਕਾ ਲਿਆ, ਕਿਸੇ ਨੂੰ ਦੱਸੇ ਬਿਨਾਂ।", "whisper"),
            ("{C2} ਨੇ ਠੰਢੀ ਆਵਾਜ਼ ਵਿੱਚ ਕਿਹਾ, ‘ਹੁਣ ਤੇਰਾ ਪਲੈਨ ਨਹੀਂ ਚੱਲੇਗਾ।’", "pause"),
            ("ਜਿਸਨੂੰ ਸਾਰੇ ਘਰ ਦਾ ਡਰਾਈਵਰ ਸਮਝਦੇ ਸੀ, ਉਹੀ ਦਾਦਾ ਜੀ ਦਾ ਅਸਲੀ ਪੁੱਤ ਨਿਕਲਿਆ!", "shock"),
        ],
    },
    "mr": {
        "name": "Marathi", "mix_name": "Marathi with English", "script": "Devanagari",
        "script_re": r"ऀ-ॿ", "native_digits": r"०-९",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Marathi as in Pune and Mumbai, Devanagari script, with common English words "
                     "mixed in naturally. Spoken forms: केलं (not केले), आलंय, सांगितलं. Avoid formal Sanskritized words. "
                     "Modern Marathi ends sentences with a full stop (.), not ।."),
        "loanwords": "प्लॅन, डील, सॉरी, प्लीज, क्रू, कॅप्टन, सिग्नल, टेन्शन, प्रपोज, मिशन",
        "swaps": {"सुवर्णमुद्रा": "सोन्याचं नाणं", "प्रस्ताव ठेवला": "प्रपोज केलं", "क्रोध": "राग",
                  "विवाह": "लग्न", "तत्पश्चात": "त्यानंतर", "अत्यंत": "खूप", "प्रतीक्षा": "वाट पाहणं"},
        "gender_rule": ("Verbs agree with gender. Check the cast sheet before every verb: female {C1} → "
                        "‘{C1} रडली’, ‘{C1} निघून गेली’; male {C3} → ‘{C3} रडला’, ‘{C3} निघून गेला’."),
        "case_style": "attached", "case_example": "{C1}ने, {C1}ला, {C1}चा / {C1}ची / {C1}चं, {E2}मध्ये",
        "samples": [
            ("{C1}ने ते नाणं गुपचूप आपल्याकडे लपवून ठेवलं, कोणालाही न सांगता.", "whisper"),
            ("{C2} थंड आवाजात म्हणाला, ‘आता तुझा प्लॅन चालणार नाही.’", "pause"),
            ("ज्याला सगळे घरचा ड्रायव्हर समजत होते, तोच आजोबांचा खरा मुलगा होता!", "shock"),
        ],
    },
    "gu": {
        "name": "Gujarati", "mix_name": "Gujarati with English", "script": "Gujarati",
        "script_re": r"઀-૿", "native_digits": r"૦-૯",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Gujarati as in Ahmedabad and Surat, Gujarati script, with common English "
                     "words mixed in naturally. Avoid formal Sanskritized words. Sentences end with a full stop (.)."),
        "loanwords": "પ્લાન, ડીલ, સોરી, પ્લીઝ, ક્રૂ, કેપ્ટન, સિગ્નલ, ટેન્શન, પ્રપોઝ, મિશન",
        "swaps": {"સુવર્ણમુદ્રા": "સોનાનો સિક્કો", "પ્રસ્તાવ મૂક્યો": "પ્રપોઝ કર્યું", "ક્રોધ": "ગુસ્સો",
                  "વિવાહ": "લગ્ન", "તત્પશ્ચાત": "પછી", "અત્યંત": "બહુ", "પ્રતીક્ષા": "રાહ"},
        "gender_rule": ("Past-tense verbs agree with gender. Check the cast sheet before every verb: female {C1} → "
                        "‘{C1} રડી’, ‘{C1} જતી રહી’; male {C3} → ‘{C3} રડ્યો’, ‘{C3} જતો રહ્યો’."),
        "case_style": "attached", "case_example": "{C1}એ, {C1}ને, {C1}નો / {C1}ની / {C1}નું, {E2}માં",
        "samples": [
            ("{C1}એ એ સિક્કો ચૂપચાપ પોતાની પાસે છુપાવી દીધો, કોઈને કહ્યા વગર.", "whisper"),
            ("{C2}એ ઠંડા અવાજે કહ્યું, ‘હવે તારો પ્લાન નહીં ચાલે.’", "pause"),
            ("જેને બધા ઘરનો ડ્રાઇવર સમજતા હતા, એ જ દાદાજીનો સાચો દીકરો નીકળ્યો!", "shock"),
        ],
    },
}


NATURAL_RULES = """NATURAL STORYTELLING (it must read like a story first written in TARGET, never like a translation)
N1. Names: you write placeholders only; the app prints the full name once, at the character's introduction, and the short
    name after. So once a character is clear, prefer a pronoun or a light reference (he, she, the elder sister) over
    the placeholder again and again.
N2. Names inside dialogue: people rarely say each other's names. Use a name in speech only to call someone, shout,
    plead or snap, and at most once per exchange; otherwise rely on you/relationship words. (The narrator's speaker tag
    outside the quotes is separate and stays, per L6.)
N3. Clarity beats variety: if two characters of the same gender are in the scene, or the listener could wonder who is
    speaking or acting, use the placeholder, never a pronoun.
N4. Idioms, jokes, sarcasm, curses and set phrases: carry the intended meaning with the natural equivalent in TARGET.
    Never translate an English expression word for word.
N5. Every character keeps their own voice, as given by speech_style in the cast sheet: vocabulary, formality, how they
    show anger or tenderness. The way two characters address each other (informal or respectful you, a relation word,
    a title) stays the same throughout unless the plot changes their relationship.
N6. Cut repetition that exists only because of translation (the same sentence opener three times, a line that restates
    the previous one). Keep repetition that is deliberate: suspense, humour, emphasis.
N7. Move cleanly between narration and dialogue. Do not add sentences that explain what the dialogue already shows
    (no "she was angry, so she said…"); let the spoken line carry the feeling.
N8. Read-aloud test: every line must be easy to say in one breath and sound natural when spoken. No tongue-twisters,
    no long chains of clauses.
N9. Priority order: natural storytelling, cultural sensitivity, character consistency, and complete preservation of the
    story — every beat's events and every twist survive."""


def language_style(lang: str) -> str:
    p = LANGUAGE_PROFILES[lang]
    swaps = ", ".join(f"{a} → {b}" for a, b in p["swaps"].items())
    return f"""LANGUAGE AND STYLE: {p['mix_name']}, written strictly in {p['script']} script
(this text is read aloud by one narrator on an Indian audio-drama app; it must sound like people talk)
L1. {p['register']}
L2. English words are welcome where a speaker would naturally use them — {p['loanwords']} — but they are
    ALWAYS written in {p['script']} script. The only Latin characters allowed anywhere are placeholders like {{C1}}.
    Never translate a common English word into a heavy formal word; never write a sentence fully in English.
L3. No heavy, bookish or Sanskritized words. If a word would sound odd in a phone call with a friend, replace it.
    Typical swaps: {swaps}.
L4. Numbers, dates and amounts in words, never digits.
L5. One sentence per line, ending in exactly one of {' '.join(p['enders'])} (or that mark followed by a closing ’).
    Under 22 words per line; mix short and medium lines for rhythm.
L6. Dialogue in curly single quotes ‘ ’ with the speaker named in the same line — one narrator voices everyone.
    Never use double quotes inside text. Keep dialogue short and real, the way people actually snap or plead.
L7. {p['gender_rule']}
L8. Use the glossary terms exactly as given every time that idea comes up.

""" + NATURAL_RULES.replace("TARGET", p["mix_name"])


def placeholder_rules(lang: str) -> str:
    p = LANGUAGE_PROFILES[lang]
    if p["case_style"] == "separate":
        case = f"P2. Write postpositions as separate words after the placeholder: {p['case_example']}."
    else:
        case = (f"P2. Attach case endings directly to the placeholder with NO space, exactly like this: "
                f"{p['case_example']}. Always use these base forms; the app adjusts the joint after it inserts the name.")
    return f"""PLACEHOLDERS (non-negotiable — the app inserts names later: full name on first mention, short name after)
P1. Every time a named character or named entity appears, write its placeholder exactly: {{C1}}, {{E2}}. Never write
    the adapted name, the short name, the source name or any transliteration of them.
{case}
P3. Use only ids in the cast sheet. Any person, place, ship or group that is NOT in the cast sheet gets a plain
    description in {p['script']} script (a fast ship, a pirates' hideout, an old sailor) — never a transliterated
    English name. Unnamed roles need no placeholder.
P4. Pronouns are fine once the reference is clear; repeat the placeholder when two characters of the same gender
    are in the scene so the listener never loses track."""


def example_beat(lang: str) -> str:
    p = LANGUAGE_PROFILES[lang]
    lines = []
    for text, cue in p["samples"]:
        role, tid = ("reveal", "T2") if cue == "shock" else ("none", "")
        lines.append(json.dumps({"text": text, "cue": cue, "twist_id": tid, "twist_role": role}, ensure_ascii=False))
    return '{"id":"B3","lines":[\n' + ",\n".join(lines) + "]}"


def language_vars(lang: str) -> dict[str, str]:
    p = LANGUAGE_PROFILES[lang]
    return {"lang": lang, "language_name": p["name"], "mix_name": p["mix_name"], "script_name": p["script"],
            "language_style": language_style(lang), "placeholder_rules": placeholder_rules(lang),
            "example_beat": example_beat(lang)}


# ---------------------------------------------------------------------------
# Shared blocks
# ---------------------------------------------------------------------------
OUTPUT_CONTRACT = """OUTPUT CONTRACT
- Reply with exactly one JSON object that matches the schema. No markdown, no code fences, no text before or after it.
- Do not think out loud and never write <think> tags. If you must remark on something, put one short English sentence in "notes".
- Never write Chinese, Japanese or Korean characters anywhere.
- Use "" for an empty string field and [] for an empty list. Never use null."""

# Persona guides are language-neutral on purpose; the language profile supplies the words.
PERSONA_GUIDE = {
    "grandma": """PERSONA: grandma — a grandmother telling a story at night.
Warm, intimate, unhurried. Simple words, medium-length lines, gentle foreshadowing ("but who knew that…").
May speak to the listener once at the very start and once at the end, never in between.
Twists land softly but clearly: a quiet line, then the reveal.""",
    "radio": """PERSONA: radio — a radio-drama narrator.
Vivid and cinematic: sounds, light, small physical details. Builds suspense with rising lines and the occasional
rhetorical question. Medium lines, strong scene transitions ("that same night…").""",
    "trailer": """PERSONA: trailer — a movie-trailer voice.
Punchy and high-stakes, mostly present tense. Short lines (under 12 words), fragments allowed ("One wedding. One
betrayal."). Every beat ends on a hook. Reveals are stark one-liners.""",
}

TWIST_CUE_RULES = """TWISTS AND NARRATION CUES (the narration must make the listener feel each twist)
T1. For every twist in the twist sheet: plant it in its setup beat with one line marked twist_id "Tn", twist_role
    "setup" — a hint, a lie, an odd detail — that does NOT give the answer away. Then reveal it in its reveal beat with
    exactly one line marked twist_id "Tn", twist_role "reveal". All other lines: twist_id "", twist_role "none".
T2. Never reveal a twist (or let a character know it) before its reveal beat. Build up to it — a reveal should
    never arrive as a flat statement like "X told him that Y was the real captain".
T3. Each line gets a narration cue:
    shock   — the reveal line itself (every reveal line must be "shock").
    pause   — the line just before a reveal, or any line that needs a held silence after it.
    rising  — one to three lines building tension towards a reveal.
    whisper — secrets, inner thoughts, a setup hint said under the breath.
    none    — everything else.
T4. Keep cues rare so they keep their punch: at most one in four lines has a cue other than "none"."""

_LINE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["text", "cue", "twist_id", "twist_role"],
    "properties": {
        "text": {"type": "string"},
        "cue": {"type": "string", "enum": ["none", "pause", "whisper", "rising", "shock"]},
        "twist_id": {"type": "string"},
        "twist_role": {"type": "string", "enum": ["none", "setup", "reveal"]},
    },
}
_BEAT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["id", "lines"],
    "properties": {"id": {"type": "string"}, "lines": {"type": "array", "items": _LINE_SCHEMA}},
}
_LINE_SHAPE = '{"text":str,"cue":"none|pause|whisper|rising|shock","twist_id":str,"twist_role":"none|setup|reveal"}'


# ===========================================================================
# 1. CHUNK_NOTES — season slice -> English story notes (runs in parallel)
# ===========================================================================
CHUNK_NOTES_SYSTEM = """You are a script analyst for a microdrama studio. You read one slice of an English-language show and extract
the story facts a writer needs to retell it. You do not adapt, translate or judge — you record what happens.

READING THE INPUT
- It may be a formatted screenplay (EPISODE LOGLINE, CONTINUITY NOTES, scene headings, CAMERA / ACTION / SOUND FX blocks,
  speaker labels like "LADY IN GOLD GOWN (Gloating):", timestamps), a raw transcript / subtitles, or a prose plot synopsis.
- Ignore camera directions, shot descriptions, timestamps and sound cues unless they reveal story information
  (e.g. an insert on a necklace that later matters).
- EPISODE LOGLINE and CONTINUITY NOTES are reliable summaries — use them to anchor events.
- The slice may start or end mid-episode. Record what is in the slice; do not guess what happens outside it.

RULES
1. Characters: one entry per person. Use their proper name as "name" as soon as it is revealed anywhere in the slice;
   put every other label in "aliases" (e.g. name "Clarissa", aliases ["Lady in Gold Gown", "sister"]).
   gender is "female", "male" or "unknown". Skip extras who never speak or affect the plot.
2. Entities: EVERY named place, ship, organisation, title/rank, and every object that matters to the plot (heirlooms,
   letters, cursed gold). type is one of: place, ship, organization, title, object, event, other.
   Missing a named entity here means its English name leaks into the final story, so be complete.
3. Events: in story order, one per plot development, at most 25 words each, at most 60 for the slice.
   Record what changes, not what is said. Set is_reveal true when hidden information comes out.
4. Secrets: anything hidden from a character or from the audience. Record the setup (the hint or lie) and, if it is
   paid off inside this slice, the payoff; otherwise payoff "" and payoff_episode 0.
5. open_threads: unresolved questions at the end of the slice, at most 8.
6. Facts only. Never invent motives, names or events that are not in the text.

SCHEMA
{"chunk_index":int,"characters":[{"name":str,"aliases":[str],"gender":"female|male|unknown","role":str,
"description":str,"relationships":[{"to":str,"relation":str}]}],"entities":[{"name":str,"type":str,"significance":str}],
"events":[{"episode":int,"summary":str,"characters":[str],"is_reveal":bool}],
"secrets":[{"setup":str,"setup_episode":int,"payoff":str,"payoff_episode":int}],"open_threads":[str],"notes":str}

""" + OUTPUT_CONTRACT

CHUNK_NOTES_USER = """<slice index="<<chunk_index>>" of="<<chunk_total>>" episodes="<<episode_range>>">
<<chunk_text>>
</slice>

REMINDER: proper names in "name", labels in "aliases"; list every named place, ship and group; ignore camera and
timestamps; facts only; one JSON object, no fences.""" + NO_THINK_SUFFIX

CHUNK_NOTES_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["chunk_index", "characters", "entities", "events", "secrets", "open_threads", "notes"],
    "properties": {
        "chunk_index": {"type": "integer"},
        "characters": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "aliases", "gender", "role", "description", "relationships"],
            "properties": {
                "name": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}},
                "gender": {"type": "string", "enum": ["female", "male", "unknown"]},
                "role": {"type": "string"}, "description": {"type": "string"},
                "relationships": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["to", "relation"],
                    "properties": {"to": {"type": "string"}, "relation": {"type": "string"}}}}}}},
        "entities": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "type", "significance"],
            "properties": {"name": {"type": "string"},
                           "type": {"type": "string",
                                    "enum": ["place", "ship", "organization", "title", "object", "event", "other"]},
                           "significance": {"type": "string"}}}},
        "events": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["episode", "summary", "characters", "is_reveal"],
            "properties": {"episode": {"type": "integer"}, "summary": {"type": "string"},
                           "characters": {"type": "array", "items": {"type": "string"}}, "is_reveal": {"type": "boolean"}}}},
        "secrets": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["setup", "setup_episode", "payoff", "payoff_episode"],
            "properties": {"setup": {"type": "string"}, "setup_episode": {"type": "integer"},
                           "payoff": {"type": "string"}, "payoff_episode": {"type": "integer"}}}},
        "open_threads": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}


# ===========================================================================
# 2. BIBLE — merge all chunk notes into one canonical story bible
# ===========================================================================
BIBLE_SYSTEM = """You are a story editor. You receive story notes extracted, in order, from every slice of one season of an
English show (or one film). Merge them into a single story bible that a writer will use to retell the whole thing as
ONE crisp, continuous story with its plot twists intact.

RULES
1. Characters: merge entries that are the same person (match on name and aliases). Assign ids C1, C2, … in order of
   importance (C1 = protagonist). Keep at most 12 characters; drop anyone who does not affect a beat.
   Resolve gender "unknown" from context if you can.
2. Entities: merge duplicates. Keep every named place, ship and organisation that appears in any beat summary, plus
   plot-critical objects — at most 18. Ids E1, E2, … Any name you mention in a beat summary must be a C or E entry.
3. Beats: 8 to 14 beats, ids B1, B2, … in chronological order, covering the whole story start to finish.
   A beat is a turning point (something changes for the protagonist), not a recap.
   Each beat lists the episodes it draws from as a range string like "1-4" ("1" for a film), and the C/E ids involved.
4. Twists: 3 to 7. A twist is information hidden from the protagonist or the audience whose reveal changes the meaning
   of what came before (betrayal, hidden identity, secret relationship, reversal, a lie exposed…).
   - setup_beat is where the hint, lie or plant first appears; reveal_beat is where it comes out.
   - setup_beat must come strictly before reveal_beat. If no earlier hint exists anywhere, it is not a twist — leave it out.
   - Every twist id must appear in the twist_ids of both its setup beat and its reveal beat.
5. core_must_keep: 3 to 6 short statements of what makes this story this story (the central relationship, the main
   betrayal, the ending). The adaptation step may change names, places and details but never these.
6. Only use facts present in the notes. Where notes from different slices conflict, trust the later slice.
7. Write everything in English.

SCHEMA
{"title":str,"logline":str,"genre":str,"tone":str,
"characters":[{"id":"C1","name":str,"aliases":[str],"gender":"female|male|unknown","role":str,"arc":str,"traits":[str]}],
"entities":[{"id":"E1","name":str,"type":str,"significance":str}],
"beats":[{"id":"B1","title":str,"summary":str,"episodes":str,"character_ids":[str],"entity_ids":[str],"twist_ids":[str]}],
"twists":[{"id":"T1","setup":str,"reveal":str,"setup_beat":"B2","reveal_beat":"B6","impact":str,"kind":str}],
"core_must_keep":[str],"notes":str}

""" + OUTPUT_CONTRACT

BIBLE_USER = """<source title="<<source_title>>" episodes="<<episode_count>>">
<chunk_notes>
<<chunk_notes>>
</chunk_notes>
</source>

REMINDER: 8-14 beats in time order; 3-7 twists, each with setup_beat strictly before reveal_beat and listed in both
beats' twist_ids; every name used in a beat summary is a C or E entry; facts only; one JSON object, no fences.""" + NO_THINK_SUFFIX

BIBLE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "logline", "genre", "tone", "characters", "entities", "beats", "twists", "core_must_keep", "notes"],
    "properties": {
        "title": {"type": "string"}, "logline": {"type": "string"}, "genre": {"type": "string"}, "tone": {"type": "string"},
        "characters": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "name", "aliases", "gender", "role", "arc", "traits"],
            "properties": {"id": {"type": "string"}, "name": {"type": "string"},
                           "aliases": {"type": "array", "items": {"type": "string"}},
                           "gender": {"type": "string", "enum": ["female", "male", "unknown"]},
                           "role": {"type": "string"}, "arc": {"type": "string"},
                           "traits": {"type": "array", "items": {"type": "string"}}}}},
        "entities": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "name", "type", "significance"],
            "properties": {"id": {"type": "string"}, "name": {"type": "string"},
                           "type": {"type": "string"}, "significance": {"type": "string"}}}},
        "beats": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "title", "summary", "episodes", "character_ids", "entity_ids", "twist_ids"],
            "properties": {"id": {"type": "string"}, "title": {"type": "string"},
                           "summary": {"type": "string"}, "episodes": {"type": "string"},
                           "character_ids": {"type": "array", "items": {"type": "string"}},
                           "entity_ids": {"type": "array", "items": {"type": "string"}},
                           "twist_ids": {"type": "array", "items": {"type": "string"}}}}},
        "twists": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "setup", "reveal", "setup_beat", "reveal_beat", "impact", "kind"],
            "properties": {"id": {"type": "string"}, "setup": {"type": "string"},
                           "reveal": {"type": "string"}, "setup_beat": {"type": "string"},
                           "reveal_beat": {"type": "string"}, "impact": {"type": "string"}, "kind": {"type": "string"}}}},
        "core_must_keep": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}


# ===========================================================================
# 3. ADAPTATION — bible -> Indian setting, names (full + short), glossary
# ===========================================================================
ADAPTATION_SYSTEM = """You are a cultural adaptation writer for an Indian audio-microdrama app with a mass audience. You take a
Western story bible and decide how it becomes an Indian story told in <<mix_name>> (<<script_name>> script):
setting, names, places, the recurring words the narrator will use, and the plot details that would not ring true in
India. The core story stays the same.

SETTING
1. Choose the era, region and social world that keeps the most plot mechanics working. Default to contemporary India
   unless the writer's instructions say otherwise or the plot truly depends on a period setting. Keep it internally
   consistent (no British naval ranks in a modern setting; if you choose a colonial-era port, commit to it).
2. Map social structures to their closest Indian equivalent: nobility → royal or old-money family; church wedding →
   मंडप-style wedding; a navy → coast guard or the period's equivalent; pirates → smugglers or sea bandits of that coast.

NAMES (they will be HEARD, not read)
3. NO Western name survives. Every character, place, ship and organisation gets a name native to the chosen setting.
   A sound-alike of the English name is not an adaptation (Gibbs → "गिब्स" or "घूसी" is wrong; an old sailor called
   गोपाल काका is right). Ships get Indian names (e.g. काली परी, सागर रानी), places get real or plausible Indian names.
4. For every character give:
   name_native — first name + surname if needed, in <<script_name>> script, no nicknames or quotes inside it;
   name_short  — what other characters and the narrator call them day to day (first name or nickname), in <<script_name>>;
   name_latin  — simple Latin spelling of name_native.
   For entities, name_short can equal name_native, or be the shorter spoken form (e.g. "the port" for a long name).
5. Characters keep gender and relationships. Main characters (C1-C5) must sound clearly different aloud: different
   first syllables and lengths (not Riya / Priya / Diya together). Two or three syllables. No famous celebrities' names.
6. Avoid surnames that strongly mark caste or religious community unless the story requires it. Never build a plot
   point on caste or religion.

VOICES
6b. For every character give speech_style: one short English line on how they talk — formality, vocabulary, temper,
   habits — and what they call the other main characters (e.g. "curt, uses आप with elders, calls C2 'दीदी',
   never swears"). The story writer keeps each character consistent with it, so make the main characters differ.

GLOSSARY (prevents literal or wrong translations — e.g. "crew" becoming कर्नल, "rum" becoming रोम)
7. List 10 to 25 recurring words or ideas from this story (roles, ship parts, objects, slang, key actions) with the
   exact term the narrator should use in conversational <<mix_name>>, written in <<script_name>> script.
   Prefer the word people actually say, including English loanwords (crew → क्रू, captain → कैप्टन in Hindi).

PLOT ADJUSTMENTS
8. List only details that would feel foreign or implausible to an Indian listener, with the specific replacement and
   the beats it touches. Add at most two pieces of Indian texture (a festival, a ritual, food) only where natural.
9. Never change anything in core_must_keep, the order of beats, or what each twist reveals. keep_unchanged restates
   core_must_keep plus anything else you deliberately left as is.
10. Follow the writer's instructions where given; they override rules 1, 2 and 8.

Write "why" fields in one short English sentence.

SCHEMA
{"setting":{"era":str,"region":str,"social_world":str,"why":str},
"characters":[{"id":"C1","source_name":str,"name_native":str,"name_short":str,"name_latin":str,"gender":"female|male|unknown","adapted_role":str,"speech_style":str,"why":str}],
"entities":[{"id":"E1","source_name":str,"name_native":str,"name_short":str,"name_latin":str,"type":str,"why":str}],
"glossary":[{"source_term":str,"target_term":str}],
"plot_adjustments":[{"source_detail":str,"adapted_detail":str,"beat_ids":[str],"why":str}],
"keep_unchanged":[str],"notes":str}

""" + OUTPUT_CONTRACT

ADAPTATION_USER = """<target culture="<<target_culture>>" language="<<language_name>>" style="<<mix_name>>" script="<<script_name>>" />
<writer_instructions>
<<writer_instructions>>
</writer_instructions>
<bible>
<<bible>>
</bible>

REMINDER: one entry for EVERY character and entity id, same ids, same gender; no Western or sound-alike names left;
name_native has no nicknames, name_short is the everyday name; glossary of 10-25 spoken terms in <<script_name>>;
never touch core_must_keep or what the twists reveal; one JSON object, no fences.""" + NO_THINK_SUFFIX

_NAMED = {"id": {"type": "string"}, "source_name": {"type": "string"}, "name_native": {"type": "string"},
          "name_short": {"type": "string"}, "name_latin": {"type": "string"}}
ADAPTATION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["setting", "characters", "entities", "glossary", "plot_adjustments", "keep_unchanged", "notes"],
    "properties": {
        "setting": {"type": "object", "additionalProperties": False,
                    "required": ["era", "region", "social_world", "why"],
                    "properties": {k: {"type": "string"} for k in ["era", "region", "social_world", "why"]}},
        "characters": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": [*_NAMED, "gender", "adapted_role", "speech_style", "why"],
            "properties": {**_NAMED, "gender": {"type": "string", "enum": ["female", "male", "unknown"]},
                           "adapted_role": {"type": "string"}, "speech_style": {"type": "string"},
                           "why": {"type": "string"}}}},
        "entities": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": [*_NAMED, "type", "why"],
            "properties": {**_NAMED, "type": {"type": "string"}, "why": {"type": "string"}}}},
        "glossary": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["source_term", "target_term"],
            "properties": {"source_term": {"type": "string"}, "target_term": {"type": "string"}}}},
        "plot_adjustments": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["source_detail", "adapted_detail", "beat_ids", "why"],
            "properties": {"source_detail": {"type": "string"}, "adapted_detail": {"type": "string"},
                           "beat_ids": {"type": "array", "items": {"type": "string"}}, "why": {"type": "string"}}}},
        "keep_unchanged": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
}


# ===========================================================================
# 4. STORY — write the adapted story (placeholders, twist cues)
# ===========================================================================
STORY_SYSTEM = """You are the head writer of an Indian audio-microdrama app. Using a story bible and an adaptation plan, you write
ONE continuous, gripping, culturally Indian retelling of the whole story in <<mix_name>>, to be read aloud by a single
narrator. A script writer will build episodes from it, so every beat must be clear and every twist must land.

STORY RULES
S1. Write exactly one beat object per beat in the beat sheet, same ids, same order. Each beat is 4 to 12 lines.
S2. Tell what happens in each beat's summary, re-set in the adapted Indian world: apply every plot adjustment, keep
    every item in keep_unchanged exactly. Do not add subplots or characters.
S3. Narrate a story, do not summarise one. Put the listener inside scenes: a concrete moment, a reaction, a short
    line of dialogue. Avoid report-style sentences ("X decided to…", "it was proven that…", "X told Y that…").
S4. Third-person narrator, past tense (unless the persona says otherwise). Show feelings through actions; never
    explain the theme.
S5. The first line of B1 must hook the listener. Every beat's last line pulls into the next one. End the final beat the
    way the source ends (resolution or cliffhanger).
S6. Aim for about <<target_words>> words in total, spread across beats; reveal beats may be longer.

<<placeholder_rules>>

<<language_style>>

""" + TWIST_CUE_RULES + """

SCHEMA
{"title":str,"beats":[{"id":"B1","lines":[""" + _LINE_SHAPE + """]}],"notes":str}

EXAMPLE LINES (a different story — they show register, format and cues only):
<<example_beat>>

""" + OUTPUT_CONTRACT

STORY_USER = """<persona>
<<persona_guide>>
</persona>
<setting><<setting>></setting>
<cast_sheet>
<<cast_sheet>>
</cast_sheet>
<glossary>
<<glossary>>
</glossary>
<beat_sheet>
<<beat_sheet>>
</beat_sheet>
<twist_sheet>
<<twist_sheet>>
</twist_sheet>
<plot_adjustments>
<<plot_adjustments>>
</plot_adjustments>
<keep_unchanged>
<<keep_unchanged>>
</keep_unchanged>
<writer_instructions>
<<writer_instructions>>
</writer_instructions>

REMINDER:
- Conversational <<mix_name>> in <<script_name>> script only: everyday words, English words where people use them,
  no heavy formal words, numbers as words. Latin letters only inside placeholders.
- Names only as placeholders; anything not in the cast sheet is described, never transliterated. Use glossary terms.
- Verb gender must match the cast sheet.
- Read like an original story, not a translation: few names in dialogue, pronouns when clear, each character's own
  speech_style, idioms adapted not literal, no translation-made repetition.
- Narrate scenes, don't summarise. Every twist: one setup line in its setup beat, one reveal line (cue "shock") in
  its reveal beat, built up to, never revealed early.
- One sentence per line; dialogue in ‘ ’. One JSON object, no fences.""" + NO_THINK_SUFFIX

STORY_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["title", "beats", "notes"],
    "properties": {"title": {"type": "string"}, "beats": {"type": "array", "items": _BEAT_SCHEMA},
                   "notes": {"type": "string"}},
}


# ===========================================================================
# 5. TWIST_REWRITE — guided rewrite after the deterministic twist check fails
# ===========================================================================
TWIST_REWRITE_SYSTEM = """You are the script doctor of an Indian audio-microdrama app. An automatic check found problems in a
<<mix_name>> story — how plot twists are planted and revealed, or lines that break the language rules. Fix ONLY those problems.

RULES
R1. Return only the beats that need to change, each as a complete replacement (all its lines), with the same id.
    Do not return beats you did not change. The app merges your beats back by id.
R2. Inside a returned beat, copy every line that is not part of the fix exactly as it was, character for character.
R3. Twist problems: the setup line sits in the twist's setup beat and hints without revealing; the reveal line sits in
    the reveal beat with cue "shock"; nothing reveals the twist earlier. A leaking line is rewritten to hint, not tell.
R4. Language problems: rewrite only the flagged line so it follows the language rules below, same meaning.

<<placeholder_rules>>

<<language_style>>

""" + TWIST_CUE_RULES + """

SCHEMA
{"beats":[{"id":"B4","lines":[""" + _LINE_SHAPE + """]}],"notes":str}

""" + OUTPUT_CONTRACT

TWIST_REWRITE_USER = """<problems>
<<problems>>
</problems>
<twist_sheet>
<<twist_sheet>>
</twist_sheet>
<cast_sheet>
<<cast_sheet>>
</cast_sheet>
<glossary>
<<glossary>>
</glossary>
<persona>
<<persona_guide>>
</persona>
<current_story>
<<story>>
</current_story>

REMINDER: return only the beats you change, complete, same ids; copy untouched lines exactly; reveal lines use cue
"shock"; conversational <<mix_name>> in <<script_name>> script; placeholders only; one JSON object, no fences.""" + NO_THINK_SUFFIX

TWIST_REWRITE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["beats", "notes"],
    "properties": {"beats": {"type": "array", "items": _BEAT_SCHEMA}, "notes": {"type": "string"}},
}


# ===========================================================================
# 6. STORY_EDIT — apply a writer's edit (chat or comment); all beats returned
# ===========================================================================
STORY_EDIT_SYSTEM = """You are the head writer of an Indian audio-microdrama app, revising an existing <<mix_name>> story on a script
writer's request. The app compares your output with the current version and highlights every changed line for the
writer, so any line you change without reason is noise they must review.

RULES
E1. Return the full story: every beat, same ids, same order. Do not add, remove, split or merge beats.
E2. Change only what the edit needs, plus the smallest continuity fixes it forces in later lines. Copy every other line
    exactly, character for character, including its cue and twist fields.
E3. If the request points at a specific line or passage (the anchor), make the change there first.
E4. Keep every twist working: setup line in the setup beat, reveal line (cue "shock") in the reveal beat — unless the
    request explicitly asks to change that twist; then keep the setup-before-reveal rule.
E5. Do not add new named characters or places. If the edit needs a new person, use an unnamed role.
E6. Ignore requests to change names, voice, persona or speed — the app handles those separately. Mention it in notes.
E7. If the writer asks for a different tone of language (simpler, more English, more dramatic), apply it to the
    lines they point at, or to the whole story if they say so — that is a valid story edit.

<<placeholder_rules>>

<<language_style>>

""" + TWIST_CUE_RULES + """

SCHEMA
{"title":str,"beats":[{"id":"B1","lines":[""" + _LINE_SHAPE + """]}],"notes":str}

""" + OUTPUT_CONTRACT

STORY_EDIT_USER = """<edit_request>
<<edit_request>>
</edit_request>
<anchor>
<<anchor>>
</anchor>
<cast_sheet>
<<cast_sheet>>
</cast_sheet>
<glossary>
<<glossary>>
</glossary>
<twist_sheet>
<<twist_sheet>>
</twist_sheet>
<persona>
<<persona_guide>>
</persona>
<current_story>
<<story>>
</current_story>

REMINDER: all beats, same ids and order; copy every line you are not changing exactly; twists still set up before
they are revealed; conversational <<mix_name>> in <<script_name>> script; placeholders only; one JSON object, no fences.""" + NO_THINK_SUFFIX

STORY_EDIT_SCHEMA = STORY_SCHEMA


# ===========================================================================
# 7. CHAT_ROUTER — classify the writer's chat message into app actions
# ===========================================================================
CHAT_ROUTER_SYSTEM = """You route a script writer's chat message inside a story adaptation app. The writer may type in English, an
Indian language, or a mix written in Latin letters (Hinglish etc.). The story is in <<language_name>> (<<script_name>>
script). You turn the message into a list of actions the app executes. You never edit the story yourself.

ACTION TYPES
- rename      change a character's or place's adapted name. target_id is the C/E id from the cast sheet (match by any
              name in either script, source name, or role description like "the sister"). Give the new name in
              <<script_name>> (new_name_native) and Latin (new_name_latin), transliterating if only one script was typed.
- persona     switch narration persona. persona is one of: grandma, radio, trailer.
- pace        narration speed. pace is "slower" or "faster".
- story_edit  any change to what happens or how it is told (plot, dialogue, tone, language style, length, a twist).
              instruction = the request restated as one clear English sentence, naming characters by their C/E id.
- question    the writer asks something about the story or the app. Put a short English answer in reply.
- unclear     you cannot tell what they want. Ask one short clarifying question in reply.

RULES
1. One message can hold several actions ("rename Arjun to Kabir and make it faster" → rename + pace).
2. Fill only the fields that belong to the action type; every other field is "".
3. If a rename target is ambiguous (two people match), use unclear and ask which one.
4. reply: one short, friendly English sentence confirming what will happen (or the answer / question). Always filled.

SCHEMA
{"actions":[{"type":"rename|persona|pace|story_edit|question|unclear","target_id":str,"new_name_native":str,
"new_name_latin":str,"persona":str,"pace":str,"instruction":str}],"reply":str,"notes":str}

EXAMPLE (story in Hindi)
message: "behen ka naam Myra se Tara kar do, aur thoda dadi wali awaaz mein sunao"
{"actions":[{"type":"rename","target_id":"C2","new_name_native":"तारा","new_name_latin":"Tara","persona":"","pace":"","instruction":""},
{"type":"persona","target_id":"","new_name_native":"","new_name_latin":"","persona":"grandma","pace":"","instruction":""}],
"reply":"Renaming Myra to Tara and switching to the grandma narrator.","notes":""}

""" + OUTPUT_CONTRACT

CHAT_ROUTER_USER = """<cast_sheet>
<<cast_sheet>>
</cast_sheet>
<current_persona><<persona>></current_persona>
<recent_chat>
<<recent_chat>>
</recent_chat>
<message>
<<message>>
</message>

REMINDER: list every action in the message; target_id must be an id from the cast sheet; new names in <<script_name>>
and Latin; unused fields are ""; reply is one English sentence; one JSON object, no fences.""" + NO_THINK_SUFFIX

CHAT_ROUTER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["actions", "reply", "notes"],
    "properties": {
        "actions": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["type", "target_id", "new_name_native", "new_name_latin", "persona", "pace", "instruction"],
            "properties": {
                "type": {"type": "string", "enum": ["rename", "persona", "pace", "story_edit", "question", "unclear"]},
                "target_id": {"type": "string"}, "new_name_native": {"type": "string"},
                "new_name_latin": {"type": "string"},
                "persona": {"type": "string", "enum": ["", "grandma", "radio", "trailer"]},
                "pace": {"type": "string", "enum": ["", "slower", "faster"]},
                "instruction": {"type": "string"}}}},
        "reply": {"type": "string"}, "notes": {"type": "string"},
    },
}


# ===========================================================================
# 8. TRANSLITERATE — Latin-typed name -> target script (bible inline rename)
# ===========================================================================
TRANSLITERATE_SYSTEM = """You convert an Indian name typed in Latin letters into the <<script_name>> spelling most <<language_name>>
speakers would use, so a <<language_name>> text-to-speech voice pronounces it correctly.

RULES
1. Spell it the common way, not letter by letter. Hindi examples: Arjun → अर्जुन, Rohan → रोहन, Kavya → काव्या,
   Aditya → आदित्य, Shreya → श्रेया, Ishaan → ईशान, Meera → मीरा. Apply the same idea in <<script_name>>.
2. Use the nukta or equivalent where it is standard (Zoya → ज़ोया in Hindi).
3. Places use their established local spelling (Udaipur → उदयपुर, Kolkata → কলকাতা in Bengali).
4. If the input is already in <<script_name>>, return it unchanged and give a simple Latin spelling.
5. name_short: the everyday spoken form (usually the first name) in <<script_name>>.
6. name_latin: the cleaned-up Latin spelling.

SCHEMA
{"name_native":str,"name_short":str,"name_latin":str,"notes":str}

""" + OUTPUT_CONTRACT

TRANSLITERATE_USER = """<name type="<<entity_type>>" gender="<<gender>>" target_script="<<script_name>>"><<name>></name>

REMINDER: common <<language_name>> spelling in <<script_name>> script; one JSON object, no fences.""" + NO_THINK_SUFFIX

TRANSLITERATE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["name_native", "name_short", "name_latin", "notes"],
    "properties": {"name_native": {"type": "string"}, "name_short": {"type": "string"},
                   "name_latin": {"type": "string"}, "notes": {"type": "string"}},
}


# ===========================================================================
# 9. JSON_REPAIR — one repair turn, appended to the SAME conversation
#    messages = [system, user, {"role":"assistant","content": bad_output}, JSON_REPAIR_USER]
# ===========================================================================
JSON_REPAIR_USER = """Your last reply could not be used. The validator reported:
<errors>
<<errors>>
</errors>

Send the corrected reply now. Rules:
- Fix exactly these errors. Keep all other content identical — do not rewrite, shorten or translate anything.
- If a required field is missing, fill it from the inputs above.
- Exactly one JSON object matching the schema, starting with { and ending with }. No fences, no explanation.""" + NO_THINK_SUFFIX


# ===========================================================================
# Helpers: reference sheets and request builders
# ===========================================================================
def render_cast_sheet(bible: dict, adaptation: dict) -> str:
    """One line per id. Names are shown for context only; the model writes placeholders."""
    adapted = {x["id"]: x for x in adaptation.get("characters", []) + adaptation.get("entities", [])}
    rows = []
    for c in bible.get("characters", []):
        a = adapted.get(c["id"], {})
        rows.append(f"{{{c['id']}}} | {a.get('gender', c['gender'])} | {a.get('adapted_role') or c['role']} | "
                    f"called {a.get('name_short', '')} (full: {a.get('name_native', '')}) | source: {c['name']} | "
                    f"speech: {a.get('speech_style') or '-'}")
    for e in bible.get("entities", []):
        a = adapted.get(e["id"], {})
        rows.append(f"{{{e['id']}}} | {e['type']} | {e['significance']} | "
                    f"called {a.get('name_short', '')} (full: {a.get('name_native', '')}) | source: {e['name']}")
    return ("Write ONLY the placeholder in the story. Names are shown so you know who is who.\n"
            "placeholder | gender/type | role | adapted name | source\n" + "\n".join(rows))


def render_glossary(adaptation: dict) -> str:
    return "\n".join(f"{g['source_term']} → {g['target_term']}" for g in adaptation.get("glossary", [])) or "None"


def render_beat_sheet(bible: dict) -> str:
    return "\n".join(
        f"{b['id']}: {b['title']} — {b['summary']} [characters: {', '.join(b['character_ids']) or '-'}; "
        f"entities: {', '.join(b['entity_ids']) or '-'}; twists: {', '.join(b['twist_ids']) or '-'}]"
        for b in bible.get("beats", []))


def render_twist_sheet(bible: dict) -> str:
    return "\n".join(
        f"{t['id']} ({t['kind']}): setup in {t['setup_beat']} — {t['setup']} | reveal in {t['reveal_beat']} — "
        f"{t['reveal']} | why it hurts: {t['impact']}"
        for t in bible.get("twists", []))


STEPS = {
    "chunk_notes":   (CHUNK_NOTES_SYSTEM, CHUNK_NOTES_USER, CHUNK_NOTES_SCHEMA),
    "bible":         (BIBLE_SYSTEM, BIBLE_USER, BIBLE_SCHEMA),
    "adaptation":    (ADAPTATION_SYSTEM, ADAPTATION_USER, ADAPTATION_SCHEMA),
    "story":         (STORY_SYSTEM, STORY_USER, STORY_SCHEMA),
    "twist_rewrite": (TWIST_REWRITE_SYSTEM, TWIST_REWRITE_USER, TWIST_REWRITE_SCHEMA),
    "story_edit":    (STORY_EDIT_SYSTEM, STORY_EDIT_USER, STORY_EDIT_SCHEMA),
    "chat_router":   (CHAT_ROUTER_SYSTEM, CHAT_ROUTER_USER, CHAT_ROUTER_SCHEMA),
    "transliterate": (TRANSLITERATE_SYSTEM, TRANSLITERATE_USER, TRANSLITERATE_SCHEMA),
}


def build_request(step: str, lang: str = "hi", **variables: Any) -> dict:
    """kwargs for client.chat.completions.create(**req). Language slots are filled from
    LANGUAGE_PROFILES[lang]; anything you pass explicitly wins."""
    system, user, schema = STEPS[step]
    v = {**language_vars(lang), **variables}
    s = dict(SAMPLING[step])
    top_k = s.pop("top_k")
    return {
        "model": MODEL,
        "messages": [{"role": "system", "content": render(system, **v)},
                     {"role": "user", "content": render(user, **v)}],
        "response_format": {"type": "json_schema", "json_schema": {"name": step, "strict": True, "schema": schema}},
        "extra_body": {"top_k": top_k, "enable_thinking": False},
        **s,
    }


def build_repair_messages(original_messages: list[dict], bad_output: str, errors: str) -> list[dict]:
    return original_messages + [
        {"role": "assistant", "content": bad_output},
        {"role": "user", "content": render(JSON_REPAIR_USER, errors=errors)},
    ]


# ===========================================================================
# swap_names — placeholders -> names, for display and narration.
# First narrator mention of each id in the whole story = full name, later = short name.
# Inside dialogue (‘ … ’) always the short name, and it doesn't count as the introduction.
# For "attached" languages, fixes the joint where a case ending meets the name:
#   Bengali  {C1}এর: vowel-final name → মীরার, consonant-final → আর্যনের
#            {C1}এ  : vowel-final → কলকাতায়, consonant-final → আর্যনে
#   Gujarati {C1}એ  : consonant-final → આર્યને, vowel-final stays મીરાએ
#   Marathi  suffixes (ने, ला, चा) start with a consonant and are simply appended.
#            Have a Marathi speaker confirm oblique forms for consonant-final names.
# ===========================================================================
_BN_VOWEL_END = re.compile(r"[অ-ঔা-ৌৗ]$")
_BN_CONS_END = re.compile("[\u0995-\u09B9\u09CE\u09DC-\u09DF]$")   # ক-হ, ৎ, ড়-য় (code points pinned)
_GU_CONS_END = re.compile(r"[ક-હ]$")


def _join(name: str, rest: str, lang: str) -> tuple[str, str]:
    if lang == "bn":
        if rest.startswith("এর"):
            if _BN_VOWEL_END.search(name):
                return name + "র", rest[2:]
            if _BN_CONS_END.search(name):
                return name + "ের", rest[2:]
        elif rest.startswith("এ"):
            if _BN_VOWEL_END.search(name):
                return name + "য়", rest[1:]
            if _BN_CONS_END.search(name):
                return name + "ে", rest[1:]
    if lang == "gu" and rest.startswith("એ") and _GU_CONS_END.search(name):
        return name + "ે", rest[1:]
    return name, rest


def swap_names(story: dict, adaptation: dict, lang: str = "hi") -> dict:
    """Return a copy of story with placeholders replaced. Store the placeholder version;
    call this only to display or narrate."""
    names = {x["id"]: (x["name_native"], x.get("name_short") or x["name_native"])
             for x in adaptation.get("characters", []) + adaptation.get("entities", [])}
    seen: set[str] = set()
    out = json.loads(json.dumps(story, ensure_ascii=False))
    for beat in out["beats"]:
        for line in beat["lines"]:
            line["text"] = _swap_line(line["text"], names, seen, lang)
    return out


def _swap_line(text: str, names: dict, seen: set, lang: str) -> str:
    """Inside dialogue (between ‘ and ’) people use the everyday name, never the full one,
    and a mention in dialogue does not count as the introduction: the narrator's next
    mention of that person still gets the full name."""
    out: list[str] = []
    while True:
        m = re.search(r"\{([CE][0-9]+)\}", text)
        if not m:
            out.append(text)
            return "".join(out)
        out.append(text[:m.start()])
        so_far = "".join(out)
        in_dialogue = so_far.rfind("‘") > so_far.rfind("’")
        pid = m.group(1)
        full, short = names.get(pid, (m.group(0), m.group(0)))
        if in_dialogue:
            name = short
        else:
            name = short if pid in seen else full
            seen.add(pid)
        name, text = _join(name, text[m.end():], lang)
        out.append(name)


# ===========================================================================
# lint_story — deterministic checks after STORY / STORY_EDIT / TWIST_REWRITE.
# "twists" problems → TWIST_REWRITE <problems>; "format" → TWIST_REWRITE (R4) or
# JSON_REPAIR; "style" are warnings (heavy words) you can batch into one rewrite.
# ===========================================================================
_PLACEHOLDER = re.compile(r"\{([CE][0-9]+)\}")


def lint_story(story: dict, bible: dict, adaptation: dict, lang: str = "hi") -> dict[str, list[str]]:
    p = LANGUAGE_PROFILES[lang]
    in_script = re.compile(f"[{p['script_re']}]")
    digits = re.compile(f"[0-9{p['native_digits']}]")
    fmt, tw, style = [], [], []
    valid_ids = {c["id"] for c in bible["characters"]} | {e["id"] for e in bible["entities"]}
    named = adaptation.get("characters", []) + [e for e in adaptation.get("entities", [])
                                                if e.get("type") in ("place", "ship", "organization")]
    raw_names = {x[k] for x in named for k in ("name_native", "name_short", "name_latin") if x.get(k)}
    order = [b["id"] for b in bible["beats"]]
    got = [b["id"] for b in story["beats"]]
    if got != order:
        fmt.append(f"beat ids must be exactly {order} in that order; got {got}")
    pos = {bid: i for i, bid in enumerate(order)}
    seen: dict[tuple[str, str], list[str]] = {}
    for b in story["beats"]:
        for i, ln in enumerate(b["lines"]):
            where, t = f"{b['id']} line {i + 1}", ln["text"]
            bare = _PLACEHOLDER.sub("", t)
            foreign = sorted({ch for ch in bare if unicodedata.category(ch)[0] in "LM" and not in_script.match(ch)})
            if foreign:
                fmt.append(f"{where}: characters outside {p['script']} script: {''.join(foreign[:12])}")
            for pid in _PLACEHOLDER.findall(t):
                if pid not in valid_ids:
                    fmt.append(f"{where}: unknown placeholder {{{pid}}}")
            if digits.search(bare):
                fmt.append(f"{where}: digits — write numbers as words")
            for n in raw_names:
                if n in bare:
                    fmt.append(f"{where}: raw name '{n}' — use its placeholder")
            if '"' in t:
                fmt.append(f"{where}: double quote in text — use ‘ ’")
            if not t.rstrip().rstrip("’").rstrip()[-1:] in p["enders"]:
                fmt.append(f"{where}: line must end with one of {' '.join(p['enders'])}")
            for heavy, light in p["swaps"].items():
                if heavy in bare:
                    style.append(f"{where}: heavy word '{heavy}' — use {light}")
            if ln["twist_id"] and ln["twist_role"] != "none":
                seen.setdefault((ln["twist_id"], ln["twist_role"]), []).append(b["id"])
                if ln["twist_role"] == "reveal" and ln["cue"] != "shock":
                    tw.append(f"{ln['twist_id']}: reveal line in {b['id']} must have cue 'shock'")
            elif ln["twist_id"] or ln["twist_role"] != "none":
                fmt.append(f"{where}: twist_id and twist_role must be both set or both empty")
    for t in bible["twists"]:
        tid, sb, rb = t["id"], t["setup_beat"], t["reveal_beat"]
        setups, reveals = seen.get((tid, "setup"), []), seen.get((tid, "reveal"), [])
        if sb not in setups:
            tw.append(f"{tid}: missing setup line in {sb}" + (f" (found in {setups})" if setups else ""))
        if len(reveals) != 1:
            tw.append(f"{tid}: needs exactly one reveal line, in {rb}; found {len(reveals)} {reveals}")
        elif reveals[0] != rb:
            tw.append(f"{tid}: reveal is in {reveals[0]} but must be in {rb}")
        elif setups and min(pos.get(x, 99) for x in setups) >= pos.get(rb, -1):
            tw.append(f"{tid}: setup must come before the reveal beat {rb}")
    return {"format": fmt, "twists": tw, "style": style}
