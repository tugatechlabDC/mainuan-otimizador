#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - funções partilhadas (interface e helper com privilégios)."""
import os
import re
import glob
import shutil
import subprocess

from i18n import _

APP_NAME = "MAINUAN OTIMIZADOR"
APP_ID = "mainuan-otimizador"
VERSION = "2.0"
AUTHOR = "David Caixinha"

CONFIG_DIR = "/etc/mainuan-otimizador"
CONFIG_FILE = CONFIG_DIR + "/memory.json"
ORIG_FILE = CONFIG_DIR + "/original.json"
SWAPFILE = "/swapfile.mainuan"
ZRAM_PRIO = 100
DISK_PRIO = 10
MIB = 1024 * 1024

ZRAM_ALGOS = ("zstd", "lz4", "lzo-rle", "lzo", "lz4hc")
ZSWAP_COMPRESSORS = ("zstd", "lz4", "lzo", "lzo-rle", "deflate", "lz4hc")

# Processos que nunca devem ser fechados/alterados (prefixos do nome)
PROTECTED_PREFIXES = (
    "systemd", "init", "dbus", "xorg", "xwayland", "kwin", "plasma", "ksmserver",
    "kded", "kglobal", "krunner", "kactivitymanager", "kscreen", "powerdevil",
    "startplasma", "sddm", "gdm", "lightdm", "pipewire", "wireplumber", "pulse",
    "networkmanager", "polkit", "xdg-", "at-spi", "gvfs", "dconf", "gnome-shell",
    "gnome-session", "mutter", "ibus", "fcitx", "gpg-agent", "ssh", "sh", "bash",
    "zsh", "fish", "login", "konsole", "yakuake", "gnome-terminal", "tmux",
    "screen", "xfce4", "xfwm", "xfdesktop", "org_kde", "udisks", "upower",
    "wpa_supplicant", "agetty", "cron", "rsyslog", "snapd", "mainuan",
)
BROWSER_KEYS = (
    "firefox", "chrome", "chromium", "brave", "opera", "vivaldi", "msedge",
    "librewolf", "zen-browser", "contentproc",
)
PROTECTED_UNIT_RE = re.compile(
    r"^(systemd-.*|dbus.*|networkmanager.*|network-manager.*|wpa_supplicant.*|sddm.*|gdm.*|lightdm.*|"
    r"polkit.*|apparmor.*|udev.*|getty@.*|serial-getty@.*|user@.*|plymouth.*|snapd.*|"
    r"mainuan-otimizador.*|accounts-daemon.*|upower.*|udisks2.*|ufw.*|rsyslog.*|cron.*)\.service$",
    re.I)

CHROMIUM_TARGETS = (
    ("Google Chrome", ("google-chrome", "google-chrome-stable"), ("/etc/opt/chrome/policies/managed",)),
    ("Chromium", ("chromium", "chromium-browser"),
     ("/etc/chromium/policies/managed", "/var/snap/chromium/current/policies/managed")),
    ("Brave", ("brave-browser", "brave"), ("/etc/brave/policies/managed",)),
    ("Microsoft Edge", ("microsoft-edge", "microsoft-edge-stable"), ("/etc/opt/edge/policies/managed",)),
)
POLICY_FILE = "mainuan-otimizador.json"
CHROMIUM_POLICY_PARTS = {
    "memory": {"MemorySaverModeEnabled": True, "HighEfficiencyModeEnabled": True},
    "general": {"BackgroundModeEnabled": False, "NetworkPredictionOptions": 2,
                "MetricsReportingEnabled": False},
}


def chromium_policy(parts):
    d = {}
    for p in parts:
        d.update(CHROMIUM_POLICY_PARTS.get(p, {}))
    return d


def read(path, default=""):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def run(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def is_protected_name(name, cmd=""):
    n = (name or "").lower()
    if any(n.startswith(p) for p in PROTECTED_PREFIXES):
        return True
    return "mainuan-otimizador" in (cmd or "")


def is_browser(name, cmd=""):
    s = ((name or "") + " " + (cmd or "")).lower()
    return any(k in s for k in BROWSER_KEYS)


def is_protected_unit(unit):
    return bool(PROTECTED_UNIT_RE.match(unit))


def meminfo():
    d = {}
    for line in read("/proc/meminfo").splitlines():
        k, _sep, v = line.partition(":")
        try:
            d[k] = int(v.split()[0])
        except (ValueError, IndexError):
            pass
    return d


def swaps():
    out = []
    for line in read("/proc/swaps").splitlines()[1:]:
        p = line.split()
        if len(p) >= 5:
            try:
                out.append({"name": p[0], "type": p[1], "size_kb": int(p[2]),
                            "used_kb": int(p[3]), "prio": int(p[4])})
            except ValueError:
                pass
    return out


def root_disk():
    rc, src = run(["findmnt", "-no", "SOURCE", "/"])
    if rc != 0 or not src:
        return None, None
    src = src.split("[")[0]
    rc, out = run(["lsblk", "-nro", "NAME,ROTA,TYPE", "-s", src])
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 3 and p[2] == "disk":
            return p[0], p[1] == "1"
    return None, None


def zram_available():
    if glob.glob("/sys/block/zram[0-9]*") or os.path.exists("/sys/class/zram-control"):
        return True
    rc, _o = run(["modinfo", "zram"])
    return rc == 0


def hardware():
    mi = meminfo()
    name, rota = root_disk()
    st = os.statvfs("/")
    own = 0
    if os.path.exists(SWAPFILE):
        try:
            own = os.path.getsize(SWAPFILE) // MIB
        except OSError:
            own = 0
    other = 0
    for s in swaps():
        if s["name"].startswith("/dev/zram") or s["name"] == SWAPFILE:
            continue
        other += s["size_kb"] // 1024
    return {
        "ram_mb": mi.get("MemTotal", 0) // 1024,
        "cpus": os.cpu_count() or 1,
        "disk": name,
        "rotational": rota,
        "nvme": bool(name and name.startswith("nvme")),
        "free_mb": st.f_bavail * st.f_frsize // MIB,
        "own_swap_mb": own,
        "other_swap_mb": other,
        "zswap": os.path.isdir("/sys/module/zswap"),
        "zram": zram_available(),
    }


def storage_label(hw):
    if hw.get("nvme"):
        return _("SSD NVMe")
    if hw.get("rotational") is True:
        return _("HDD (disco mecânico)")
    if hw.get("rotational") is False:
        return _("SSD")
    return _("armazenamento desconhecido")


def fmt_mb(mb):
    return f"{mb / 1024:.1f} GiB" if mb >= 1024 else f"{int(mb)} MiB"


def auto_plan(hw):
    """Plano ideal para o hardware detetado (RAM + armazenamento)."""
    ram = hw["ram_mb"]
    gb = ram / 1024.0
    notes = []
    if gb <= 2:
        zp, swp, disk = 100, 100, 4096
    elif gb <= 4:
        zp, swp, disk = 75, 100, 4096
    elif gb <= 8:
        zp, swp, disk = 50, 100, 2048
    elif gb <= 16:
        zp, swp, disk = 35, 80, 2048
    else:
        zp, swp, disk = 25, 60, 0
    algo = "lz4" if (hw["cpus"] <= 2 or gb <= 2) else "zstd"

    if hw.get("rotational") is True:
        disk = 2048 if gb <= 4 else 0
        notes.append(_("Disco mecânico: swap em disco reduzida/evitada (é lenta); o zram faz o trabalho."))
    if hw["other_swap_mb"] > 0:
        disk = 0
        notes.append(_("Já existe swap em disco no sistema; é mantida como reserva."))
    if disk > 0:
        livre = hw["free_mb"] + hw["own_swap_mb"]
        if livre < disk * 2 + 4096:
            disk = 0
            notes.append(_("Pouco espaço livre: não foi criada swap em disco."))

    if hw["zram"]:
        plan = {"kind": "zram", "zram_percent": zp, "zram_algo": algo, "zswap": False,
                "zswap_compressor": "zstd", "zswap_pool_percent": 20, "swapfile_mb": disk,
                "swappiness": swp, "page_cluster": 0}
        notes.insert(0, _("zram com prioridade máxima; zswap desligado (seria redundante)."))
    elif hw["zswap"]:
        plan = {"kind": "zswap", "zram_percent": 0, "zram_algo": algo, "zswap": True,
                "zswap_compressor": "zstd", "zswap_pool_percent": 20,
                "swapfile_mb": max(disk, 2048) if hw["other_swap_mb"] == 0 else 0,
                "swappiness": 60, "page_cluster": 0}
        notes.insert(0, _("O kernel não tem zram: usado zswap + swap em disco."))
    else:
        plan = {"kind": "swap", "zram_percent": 0, "zram_algo": algo, "zswap": False,
                "zswap_compressor": "zstd", "zswap_pool_percent": 20,
                "swapfile_mb": max(disk, 2048) if hw["other_swap_mb"] == 0 else 0,
                "swappiness": 60, "page_cluster": 3}
        notes.insert(0, _("Sem zram/zswap no kernel: swap tradicional em ficheiro."))
    plan["notes"] = notes
    return plan


def manual_plan(cfg):
    kind = cfg["kind"]
    return {
        "kind": kind,
        "zram_percent": cfg["zram_percent"] if kind == "zram" else 0,
        "zram_algo": cfg["zram_algo"],
        "zswap": kind == "zswap",
        "zswap_compressor": cfg["zswap_compressor"],
        "zswap_pool_percent": cfg["zswap_pool_percent"],
        "swapfile_mb": cfg["swapfile_mb"],
        "swappiness": cfg["swappiness"],
        "page_cluster": 0 if kind in ("zram", "zswap") else 3,
        "notes": [],
    }


def _int(cfg, key, lo, hi):
    v = cfg.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < lo or v > hi:
        raise ValueError(_("valor inválido para {key}").format(key=key))
    return v


def validate_config(cfg):
    if not isinstance(cfg, dict):
        raise ValueError(_("configuração inválida"))
    mode = cfg.get("mode")
    if mode == "auto":
        return {"mode": "auto"}
    if mode != "manual":
        raise ValueError(_("modo inválido"))
    kind = cfg.get("kind")
    if kind not in ("zram", "zswap", "swap"):
        raise ValueError(_("tipo inválido"))
    out = {"mode": "manual", "kind": kind,
           "zram_percent": _int(cfg, "zram_percent", 10, 200),
           "zswap_pool_percent": _int(cfg, "zswap_pool_percent", 5, 50),
           "swapfile_mb": _int(cfg, "swapfile_mb", 0, 131072),
           "swappiness": _int(cfg, "swappiness", 0, 200)}
    if cfg.get("zram_algo") not in ZRAM_ALGOS:
        raise ValueError(_("algoritmo zram inválido"))
    if cfg.get("zswap_compressor") not in ZSWAP_COMPRESSORS:
        raise ValueError(_("compressor zswap inválido"))
    out["zram_algo"] = cfg["zram_algo"]
    out["zswap_compressor"] = cfg["zswap_compressor"]
    return out


def resolve_plan(cfg, hw=None):
    cfg = validate_config(cfg)
    if cfg["mode"] == "auto":
        return auto_plan(hw or hardware())
    return manual_plan(cfg)


def plan_rows(plan, hw=None):
    """Linhas (rótulo, valor) legíveis para a interface."""
    rows = []
    kind = plan["kind"]
    if kind == "zram":
        pct = plan["zram_percent"]
        if hw:
            val = _("{p}% da RAM (≈ {s})").format(p=pct, s=fmt_mb(min(hw["ram_mb"] * pct // 100, 16384)))
        else:
            val = _("{p}% da RAM").format(p=pct)
        rows.append((_("zram"), val))
        rows.append((_("Compressão"), plan["zram_algo"]))
        rows.append((_("Prioridade"), str(ZRAM_PRIO)))
    elif kind == "zswap":
        rows.append((_("zswap"), _("ativo")))
        rows.append((_("Compressão"), plan["zswap_compressor"]))
        rows.append((_("Cache máxima"), _("{p}% da RAM").format(p=plan["zswap_pool_percent"])))
    else:
        rows.append((_("Tipo"), _("Swap tradicional (sem zram, sem zswap)")))
    if plan["swapfile_mb"] > 0:
        rows.append((_("Swap em ficheiro"), fmt_mb(plan["swapfile_mb"])))
    else:
        rows.append((_("Swap em ficheiro"), _("nenhuma gerida por esta aplicação")))
    rows.append((_("Swappiness"), str(plan["swappiness"])))
    return rows


def describe_plan(plan, hw=None):
    return ["%s: %s" % r for r in plan_rows(plan, hw)]


def chromium_installed():
    found = []
    for name, bins, dirs in CHROMIUM_TARGETS:
        ok = any(shutil.which(b) for b in bins)
        if name == "Chromium" and os.path.isdir("/snap/chromium"):
            ok = True
        if ok:
            found.append((name, dirs))
    return found
