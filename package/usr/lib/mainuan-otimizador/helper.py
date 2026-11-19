#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - helper executado como root via pkexec / systemd.
Todos os argumentos são validados; nada é executado através de shell."""
import os
import sys
import re
import json
import time
import glob
import shutil
import signal
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import i18n  # noqa: E402
from i18n import _  # noqa: E402

ZP = "/sys/module/zswap/parameters/"
GROUPS = {
    "bluetooth": ("bluetooth.service",),
    "printing": ("cups.service", "cups.socket", "cups.path", "cups-browsed.service"),
}


def out(msg):
    print(msg, flush=True)


def sh(cmd, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        out(f"  ! {cmd[0]}: {e}")
        return False
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip().splitlines()
        out(f"  ! {cmd[0]}: {msg[-1] if msg else _('falhou')}")
    return p.returncode == 0


def write(path, val):
    try:
        with open(path, "w") as f:
            f.write(str(val))
        return True
    except OSError as e:
        out("  ! " + _("não foi possível escrever {p}: {e}").format(p=path, e=e.strerror))
        return False


def swap_active(name):
    return any(s["name"] == name for s in C.swaps())


def unit_exists(unit):
    rc, _out = C.run(["systemctl", "cat", unit])
    return rc == 0


# ---------------------------------------------------------------- memória
def save_original():
    if os.path.exists(C.ORIG_FILE):
        return
    d = {"swappiness": C.read("/proc/sys/vm/swappiness"),
         "page_cluster": C.read("/proc/sys/vm/page-cluster")}
    for k in ("enabled", "compressor", "max_pool_percent"):
        d["zswap_" + k] = C.read(ZP + k)
    os.makedirs(C.CONFIG_DIR, exist_ok=True)
    with open(C.ORIG_FILE, "w") as f:
        json.dump(d, f)


def zram_teardown():
    for d in sorted(glob.glob("/sys/block/zram[0-9]*")):
        dev = "/dev/" + os.path.basename(d)
        if swap_active(dev):
            sh(["swapoff", dev])
        if C.read(d + "/disksize", "0") != "0":
            write(d + "/reset", "1")


def other_zram_manager():
    for p in ("/etc/systemd/zram-generator.conf", "/usr/bin/init-zram-swapping",
              "/lib/systemd/system/zram-config.service", "/usr/lib/systemd/system/zram-config.service"):
        if os.path.exists(p):
            return p
    return None


def zram_setup(plan):
    ram = C.meminfo().get("MemTotal", 0) // 1024
    size_mb = min(ram * plan["zram_percent"] // 100, 16384)
    if size_mb < 128:
        out("  " + _("zram ignorado (tamanho demasiado pequeno)"))
        return
    other = other_zram_manager()
    if other:
        out("  ! " + _("atenção: outro gestor de zram detetado ({p}); pode haver conflito").format(p=other))
    if not os.path.exists("/sys/block/zram0"):
        sh(["modprobe", "zram"])
        for _i in range(10):
            if os.path.exists("/sys/block/zram0"):
                break
            time.sleep(0.3)
    if not os.path.exists("/sys/block/zram0") and os.path.exists("/sys/class/zram-control/hot_add"):
        C.read("/sys/class/zram-control/hot_add")
    if not os.path.exists("/sys/block/zram0"):
        out("  ! " + _("zram não está disponível neste kernel"))
        return
    dev, sysd = "/dev/zram0", "/sys/block/zram0"
    for _i in range(10):
        if os.path.exists(dev):
            break
        time.sleep(0.3)
    zram_teardown()
    algos = C.read(sysd + "/comp_algorithm").replace("[", "").replace("]", "").split()
    algo = plan["zram_algo"]
    if algo not in algos:
        algo = next((a for a in ("zstd", "lz4", "lzo-rle", "lzo") if a in algos), None)
        if algo:
            out("  " + _("algoritmo pedido indisponível; usado {a}").format(a=algo))
    if algo:
        write(sysd + "/comp_algorithm", algo)
    if not write(sysd + "/disksize", str(size_mb * C.MIB)):
        return
    if sh(["mkswap", "-L", "mainuan-zram", dev]) and sh(["swapon", "-p", str(C.ZRAM_PRIO), dev]):
        out("  " + _("zram ativo: {s} ({a})").format(s=C.fmt_mb(size_mb), a=algo or _("predefinido")))


def swapfile_remove():
    if swap_active(C.SWAPFILE):
        sh(["swapoff", C.SWAPFILE])
    try:
        os.remove(C.SWAPFILE)
        out("  " + _("swap em ficheiro removida"))
    except FileNotFoundError:
        pass
    except OSError as e:
        out("  ! " + _("não foi possível remover {p}: {e}").format(p=C.SWAPFILE, e=e.strerror))


def swapfile_ensure(size_mb):
    if size_mb <= 0:
        swapfile_remove()
        return
    want = size_mb * C.MIB
    if os.path.exists(C.SWAPFILE) and os.path.getsize(C.SWAPFILE) == want:
        if not swap_active(C.SWAPFILE):
            sh(["swapon", "-p", str(C.DISK_PRIO), C.SWAPFILE])
        return
    swapfile_remove()
    _rc, fs = C.run(["findmnt", "-no", "FSTYPE", "-T", "/"])
    created = False
    if fs == "btrfs" and shutil.which("btrfs"):
        created = sh(["btrfs", "filesystem", "mkswapfile", "--size", f"{size_mb}m", C.SWAPFILE])
    if not created:
        try:
            with open(C.SWAPFILE, "wb"):
                pass
            os.chmod(C.SWAPFILE, 0o600)
        except OSError as e:
            out("  ! " + _("não foi possível criar {p}: {e}").format(p=C.SWAPFILE, e=e.strerror))
            return
        if fs == "btrfs":
            sh(["chattr", "+C", C.SWAPFILE])
        if not sh(["fallocate", "-l", str(want), C.SWAPFILE]):
            sh(["dd", "if=/dev/zero", f"of={C.SWAPFILE}", "bs=1M", f"count={size_mb}", "status=none"])
        os.chmod(C.SWAPFILE, 0o600)
        if not sh(["mkswap", C.SWAPFILE]):
            swapfile_remove()
            return
    if sh(["swapon", "-p", str(C.DISK_PRIO), C.SWAPFILE]):
        out("  " + _("swap em ficheiro ativa: {s}").format(s=C.fmt_mb(size_mb)))
    else:
        swapfile_remove()


def zswap_apply(plan):
    if not os.path.isdir("/sys/module/zswap"):
        if plan["zswap"]:
            out("  ! " + _("zswap não está disponível neste kernel"))
        return
    if plan["zswap"]:
        write(ZP + "compressor", plan["zswap_compressor"])
        write(ZP + "max_pool_percent", plan["zswap_pool_percent"])
        write(ZP + "enabled", "Y")
        out("  " + _("zswap ativo ({c}, {p}%)").format(c=C.read(ZP + "compressor"),
                                                     p=C.read(ZP + "max_pool_percent")))
    else:
        write(ZP + "enabled", "N")


def apply_plan(plan):
    save_original()
    out(_("A aplicar:") + " " + " | ".join(C.describe_plan(plan)))
    if plan["zram_percent"] > 0:
        zram_setup(plan)
    else:
        zram_teardown()
    swapfile_ensure(plan["swapfile_mb"])
    zswap_apply(plan)
    write("/proc/sys/vm/swappiness", plan["swappiness"])
    write("/proc/sys/vm/page-cluster", plan["page_cluster"])
    for n in plan.get("notes", []):
        out("  " + _("nota:") + " " + n)


def cmd_set_memory(arg):
    cfg = C.validate_config(json.loads(arg))
    os.makedirs(C.CONFIG_DIR, exist_ok=True)
    with open(C.CONFIG_FILE, "w") as f:
        json.dump(cfg, f)
    os.chmod(C.CONFIG_FILE, 0o644)
    apply_plan(C.resolve_plan(cfg))
    out("OK")


def cmd_apply_saved():
    if not os.path.exists(C.CONFIG_FILE):
        return
    cfg = C.validate_config(json.load(open(C.CONFIG_FILE)))
    apply_plan(C.resolve_plan(cfg))


def cmd_restore():
    zram_teardown()
    swapfile_remove()
    try:
        o = json.load(open(C.ORIG_FILE))
    except (OSError, ValueError):
        o = {}
    write("/proc/sys/vm/swappiness", o.get("swappiness") or 60)
    write("/proc/sys/vm/page-cluster", o.get("page_cluster") or 3)
    if os.path.isdir("/sys/module/zswap"):
        if o.get("zswap_compressor"):
            write(ZP + "compressor", o["zswap_compressor"])
        if o.get("zswap_max_pool_percent"):
            write(ZP + "max_pool_percent", o["zswap_max_pool_percent"])
        if o.get("zswap_enabled"):
            write(ZP + "enabled", o["zswap_enabled"])
    for p in (C.CONFIG_FILE, C.ORIG_FILE):
        try:
            os.remove(p)
        except OSError:
            pass
    out(_("Predefinições restauradas."))
    out("OK")


# ------------------------------------------------------------ otimização
def cmd_drop_caches():
    os.sync()
    write("/proc/sys/vm/drop_caches", "3")
    write("/proc/sys/vm/compact_memory", "1")
    out("OK")


def cmd_governor(name):
    if name not in ("powersave", "performance", "schedutil", "ondemand", "conservative"):
        raise ValueError(_("governor inválido"))
    n = 0
    for d in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq"):
        avail = C.read(d + "/scaling_available_governors").split()
        if name in avail and write(d + "/scaling_governor", name):
            n += 1
    out(_("Governor '{g}' aplicado a {n} núcleo(s).").format(g=name, n=n))
    if n == 0:
        raise ValueError(_("este sistema não permite alterar o governor"))


def cmd_terminate(pid_s, sig):
    pid = int(pid_s)
    if pid <= 1 or pid == os.getpid():
        raise ValueError(_("pid inválido"))
    if sig not in ("TERM", "KILL"):
        raise ValueError(_("sinal inválido"))
    cmdline = open(f"/proc/{pid}/cmdline", "rb").read()
    if not cmdline:
        raise ValueError(_("processo do kernel"))
    name = C.read(f"/proc/{pid}/comm")
    if C.is_protected_name(name):
        raise ValueError(_("'{n}' é um processo essencial").format(n=name))
    os.kill(pid, signal.SIGTERM if sig == "TERM" else signal.SIGKILL)
    out("OK")


def cmd_service(action, unit):
    if not re.fullmatch(r"[A-Za-z0-9@._:\-]+\.service", unit):
        raise ValueError(_("nome de serviço inválido"))
    if C.is_protected_unit(unit) and action in ("disable", "mask", "stop"):
        raise ValueError(_("'{n}' é um serviço essencial").format(n=unit))
    if action == "disable":
        ok = sh(["systemctl", "disable", "--now", unit])
    elif action == "mask":
        sh(["systemctl", "disable", "--now", unit])
        ok = sh(["systemctl", "mask", unit])
    elif action == "enable":
        sh(["systemctl", "unmask", unit])
        ok = sh(["systemctl", "enable", "--now", unit])
    else:
        raise ValueError(_("ação inválida"))
    if not ok:
        raise ValueError(_("o systemctl falhou"))
    out("OK")


def cmd_group(group, action):
    """Bluetooth / impressão: grupos de unidades pré-definidos (lista fixa)."""
    if group not in GROUPS or action not in ("enable", "disable"):
        raise ValueError(_("ação inválida"))
    done = 0
    for u in GROUPS[group]:
        if not unit_exists(u):
            continue
        if action == "disable":
            sh(["systemctl", "disable", "--now", u])
        else:
            sh(["systemctl", "enable", "--now", u])
        done += 1
    if done == 0:
        raise ValueError(_("serviço não encontrado neste sistema"))
    out(_("Serviços desativados.") if action == "disable" else _("Serviços ativados."))
    out("OK")


def cmd_trim(action):
    if action == "enable":
        if not unit_exists("fstrim.timer"):
            raise ValueError(_("fstrim.timer não existe neste sistema"))
        sh(["systemctl", "enable", "--now", "fstrim.timer"])
        sh(["fstrim", "-av"])
    elif action == "disable":
        sh(["systemctl", "disable", "--now", "fstrim.timer"])
    else:
        raise ValueError(_("ação inválida"))
    out("OK")


def cmd_earlyoom(action):
    if action == "enable":
        if not shutil.which("earlyoom"):
            env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
            out(_("A instalar o EarlyOOM…"))
            if not sh(["apt-get", "install", "-y", "earlyoom"], env=env):
                raise ValueError(_("não foi possível instalar o EarlyOOM (apt ocupado ou sem rede)"))
        sh(["systemctl", "enable", "--now", "earlyoom.service"])
    elif action == "disable":
        sh(["systemctl", "disable", "--now", "earlyoom.service"])
    else:
        raise ValueError(_("ação inválida"))
    out("OK")


def cmd_browser_policy(action, parts="memory,general"):
    if action not in ("apply", "remove"):
        raise ValueError(_("ação inválida"))
    plist = [p for p in parts.split(",") if p in C.CHROMIUM_POLICY_PARTS]
    if action == "apply" and not plist:
        raise ValueError(_("ação inválida"))
    found = C.chromium_installed()
    if action == "apply" and not found:
        out(_("Nenhum navegador baseado em Chromium encontrado."))
    targets = found if action == "apply" else [(n, d) for n, _b, d in C.CHROMIUM_TARGETS]
    for name, dirs in targets:
        for d in dirs:
            path = os.path.join(d, C.POLICY_FILE)
            if action == "apply":
                os.makedirs(d, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(C.chromium_policy(plist), f, indent=2)
                os.chmod(path, 0o644)
                out(_("Política aplicada: {n}").format(n=name) + f" ({path})")
            elif os.path.exists(path):
                os.remove(path)
                out(_("Política removida: {n}").format(n=name))
    out("OK")


def main(argv):
    args = argv[1:]
    if args and args[0].startswith("--lang="):
        i18n.set_lang(args[0][7:])
        args = args[1:]
    if os.geteuid() != 0:
        out(_("Este helper tem de ser executado como root."))
        return 1
    if not args:
        out("uso: helper.py [--lang=xx] <comando> [args]")
        return 2
    c, a = args[0], args[1:]
    try:
        if c == "set-memory" and len(a) == 1:
            cmd_set_memory(a[0])
        elif c == "apply-saved":
            cmd_apply_saved()
        elif c == "restore":
            cmd_restore()
        elif c == "drop-caches":
            cmd_drop_caches()
        elif c == "governor" and len(a) == 1:
            cmd_governor(a[0])
        elif c == "terminate" and len(a) == 2:
            cmd_terminate(a[0], a[1])
        elif c == "service" and len(a) == 2:
            cmd_service(a[0], a[1])
        elif c == "group" and len(a) == 2:
            cmd_group(a[0], a[1])
        elif c == "trim" and len(a) == 1:
            cmd_trim(a[0])
        elif c == "earlyoom" and len(a) == 1:
            cmd_earlyoom(a[0])
        elif c == "browser-policy" and 1 <= len(a) <= 2:
            cmd_browser_policy(*a)
        else:
            out(_("comando inválido"))
            return 2
    except (ValueError, OSError, json.JSONDecodeError) as e:
        out(_("Erro:") + f" {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
