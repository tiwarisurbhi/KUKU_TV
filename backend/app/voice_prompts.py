"""VOICE_PICK — choose the narrator voice for one story from real Cartesia voices.

Kept outside qwen_prompts.py (whose prompt text is frozen) but written to the same
conventions: <<slots>> filled by qwen_prompts.render, strict JSON schema, `notes`
pressure valve, OUTPUT_CONTRACT, REMINDER at the end of the user message.
The code filters the catalog (language, native speaker, gender) BEFORE this runs;
the model only ranks ~12 finalists and must answer with an id from the list.
"""
from . import qwen_prompts as qp

SAMPLING = {"temperature": 0.2, "top_p": 0.8, "top_k": 20, "presence_penalty": 0.0, "max_tokens": 500}

VOICE_PICK_SYSTEM = """You are the casting director of an Indian audio-microdrama app. You choose the ONE narrator voice that will read a
whole story aloud, from a short list of real voices in the text-to-speech catalog.

HOW TO CHOOSE
1. Fit the narrator persona first. A grandmother storyteller needs a warm, mature, unhurried voice; a radio-drama host a
   clear, expressive, theatrical one; a trailer voice a deep, intense, dramatic one.
2. Then fit the story: genre, tone, region and social world. A Kolkata family drama wants a different voice from a
   Mumbai crime thriller.
3. Prefer native speakers of <<language_name>>, and an accent that matches the story's region when one is listed.
4. Prefer voices described for narration, storytelling, drama or broadcasting over ones described for customer
   support, assistants, IVR or sales calls.
5. Choose ONLY ids that appear in the list, copied exactly. Never invent an id.
6. backup_ids: the next two best ids from the list, best first, different from voice_id.
7. reason: one short English sentence the writer will see, saying why this voice suits this story
   (e.g. "warm, older voice suits a Kolkata family drama").

SCHEMA
{"voice_id":str,"backup_ids":[str],"reason":str,"notes":str}

""" + qp.OUTPUT_CONTRACT

VOICE_PICK_USER = """<story language="<<language_name>>" genre="<<genre>>" tone="<<tone>>">
Logline: <<logline>>
Setting: <<setting>>
</story>
<narrator_persona>
<<persona_guide>>
</narrator_persona>
<voices>
id | name | gender | accent | native speaker | tagline | description
<<voices>>
</voices>

REMINDER: voice_id and backup_ids are ids copied exactly from the list above; reason is one short English sentence;
one JSON object, no fences.""" + qp.NO_THINK_SUFFIX

VOICE_PICK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["voice_id", "backup_ids", "reason", "notes"],
    "properties": {"voice_id": {"type": "string"}, "backup_ids": {"type": "array", "items": {"type": "string"}},
                   "reason": {"type": "string"}, "notes": {"type": "string"}},
}


def build_voice_request(lang: str = "hi", **variables) -> dict:
    v = {**qp.language_vars(lang), **variables}
    s = dict(SAMPLING)
    top_k = s.pop("top_k")
    return {
        "model": qp.MODEL,
        "messages": [{"role": "system", "content": qp.render(VOICE_PICK_SYSTEM, **v)},
                     {"role": "user", "content": qp.render(VOICE_PICK_USER, **v)}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "voice_pick", "strict": True, "schema": VOICE_PICK_SCHEMA}},
        "extra_body": {"top_k": top_k, "enable_thinking": False},
        **s,
    }
