"""Canned answers for MOCK_LLM=1, one per qwen_prompts step. Built from the prototype's sample
story so the whole UI can be tested offline. The mock story passes lint_story (Hindi)."""
import json
import re

ENT = [  # id, source, kind/type, person, native, short, latin, gender
    ("C1", "Juliana", "heroine", True, "जाह्नवी", "जाह्नवी", "Jahnavi", "female"),
    ("C2", "Gerald", "fiancé", True, "राजवीर", "राजवीर", "Rajveer", "male"),
    ("C3", "Clarissa", "cousin", True, "कामिनी", "कामिनी", "Kamini", "female"),
    ("E1", "Cathedral", "place", False, "मंडप", "मंडप", "mandap", ""),
    ("E2", "Bridal gown", "object", False, "लहंगा", "लहंगा", "lehenga", ""),
]
TR = {"arjun": "अर्जुन", "meera": "मीरा", "vikram": "विक्रम", "ananya": "अनन्या", "kabir": "कबीर", "radha": "राधा",
      "haveli": "हवेली", "temple": "मंदिर", "saree": "साड़ी", "ghagra": "घाघरा", "tara": "तारा"}

S = lambda text, cue="none", tid="", role="none": {"text": text, "cue": cue, "twist_id": tid, "twist_role": role}
STORY = [
    ("B1", [S("{C1} बरसों बाद अपनी शादी के लिए महल लौटी।"),
            S("अलमारी में माँ का पुराना {E2} तह किया रखा था, जैसे उसी का इंतज़ार कर रहा हो।", "whisper", "T3", "setup"),
            S("माँ के जाने के बाद से महल पर चाचा का राज था।"),
            S("और महल के काग़ज़ों की बात पर वो हमेशा नज़र फेर लेते थे।", "whisper", "T4", "setup")]),
    ("B2", [S("मेले में {C2} ने कभी उससे वादा किया था कि वो इंतज़ार करेगा।"),
            S("आज वो आँगन के पार खड़ा था, पर उसकी आँखें {C1} से कतरा रही थीं।", "whisper", "T1", "setup")]),
    ("B3", [S("{E1} में जाने से पहले {C3} ने {C1} का घूँघट ठीक किया, कुछ ज़्यादा ही जल्दी में।", "whisper", "T2", "setup"),
            S("उसकी उँगलियाँ काँप रही थीं, पर उसने कुछ नहीं कहा।", "none", "T5", "setup")]),
    ("B4", [S("{C1} अपनी माँ का {E2} पहने आँगन में पहुँची।", "rising"),
            S("ढोल रुक गए, और सबकी नज़रें {E1} की तरफ़ मुड़ गईं।", "pause"),
            S("पर {E1} में उसका इंतज़ार कोई और कर रहा था!", "shock", "T1", "reveal")]),
    ("B5", [S("{C2} चुपचाप {C3} के बगल में जा खड़ा हुआ।", "pause"),
            S("परिवार ने बहुत पहले ही फ़ैसला कर लिया था!", "shock", "T2", "reveal")]),
    ("B6", [S("भीड़ से हटकर {C1} ने {E2} की सिलाई टटोली।", "rising"),
            S("सिलाई में माँ के हाथ की लिखी एक चिट्ठी छिपी थी!", "shock", "T3", "reveal")]),
    ("B7", [S("{C1} ने काँपते हाथों से चिट्ठी खोली।", "pause"),
            S("महल चाचा का कभी था ही नहीं, वो माँ का था, और अब {C1} का था!", "shock", "T4", "reveal"),
            S("{C1} ने चिट्ठी को कसकर मुट्ठी में भींच लिया।", "whisper", "T6", "setup")]),
    ("B8", [S("{C3} ने धीरे से कहा, ‘मैंने घूँघट इसलिए जल्दी ठीक किया था कि चाचा सिलाई न देख लें।’", "shock", "T5", "reveal"),
            S("उसने {C1} की हथेली में तिजोरी की चाबी रख दी।")]),
    ("B9", [S("{C1} {E1} तक गई, दुल्हन बनकर नहीं, महल की मालकिन बनकर।", "rising"),
            S("उसने सबके सामने चिट्ठी पढ़ दी, और चाचा का चेहरा उतर गया!", "shock", "T6", "reveal")]),
    ("B10", [S("शाम तक आँगन ख़ाली था।"),
             S("{C1} ने माँ का {E2} फिर से तह किया, इस बार अपनी अलमारी में।")]),
]
TWISTS = [("T1", "B2", "B4", "Someone else waits at the altar"), ("T2", "B3", "B5", "The family already chose"),
          ("T3", "B1", "B6", "A letter hidden in the seam"), ("T4", "B1", "B7", "The palace is hers"),
          ("T5", "B3", "B8", "The cousin was protecting her"), ("T6", "B7", "B9", "Bride becomes owner")]


def _tag(user: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>\n?(.*?)\n?</{tag}>", user, re.S)
    return m.group(1).strip() if m else ""


def _cast(user: str) -> dict:
    """id -> set of names currently in the cast sheet (+ the mock's Latin/source names)."""
    out = {}
    for m in re.finditer(r"\{(\w+)\} \|.*?called (.*?) \(full: (.*?)\) \| source: ([^|\n]+)", user):
        out[m.group(1)] = {m.group(2).strip(), m.group(3).strip(), m.group(4).strip()}
    for e in ENT:
        out.setdefault(e[0], set()).update({e[1], e[6]})
    return out


def respond(step: str, user: str, lang: str = "hi") -> dict:
    n = "(mock)"
    if step == "chunk_notes":
        return {"chunk_index": 1, "notes": n, "open_threads": [], "secrets": [],
                "characters": [{"name": e[1], "aliases": [], "gender": e[7], "role": e[2], "description": "", "relationships": []}
                               for e in ENT if e[3]],
                "entities": [{"name": e[1], "type": e[2], "significance": ""} for e in ENT if not e[3]],
                "events": [{"episode": 1, "summary": f"Beat {b[0]}", "characters": [], "is_reveal": False} for b in STORY]}
    if step == "bible":
        tw_by_beat = {}
        for t in TWISTS:
            tw_by_beat.setdefault(t[1], []).append(t[0]); tw_by_beat.setdefault(t[2], []).append(t[0])
        return {"title": "The Mother's Gown", "logline": "A bride finds out the estate is hers.", "genre": "Melodrama",
                "tone": "tense", "core_must_keep": ["The letter in the seam", "She ends as the owner"], "notes": n,
                "characters": [{"id": e[0], "name": e[1], "aliases": [], "gender": e[7], "role": e[2], "arc": "", "traits": []}
                               for e in ENT if e[3]],
                "entities": [{"id": e[0], "name": e[1], "type": e[2], "significance": ""} for e in ENT if not e[3]],
                "beats": [{"id": b[0], "title": b[0], "summary": f"Beat {b[0]}", "episodes": "1", "character_ids": [],
                           "entity_ids": [], "twist_ids": tw_by_beat.get(b[0], [])} for b in STORY],
                "twists": [{"id": t[0], "setup": t[3], "reveal": t[3], "setup_beat": t[1], "reveal_beat": t[2],
                            "impact": "", "kind": t[3]} for t in TWISTS]}
    if step == "adaptation":
        return {"setting": {"era": "contemporary", "region": "Rajasthan", "social_world": "old royal family", "why": ""},
                "characters": [{"id": e[0], "source_name": e[1], "name_native": e[4], "name_short": e[5], "name_latin": e[6],
                                "gender": e[7], "adapted_role": e[2], "speech_style": "", "why": ""} for e in ENT if e[3]],
                "entities": [{"id": e[0], "source_name": e[1], "name_native": e[4], "name_short": e[5], "name_latin": e[6],
                              "type": e[2], "why": ""} for e in ENT if not e[3]],
                "glossary": [{"source_term": a, "target_term": b} for a, b in
                             [("veil", "घूँघट"), ("deeds", "काग़ज़"), ("estate", "महल"), ("strongbox", "तिजोरी"),
                              ("wedding", "शादी"), ("letter", "चिट्ठी"), ("uncle", "चाचा"), ("seam", "सिलाई"),
                              ("fair", "मेला"), ("bride", "दुल्हन")]],
                "plot_adjustments": [], "keep_unchanged": ["The letter in the seam"], "notes": n}
    if step == "story":
        return {"title": "माँ का {E2}", "beats": [{"id": b, "lines": ls} for b, ls in STORY], "notes": n}
    if step == "twist_rewrite":
        return {"beats": [], "notes": n}
    if step == "story_edit":
        story = json.loads(_tag(user, "current_story"))
        anchor = _tag(user, "anchor")
        names = {e[0]: e[4] for e in ENT}
        target = None
        if anchor and anchor != "None":
            for b in story["beats"]:
                txt = " ".join(re.sub(r"\{(\w+)\}", lambda m: names.get(m.group(1), ""), l["text"]) for l in b["lines"])
                if anchor[:6] in txt:
                    target = b["id"]
        target = target or "B4"
        for b in story["beats"]:
            if b["id"] == target:
                plain = [l for l in b["lines"] if l["twist_role"] == "none"]
                if plain and len(b["lines"]) > 1:
                    b["lines"].remove(plain[0])                            # "tighten": drop a non-twist line
                else:
                    b["lines"][0]["text"] = b["lines"][0]["text"].rstrip("।!?") + ", बस।"
        return {"title": story.get("title", ""), "beats": story["beats"], "notes": n}
    if step == "chat_router":
        msg = _tag(user, "message")
        low = msg.lower()
        quote = re.search(r'selected text: "([^"]+)"\) ?(.*)', msg)
        body = (quote.group(2) if quote else msg).strip()
        cast = _cast(user)
        none = {"target_id": "", "new_name_native": "", "new_name_latin": "", "persona": "", "pace": "", "instruction": ""}
        target = None
        if quote:
            q = quote.group(1).strip(" ।.!?’‘")
            target = next((k for k, v in cast.items() if q in v), None)
        m = re.search(r"rename\s+@?(\S+)\s+(?:to\s+)?@?(\S+)", body, re.I)
        if m:
            target = next((k for k, v in cast.items() if m.group(1).strip(".,") in v), target)
            new = m.group(2).strip(".,!")
        else:
            new = body.strip(".,!") if re.fullmatch(r"[A-Za-z]+", body.strip(".,!")) else ""
        if target and new:
            return {"actions": [{**none, "type": "rename", "target_id": target, "new_name_native": TR.get(new.lower(), new),
                                 "new_name_latin": new.title()}], "reply": f"Renaming to {new.title()}.", "notes": n}
        if re.search(r"voice|narrat|persona|radio|trailer|grandma|ott|slower|faster", low):
            persona = "radio" if "radio" in low else "trailer" if "trailer" in low else "grandma" if "grandma" in low else "ott" if "ott" in low else ""
            acts = []
            if persona:
                acts.append({**none, "type": "persona", "persona": persona})
            if re.search(r"slow|faster|quick", low):
                acts.append({**none, "type": "pace", "pace": "faster" if re.search(r"fast|quick", low) else "slower"})
            return {"actions": acts or [{**none, "type": "persona", "persona": "radio"}], "reply": "Changing the narrator.", "notes": n}
        if body.endswith("?"):
            return {"actions": [{**none, "type": "question"}], "reply": "(mock) It ends with her as the owner of the palace.", "notes": n}
        return {"actions": [{**none, "type": "story_edit", "instruction": body}], "reply": "Tightening that passage.", "notes": n}
    if step == "voice_pick":
        ids = re.findall(r"^(\S+) \| ", _tag(user, "voices"), re.M)[1:]      # skip the header row
        return {"voice_id": ids[0] if ids else "", "backup_ids": ids[1:3], "reason": "(mock) warm voice suits this family drama", "notes": n}
    if step == "transliterate":
        typed = re.search(r">([^<]+)</name>", user).group(1).strip()
        native = TR.get(typed.lower(), typed)
        return {"name_native": native, "name_short": native, "name_latin": typed.title(), "notes": n}
    raise ValueError(step)
