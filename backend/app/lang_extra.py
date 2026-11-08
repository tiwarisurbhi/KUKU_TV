"""Odia, Tamil, Telugu, Kannada and Malayalam for qwen_prompts.

qwen_prompts.py ships five language profiles (hi, bn, pa, mr, gu) and stays untouched. This module
adds five more profiles in the same shape and extends the name-joint fixer (`_join`) that
swap_names() uses, so placeholders like {C1}உக்கு print as மீராவுக்கு / அர்ஜுனுக்கு.
It is imported from app/__init__.py, so every `app.*` import sees all ten languages.

Case-ending joints for the Dravidian languages are rule-based and cover the common shapes
(vowel-final, consonant-final, ம்/ം-final place names). Have a native speaker spot-check them.
"""
from . import qwen_prompts as qp

PROFILES = {
    "or": {
        "name": "Odia", "mix_name": "Odia with English", "script": "Odia",
        "script_re": "଀-୿", "native_digits": "୦-୯",
        "enders": "।?!", "end_char": "।",
        "register": ("Everyday spoken Odia as heard in Bhubaneswar and Cuttack today, Odia script, with common English "
                     "words mixed in naturally. Avoid formal Sanskritized words. Sentences end with a danda (।). "
                     "ତୁ/ତୁମେ/ଆପଣ show the relationship."),
        "loanwords": "ପ୍ଲାନ, ଡିଲ, ସରି, ପ୍ଲିଜ, କ୍ରୁ, କ୍ୟାପଟେନ, ସିଗନାଲ, ଟେନସନ, ପ୍ରପୋଜ, ମିଶନ",
        "swaps": {"ସ୍ୱର୍ଣ୍ଣମୁଦ୍ରା": "ସୁନା କଏନ", "ବିବାହ": "ବାହାଘର", "କ୍ରୋଧ": "ରାଗ", "ଅଶ୍ରୁ": "ଲୁହ",
                  "ତତ୍କ୍ଷଣାତ୍": "ସଙ୍ଗେ ସଙ୍ଗେ", "ଅତ୍ୟନ୍ତ": "ବହୁତ"},
        "gender_rule": ("Odia verbs do not change with gender, so make gender clear through nouns and pronouns "
                        "(ଝିଅଟି, ପୁଅଟି) and keep ସେ references unambiguous."),
        "case_style": "attached", "case_example": "{C1}କୁ, {C1}ର, {C1}ଠାରୁ, {E2}ରେ",
        "samples": [
            ("{C1}ର ବେକରେ ଗୋଟିଏ ଅଜବ ସୁନା କଏନ ଝୁଲୁଥିଲା, କାହାରି ନଜର ପଡ଼ିନଥିଲା।", "whisper"),
            ("{C2} ଥଣ୍ଡା ଗଳାରେ କହିଲା, ‘ତୁମ ପ୍ଲାନ ଆଉ କାମ କରିବନି।’", "pause"),
            ("ଯାହାକୁ ସମସ୍ତେ ଘରର ଡ୍ରାଇଭର ଭାବୁଥିଲେ, ସେ ହିଁ ଥିଲା ଜେଜେଙ୍କ ଅସଲି ପୁଅ!", "shock"),
        ],
    },
    "ta": {
        "name": "Tamil", "mix_name": "Tamil with English", "script": "Tamil",
        "script_re": "஀-௿", "native_digits": "௦-௯",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Tamil as heard in Chennai today, the register of modern Tamil web series and audio "
                     "stories, Tamil script, with common English words mixed in naturally. Narration stays close to plain "
                     "written Tamil, never literary or purist; dialogue uses spoken forms (இருக்கு, போறேன், சொல்லு). "
                     "Sentences end with a full stop (.). நீ/நீங்க show the relationship."),
        "loanwords": "பிளான், டீல், சாரி, ப்ளீஸ், க்ரூ, கேப்டன், சிக்னல், டென்ஷன், ப்ரபோஸ், மிஷன்",
        "swaps": {"பொற்காசு": "தங்கக் காசு", "சினம்": "கோபம்", "மணமுடித்தல்": "கல்யாணம்", "விழிநீர்": "கண்ணீர்",
                  "உடனடியாக": "உடனே", "அச்சம்": "பயம்", "இல்லம்": "வீடு"},
        "gender_rule": ("Third-person verbs agree with gender. Check the cast sheet before every verb: female {C1} → "
                        "‘{C1} அழுதாள்’, ‘{C1} போனாள்’; male {C3} → ‘{C3} அழுதான்’, ‘{C3} போனான்’."),
        "case_style": "attached", "case_example": "{C1}ஐ, {C1}உக்கு, {C1}இன், {C1}இடம், {E2}இல்",
        "samples": [
            ("{C1}இன் கழுத்தில் ஒரு விசித்திரமான தங்கக் காசு தொங்கிக்கொண்டிருந்தது, யாரும் அதைக் கவனிக்கவில்லை.", "whisper"),
            ("{C2}இன் குரல் குளிர்ந்திருந்தது, ‘உன் பிளான் இனிமே வேலை செய்யாது.’", "pause"),
            ("எல்லோரும் வீட்டு டிரைவர் என்று நினைத்தவன்தான், தாத்தாவின் உண்மையான மகன்!", "shock"),
        ],
    },
    "te": {
        "name": "Telugu", "mix_name": "Telugu with English", "script": "Telugu",
        "script_re": "ఀ-౿", "native_digits": "౦-౯",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Telugu as heard in Hyderabad and Vijayawada today, Telugu script, with common English "
                     "words mixed in naturally. Never grānthika (bookish) forms or heavy Sanskritized words; dialogue uses "
                     "spoken forms (ఉంది, వెళ్తున్నా, చెప్పు). Sentences end with a full stop (.). నువ్వు/మీరు show "
                     "the relationship."),
        "loanwords": "ప్లాన్, డీల్, సారీ, ప్లీజ్, క్రూ, కెప్టెన్, సిగ్నల్, టెన్షన్, ప్రపోజ్, మిషన్",
        "swaps": {"స్వర్ణముద్ర": "బంగారు నాణెం", "క్రోధం": "కోపం", "వివాహం": "పెళ్లి", "అశ్రువులు": "కన్నీళ్లు",
                  "తక్షణమే": "వెంటనే", "అత్యంత": "చాలా", "గృహం": "ఇల్లు"},
        "gender_rule": ("Past-tense verbs mark gender in the third person. Check the cast sheet before every verb: female "
                        "{C1} → ‘{C1} ఏడ్చింది’, ‘{C1} వెళ్లిపోయింది’; male {C3} → ‘{C3} ఏడ్చాడు’, ‘{C3} వెళ్లిపోయాడు’."),
        "case_style": "attached", "case_example": "{C1}ని, {C1}కి, {C1}తో, {C1}ది, {E2}లో",
        "samples": [
            ("{C1} మెడలో ఒక వింత బంగారు నాణెం వేలాడుతోంది, ఎవరూ దాన్ని గమనించలేదు.", "whisper"),
            ("{C2} గొంతు చల్లగా ఉంది, ‘నీ ప్లాన్ ఇక పనిచేయదు.’", "pause"),
            ("అందరూ ఇంటి డ్రైవర్ అనుకున్నవాడే, తాతయ్య అసలైన కొడుకు!", "shock"),
        ],
    },
    "kn": {
        "name": "Kannada", "mix_name": "Kannada with English", "script": "Kannada",
        "script_re": "ಀ-೿", "native_digits": "೦-೯",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Kannada as heard in Bengaluru today, Kannada script, with common English words mixed "
                     "in naturally. Avoid heavy Sanskritized words; dialogue uses spoken forms (ಹೋಗ್ತೀನಿ, ಹೇಳು, ಗೊತ್ತಿಲ್ಲ). "
                     "Sentences end with a full stop (.). ನೀನು/ನೀವು show the relationship."),
        "loanwords": "ಪ್ಲಾನ್, ಡೀಲ್, ಸಾರಿ, ಪ್ಲೀಸ್, ಕ್ರೂ, ಕ್ಯಾಪ್ಟನ್, ಸಿಗ್ನಲ್, ಟೆನ್ಷನ್, ಪ್ರಪೋಸ್, ಮಿಷನ್",
        "swaps": {"ಕ್ರೋಧ": "ಸಿಟ್ಟು", "ವಿವಾಹ": "ಮದುವೆ", "ಅಶ್ರು": "ಕಣ್ಣೀರು", "ಅತ್ಯಂತ": "ತುಂಬಾ", "ಗೃಹ": "ಮನೆ",
                  "ಸ್ವರ್ಣ": "ಚಿನ್ನ"},
        "gender_rule": ("Third-person verbs agree with gender. Check the cast sheet before every verb: female {C1} → "
                        "‘{C1} ಅತ್ತಳು’, ‘{C1} ಹೋದಳು’; male {C3} → ‘{C3} ಅತ್ತನು’, ‘{C3} ಹೋದನು’."),
        "case_style": "attached", "case_example": "{C1}ಗೆ, {C1}ನ, {C1}ನ್ನ, {C1}ಜೊತೆ, {E2}ಅಲ್ಲಿ",
        "samples": [
            ("{C1} ಕುತ್ತಿಗೆಯಲ್ಲಿ ಒಂದು ವಿಚಿತ್ರ ಚಿನ್ನದ ನಾಣ್ಯ ನೇತಾಡುತ್ತಿತ್ತು, ಯಾರೂ ಅದನ್ನು ಗಮನಿಸಲಿಲ್ಲ.", "whisper"),
            ("{C2} ದನಿ ತಣ್ಣಗಿತ್ತು, ‘ನಿನ್ನ ಪ್ಲಾನ್ ಇನ್ನು ಕೆಲಸ ಮಾಡಲ್ಲ.’", "pause"),
            ("ಎಲ್ಲರೂ ಮನೆಯ ಡ್ರೈವರ್ ಅಂದುಕೊಂಡಿದ್ದವನೇ, ತಾತನ ನಿಜವಾದ ಮಗ!", "shock"),
        ],
    },
    "ml": {
        "name": "Malayalam", "mix_name": "Malayalam with English", "script": "Malayalam",
        "script_re": "ഀ-ൿ", "native_digits": "൦-൯",
        "enders": ".?!", "end_char": ".",
        "register": ("Everyday spoken Malayalam as heard in Kochi and Thiruvananthapuram today, Malayalam script, with common "
                     "English words mixed in naturally. Avoid heavy Sanskritized words; dialogue uses spoken forms (ഉണ്ട്, "
                     "പോവാ, പറ). Sentences end with a full stop (.). നീ/നിങ്ങൾ/ചേട്ടൻ/ചേച്ചി show the relationship."),
        "loanwords": "പ്ലാൻ, ഡീൽ, സോറി, പ്ലീസ്, ക്രൂ, ക്യാപ്റ്റൻ, സിഗ്നൽ, ടെൻഷൻ, പ്രൊപ്പോസ്, മിഷൻ",
        "swaps": {"ക്രോധം": "ദേഷ്യം", "വിവാഹം കഴിച്ചു": "കല്യാണം കഴിച്ചു", "അശ്രു": "കണ്ണീർ", "തൽക്ഷണം": "ഉടനെ",
                  "അത്യന്തം": "വല്ലാതെ", "ഗൃഹം": "വീട്"},
        "gender_rule": ("Malayalam verbs do not change with gender, so make gender clear through nouns and pronouns "
                        "(അവൾ, അവൻ, പെൺകുട്ടി) and keep references unambiguous."),
        "case_style": "attached", "case_example": "{C1}എ, {C1}ഉടെ, {C1}ക്ക്, {C1}ഓട്, {E2}ഇൽ",
        "samples": [
            ("{C1}ഉടെ കഴുത്തിൽ ഒരു വിചിത്രമായ സ്വർണ്ണ നാണയം തൂങ്ങിക്കിടന്നു, ആരും അത് ശ്രദ്ധിച്ചില്ല.", "whisper"),
            ("{C2}ഉടെ ശബ്ദം തണുത്തിരുന്നു, ‘നിന്റെ പ്ലാൻ ഇനി നടക്കില്ല.’", "pause"),
            ("എല്ലാവരും വീട്ടിലെ ഡ്രൈവർ എന്ന് കരുതിയവൻ തന്നെയായിരുന്നു മുത്തച്ഛന്റെ ശരിക്കുള്ള മകൻ!", "shock"),
        ],
    },
}

ZWNJ = "‌"

# ---------- Tamil ----------
_TA_VIRAMA = "்"
_TA_SIGN = {"அ": "", "ஆ": "ா", "இ": "ி", "ஈ": "ீ", "உ": "ு", "ஊ": "ூ", "எ": "ெ", "ஏ": "ே", "ஐ": "ை",
            "ஒ": "ொ", "ஓ": "ோ", "ஔ": "ௌ"}
_TA_HARD = set("கசடதபற")
_TA_Y_GLIDE = set("ிீெேை")          # front vowels glide with ய; others with வ


def _ta(name: str, rest: str):
    if not rest or rest[0] not in _TA_SIGN:
        return name, rest
    v, tail = rest[0], rest[1:]
    last = name[-1]
    if last == _TA_VIRAMA and len(name) >= 2:
        cons = name[-2]
        if cons == "ம" and rest.startswith("இல்"):                 # கும்பகோணம் + இல் → கும்பகோணத்தில்
            return name[:-2] + "த்த" + _TA_SIGN[v], tail
        if cons in _TA_HARD:                                        # கார்த்திக் + உக்கு → கார்த்திக்குக்கு
            return name + cons + _TA_SIGN[v], tail
        return name[:-1] + _TA_SIGN[v], tail                        # அர்ஜுன் + இன் → அர்ஜுனின்
    if last in _TA_Y_GLIDE and rest.startswith("உக்கு"):            # லக்ஷ்மி + உக்கு → லக்ஷ்மிக்கு
        return name, tail
    glide = "ய" if last in _TA_Y_GLIDE else "வ"                     # மீரா + இன் → மீராவின்
    return name + glide + _TA_SIGN[v], tail


# ---------- Malayalam ----------
_ML_CHILLU = {"ൻ": "ന", "ൺ": "ണ", "ർ": "ര", "ൽ": "ല", "ൾ": "ള", "ൿ": "ക", "ൺ": "ണ", "ൻ": "ന",
              "ർ": "ര", "ൽ": "ല", "ൾ": "ള"}
_ML_VIRAMA = "്"
_ML_Y_GLIDE = set("ിീെേൈ")
_ML_V_GLIDE = set("ുൂോൊൌ")


def _ml(name: str, rest: str):
    suf = next((s for s in ("ഉടെ", "ഓട്", "ക്ക്", "ഇൽ", "എ") if rest.startswith(s)), None)
    if not suf:
        return name, rest
    tail = rest[len(suf):]
    last = name[-1]
    if last in _ML_CHILLU or last == "ം" or last == _ML_VIRAMA:
        is_n = last in ("ൻ", "ൻ")
        base = (name[:-1] + _ML_CHILLU[last]) if last in _ML_CHILLU else (name[:-1] + "ത്ത") if last == "ം" else name[:-1]
        out = {"എ": "െ" if is_n else "ിനെ", "ഉടെ": "്റെ" if is_n else "ിന്റെ", "ക്ക്": "്" if is_n else "ിന്",
               "ഓട്": "ോട്" if is_n else "ിനോട്", "ഇൽ": "ിൽ"}[suf]
        return base + out, tail                                     # അർജുൻ → അർജുന്റെ, കേരളം → കേരളത്തിൽ
    if suf == "ക്ക്":
        if last in _ML_Y_GLIDE:
            return name + "ക്ക്", tail                              # ലക്ഷ്മിക്ക്
        if last in _ML_V_GLIDE:
            return name + "വിന്", tail                              # ഗുരുവിന്
        return name + "യ്ക്ക്", tail                                # മീരയ്ക്ക്
    glide = "വ" if last in _ML_V_GLIDE else "യ"
    sign = {"എ": "െ", "ഉടെ": "ുടെ", "ഓട്": "ോട്", "ഇൽ": "ിൽ"}[suf]
    return name + glide + sign, tail                                # മീരയുടെ, കൊച്ചിയിൽ


# ---------- Kannada ----------
_KN_VIRAMA = "್"


def _kn(name: str, rest: str):
    last = name[-1]
    if rest.startswith("ಅಲ್ಲಿ"):
        tail = rest[len("ಅಲ್ಲಿ"):]
        if last == "ು":
            return name[:-1] + "ಲ್ಲಿ", tail                         # ಬೆಂಗಳೂರು → ಬೆಂಗಳೂರಲ್ಲಿ
        if last in "ಿೀೆೇೈ":
            return name + "ಯಲ್ಲಿ", tail                             # ಹಳ್ಳಿಯಲ್ಲಿ
        if last == _KN_VIRAMA:
            return name + ZWNJ + "ನಲ್ಲಿ", tail                      # ಮಾಲ್‌ನಲ್ಲಿ
        return name + "ದಲ್ಲಿ", tail                                 # ಗೋವಾದಲ್ಲಿ, ಮಂಡಪದಲ್ಲಿ
    if rest.startswith("ಗೆ") and last == "ು":
        return name[:-1] + "ಿ", rest                                # ಬೆಂಗಳೂರಿಗೆ
    if last == _KN_VIRAMA and rest and "ಕ" <= rest[0] <= "ಹ":
        return name + ZWNJ, rest                                    # ಅರ್ಜುನ್‌ಗೆ
    return name, rest


# ---------- Telugu / Odia: suffixes start with a consonant ----------
def _virama_zwnj(virama: str, lo: str, hi: str):
    def f(name: str, rest: str):
        if name.endswith(virama) and rest and lo <= rest[0] <= hi:
            return name + ZWNJ, rest                                # హైదరాబాద్‌లో
        return name, rest
    return f


_JOINERS = {"ta": _ta, "ml": _ml, "kn": _kn,
            "te": _virama_zwnj("్", "క", "హ"),
            "or": _virama_zwnj("୍", "କ", "ହ")}
_orig_join = qp._join


def _join(name: str, rest: str, lang: str):
    f = _JOINERS.get(lang)
    if f and name and not name.startswith("{"):
        return f(name, rest)
    return _orig_join(name, rest, lang)


def install() -> None:
    for k, v in PROFILES.items():
        qp.LANGUAGE_PROFILES.setdefault(k, v)
    qp._join = _join


install()
