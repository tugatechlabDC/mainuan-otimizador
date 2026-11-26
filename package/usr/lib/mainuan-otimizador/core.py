#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - funções sem privilégios usadas pela interface."""
import os
import shutil
import subprocess
import configparser

import i18n
from i18n import _
import common as C

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.py")


# ------------------------------------------------------------- helper root
def run_helper(*args, timeout=900):
    cmd = [HELPER, "--lang=" + i18n.get_lang()] + [str(a) for a in args]
    if os.geteuid() != 0:
        cmd = ["pkexec"] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, _("Tempo esgotado.")
    except OSError as e:
        return 127, _("Não foi possível executar o helper: {e}").format(e=e)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode in (126, 127) and not out:
        return p.returncode, _("Autenticação cancelada ou recusada.")
    return p.returncode, out


def system_is_dark():
    """True/False consoante o tema do sistema; None se não for possível saber."""
    desk = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    kde = os.path.expanduser("~/.config/kdeglobals")
    if "KDE" in desk or os.path.exists(kde):
        cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
        cp.optionxform = str
        try:
            cp.read(kde, encoding="utf-8")
            r, g, b = [int(x) for x in cp["Colors:Window"]["BackgroundNormal"].split(",")[:3]]
            return (0.299 * r + 0.587 * g + 0.114 * b) < 128
        except (KeyError, ValueError, configparser.Error, OSError):
            pass
    if shutil.which("gsettings"):
        rc, out = C.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], timeout=2)
        if rc == 0 and "prefer-dark" in out:
            return True
        if rc == 0 and "prefer-light" in out:
            return False
        rc, out = C.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], timeout=2)
        if rc == 0 and out:
            return "dark" in out.lower()
    return None
