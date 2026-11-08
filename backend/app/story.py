"""Story text helpers shared by the pipeline, edits and narration.

The story is stored as beats whose text contains {ID} placeholders for bible terms.
Renames are then a dictionary change, not a rewrite, and the frontend resolves the
same placeholders the same way.
"""
import difflib
import re

PH = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
# must match the frontend: split(/(?<=[।.!?”])\s+/)
SENT_SPLIT = re.compile(r"(?<=[।.!?”])\s+")


def resolve(text: str, terms: dict) -> str:
    return PH.sub(lambda m: terms[m.group(1)]["val"] if m.group(1) in terms else m.group(1), text)


def sanitize(text: str, terms: dict) -> str:
    """Drop braces around unknown ids so a stray placeholder never reaches the reader or TTS."""
    return PH.sub(lambda m: m.group(0) if m.group(1) in terms else m.group(1), text).strip()


def sentences(beats: list) -> list:
    out = []
    for b in beats:
        for i, raw in enumerate(SENT_SPLIT.split(b["text"])):
            if raw:
                out.append({"sid": f"{b['id']}-{i}", "beat": b["id"], "raw": raw})
    return out


def _tokens(s: str) -> list:
    return re.findall(r"\s*\S+\s*", s) or [s]


def word_diff(before: str, after: str):
    """-> (before_segs, after_segs) in the frontend's {n, hl, t} shape."""
    a, b = _tokens(before), _tokens(after)
    bs, as_ = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            bs.append({"n": True, "hl": False, "t": "".join(a[i1:i2])})
            as_.append({"n": True, "hl": False, "t": "".join(b[j1:j2])})
        else:
            if i2 > i1:
                bs.append({"n": False, "hl": True, "t": "".join(a[i1:i2])})
            if j2 > j1:
                as_.append({"n": False, "hl": True, "t": "".join(b[j1:j2])})
    return bs, as_


def highlight(text: str, needle: str):
    if not needle or needle not in text:
        return [{"n": True, "hl": False, "t": text}]
    out, parts = [], text.split(needle)
    for i, p in enumerate(parts):
        if p:
            out.append({"n": True, "hl": False, "t": p})
        if i < len(parts) - 1:
            out.append({"n": False, "hl": True, "t": needle})
    return out


def check_twists(beats: list, twists: list) -> list:
    """Problems with twist structure (empty list = fine)."""
    order = {b["id"]: i for i, b in enumerate(beats)}
    problems = []
    for t in twists:
        if t["beat"] not in order or t["setup"] not in order:
            problems.append(f"twist {t['id']} points at a missing beat")
        elif order[t["setup"]] >= order[t["beat"]]:
            problems.append(f"twist {t['id']}: setup {t['setup']} does not come before reveal {t['beat']}")
    return problems
