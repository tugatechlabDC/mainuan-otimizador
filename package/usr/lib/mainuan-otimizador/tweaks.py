#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - ajustes extra do «Otimizar RAM».
Cada ajuste executa automaticamente os comandos necessários e regista-os."""
import os
import glob
import json
import shutil
import subprocess

import common as C
import core
from i18n import _, N_

STATE = os.path.expanduser("~/.config/mainuan-otimizador/tweaks.json")
HW = {}  # preenchido pela interface (hardware detetado)

BG_AUTOSTART = (  # entradas de arranque não essenciais e o processo a terminar
    ("org.kde.discover.notifier.desktop", "DiscoverNotifier"),
    ("geoclue-demo-agent.desktop", "geoclue-demo-agent"),
    ("snap-userd-autostart.desktop", None),
)


def _load():
    try:
        with open(STATE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(d, f)


def desktop():
    return os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


def is_kde():
    return "KDE" in desktop()


def is_gnome():
    d = desktop()
    return "GNOME" in d or "UBUNTU" in d


def kwrite():
    return shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")


def baloo():
    return shutil.which("balooctl6") or shutil.which("balooctl")


class Runner:
    """Executa comandos e guarda o registo (tipo, texto) para mostrar ao utilizador."""

    def __init__(self):
        self.log = []
        self.failed = False

    def note(self, kind, text):
        self.log.append((kind, text))

    def run(self, argv, soft=False, timeout=180):
        self.log.append(("cmd", "$ " + " ".join(argv)))
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            self.log.append(("err", str(e)))
            if not soft:
                self.failed = True
            return False
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        if out:
            self.log.append(("info", out[:300]))
        if p.returncode != 0 and not soft:
            self.failed = True
        return p.returncode == 0

    def root(self, *args):
        self.log.append(("cmd", "$ pkexec %s %s" % (os.path.basename(core.HELPER), " ".join(args))))
        rc, out = core.run_helper(*args)
        for line in out.splitlines():
            line = line.strip()
            if line and line != "OK":
                self.log.append(("err" if line.startswith(("!", "Erro", "Error")) else "info", line))
        if rc != 0:
            self.failed = True
            if not out:
                self.log.append(("err", _("Cancelado ou sem autorização.")))
        return rc == 0


# ----------------------------------------------------------------- ajustes
def _kde_reconfigure(r):
    r.run(["dbus-send", "--session", "--dest=org.kde.KWin", "--type=method_call",
           "/KWin", "org.kde.KWin.reconfigure"], soft=True)


def cache_apply(r, _p=None):
    r.root("drop-caches")


def baloo_apply(r, _p=None):
    kw = kwrite()
    if kw:
        r.run([kw, "--file", "baloofilerc", "--group", "Basic Settings", "--key", "Indexing-Enabled", "false"])
    if baloo():
        r.run([baloo(), "disable"])
    r.run(["pkill", "-x", "baloo_file"], soft=True)
    r.run(["pkill", "-x", "baloo_file_extractor"], soft=True)


def baloo_revert(r):
    kw = kwrite()
    if kw:
        r.run([kw, "--file", "baloofilerc", "--group", "Basic Settings", "--key", "Indexing-Enabled", "true"])
    if baloo():
        r.run([baloo(), "enable"])


_ANIM_KEYS = ("blurEnabled", "translucencyEnabled", "kwin4_effect_translucencyEnabled")


def anim_apply(r, _p=None):
    if kwrite() and is_kde():
        kw = kwrite()
        r.run([kw, "--file", "kdeglobals", "--group", "KDE", "--key", "AnimationDurationFactor", "0"])
        for k in _ANIM_KEYS:
            r.run([kw, "--file", "kwinrc", "--group", "Plugins", "--key", k, "false"])
        _kde_reconfigure(r)
    else:
        r.run(["gsettings", "set", "org.gnome.desktop.interface", "enable-animations", "false"])


def anim_revert(r):
    if kwrite() and is_kde():
        kw = kwrite()
        r.run([kw, "--file", "kdeglobals", "--group", "KDE", "--key", "AnimationDurationFactor", "--delete"])
        for k in _ANIM_KEYS:
            r.run([kw, "--file", "kwinrc", "--group", "Plugins", "--key", k, "--delete"])
        _kde_reconfigure(r)
    else:
        r.run(["gsettings", "set", "org.gnome.desktop.interface", "enable-animations", "true"])


KALENDARAC = "org.kde.kalendarac.desktop"


def akonadi_apply(r, _p=None):
    r.run(["akonadictl", "stop"], soft=True)
    kw = kwrite()
    if kw:
        r.run([kw, "--file", "akonadiserverrc", "--group", "%General", "--key", "StartServer", "false"])
    if os.path.exists("/etc/xdg/autostart/" + KALENDARAC):
        r.note("cmd", "$ autostart: Hidden=true " + KALENDARAC)
        core.xdg_disable({"id": KALENDARAC, "name": "Kalendarac"})
        st = _load()
        st["akonadi_autostart"] = True
        _save(st)


def akonadi_revert(r):
    kw = kwrite()
    if kw:
        r.run([kw, "--file", "akonadiserverrc", "--group", "%General", "--key", "StartServer", "--delete"])
    if _load().get("akonadi_autostart"):
        r.note("cmd", "$ autostart: Hidden=false " + KALENDARAC)
        core.xdg_enable({"id": KALENDARAC, "name": "Kalendarac"})
        st = _load()
        st.pop("akonadi_autostart", None)
        _save(st)


def widgets_apply(r, _p=None):
    st = _load()
    done = st.setdefault("widgets", [])
    for fn, proc in BG_AUTOSTART:
        exists = os.path.exists("/etc/xdg/autostart/" + fn) or os.path.exists(core.XDG_USER + "/" + fn)
        if not exists:
            continue
        r.note("cmd", "$ autostart: Hidden=true " + fn)
        core.xdg_disable({"id": fn, "name": fn[:-8]})
        if fn not in done:
            done.append(fn)
        if proc:
            r.run(["pkill", "-f", proc], soft=True)
    _save(st)
    if is_kde():
        pats = glob.glob(os.path.expanduser("~/.cache/plasma_theme_*.kcache")) + \
            [os.path.expanduser("~/.cache/icon-cache.kcache")]
        for p in pats:
            if os.path.exists(p):
                r.note("cmd", "$ rm -f " + p)
                try:
                    os.remove(p)
                except OSError as e:
                    r.note("err", str(e))
    r.note("info", _("Os widgets do Plasma não foram removidos; só foram limpas caches e serviços auxiliares."))


def widgets_revert(r):
    st = _load()
    for fn in st.get("widgets", []):
        r.note("cmd", "$ autostart: Hidden=false " + fn)
        core.xdg_enable({"id": fn, "name": fn[:-8]})
    st["widgets"] = []
    _save(st)


def power_apply(r, param="balanced"):
    if param not in ("balanced", "power-saver"):
        param = "balanced"
    ppc = shutil.which("powerprofilesctl")
    if ppc:
        r.run([ppc, "set", param])
        return
    order = ("powersave",) if param == "power-saver" else ("schedutil", "ondemand", "powersave")
    for g in order:
        r.note("cmd", "$ governor " + g)
        if r.root("governor", g):
            r.failed = False
            return


def power_revert(r):
    power_apply(r, "balanced")


def trim_apply(r, _p=None):
    r.root("trim", "enable")


def trim_revert(r):
    r.root("trim", "disable")


def earlyoom_apply(r, _p=None):
    r.root("earlyoom", "enable")


def earlyoom_revert(r):
    r.root("earlyoom", "disable")


def bt_apply(r, _p=None):
    r.root("group", "bluetooth", "disable")


def bt_revert(r):
    r.root("group", "bluetooth", "enable")


def print_apply(r, _p=None):
    r.root("group", "printing", "disable")


def print_revert(r):
    r.root("group", "printing", "enable")


# ------------------------------------------------------------ disponibilidade
def _unit_file(name):
    return any(os.path.exists(d + name) for d in ("/usr/lib/systemd/system/", "/lib/systemd/system/",
                                                   "/etc/systemd/system/"))


def av_baloo():
    return (True, "") if baloo() else (False, N_("Baloo não está instalado."))


def av_anim():
    if is_kde() and kwrite():
        return True, ""
    if shutil.which("gsettings") and is_gnome():
        return True, ""
    return False, N_("Disponível apenas em KDE Plasma ou GNOME.")


def av_akonadi():
    return (True, "") if shutil.which("akonadictl") else (False, N_("O Akonadi não está instalado."))


def av_widgets():
    if is_kde():
        return True, ""
    for fn, _proc in BG_AUTOSTART:
        if os.path.exists("/etc/xdg/autostart/" + fn):
            return True, ""
    return False, N_("Nada para limpar neste ambiente.")


def av_power():
    if shutil.which("powerprofilesctl") or glob.glob("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"):
        return True, ""
    return False, N_("Este sistema não permite alterar o perfil de energia.")


def av_trim():
    if not shutil.which("fstrim") or not _unit_file("fstrim.timer"):
        return False, N_("O fstrim não está disponível.")
    if HW.get("rotational") is True:
        return False, N_("O disco é mecânico (HDD): o TRIM só serve para SSD.")
    return True, ""


def av_earlyoom():
    if shutil.which("earlyoom") or shutil.which("apt-get"):
        return True, ""
    return False, N_("Requer o gestor de pacotes apt.")


def av_bt():
    return (True, "") if _unit_file("bluetooth.service") else (False, N_("Serviço Bluetooth não encontrado."))


def av_print():
    return (True, "") if _unit_file("cups.service") else (False, N_("Serviço de impressão não encontrado."))


class Tweak:
    def __init__(self, tid, label, desc, apply, revert, avail, default=False, combo=None):
        self.id, self.label, self.desc = tid, label, desc
        self.apply, self.revert, self.avail = apply, revert, avail
        self.default, self.combo = default, combo


TWEAKS = [
    Tweak("cache", N_("Libertar também a cache do sistema (pede palavra-passe)"),
          N_("Remove a cache de ficheiros da memória; é recriada conforme for precisa."),
          cache_apply, None, lambda: (True, ""), default=True),
    Tweak("baloo", N_("Desativar o indexador de ficheiros (Baloo - KDE Baloo)"),
          N_("Pára a indexação de ficheiros em segundo plano; a pesquisa de ficheiros fica mais limitada."),
          baloo_apply, baloo_revert, av_baloo),
    Tweak("anim", N_("Reduzir animações e transparências"),
          N_("Desliga animações e efeitos de desfoque/transparência do ambiente de trabalho."),
          anim_apply, anim_revert, av_anim),
    Tweak("akonadi", N_("Desativar o Akonadi (se não usar o KMail/Kontact)"),
          N_("Pára o servidor de contactos, calendário e correio do KDE; pare só se não usar estas aplicações."),
          akonadi_apply, akonadi_revert, av_akonadi),
    Tweak("widgets", N_("Limpar widgets e serviços em segundo plano"),
          N_("Limpa caches do Plasma e desativa avisos/serviços auxiliares não essenciais no arranque."),
          widgets_apply, widgets_revert, av_widgets),
    Tweak("power", N_("Ajustar o perfil de energia"),
          N_("Equilibrado mantém o desempenho; poupança de energia reduz CPU e consumo."),
          power_apply, power_revert, av_power,
          combo=(("balanced", N_("Equilibrado")), ("power-saver", N_("Poupança de energia")))),
    Tweak("trim", N_("Ativar o TRIM do SSD (pede palavra-passe)"),
          N_("Ativa a limpeza semanal do SSD (fstrim.timer) e executa-a agora."),
          trim_apply, trim_revert, av_trim),
    Tweak("earlyoom", N_("Instalar o EarlyOOM para evitar congelamentos (pede palavra-passe)"),
          N_("Fecha o processo mais pesado antes de o sistema ficar sem memória e congelar. Precisa de internet."),
          earlyoom_apply, earlyoom_revert, av_earlyoom),
    Tweak("bluetooth", N_("Desativar o serviço Bluetooth (pede palavra-passe)"),
          N_("Poupa memória; rato, teclado e auscultadores Bluetooth deixam de funcionar."),
          bt_apply, bt_revert, av_bt),
    Tweak("printing", N_("Desativar o serviço de impressão (pede palavra-passe)"),
          N_("Poupa memória; deixa de ser possível imprimir até o reativar."),
          print_apply, print_revert, av_print),
]
BY_ID = {t.id: t for t in TWEAKS}


def run_selected(selection, mode="apply"):
    """selection: lista de (id, parâmetro). Devolve o registo [(tipo, texto)]."""
    r = Runner()
    for tid, param in selection:
        t = BY_ID.get(tid)
        if not t:
            continue
        fn = t.apply if mode == "apply" else t.revert
        if fn is None:
            continue
        r.failed = False
        r.note("head", _(t.label))
        try:
            fn(r, param) if mode == "apply" else fn(r)
        except Exception as e:  # noqa: BLE001
            r.note("err", str(e))
            r.failed = True
        r.note("err" if r.failed else "ok",
               _("Falhou ou foi cancelado.") if r.failed else
               (_("Concluído.") if mode == "apply" else _("Revertido.")))
    return r.log
