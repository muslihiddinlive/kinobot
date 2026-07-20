from .uz import UZ
from .ru import RU
from .en import EN
from .tr import TR

LANGUAGES = {"uz": UZ, "ru": RU, "en": EN, "tr": TR}

def t(key: str, lang: str = "uz", **kwargs) -> str:
    texts = LANGUAGES.get(lang, UZ)
    text = texts.get(key, UZ.get(key, key))
    if kwargs:
        try: text = text.format(**kwargs)
        except: pass
    return text

LANG_BUTTONS = [
    ("🇺🇿 O'zbekcha", "uz"),
    ("🇷🇺 Русский",   "ru"),
    ("🇬🇧 English",   "en"),
    ("🇹🇷 Türkçe",    "tr"),
]
