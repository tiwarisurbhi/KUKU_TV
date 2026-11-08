"""Live view of what the model is writing, for the Adapt page.

The model streams JSON. This module reads the half-finished JSON (no parser needed:
it just walks the string literals in order and remembers which key each belongs to)
and turns it into readable lines: beats as they are found, names as they are mapped,
story sentences as they are written. Nothing here is saved or narrated; it is a
progress view only, kept in memory and served with GET /api/projects/{id}.
"""
import json
import re
import time

LIVE: dict = {}                  # project id -> {"label", "lines", "chars", "t"}
_STR = re.compile(r'"((?:[^"\\]|\\.)*)("|$)', re.S)
_PH = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
MAX_LINES = 18


def _unescape(v: str) -> str:
    v = re.sub(r"\\u[0-9a-fA-F]{0,3}$|\\$", "", v)       # drop a cut-off escape at the very end
    try:
        return json.loads(f'"{v}"')
    except json.JSONDecodeError:
        return v.replace('\\"', '"').replace("\\n", " ")


def tokens(text: str):
    """-> [(section, key, value, is_open)] for every string VALUE in partial JSON, in order."""
    out, key, section, pos = [], None, None, 0
    for m in _STR.finditer(text):
        if m.start() < pos:
            continue
        pos = m.end()
        raw, closed = m.group(1), m.group(2) == '"'
        rest = text[m.end():m.end() + 40].lstrip()
        if closed and rest.startswith(":"):                    # it's a key
            key = raw
            after = rest[1:].lstrip()
            if after.startswith("["):
                section = key
            continue
        if not closed:
            prev = text[:m.start()].rstrip()[-1:]
            if prev not in (":", "["):                         # an unfinished string after { or , may be a key: wait for it
                continue
        out.append((section, key, _unescape(raw), not closed))
    return out


def _resolve(t: str, names: dict) -> str:
    t = re.sub(r"\{[A-Za-z0-9_]*$", "", t)                  # hide a placeholder still being typed
    return _PH.sub(lambda m: names[m.group(1)].get("name_native", m.group(1)) if m.group(1) in names else "…", t)


def lines_for(stage: str, text: str, names: dict, lang_cls: str) -> list:
    """Readable lines for one qwen_prompts step's partial output. Each: {text, cls, open}."""
    out, held = [], ""
    for section, key, v, is_open in tokens(text):
        if not v.strip() and not is_open:
            continue
        line = None
        if key == "notes":
            line = (v, "ll-think")
        elif stage == "chunk_notes":
            if section == "characters" and key == "name":
                line = (f"Noticed {v}", "meta")
            elif section == "entities" and key == "name":
                line = (f"Place / thing — {v}", "meta")
            elif section == "events" and key == "summary":
                line = (v, "")
            elif section == "secrets" and key == "setup" and v.strip():
                line = (f"Secret — {v}", "twist")
        elif stage == "bible":
            if key == "logline":
                line = (v, "")
            elif key == "genre":
                line = (f"Genre — {v}", "meta")
            elif section == "characters" and key == "name":
                line = (f"Cast — {v}", "meta")
            elif section == "beats" and key == "summary":
                line = (v, "")
            elif section == "twists" and key == "reveal":
                line = (f"Twist — {v}", "twist")
        elif stage == "adaptation":
            if key == "region":
                line = (f"Setting — {v}", "meta")
            elif section in ("characters", "entities") and key == "source_name":
                held = v
            elif section in ("characters", "entities") and key == "name_native":
                line = (f"{held} → {v}", lang_cls)
            elif section == "glossary" and key == "source_term":
                held = v
            elif section == "glossary" and key == "target_term":
                line = (f"{held} → {v}", "meta " + lang_cls)
        elif stage == "story":
            if key == "title":
                line = (_resolve(v, names), lang_cls + " title")
            elif section == "lines" and key == "text":
                line = (_resolve(v, names), lang_cls)
        if line:
            out.append({"text": line[0], "cls": line[1].strip(), "open": is_open})
    return out[-MAX_LINES:]


def updater(pid: str, label: str, stage: str, terms_fn, lang_cls: str):
    """A callback for llm.structured(on_text=...) that keeps LIVE[pid] current."""
    def on_text(text: str):
        LIVE[pid] = {"label": label, "lines": lines_for(stage, text, terms_fn(), lang_cls),
                     "chars": len(text), "t": time.time()}
    return on_text


def clear(pid: str):
    LIVE.pop(pid, None)
