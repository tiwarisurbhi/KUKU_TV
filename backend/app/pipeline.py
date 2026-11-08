"""Source -> adapted story, using qwen_prompts for every model call.

UI step  | qwen_prompts step(s)
0 Reading source    chunk_notes (parallel over ~8k-word slices)
1 Extracting beats  bible
2 Tagging twists    (bible's twists, linked to setup/reveal beats)
3 Adapting culture  adaptation (names full + short, glossary, plot adjustments)
4 Writing story     story (line-level cues and twist marks, {C1} placeholders)
5 Checking twists   lint_story -> twist_rewrite (merge beats by id) -> lint again
"""
import asyncio
import json
import logging

from . import config, db, display, live, llm, persona_prompts, voices
from . import qwen_prompts as qp

log = logging.getLogger("pipeline")


def chunk_words(text: str) -> list:
    words = text.split()
    size, ov = config.CHUNK_WORDS, config.CHUNK_OVERLAP_WORDS
    if len(words) <= size:
        return [text]
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + size]))
        i += size - ov
    return out


def _set(p, **kw):
    p.update(kw)
    db.save(p)


def dump(model) -> dict:
    return model.model_dump(exclude={"notes"})


# ---------- shared sheets (also used by edits) ----------
def sheets(p: dict) -> dict:
    b, a = p["bible"], p["adaptation"]
    return {"cast_sheet": qp.render_cast_sheet(b, a), "glossary": qp.render_glossary(a),
            "twist_sheet": qp.render_twist_sheet(b), "persona_guide": persona_prompts.guide(p.get("persona") or "ott", p["lang"])}


def merge_beats(story: dict, beats: list) -> dict:
    by_id = {b["id"]: b for b in beats}
    return {**story, "beats": [by_id.get(b["id"], b) for b in story["beats"]]}


async def check_and_fix(p: dict, story: dict, on_text=None) -> tuple:
    """lint_story; if twists/format problems, one twist_rewrite merged by beat id; lint again."""
    lint = qp.lint_story(story, p["bible"], p["adaptation"], p["lang"])
    problems = lint["twists"] + lint["format"]
    if problems:
        r = await llm.call("twist_rewrite", p["lang"], on_text=on_text, problems="\n".join(problems[:40]),
                           story=story, **sheets(p))
        fixed = [b for b in dump(r)["beats"] if b.get("lines")]
        if fixed:
            story = merge_beats(story, fixed)
        lint = qp.lint_story(story, p["bible"], p["adaptation"], p["lang"])
    return story, lint


async def run(p: dict) -> None:
    try:
        await _run(p)
    except Exception as e:                       # surface any failure to the UI
        log.exception("pipeline failed")
        _set(p, status="error", error=str(e)[:500])
    finally:
        live.clear(p["id"])


async def _run(p: dict) -> None:
    lang = p["lang"]
    culture = config.CULTURES.get(p["culture"], "India")
    trace = ["", "", "", "", "", ""]
    lc = f"story-{lang}"
    names = lambda: display.name_table(p.get("adaptation") or {})
    _set(p, status="running", step=0, trace=trace, error=None)

    # 0 — read in chunks (parallel)
    chunks = chunk_words(p["source"])
    done = 0

    async def read(i, text):
        nonlocal done
        r = await llm.call("chunk_notes", lang, chunk_index=i + 1, chunk_total=len(chunks), episode_range="",
                           chunk_text=text,
                           on_text=live.updater(p["id"], f"Reading part {i + 1} of {len(chunks)}" if len(chunks) > 1
                                                else "Reading the source", "chunk_notes", names, lc))
        done += 1
        trace[0] = f"Read {done} of {len(chunks)} part{'s' if len(chunks) > 1 else ''}"
        db.save(p)
        return dump(r)

    notes = await asyncio.gather(*[read(i, c) for i, c in enumerate(chunks)])
    _set(p, step=1)

    # 1+2 — bible
    bible = dump(await llm.call("bible", lang, source_title="", episode_count="", chunk_notes=notes,
                                on_text=live.updater(p["id"], "Extracting beats and twists", "bible", names, lc)))
    trace[0] = f"{bible['genre'] or 'Story'} · {len(bible['characters'])} characters, {len(bible['entities'])} places and objects"
    trace[1] = f"{len(bible['beats'])} beats, from opening to resolution"
    _set(p, step=2, bible=bible)
    trace[2] = f"{len(bible['twists'])} twists, each linked back to the beat that sets it up"
    _set(p, step=3)

    # 3 — adaptation
    ad = dump(await llm.call("adaptation", lang, target_culture=culture, writer_instructions="", bible=bible,
                             on_text=live.updater(p["id"], f"Adapting names and places for {culture}", "adaptation", names, lc)))
    ids = {x["id"] for x in ad["characters"] + ad["entities"]}
    missing = [x["id"] for x in bible["characters"] + bible["entities"] if x["id"] not in ids]
    for mid in missing:                                   # never let a raw {Cn} reach the reader
        src = next(x for x in bible["characters"] + bible["entities"] if x["id"] == mid)
        (ad["characters"] if mid.startswith("C") else ad["entities"]).append(
            {"id": mid, "source_name": src["name"], "name_native": src["name"], "name_short": src["name"],
             "name_latin": src["name"], **({"gender": src.get("gender", "unknown"), "adapted_role": src.get("role", ""),
                                            "speech_style": "", "why": ""} if mid.startswith("C") else {"type": src.get("type", "other"), "why": ""})})
    trace[3] = (f"{culture} — {len(ad['characters'])} names, {len(ad['entities'])} places/objects, "
                f"{len(ad['glossary'])} glossary terms" + (f" ({len(missing)} kept from source)" if missing else ""))
    _set(p, step=4, adaptation=ad)
    # cast the narrator now (needs only bible + adaptation); runs while the story is being written
    casting = asyncio.create_task(voices.pick(p, p.get("persona") or "ott"))

    # 4 — story
    words = len(p["source"].split())
    target = max(350, min(900, words // 12))
    s = sheets(p)
    story = dump(await llm.call(
        "story", lang, setting=ad["setting"], beat_sheet=qp.render_beat_sheet(bible),
        plot_adjustments=ad["plot_adjustments"], keep_unchanged=ad["keep_unchanged"], writer_instructions="",
        target_words=target, cast_sheet=s["cast_sheet"], glossary=s["glossary"], twist_sheet=s["twist_sheet"],
        persona_guide=s["persona_guide"],
        on_text=live.updater(p["id"], f"Writing the story in {qp.LANGUAGE_PROFILES[lang]['mix_name']}", "story", names, lc)))
    n_lines = sum(len(b["lines"]) for b in story["beats"])
    trace[4] = f"One continuous story, {len(story['beats'])} beats, {n_lines} lines"
    _set(p, step=5)

    # 5 — lint -> twist_rewrite -> lint
    story, lint = await check_and_fix(p, story, live.updater(p["id"], "Fixing flagged lines", "story", names, lc))
    tw = display.twists({**p, "story": story})
    bad = len(lint["twists"]) + len(lint["format"])
    trace[5] = (f"All {len(tw)} twists set up before their reveal; lint clean" if not bad else
                f"{len(tw)} twists in place; {bad} lint issue{'s' if bad != 1 else ''} left after one fix")
    if lint["style"]:
        trace[5] += f" · {len(lint['style'])} heavy-word warnings"
    voice = await casting
    if voice.get("name"):
        trace[3] += f" · narrator {voice['name']}"
    _set(p, status="ready", step=6, story=story, lint=lint, version=1, voice=voice)
    db.add_version(p["id"], 1, {"story": story, "adaptation": ad})
