#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - idiomas: pt-PT (origem), en, es, fr, pt-BR.
O idioma é detetado automaticamente a partir do sistema; não há menu de idiomas."""
import os

LANGS = ("pt-PT", "en", "es", "fr", "pt-BR")
_IDX = {"en": 0, "es": 1, "fr": 2, "pt-BR": 3}
_lang = "pt-PT"


def _norm(code):
    c = code.split(".")[0].split("@")[0].replace("-", "_")
    lang, _s, reg = c.partition("_")
    lang = lang.lower()
    if lang == "pt":
        return "pt-BR" if reg.upper() == "BR" else "pt-PT"
    if lang in ("en", "es", "fr"):
        return lang
    return None


def detect_lang(env=None):
    env = os.environ if env is None else env
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = env.get(var, "")
        for part in v.split(":"):
            if part and part not in ("C", "POSIX"):
                l = _norm(part)
                if l:
                    return l
    return "en"


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "en"


def get_lang():
    return _lang


def _(s):
    if _lang == "pt-PT":
        return s
    from translations import T
    row = T.get(s)
    if row is None:
        return s
    if _lang == "pt-BR":
        return row[3] or s
    return row[_IDX[_lang]] or s


def N_(s):
    """Marca um texto para tradução posterior (identidade)."""
    return s
