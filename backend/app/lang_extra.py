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
        "loanwords": "ಪ್ಲಾನ್, ಡೀಲ್, ಸಾರಿ, ಪ್ಲೀಸ್, ಕ್ರೂ, ಕ್ಯಾಪ್ಟನ್, ಸಿಗ್ನಲ್, ಟೆನ್ಷನ್, ಪ್ರಪೋಸ್, ಮಿ�