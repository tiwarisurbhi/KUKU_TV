"""What the editor sees and the narrator reads, derived from the stored placeholder story.

The story is stored with {C1}/{E2} placeholders (qwen_prompts contract). Display and
narration always go through qwen_prompts.swap_names(): full name on first narrator
mention, short name after and in dialogue, and fused case endings fixed for bn/gu.
"""
import re

from . import qwen_prompts as qp
from .story import highlight, word_diff

_PH = re.compile(r"\{([CE][0-9]+)\}")


def name_table(adaptation: dict) -> dict:
    return {x["id"]: x for x in adaptation.get("characters", []) + adaptation.get("entities", [])}


def swapped(story: dict, adaptation: dict, lang: str) -> dict:
    return qp.swap_names(story, adaptation, lang)


def _parts_for(story: dict, adaptation: dict, lang: str) -> list:
    """Same walk as qp._swap_line, but remembers which span is which name (for the name 'morph'
    animation and the bible hover). Verified against swap_names; falls back to plain text."""
    names = {x["id"]: (x["name_native"], x.get("name_short") or x["name_native"]) for x in name_table(adaptation).values()}
    src = {k: v.get("source_name", "") for k, v in name_table(adaptation).items()}
    seen, out = set(), []
    for beat in story["beats"]:
        for line in beat["lines"]:
            text, parts, done = line["text"], [], ""
            while True:
                m = _PH.search(text)
                if not m:
                    if text:
                        parts.append({"t": text})
                    break
                if m.start():
                    parts.append({"t": text[:m.start()]})
                done += text[:m.start()]
                in_dialogue = done.rfind("‘") > done.rfind("’")
                pid = m.group(1)
                full, short = names.get(pid, (m.group(0), m.group(0)))
                if in_dialogue:
                    name = short
                else:
                    name = short if pid in seen else full
                    seen.add(pid)
                name, text = qp._join(name, text[m.end():], lang)
                parts.append({"t": name, "id": pid, "src": src.get(pid, "")})
                done += name
            out.append(parts)
    return out


def lines(p: dict) -> list:
    story, ad, lang = p["story"], p["adaptation"], p["lang"]
    sw = swapped(story, ad, lang)
    parts = _parts_for(story, ad, lang)
    out, k = [], 0
    for b_raw, b_sw in zip(story["beats"], sw["beats"]):
        for i, (raw, ln) in enumerate(zip(b_raw["lines"], b_sw["lines"])):
            pr = parts[k] if "".join(x["t"] for x in parts[k]) == ln["text"] else [{"t": ln["text"]}]
            out.append({"sid": f"{b_raw['id']}-{i}", "beat": b_raw["id"], "text": ln["text"], "cue": raw["cue"],
                        "twist_id": raw["twist_id"], "twist_role": raw["twist_role"], "parts": pr})
            k += 1
    return out


def title(p: dict) -> str:
    names = name_table(p["adaptation"])
    return _PH.sub(lambda m: names[m.group(1)]["name_native"] if m.group(1) in names else "", p["story"].get("title", "")).strip()


def terms(p: dict) -> dict:
    """Bible panel rows: kind, source name, adapted (full) name, short name, Latin, gloss."""
    bible = {x["id"]: x for x in p["bible"].get("characters", []) + p["bible"].get("entities", [])}
    out = {}
    for x in p["adaptation"].get("characters", []):
        role = (x.get("adapted_role") or bible.get(x["id"], {}).get("role") or "Character").split(",")[0].strip()
        out[x["id"]] = {"kind": role[:1].upper() + role[1:28], "src": x.get("source_name") or bible.get(x["id"], {}).get("name", ""),
                        "val": x["name_native"], "short": x.get("name_short") or x["name_native"],
                        "en": x.get("name_latin", ""), "person": True,
                        "gloss": f"called {x.get('name_short') or x['name_native']}" if x.get("name_short") and x.get("name_short") != x["name_native"] else ""}
    for x in p["adaptation"].get("entities", []):
        t = (x.get("type") or "other")
        out[x["id"]] = {"kind": t[:1].upper() + t[1:], "src": x.get("source_name") or bible.get(x["id"], {}).get("name", ""),
                        "val": x["name_native"], "short": x.get("name_short") or x["name_native"],
                        "en": x.get("name_latin", ""), "person": False, "gloss": x.get("name_latin", "")}
    return out


def twists(p: dict, ls: list = None) -> list:
    """Line-level twist map for the UI: which line plants it, which line reveals it."""
    ls = ls or lines(p)
    label = {t["id"]: (t.get("kind") or "").strip() or "Twist" for t in p["bible"].get("twists", [])}
    desc = {t["id"]: t.get("reveal", "") for t in p["bible"].get("twists", [])}
    found = {}
    for l in ls:
        if l["twist_id"] and l["twist_role"] in ("setup", "reveal"):
            t = found.setdefault(l["twist_id"], {"id": l["twist_id"], "label": label.get(l["twist_id"], "Twist"),
                                                  "reveal_text": desc.get(l["twist_id"], "")})
            if l["twist_role"] == "reveal" and "reveal_sid" not in t:
                t.update(reveal_sid=l["sid"], reveal_beat=l["beat"])
            if l["twist_role"] == "setup" and "setup_sid" not in t:
                t.update(setup_sid=l["sid"], setup_beat=l["beat"])
    return [t for t in found.values() if "reveal_sid" in t]


def beat_texts(story: dict, adaptation: dict, lang: str) -> dict:
    sw = swapped(story, adaptation, lang)
    return {b["id"]: " ".join(l["text"] for l in b["lines"]) for b in sw["beats"]}


def diff_rows(p: dict, new_story: dict = None, new_adaptation: dict = None) -> list:
    """Changed passages (by beat) between the current version and a draft, in display text."""
    before = beat_texts(p["story"], p["adaptation"], p["lang"])
    after = beat_texts(new_story or p["story"], new_adaptation or p["adaptation"], p["lang"])
    rows = []
    for bid, old in before.items():
        new = after.get(bid, "")
        if old.strip() != new.strip():
            bs, as_ = word_diff(old, new)
            rows.append({"where": "Story", "before": bs, "after": as_, "bodyRow": True, "beat": bid})
    return rows


def rename_row(kind: str, src: str, old: str, new: str) -> dict:
    return {"where": "Bible · " + kind, "before": highlight(f"{src} → {old}", old),
            "after": highlight(f"{src} → {new}", new), "bodyRow": False}
