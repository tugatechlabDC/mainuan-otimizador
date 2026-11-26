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


def _base(code):
    return code.split(".")[0].split("@")[0].replace("-", "_").partition("_")[0].lower()


def _file_locale():
    """Idioma configurado no sistema, quando o ambiente não o indica."""
    for path in ("/etc/locale.conf", "/etc/default/locale"):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("LANG="):
                        v = line.split("=", 1)[1].strip().strip('"')
                        if v and _base(v) not in ("c", "posix"):
                            return v
        except OSError:
            pass
    return ""


def detect_lang(env=None):
    """Idioma do sistema: pt-PT, pt-BR, es, fr ou en. Qualquer outro idioma -> en."""
    env = os.environ if env is None else env
    found = ""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for part in env.get(var, "").split(":"):
            part = part.strip()
            if part and _base(part) not in ("c", "posix"):
                found = part
                break
        if found:
            break
    if not found and env is os.environ:
        found = _file_locale()
    return _norm(found) or "en" if found else "en"


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
