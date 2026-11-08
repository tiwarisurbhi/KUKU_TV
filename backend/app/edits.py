"""Chat messages and comments -> drafts (Keep / Undo).

Every message goes through qwen_prompts' chat_router, which returns actions:
  rename       -> name change in the adaptation (no story rewrite needed: placeholders)
  persona/pace -> narrator settings
  story_edit   -> story_edit step (all beats, ids locked) -> lint_story -> twist_rewrite
  question/unclear -> a reply, no draft
A draft never changes the saved project; its `apply` comes back through PUT /state on Keep.
"""
import copy
import json
import logging
import re

from . import display, llm, pipeline
from . import qwen_prompts as qp

log = logging.getLogger("edits")
PERSONA_NAMES = {"ott": "OTT storyteller", "grandma": "Grandmother storyteller", "radio": "Radio-drama host", "trailer": "Thriller trailer voice"}
LATIN = re.compile(r"^[A-Za-z][A-Za-z\s'.-]*$")


def _with_names(adaptation: dict, changes: dict) -> dict:
    ad = copy.deepcopy(adaptation)
    for x in ad["characters"] + ad["entities"]:
        if x["id"] in changes:
            x.update({k: v for k, v in changes[x["id"]].items() if v})
    return ad


def rename_draft(p: dict, changes: dict, title: str = "") -> dict:
    """changes: {id: {name_native, name_short, name_latin}}"""
    ad2 = _with_names(p["adaptation"], changes)
    t_old, t_new = display.terms(p), display.terms({**p, "adaptation": ad2})
    rows = [display.rename_row(t_old[k]["kind"], t_old[k]["src"], t_old[k]["val"], t_new[k]["val"])
            for k in changes if k in t_old]
    story_rows = display.diff_rows(p, new_adaptation=ad2)
    n = len(story_rows)
    first = next(iter(changes))
    return {"kind": "story", "title": title or f"Rename {t_old[first]['val']} → {t_new[first]['val']}",
            "sub": f"{n} passage{'s' if n != 1 else ''} and the bible change. Twists are untouched.",
            "rows": (rows + story_rows)[:3], "more": max(0, len(rows) + n - 3),
            "apply": {"names": {k: {f: v for f, v in ch.items() if v} for k, ch in changes.items()}}}


def persona_draft(p: dict, persona: str, pace: float, title: str = "") -> dict:
    cur_persona, cur_pace = p.get("persona", "ott"), float(p.get("pace", 1.0))
    pace = min(1.2, max(0.8, round(pace * 20) / 20))
    prows = [{"label": "Narrator", "before": PERSONA_NAMES[cur_persona], "after": PERSONA_NAMES[persona],
              "cls": "new" if persona != cur_persona else ""},
             {"label": "Pace", "before": f"{cur_pace:.2f}×", "after": f"{pace:.2f}×", "cls": "new" if pace != cur_pace else ""}]
    return {"kind": "persona", "title": title or "Change how the narrator sounds",
            "sub": "The story text stays exactly as it is.", "prows": prows, "apply": {"persona": persona, "pace": pace}}


async def story_edit(p: dict, instruction: str, anchor: str = "", title: str = "") -> dict:
    s = pipeline.sheets(p)
    r = pipeline.dump(await llm.call("story_edit", p["lang"], edit_request=instruction, anchor=anchor or "",
                                     story=p["story"], **s))
    old_ids = [b["id"] for b in p["story"]["beats"]]
    by_id = {b["id"]: b for b in r["beats"] if b.get("lines")}
    if not by_id:
        return {"kind": "none", "title": "No change", "sub": "The model returned no usable beats."}
    new = {**p["story"], "beats": [by_id.get(bid, ob) for bid, ob in zip(old_ids, p["story"]["beats"])]}  # ids/order locked
    if r.get("title"):
        new["title"] = r["title"]
    new, lint = await pipeline.check_and_fix(p, new)
    rows = display.diff_rows(p, new_story=new)
    if not rows:
        return {"kind": "none", "title": "No change", "sub": "Nothing in the story changed for that request."}
    n = len(rows)
    left = len(lint["twists"]) + len(lint["format"])
    return {"kind": "story", "title": title or "Edit the story",
            "sub": f"{n} passage{'s' if n != 1 else ''} change." + (" Twists and their setups stay intact." if not lint["twists"]
                                                                       else f" Note: {len(lint['twists'])} twist issue(s) remain."),
            "rows": rows[:3], "more": max(0, n - 3), "apply": {"story": new}, "lint_left": left}


async def handle(p: dict, message: str, quote: str = "", beat: str = "") -> dict:
    """Route a chat message or a comment (with its selected text) to the right draft."""
    s = pipeline.sheets(p)
    recent = "\n".join(p.get("chat", [])[-6:]) or ""
    msg = message if not quote else f'(About the selected text: "{quote}") {message}'
    r = await llm.call("chat_router", p["lang"], cast_sheet=s["cast_sheet"], persona=p.get("persona", "ott"),
                       recent_chat=recent, message=msg)
    p.setdefault("chat", []).append(f"writer: {msg}")
    acts = r.actions
    known = display.name_table(p["adaptation"])
    renames = [a for a in acts if a.type == "rename" and a.target_id in known and (a.new_name_native or a.new_name_latin)]
    voice = [a for a in acts if a.type in ("persona", "pace")]
    edits = [a for a in acts if a.type == "story_edit" and a.instruction.strip()]
    others = [a.type for a in acts if a not in renames + voice + edits]

    if edits:
        d = await story_edit(p, " ".join(a.instruction for a in edits), anchor=quote, title=_short(r.reply) or "Edit the story")
    elif renames:
        changes = {}
        for a in renames:
            native, latin = a.new_name_native.strip(), a.new_name_latin.strip()
            if not native and latin:
                native = (await transliterate(p, a.target_id, latin))["name_native"]
            changes[a.target_id] = {"name_native": native, "name_short": native.split()[0] if native else "",
                                    "name_latin": latin}
        d = rename_draft(p, changes)
    elif voice:
        persona, pace = p.get("persona", "ott"), float(p.get("pace", 1.0))
        for a in voice:
            if a.type == "persona" and a.persona:
                persona = a.persona
            if a.type == "pace" and a.pace:
                pace += 0.1 if a.pace == "faster" else -0.1
        d = persona_draft(p, persona, pace, title=_short(r.reply))
    else:
        d = {"kind": "reply", "title": r.reply or "I couldn't tell what to change.", "sub": ""}
    if (edits or renames) and voice:
        d["also"] = "Voice changes in that message were skipped — send them on their own."
    d["reply"] = r.reply
    p["chat"].append(f"app: {r.reply}")
    if others:
        log.info("router actions not applied: %s", others)
    return d


async def transliterate(p: dict, key: str, value: str) -> dict:
    """-> {name_native, name_short, name_latin}"""
    t = display.name_table(p["adaptation"])[key]
    value = value.strip()
    script = re.compile(f"[{qp.LANGUAGE_PROFILES[p['lang']]['script_re']}]")
    if not LATIN.match(value) and script.search(value):          # already typed in the target script
        return {"name_native": value, "name_short": value.split()[0], "name_latin": t.get("name_latin", "")}
    r = await llm.call("transliterate", p["lang"], entity_type="person" if key.startswith("C") else t.get("type", "place"),
                       gender=t.get("gender", "unknown"), name=value)
    return {"name_native": r.name_native.strip() or value, "name_short": (r.name_short or r.name_native).strip(),
            "name_latin": r.name_latin.strip() or value}


def _short(reply: str) -> str:
    reply = (reply or "").strip().rstrip(".")
    return reply if len(reply) <= 60 else reply[:57] + "…"
