#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - funções sem privilégios usadas pela interface."""
import os
import re
import json
import glob
import time
import shutil
import pwd
import subprocess
import configparser

import common as C
import i18n
from i18n import _, N_

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper.py")
CLK = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")


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


# ---------------------------------------------------------------- monitor
def gib(kb):
    return f"{kb / 1048576:.1f} GiB"


def size_kb(kb):
    return gib(kb) if kb >= 1048576 else f"{kb // 1024} MiB"


class Monitor:
    def __init__(self):
        self.prev = self._cpu()

    @staticmethod
    def _cpu():
        v = [int(x) for x in C.read("/proc/stat").splitlines()[0].split()[1:9]]
        return sum(v), v[3] + v[4]

    def snapshot(self):
        total, idle = self._cpu()
        pt, pi = self.prev
        self.prev = (total, idle)
        dt, di = total - pt, idle - pi
        cpu = max(0.0, min(100.0, 100.0 * (dt - di) / dt)) if dt > 0 else 0.0
        mi = C.meminfo()
        tot = mi.get("MemTotal", 1)
        used = tot - mi.get("MemAvailable", 0)
        cache = mi.get("Cached", 0) + mi.get("Buffers", 0) + mi.get("SReclaimable", 0)
        st = mi.get("SwapTotal", 0)
        su = st - mi.get("SwapFree", 0)
        la = os.getloadavg()[0]
        n = os.cpu_count() or 1
        zram = any(s["name"].startswith("/dev/zram") for s in C.swaps())
        return {
            "cpu": cpu,
            "cpu_sub": (_("{n} núcleo") if n == 1 else _("{n} núcleos")).format(n=n)
            + " · " + _("carga {l}").format(l=f"{la:.2f}"),
            "ram": 100.0 * used / tot,
            "ram_sub": f"{gib(used)} / {gib(tot)}",
            "cache": min(100.0, 100.0 * cache / tot),
            "cache_sub": _("{x} em cache de ficheiros").format(x=gib(cache)),
            "swap": (100.0 * su / st) if st > 0 else None,
            "swap_sub": (f"{size_kb(su)} / {size_kb(st)}" + (" · " + _("inclui zram") if zram else ""))
            if st > 0 else _("Sem swap ativa"),
        }


# --------------------------------------------------------------- processos
_users = {}


def uname(uid):
    if uid not in _users:
        try:
            _users[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _users[uid] = str(uid)
    return _users[uid]


def _snapshot():
    snap = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                s = f.read()
            i = s.rfind(")")
            comm = s[s.find("(") + 1:i]
            r = s[i + 2:].split()
            with open(f"/proc/{d}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            if not cmd:
                continue
            snap[int(d)] = {
                "pid": int(d), "name": comm, "uid": os.stat(f"/proc/{d}").st_uid,
                "ppid": int(r[1]), "tty": int(r[4]), "ticks": int(r[11]) + int(r[12]),
                "nice": int(r[16]), "start": int(r[19]), "rss_kb": int(r[21]) * PAGE // 1024,
                "cmd": cmd,
            }
        except (OSError, ValueError, IndexError):
            continue
    return snap


class ProcSampler:
    def __init__(self):
        self.prev = {}
        self.t = None

    def sample(self):
        now = time.monotonic()
        snap = _snapshot()
        dt = (now - self.t) if self.t else None
        try:
            up = float(C.read("/proc/uptime", "0 0").split()[0])
        except (ValueError, IndexError):
            up = 0.0
        res = []
        for pid, s in snap.items():
            cpu = 0.0
            pv = self.prev.get(pid)
            if dt and pv and pv["ticks"] <= s["ticks"]:
                cpu = (s["ticks"] - pv["ticks"]) / CLK / dt * 100.0
            e = dict(s)
            e["cpu"] = cpu
            e["age"] = up - s["start"] / CLK
            res.append(e)
        self.prev, self.t = snap, now
        return res


def window_pids():
    """PIDs com janela (só X11 com wmctrl). None = não é possível saber."""
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return None
    if not shutil.which("wmctrl"):
        return None
    rc, out = C.run(["wmctrl", "-lp"])
    if rc != 0:
        return None
    s = set()
    for line in out.splitlines():
        p = line.split(None, 4)
        if len(p) >= 3 and p[2].isdigit() and p[2] != "0":
            s.add(int(p[2]))
    return s


def _chain(pid, by_pid, limit=8):
    seen = []
    while pid in by_pid and len(seen) < limit:
        seen.append(pid)
        pid = by_pid[pid]["ppid"]
    return seen


def ram_candidates(procs, win):
    me = os.getuid()
    by_pid = {p["pid"]: p for p in procs}
    mine = set(_chain(os.getpid(), by_pid, 20))
    res = []
    for p in procs:
        if p["uid"] != me or p["pid"] in mine or p["tty"] != 0:
            continue
        if p["rss_kb"] < 100 * 1024 or p["cpu"] >= 1.0 or p["age"] < 300:
            continue
        if C.is_protected_name(p["name"], p["cmd"]) or C.is_browser(p["name"], p["cmd"]):
            continue
        if win is not None and any(x in win for x in _chain(p["pid"], by_pid)):
            continue
        q = dict(p)
        q["checked"] = win is not None
        res.append(q)
    res.sort(key=lambda x: -x["rss_kb"])
    return res[:30]


def cpu_candidates(procs):
    me = os.getuid()
    by_pid = {p["pid"]: p for p in procs}
    mine = set(_chain(os.getpid(), by_pid, 20))
    res = []
    for p in procs:
        if p["uid"] != me or p["pid"] in mine or p["cpu"] < 15.0:
            continue
        if C.is_protected_name(p["name"], p["cmd"]):
            continue
        q = dict(p)
        q["checked"] = True
        res.append(q)
    res.sort(key=lambda x: -x["cpu"])
    return res[:20]


def same_process(pid, name):
    return C.read(f"/proc/{pid}/comm") == name


def lower_priority(pid, nice=10):
    n = 0
    for t in glob.glob(f"/proc/{pid}/task/[0-9]*"):
        try:
            os.setpriority(os.PRIO_PROCESS, int(os.path.basename(t)), nice)
            n += 1
        except OSError:
            pass
    return n


# ----------------------------------------------------------------- arranque
XDG_USER = os.path.expanduser("~/.config/autostart")
XDG_SYS = ["/etc/xdg/autostart"]
STATE_FILE = os.path.expanduser("~/.config/mainuan-otimizador/state.json")
USER_UNITS = os.path.expanduser("~/.config/systemd/user")

HINTS = {
    "bluetooth.service": N_("Bluetooth — seguro desativar se não usar"),
    "cups.service": N_("Impressão — desative se não imprime"),
    "cups-browsed.service": N_("Deteção de impressoras na rede"),
    "avahi-daemon.service": N_("Descoberta de dispositivos na rede (mDNS)"),
    "modemmanager.service": N_("Modems 3G/4G — desative se não usar"),
    "apport.service": N_("Relatórios de falhas"),
    "whoopsie.service": N_("Envio de relatórios de erros"),
    "kerneloops.service": N_("Relatórios de erros do kernel"),
    "org.kde.discover.notifier.desktop": N_("Avisos de atualizações do Discover"),
    "snap-userd-autostart.desktop": N_("Integração de snaps na sessão"),
    "geoclue-demo-agent.desktop": N_("Demonstração de localização"),
    "blueman.desktop": N_("Applet Bluetooth"),
    "org.kde.kalendarac.desktop": N_("Alarmes de calendário (Akonadi)"),
}


def _load_state():
    try:
        with open(STATE_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(d):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(d, f)


def _desktop(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError, OSError):
        return {}
    return dict(cp["Desktop Entry"]) if cp.has_section("Desktop Entry") else {}


def _is_true(v):
    return str(v).strip().lower() in ("true", "1", "yes")


def list_xdg():
    entries = {}
    for d in XDG_SYS:
        for f in glob.glob(d + "/*.desktop"):
            entries[os.path.basename(f)] = {"sys": _desktop(f), "usr": None}
    for f in glob.glob(XDG_USER + "/*.desktop"):
        b = os.path.basename(f)
        entries.setdefault(b, {"sys": None, "usr": None})["usr"] = _desktop(f)
    items = []
    for fn, e in sorted(entries.items()):
        d = dict(e["sys"] or {})
        d.update(e["usr"] or {})
        if not d.get("Exec"):
            continue
        disabled = _is_true(d.get("Hidden", "false")) or \
            str(d.get("X-GNOME-Autostart-enabled", "true")).lower() == "false"
        name = d.get("Name[pt_PT]") or d.get("Name[pt]") or d.get("Name") or fn
        prot = any(k in fn.lower() for k in ("polkit", "pipewire", "wireplumber", "xdg-desktop-portal", "at-spi", "dbus"))
        items.append({"key": "xdg:" + fn, "kind": "xdg", "id": fn, "name": name,
                      "state": _("Desativado") if disabled else _("Ativo"), "enabled": not disabled,
                      "desc": (_(HINTS[fn]) if fn in HINTS else (d.get("Comment") or d.get("Exec", ""))),
                      "protected": prot, "has_sys": e["sys"] is not None, "has_usr": e["usr"] is not None})
    return items


def _units(user):
    base = ["systemctl"] + (["--user"] if user else [])
    rc, out = C.run(base + ["list-unit-files", "--type=service", "--no-legend", "--no-pager",
                            "--state=enabled,enabled-runtime"], timeout=25)
    enabled = {}
    for line in out.splitlines():
        p = line.split()
        if p and p[0].endswith(".service") and "@." not in p[0]:
            enabled[p[0]] = p[1] if len(p) > 1 else "enabled"
    rc, out = C.run(base + ["list-units", "--type=service", "--all", "--no-legend", "--no-pager", "--plain"],
                    timeout=25)
    info = {}
    for line in out.splitlines():
        p = line.split(None, 4)
        if len(p) >= 4:
            info[p[0]] = {"sub": p[3], "desc": p[4].strip() if len(p) > 4 else ""}
    return enabled, info


def list_units(user):
    kind = "usr" if user else "sys"
    enabled, info = _units(user)
    rec = _load_state().get(kind, {})
    items = []
    names = set(enabled) | set(rec)
    for u in sorted(names):
        i = info.get(u, {})
        if u in enabled:
            state = _("A correr") if i.get("sub") == "running" else _("Ativo")
        else:
            state = _("Eliminado (mascarado)") if rec.get(u) == "masked" else _("Desativado")
        desc = (_(HINTS[u.lower()]) if u.lower() in HINTS else (i.get("desc") or ""))
        items.append({"key": f"{kind}:{u}", "kind": kind, "id": u, "name": u[:-8],
                      "state": state, "enabled": u in enabled, "desc": desc,
                      "protected": (not user) and C.is_protected_unit(u)})
    return items


def list_startup():
    return list_xdg() + list_units(True) + list_units(False)


def _remove_lines(path, keys):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    keep = [l for l in lines if l.split("=", 1)[0].strip() not in keys]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(keep) + "\n")


def xdg_disable(item):
    os.makedirs(XDG_USER, exist_ok=True)
    path = os.path.join(XDG_USER, item["id"])
    if os.path.exists(path):
        _remove_lines(path, ("Hidden", "X-GNOME-Autostart-enabled"))
        with open(path, "a", encoding="utf-8") as f:
            f.write("Hidden=true\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=%s\nHidden=true\n" % item["name"])


def xdg_enable(item):
    path = os.path.join(XDG_USER, item["id"])
    if not os.path.exists(path):
        return
    _remove_lines(path, ("Hidden", "X-GNOME-Autostart-enabled"))
    if not _desktop(path).get("Exec"):
        os.remove(path)


def xdg_delete(item):
    path = os.path.join(XDG_USER, item["id"])
    if item["has_sys"]:
        xdg_disable(item)
        return _("'{n}' é uma entrada do sistema: foi desativada (não pode ser apagada sem root).").format(n=item["name"])
    if os.path.exists(path):
        os.remove(path)
    return _("'{n}' eliminada.").format(n=item["name"])


def user_unit_delete(unit):
    path = os.path.join(USER_UNITS, unit)
    C.run(["systemctl", "--user", "disable", "--now", unit])
    if os.path.isfile(path) and not os.path.islink(path):
        os.remove(path)
        C.run(["systemctl", "--user", "daemon-reload"])
        return "eliminado"
    C.run(["systemctl", "--user", "mask", unit])
    return "masked"


# ------------------------------------------------------------------ Firefox
FF_BEGIN = "// MAINUAN OTIMIZADOR BEGIN"
FF_END = "// MAINUAN OTIMIZADOR END"
FF_PARTS = {
    "memory": (
        ("browser.tabs.unloadOnLowMemory", True),
        ("browser.tabs.min_inactive_duration_before_unload", 300000),
        ("dom.ipc.processCount", 4),
        ("browser.cache.memory.capacity", 131072),
        ("browser.sessionhistory.max_total_viewers", 2),
    ),
    "general": (
        ("network.prefetch-next", False),
        ("network.dns.disablePrefetch", True),
        ("network.predictor.enabled", False),
        ("datareporting.healthreport.uploadEnabled", False),
        ("toolkit.telemetry.enabled", False),
        ("toolkit.telemetry.unified", False),
        ("browser.newtabpage.activity-stream.feeds.telemetry", False),
        ("browser.newtabpage.activity-stream.telemetry", False),
        ("browser.newtabpage.activity-stream.feeds.section.topstories", False),
        ("browser.newtabpage.activity-stream.showSponsored", False),
    ),
}


def firefox_profiles():
    roots = ["~/.mozilla/firefox", "~/snap/firefox/common/.mozilla/firefox",
             "~/.var/app/org.mozilla.firefox/.mozilla/firefox"]
    res = []
    for r in roots:
        for p in glob.glob(os.path.expanduser(r) + "/*"):
            if os.path.isdir(p) and os.path.exists(p + "/prefs.js"):
                res.append(p)
    return res


def _js(v):
    return "true" if v is True else "false" if v is False else str(v)


def _strip_block(text):
    out, skip = [], False
    for line in text.splitlines():
        if line.strip() == FF_BEGIN:
            skip = True
            continue
        if line.strip() == FF_END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip("\n")


def firefox_applied(profile):
    return FF_BEGIN in C.read(profile + "/user.js")


def firefox_apply(profile, parts=("memory", "general")):
    path = profile + "/user.js"
    base = _strip_block(C.read(path))
    prefs = [kv for p in parts for kv in FF_PARTS.get(p, ())]
    block = [FF_BEGIN] + ['user_pref("%s", %s);' % (k, _js(v)) for k, v in prefs] + [FF_END]
    with open(path, "w", encoding="utf-8") as f:
        f.write((base + "\n" if base else "") + "\n".join(block) + "\n")


def firefox_remove(profile):
    path = profile + "/user.js"
    if not os.path.exists(path):
        return
    base = _strip_block(C.read(path))
    if base.strip():
        with open(path, "w", encoding="utf-8") as f:
            f.write(base + "\n")
    else:
        os.remove(path)


def detect_browsers():
    """Lista de (nome, suportado) dos navegadores instalados."""
    res = []
    ff = len(firefox_profiles())
    if ff or shutil.which("firefox") or os.path.isdir("/snap/firefox"):
        n = _("Firefox ({n} perfil)") if ff == 1 else _("Firefox ({n} perfis)")
        res.append((n.format(n=ff), True))
    for name, _dirs in C.chromium_installed():
        res.append((name, True))
    for name, binaries in (("Opera", ("opera",)), ("Vivaldi", ("vivaldi", "vivaldi-stable"))):
        if any(shutil.which(b) for b in binaries):
            res.append((name, False))
    return res


def browser_ram_kb():
    tot = 0
    for p in _snapshot().values():
        if C.is_browser(p["name"], p["cmd"]) and p["uid"] == os.getuid():
            tot += p["rss_kb"]
    return tot


# -------------------------------------------------------------------- tema
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
