# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - gestão de serviços systemd, arranque, diagnóstico, otimização e histórico.
Leituras sem privilégios; as alterações ao sistema passam pelo helper (pkexec)."""
import os
import re
import json
import time
import glob
import shutil
import subprocess

import common as C

ENV = dict(os.environ, LC_ALL="C", LANG="C", SYSTEMD_COLORS="0", SYSTEMD_PAGER="")
HISTORY_FILE = os.path.expanduser("~/.config/mainuan-otimizador/history.json")
FREQUENT_SECS = 300
MIB = 1048576


# ------------------------------------------------------------------ utilitários
def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV)
        return p.returncode, p.stdout or "", p.stderr or ""
    except (OSError, subprocess.TimeoutExpired):
        return 127, "", ""


def sctl(scope, *args, timeout=20):
    cmd = ["systemctl"] + (["--user"] if scope == "user" else []) + ["--no-pager"] + list(args)
    return run(cmd, timeout)


def parse_show(text):
    """Blocos 'Chave=Valor' separados por linhas em branco -> lista de dicionários."""
    blocks, cur = [], {}
    for line in text.splitlines():
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        k, _s, v = line.partition("=")
        cur[k] = v
    if cur:
        blocks.append(cur)
    return blocks


def to_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def span_secs(text):
    """'1h 30min 5.2s' -> segundos (float) ou None."""
    units = {"us": 1e-6, "ms": 1e-3, "s": 1, "sec": 1, "min": 60, "h": 3600, "hr": 3600,
             "d": 86400, "w": 604800, "month": 2592000, "y": 31557600}
    tot, found = 0.0, False
    for num, u in re.findall(r"([\d.]+)\s*(us|ms|month|min|sec|s|h|hr|d|w|y)\b", text or ""):
        try:
            tot += float(num) * units[u]
            found = True
        except (ValueError, KeyError):
            pass
    return tot if found else None


def valid_unit(u):
    return bool(re.fullmatch(r"[A-Za-z0-9@._:\\-]+\.(service|socket|timer|path|target|mount|swap)", u or ""))


def valid_pkg(p):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9+.\-]*(:[a-z0-9]+)?", p or ""))


# ------------------------------------------------------------------ serviços
SHOW_PROPS = "Id,Description,LoadState,ActiveState,SubState,UnitFileState,MemoryCurrent,FragmentPath,MainPID"


def list_services():
    out = []
    for scope in ("system", "user"):
        rc, txt, _e = sctl(scope, "show", "--type=service", "--all", "-p", SHOW_PROPS, timeout=40)
        if rc != 0:
            continue
        seen = {}
        for b in parse_show(txt):
            name = b.get("Id", "")
            if not name.endswith(".service") or "@." in name or b.get("LoadState") == "not-found":
                continue
            mem = to_int(b.get("MemoryCurrent"))
            if mem is not None and mem >= 2 ** 63:
                mem = None
            seen[name] = dict(name=name, scope=scope, description=b.get("Description", ""),
                              active=b.get("ActiveState", ""), sub=b.get("SubState", ""),
                              boot=b.get("UnitFileState", "") or "static", memory=mem,
                              file=b.get("FragmentPath", ""), pid=to_int(b.get("MainPID"), 0))
        rc, txt, _e = sctl(scope, "list-unit-files", "--type=service", "--no-legend")
        if rc == 0:
            for line in txt.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0].endswith(".service") and "@." not in parts[0] \
                        and parts[0] not in seen:
                    seen[parts[0]] = dict(name=parts[0], scope=scope, description="", active="inactive",
                                          sub="dead", boot=parts[1], memory=None, file="", pid=0)
        for s in seen.values():
            s["protected"] = scope == "system" and is_protected(s["name"])
            out.append(s)
    out.sort(key=lambda s: (s["scope"] != "system", s["name"].lower()))
    return out


PROTECTED_RE = re.compile(
    r"^(systemd-.*|dbus.*|networkmanager\.service|network-manager\.service|sddm.*|gdm.*|lightdm.*|"
    r"display-manager.*|polkit.*|apparmor.*|udev.*|getty@.*|serial-getty@.*|getty-static.*|user@.*|"
    r"user-runtime-dir@.*|plymouth.*|accounts-daemon.*|udisks2.*|rsyslog.*|cron.*|login.*|"
    r"mainuan-otimizador.*|emergency.*|rescue.*|ssh\.service|sshd\.service)$", re.I)
PROTECTION_EXCEPTIONS = ("systemd-networkd-wait-online.service",)


def is_protected(unit):
    if unit.lower() in PROTECTION_EXCEPTIONS:
        return False
    return bool(PROTECTED_RE.match(unit))


def service_details(unit, scope="system"):
    props = "Id,Description,ActiveState,SubState,UnitFileState,MemoryCurrent,FragmentPath,MainPID," \
            "ActiveEnterTimestamp,Requires,WantedBy,RequiredBy"
    rc, txt, _e = sctl(scope, "show", unit, "-p", props)
    b = parse_show(txt)[0] if txt.strip() else {}
    rc, st, _e = sctl(scope, "status", unit, "-n", "6", "--no-pager", "-l")
    pkg = ""
    frag = b.get("FragmentPath", "")
    if frag and scope == "system":
        rc, o, _e = run(["dpkg", "-S", frag])
        if rc == 0 and ":" in o:
            pkg = o.split(":")[0].strip()
    mem = to_int(b.get("MemoryCurrent"))
    return dict(since=b.get("ActiveEnterTimestamp", ""), pid=to_int(b.get("MainPID"), 0),
                memory=None if mem is None or mem >= 2 ** 63 else mem, package=pkg, file=frag,
                requires=b.get("Requires", "").split(), wanted_by=(b.get("WantedBy", "") + " " + b.get("RequiredBy", "")).split(),
                status=st.strip())


# ------------------------------------------------------------------ histórico
def history_load():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def history_save(items):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(items[-300:], f, ensure_ascii=False)
    except OSError:
        pass


def history_add(source, steps):
    items = history_load()
    ok = sum(1 for s in steps if s.get("ok"))
    result = "ok" if ok == len(steps) else ("failed" if ok == 0 else "partial")
    if any(s.get("message") == "cancelled" for s in steps) and ok == 0:
        result = "cancelled"
    rec = dict(id=int(time.time() * 1000), at=int(time.time()), source=source, result=result,
               undone=False, steps=[dict(unit=s["unit"], scope=s.get("scope", "system"),
                                         action=s["action"], ok=bool(s.get("ok")),
                                         message=s.get("message", "")) for s in steps])
    items.append(rec)
    history_save(items)
    return rec


OPPOSITE = {"start": "stop", "stop": "start", "enable": "disable", "disable": "enable",
            "enable-now": "disable-now", "disable-now": "enable-now"}


def undo_steps(rec):
    return [dict(unit=s["unit"], scope=s["scope"], action=OPPOSITE[s["action"]])
            for s in rec["steps"] if s.get("ok") and s["action"] in OPPOSITE]


def can_undo(rec):
    return (not rec.get("undone")) and rec.get("result") in ("ok", "partial") and bool(undo_steps(rec))


def history_mark_undone(rec_id):
    items = history_load()
    for r in items:
        if r.get("id") == rec_id:
            r["undone"] = True
    history_save(items)


# ------------------------------------------------------------------ ações
def apply_steps(steps, source="services", record=True):
    """Executa passos [{unit, scope, action}]. Sistema -> helper (1 palavra-passe); utilizador -> local.
    Devolve lista de resultados [{unit, scope, action, ok, message}]."""
    import core
    results = [None] * len(steps)
    sys_idx = [i for i, s in enumerate(steps) if s.get("scope", "system") == "system"
               and s["action"] != "remove-autostart"]
    if sys_idx:
        payload = json.dumps([dict(unit=steps[i]["unit"], action=steps[i]["action"]) for i in sys_idx])
        rc, outp = core.run_helper("svc-batch", payload, timeout=1800)
        got = {}
        for line in outp.splitlines():
            if line.startswith("@@RES "):
                try:
                    r = json.loads(line[6:])
                    got[(r["unit"], r["action"])] = r
                except (ValueError, KeyError):
                    pass
        for i in sys_idx:
            s = steps[i]
            r = got.get((s["unit"], s["action"]))
            if r is None:
                msg = "cancelled" if rc in (126, 127) or not outp.strip() else outp.strip().splitlines()[-1]
                r = dict(ok=False, message=msg)
            results[i] = dict(s, scope="system", ok=bool(r.get("ok")), message=r.get("message", ""))
    for i, s in enumerate(steps):
        if results[i] is not None:
            continue
        results[i] = dict(s, scope=s.get("scope", "system"), **_local_step(s))
    if record and results:
        history_add(source, results)
    return results


def _local_step(s):
    act, unit = s["action"], s["unit"]
    if act == "remove-autostart":
        path = os.path.join(os.path.expanduser("~/.config/autostart"), unit)
        try:
            os.remove(path)
            return dict(ok=True, message="")
        except OSError as e:
            return dict(ok=False, message=e.strerror or str(e))
    if not valid_unit(unit):
        return dict(ok=False, message="invalid")
    cmds = {"start": ["start"], "stop": ["stop"], "restart": ["restart"], "enable": ["enable"],
            "disable": ["disable"], "enable-now": ["enable", "--now"], "disable-now": ["disable", "--now"]}
    if act not in cmds:
        return dict(ok=False, message="invalid")
    rc, o, e = sctl("user", *(cmds[act] + [unit]))
    return dict(ok=rc == 0, message=(e or o).strip().splitlines()[-1] if rc != 0 and (e or o).strip() else "")


def grant_journal_access():
    import core
    rc, outp = core.run_helper("svc-batch", json.dumps([dict(unit="-", action="add-journal-group")]))
    for line in outp.splitlines():
        if line.startswith("@@RES "):
            try:
                r = json.loads(line[6:])
                return bool(r.get("ok")), r.get("message", "")
            except ValueError:
                pass
    return False, outp.strip().splitlines()[-1] if outp.strip() else ""


# ------------------------------------------------------------------ sistema
def os_release():
    d = {}
    for line in C.read("/etc/os-release").splitlines():
        k, _s, v = line.partition("=")
        d[k] = v.strip().strip('"')
    return d


_cpu_prev = None


def cpu_usage():
    global _cpu_prev
    def snap():
        v = [int(x) for x in C.read("/proc/stat").splitlines()[0].split()[1:9]]
        return sum(v), v[3] + v[4]
    t0, i0 = snap()
    if _cpu_prev is None:
        time.sleep(0.25)
        t1, i1 = snap()
    else:
        t0, i0 = _cpu_prev
        t1, i1 = snap()
    _cpu_prev = (t1, i1)
    dt = t1 - t0
    return 0.0 if dt <= 0 else max(0.0, min(100.0, 100.0 * (dt - (i1 - i0)) / dt))


def system_info():
    osr = os_release()
    mi = C.meminfo()
    cpu = ""
    for line in C.read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    try:
        up = float(C.read("/proc/uptime").split()[0])
    except (ValueError, IndexError):
        up = 0
    sess = os.environ.get("XDG_CURRENT_DESKTOP", "")
    proto = os.environ.get("XDG_SESSION_TYPE", "")
    kb = 1024
    return dict(distro=osr.get("PRETTY_NAME", osr.get("NAME", "Linux")), kernel=os.uname().release,
                session=" · ".join(x for x in (sess, proto.capitalize() if proto else "") if x),
                uptime=up, cpu=cpu, threads=os.cpu_count() or 1, cpu_use=cpu_usage(),
                mem_total=mi.get("MemTotal", 0) * kb, mem_avail=mi.get("MemAvailable", 0) * kb,
                swap_total=mi.get("SwapTotal", 0) * kb, swap_free=mi.get("SwapFree", 0) * kb)


def parse_startup(text):
    """'Startup finished in 3.1s (firmware) + 2s (loader) + ... = 20s' -> dict ms."""
    m = re.search(r"Startup finished in (.*)", text or "")
    if not m:
        return None
    body = m.group(1)
    total = None
    if "=" in body:
        body, tot = body.rsplit("=", 1)
        total = span_secs(tot)
    parts = {}
    for chunk in body.split("+"):
        mm = re.match(r"\s*(.*?)\s*\((\w+)\)", chunk)
        if mm:
            secs = span_secs(mm.group(1))
            if secs is not None:
                parts[mm.group(2)] = int(secs * 1000)
    if total is None:
        total = sum(parts.values()) / 1000.0
    return dict(total=int(total * 1000), parts=parts)


def boot_blame():
    rc, o, _e = run(["systemd-analyze", "blame", "--no-pager"], 30)
    res = []
    if rc != 0:
        return res
    for line in o.splitlines():
        m = re.match(r"\s*(.*?)\s+(\S+\.(?:service|mount|target|socket|device|timer|path|swap|scope))\s*$", line)
        if m:
            secs = span_secs(m.group(1))
            if secs is not None:
                res.append(dict(name=m.group(2), ms=int(secs * 1000)))
    res.sort(key=lambda x: -x["ms"])
    return res


def boot_chain():
    rc, o, _e = run(["systemd-analyze", "critical-chain", "--no-pager"], 30)
    chain = []
    if rc != 0:
        return chain
    for line in o.splitlines():
        if "@" not in line:
            continue
        m = re.search(r"([A-Za-z0-9@._:\\-]+\.(?:service|target|mount|socket|device|timer|path|swap|slice))\s+@([\d.a-z ]+?)(?:\s+\+([\d.a-z ]+))?\s*$", line)
        if m:
            at = span_secs(m.group(2))
            took = span_secs(m.group(3)) if m.group(3) else None
            chain.append(dict(name=m.group(1), at=int((at or 0) * 1000), took=int(took * 1000) if took else None))
    return chain


def boot_analysis():
    rc, o, _e = run(["systemd-analyze", "time", "--no-pager"], 30)
    st = parse_startup(o) if rc == 0 else None
    return dict(boot=st, slowest=boot_blame()[:10], chain=boot_chain())


def journal_access():
    """Dict(can_read, in_group_pending)."""
    if os.geteuid() == 0:
        return dict(can_read=True, pending=False)
    try:
        names = [g.gr_name for g in __import__("grp").getgrall() if os.environ.get("USER", "") in g.gr_mem]
    except (OSError, KeyError):
        names = []
    try:
        import grp
        cur = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    except (KeyError, ImportError):
        cur = set()
    can = bool(cur & {"adm", "systemd-journal", "root"})
    pending = (not can) and bool(set(names) & {"adm", "systemd-journal"})
    return dict(can_read=can, pending=pending)


def boot_history(limit=8):
    acc = journal_access()
    out = []
    if not acc["can_read"]:
        return dict(boots=out, access=acc)
    rc, o, _e = run(["journalctl", "--list-boots", "--no-pager"], 20)
    ids = []
    for line in o.splitlines():
        m = re.match(r"\s*(-?\d+)\s", line)
        if m:
            ids.append(int(m.group(1)))
    for bid in ids[-limit:]:
        rc, o, _e = run(["journalctl", "-b", str(bid), "-o", "short-unix", "--no-pager", "-g",
                         "Startup finished in", "-n", "1"], 20)
        st = parse_startup(o) if rc == 0 else None
        if st:
            m = re.match(r"\s*([\d.]+)", o)
            out.append(dict(id=bid, at=int(float(m.group(1))) if m else 0, total=st["total"]))
    out.sort(key=lambda b: b["at"], reverse=True)
    return dict(boots=out, access=acc)


def list_timers():
    rc, txt, _e = sctl("system", "show", "--type=timer", "--all", "-p",
                       "Id,ActiveState,Unit,NextElapseUSecRealtime,LastTriggerUSec,TimersMonotonic,TimersCalendar", timeout=30)
    res = []
    if rc != 0:
        return res
    for b in parse_show(txt):
        name = b.get("Id", "")
        if not name.endswith(".timer"):
            continue
        period = None
        mono = b.get("TimersMonotonic", "")
        m = re.search(r"OnUnitActiveUSec=([^;}]+)", mono) or re.search(r"OnUnitInactiveUSec=([^;}]+)", mono)
        if m:
            period = span_secs(m.group(1))
        cal = b.get("TimersCalendar", "")
        mc = re.search(r"OnCalendar=([^;}]+)", cal)
        if period is None and mc:
            spec = mc.group(1).strip()
            mm = re.search(r"\*:\d+/(\d+)", spec)
            if mm:
                period = int(mm.group(1)) * 60
            elif spec in ("minutely",):
                period = 60
            elif spec.startswith("hourly") or re.match(r"\*-\*-\* \*:", spec):
                period = 3600
            elif spec.startswith("daily") or re.match(r"\*-\*-\* \d", spec):
                period = 86400
            elif spec.startswith("weekly"):
                period = 604800
        res.append(dict(name=name, unit=b.get("Unit", ""), active=b.get("ActiveState", ""),
                        period=period))
    return res


def frequent_timers():
    return sorted([t for t in list_timers() if t["period"] is not None and t["period"] <= FREQUENT_SECS
                   and t["active"] == "active"], key=lambda t: t["period"])


# ------------------------------------------------------------------ resumo
def overview():
    svcs = list_services()
    sysv = [s for s in svcs if s["scope"] == "system"]
    failed = [s for s in svcs if s["active"] == "failed"]
    return dict(
        active=sum(1 for s in sysv if s["active"] == "active"),
        inactive=sum(1 for s in sysv if s["active"] not in ("active", "failed")),
        failed=sum(1 for s in svcs if s["active"] == "failed"),
        enabled=sum(1 for s in sysv if s["boot"] in ("enabled", "enabled-runtime")),
        failed_units=failed, services=svcs)


# ------------------------------------------------------------------ registos
PRIORITY = {"emerg": 0, "error": 3, "warn": 4, "info": 6, "debug": 7}


def query_logs(unit=None, scope="system", priority=3, range_="day", text=None, limit=800):
    cmd = ["journalctl", "--no-pager", "-o", "json", "-n", str(limit), "-p", str(priority)]
    if scope == "user":
        cmd.append("--user")
    if unit:
        cmd += ["-u" if scope == "system" else "--user-unit", unit]
    if range_ == "boot":
        cmd += ["-b"]
    elif range_ == "week":
        cmd += ["--since", "7 days ago"]
    else:
        cmd += ["--since", "24 hours ago"]
    if text:
        cmd += ["-g", re.escape(text), "--case-sensitive=false"]
    rc, o, e = run(cmd, 40)
    rows = []
    for line in o.splitlines():
        try:
            j = json.loads(line)
        except ValueError:
            continue
        msg = j.get("MESSAGE", "")
        if isinstance(msg, list):
            msg = bytes(msg).decode("utf-8", "replace")
        rows.append(dict(ts=int(j.get("__REALTIME_TIMESTAMP", "0")) // 1000000,
                         priority=to_int(j.get("PRIORITY"), 6),
                         source=j.get("SYSLOG_IDENTIFIER") or j.get("_COMM") or "",
                         unit=j.get("_SYSTEMD_UNIT") or j.get("USER_UNIT") or "",
                         boot=j.get("_BOOT_ID", ""), message=str(msg)))
    return rows, rc == 0


# ------------------------------------------------------------------ diagnóstico
def _unit_package(frag):
    if not frag or not os.path.exists(frag):
        return ""
    rc, o, _e = run(["dpkg", "-S", frag])
    return o.split(":")[0].strip() if rc == 0 and ":" in o else ""


def _package_damage(pkg):
    """(n_ficheiros, exemplo) de ficheiros em falta/alterados (ignora ficheiros de configuração)."""
    rc, o, _e = run(["dpkg", "--verify", pkg], 60)
    bad = []
    for line in o.splitlines():
        if re.match(r"^\S+\s+c\s+/", line):
            continue  # ficheiro de configuração: alterações são normais
        m = re.match(r"^(missing|\S{9})\s+(/\S.*)$", line.strip()) or re.match(r"^(missing)\s+(/\S.*)$", line)
        if not m:
            continue
        flags, path = m.group(1), m.group(2).strip()
        if flags == "missing" or flags[2] == "5":
            bad.append(path)
    return len(bad), (bad[0] if bad else "")


def _pkg_installable(pkg):
    rc, o, _e = run(["apt-cache", "policy", pkg], 20)
    cand = re.search(r"Candidate:\s*(\S+)", o)
    inst = re.search(r"Installed:\s*(\S+)", o)
    return bool(cand and cand.group(1) != "(none)" and (not inst or inst.group(1) == cand.group(1)))


def _exec_path(unit, scope):
    rc, o, _e = sctl(scope, "show", unit, "-p", "ExecStart")
    m = re.search(r"path=(\S+)", o)
    return m.group(1).rstrip(";") if m else ""


def _broken_links():
    bad = []
    base = "/etc/systemd/system"
    for root, dirs, files in os.walk(base):
        for n in dirs + files:
            p = os.path.join(root, n)
            if os.path.islink(p) and not os.path.exists(p):
                bad.append(p)
    return bad


def diagnose(range_="day"):
    items = []
    # 1) unidades falhadas (sistema e utilizador)
    for scope in ("system", "user"):
        rc, o, _e = sctl(scope, "--failed", "--plain", "--no-legend", "--type=service")
        for line in o.splitlines():
            parts = line.replace("●", "").split()
            if not parts or not parts[0].endswith(".service"):
                continue
            unit = parts[0]
            rc, so, _e = sctl(scope, "show", unit, "-p",
                              "ActiveState,Result,ExecMainStatus,NRestarts,FragmentPath,LoadState,RequiredBy")
            b = parse_show(so)[0] if so.strip() else {}
            reasons, fixes = [], []
            reasons.append(("unit_state", dict(state=b.get("ActiveState", "failed"), result=b.get("Result", ""),
                                               status=b.get("ExecMainStatus", ""))))
            pkg = _unit_package(b.get("FragmentPath", "")) if scope == "system" else ""
            if pkg:
                reasons.append(("owner", dict(package=pkg)))
            exe = _exec_path(unit, scope)
            exec_missing = bool(exe and exe.startswith("/") and not os.path.exists(exe))
            if exec_missing:
                reasons.append(("exec_missing", dict(path=exe)))
            nr = to_int(b.get("NRestarts"), 0)
            if nr:
                reasons.append(("restarts", dict(count=nr)))
            kind = "failing"
            if pkg and (exec_missing or True):
                n, ex = _package_damage(pkg)
                if n:
                    if _pkg_installable(pkg):
                        reasons.append(("package_damaged", dict(package=pkg, count=n, example=ex)))
                        fixes.append(dict(fix="reinstall", target=pkg,
                                          steps=[dict(unit=pkg, scope="system", action="package-reinstall")]))
                        kind = "repairable"
                    else:
                        reasons.append(("package_damaged_unavailable", dict(package=pkg, count=n, example=ex)))
            if not fixes and not exec_missing and b.get("LoadState") == "loaded":
                fixes.append(dict(fix="restart", target=unit, steps=[dict(unit=unit, scope=scope, action="restart")]))
                kind = "repairable" if kind == "repairable" else "failing"
            req = b.get("RequiredBy", "").split()
            if req:
                reasons.append(("required_by", dict(units=", ".join(req[:4]))))
            elif not (scope == "system" and is_protected(unit)):
                fixes.append(dict(fix="disable", target=unit, steps=[dict(unit=unit, scope=scope, action="disable")]))
            if scope == "system" and is_protected(unit):
                fixes = [f for f in fixes if f["fix"] != "disable"]
            items.append(dict(id=f"unit:{scope}:{unit}", subject="unit", name=unit, scope=scope, kind=kind,
                              count=1, this_boot=True, first=0, last=0, reasons=reasons, fixes=fixes, samples=[]))
    # 2) erros do diário agrupados por origem
    rows, ok = query_logs(None, "system", 3, range_, None, 1500)
    groups = {}
    for r in rows:
        key = r["unit"] or r["source"] or "?"
        g = groups.setdefault(key, dict(count=0, first=r["ts"], last=r["ts"], boots=set(), samples=[]))
        g["count"] += 1
        g["first"], g["last"] = min(g["first"], r["ts"]), max(g["last"], r["ts"])
        g["boots"].add(r["boot"])
        if len(g["samples"]) < 3 and r["message"] not in g["samples"]:
            g["samples"].append(r["message"])
    cur_boot = ""
    rc, o, _e = run(["journalctl", "-b", "-n", "1", "-o", "json", "--no-pager"], 10)
    try:
        cur_boot = json.loads(o.splitlines()[0]).get("_BOOT_ID", "") if o.strip() else ""
    except (ValueError, IndexError):
        pass
    quiet = 0
    by_name = {i["name"]: i for i in items}
    for key, g in groups.items():
        it = by_name.get(key) or by_name.get(key + ".service")
        if it:
            it.update(count=max(it["count"], g["count"]), first=g["first"], last=g["last"],
                      this_boot=(cur_boot in g["boots"]) if cur_boot else True, samples=g["samples"])
            if len(g["boots"]) > 1:
                it["reasons"].append(("repeats", dict(boots=len(g["boots"]))))
        else:
            quiet += g["count"]
    # 3) sistema: pacotes, dependências, ligações
    rc, o, _e = run(["dpkg", "--audit"], 30)
    if rc == 0 and o.strip():
        pk = ", ".join(re.findall(r"^\s*(\S+)\s", o, re.M)[:5])
        items.append(dict(id="system:dpkg", subject="system", name="dpkg", scope="system", kind="repairable",
                          count=1, this_boot=True, first=0, last=0, samples=[],
                          reasons=[("dpkg_audit", dict(packages=pk))],
                          fixes=[dict(fix="configure", target="dpkg",
                                      steps=[dict(unit="dpkg", scope="system", action="dpkg-configure")])]))
    if shutil.which("apt-get"):
        rc, o, e = run(["apt-get", "check"], 40)
        if rc != 0:
            detail = ((e or o).strip().splitlines() or [""])[-1][:160]
            items.append(dict(id="system:apt", subject="system", name="apt", scope="system", kind="repairable",
                              count=1, this_boot=True, first=0, last=0, samples=[],
                              reasons=[("apt_broken", dict(detail=detail))],
                              fixes=[dict(fix="fix-broken", target="apt",
                                          steps=[dict(unit="apt", scope="system", action="apt-fix-broken")])]))
    bl = _broken_links()
    if bl:
        items.append(dict(id="system:links", subject="system", name="links", scope="system", kind="repairable",
                          count=len(bl), this_boot=True, first=0, last=0, samples=[],
                          reasons=[("broken_links", dict(count=len(bl), example=bl[0]))],
                          fixes=[dict(fix="remove-links", target=str(len(bl)),
                                      steps=[dict(unit=p, scope="system", action="remove-link") for p in bl])]))
    dm = "/etc/systemd/system/display-manager.service"
    if not os.path.lexists(dm) and os.path.exists("/run/systemd/system"):
        cands = [u for u in ("gdm.service", "gdm3.service", "sddm.service", "lightdm.service", "lxdm.service")
                 if os.path.exists("/usr/lib/systemd/system/" + u) or os.path.exists("/lib/systemd/system/" + u)]
        rc, tgt, _e = run(["systemctl", "get-default"])
        if cands and "graphical" in tgt:
            if len(cands) == 1:
                items.append(dict(id="system:display-manager", subject="system", name="display-manager",
                                  scope="system", kind="repairable", count=1, this_boot=True, first=0, last=0,
                                  samples=[], reasons=[("dm_link_missing", dict(unit=cands[0]))],
                                  fixes=[dict(fix="enable", target=cands[0],
                                              steps=[dict(unit=cands[0], scope="system", action="enable")])]))
            else:
                items.append(dict(id="system:display-manager", subject="system", name="display-manager",
                                  scope="system", kind="failing", count=1, this_boot=True, first=0, last=0,
                                  samples=[], reasons=[("dm_link_ambiguous", dict(units=", ".join(cands)))], fixes=[]))
    # 4) entradas de arranque automático órfãs
    for f in sorted(glob.glob(os.path.expanduser("~/.config/autostart/*.desktop"))):
        ex = ""
        for line in C.read(f).splitlines():
            if line.startswith("Exec="):
                ex = line[5:].strip()
                break
        toks = ex.split()
        if not toks:
            continue
        base = os.path.basename(f)
        if toks[0] == "flatpak" and "run" in toks:
            app = next((t for t in toks[toks.index("run") + 1:] if not t.startswith("-") and "=" not in t), "")
            rc, _o, _e = run(["flatpak", "info", app], 10) if app and shutil.which("flatpak") else (1, "", "")
            if app and shutil.which("flatpak") and rc != 0:
                items.append(dict(id="autostart:" + base, subject="unit", name=base, scope="user", kind="repairable",
                                  count=1, this_boot=True, first=0, last=0, samples=[],
                                  reasons=[("autostart_flatpak_missing", dict(file=base, app=app))],
                                  fixes=[dict(fix="remove-autostart", target=base,
                                              steps=[dict(unit=base, scope="user", action="remove-autostart")])]))
            continue
        prog = toks[0]
        if (prog.startswith("/") and not os.path.exists(prog)) or (not prog.startswith("/") and not shutil.which(prog)
                                                                    and prog != "env"):
            items.append(dict(id="autostart:" + base, subject="unit", name=base, scope="user", kind="repairable",
                              count=1, this_boot=True, first=0, last=0, samples=[],
                              reasons=[("autostart_program_missing", dict(file=base, program=prog))],
                              fixes=[dict(fix="remove-autostart", target=base,
                                          steps=[dict(unit=base, scope="user", action="remove-autostart")])]))
    items.sort(key=lambda i: (i["kind"] != "repairable", -i["count"]))
    return dict(items=items, quiet=quiet, ok=ok)


# ------------------------------------------------------------------ otimização
def _exists(*paths):
    return any(os.path.exists(p) for p in paths)


def _virt():
    rc, o, _e = run(["systemd-detect-virt"], 5)
    v = o.strip()
    return "" if (not v or v == "none") else v


def _vendor():
    for line in C.read("/proc/cpuinfo").splitlines():
        if line.startswith("vendor_id"):
            return line.split(":", 1)[1].strip()
    return ""


def _root_ssd():
    try:
        rc, o, _e = run(["findmnt", "-no", "SOURCE", "/"], 5)
        dev = o.strip().split("[")[0]
        rc, o, _e = run(["lsblk", "-no", "PKNAME,ROTA,TYPE", dev], 5)
        for line in o.splitlines():
            p = line.split()
            if len(p) >= 2 and p[1] == "0":
                return p[0] if p[0] != "0" else os.path.basename(dev)
        base = os.path.basename(dev)
        if base.startswith("nvme"):
            return base
    except (OSError, IndexError):
        pass
    return ""


OPT_DEFS = (
    # id, categoria, risco, unidades
    ("printing", "hardware", "safe", ("cups.service", "cups.socket", "cups.path", "cups-browsed.service")),
    ("bluetooth", "hardware", "safe", ("bluetooth.service",)),
    ("wifi", "hardware", "review", ("wpa_supplicant.service",)),
    ("modem", "hardware", "safe", ("ModemManager.service",)),
    ("thunderbolt", "hardware", "safe", ("bolt.service",)),
    ("hybrid_gpu", "hardware", "safe", ("switcheroo-control.service",)),
    ("battery", "hardware", "safe", ("tlp.service", "laptop-mode.service")),
    ("thermald", "hardware", "safe", ("thermald.service",)),
    ("vm_tools_physical", "unused", "safe", ("qemu-guest-agent.service", "open-vm-tools.service", "vmtoolsd.service",
                                              "virtualbox-guest-utils.service", "vboxservice.service", "spice-vdagentd.service")),
    ("vm_tools_other", "unused", "safe", ("open-vm-tools.service", "vmtoolsd.service", "virtualbox-guest-utils.service",
                                           "vboxservice.service")),
    ("smart_in_vm", "unused", "safe", ("smartd.service", "smartmontools.service")),
    ("lvm", "unused", "review", ("lvm2-monitor.service",)),
    ("mdraid", "unused", "safe", ("mdmonitor.service",)),
    ("nfs", "unused", "safe", ("rpcbind.service", "rpcbind.socket", "nfs-blkmap.service")),
    ("snap", "unused", "review", ("snapd.service", "snapd.socket", "snapd.seeded.service")),
    ("wait_online", "boot", "review", ("NetworkManager-wait-online.service", "systemd-networkd-wait-online.service")),
)


def _unit_state(unit):
    rc, o, _e = sctl("system", "show", unit, "-p", "LoadState,ActiveState,UnitFileState,MemoryCurrent")
    b = parse_show(o)[0] if o.strip() else {}
    if b.get("LoadState") in (None, "not-found", "masked"):
        return None
    mem = to_int(b.get("MemoryCurrent"), 0) or 0
    return dict(unit=unit, active=b.get("ActiveState") == "active",
                enabled=b.get("UnitFileState", "") in ("enabled", "enabled-runtime"),
                ram=0 if mem >= 2 ** 63 else mem)


def _applies(fid):
    virt = _virt()
    if fid == "printing":
        pc = C.read("/etc/cups/printers.conf").strip() if os.access("/etc/cups/printers.conf", os.R_OK) else ""
        rc, o, _e = run(["lpstat", "-p"], 5) if shutil.which("lpstat") else (1, "", "")
        return (not pc) and not o.strip() and not glob.glob("/dev/usb/lp*"), {}
    if fid == "bluetooth":
        return not glob.glob("/sys/class/bluetooth/*"), {}
    if fid == "wifi":
        return not glob.glob("/sys/class/net/*/wireless") and not glob.glob("/sys/class/net/wl*"), {}
    if fid == "modem":
        return not glob.glob("/dev/cdc-wdm*") and not glob.glob("/sys/class/net/ww*"), {}
    if fid == "thunderbolt":
        return not glob.glob("/sys/bus/thunderbolt/devices/*"), {}
    if fid == "hybrid_gpu":
        return len([c for c in glob.glob("/sys/class/drm/card[0-9]*") if "-" not in os.path.basename(c)]) < 2, {}
    if fid == "battery":
        return not glob.glob("/sys/class/power_supply/BAT*"), {}
    if fid == "thermald":
        v = _vendor()
        return bool(v) and v != "GenuineIntel", dict(vendor=v)
    if fid == "vm_tools_physical":
        return virt == "", {}
    if fid == "vm_tools_other":
        return virt != "", dict(platform=virt)
    if fid == "smart_in_vm":
        return virt != "", {}
    if fid == "lvm":
        dm = [p for p in glob.glob("/sys/block/dm-*/dm/uuid") if C.read(p).startswith("LVM-")]
        return not dm, {}
    if fid == "mdraid":
        return not re.search(r"^md\d+", C.read("/proc/mdstat"), re.M), {}
    if fid == "nfs":
        nfs_mounts = [l for l in C.read("/proc/mounts").splitlines() if " nfs" in l]
        exports = [l for l in C.read("/etc/exports").splitlines() if l.strip() and not l.startswith("#")]
        return not nfs_mounts and not exports, {}
    if fid == "snap":
        return not glob.glob("/var/lib/snapd/snaps/*.snap"), {}
    return True, {}


def scan_optimization():
    blame = {b["name"]: b["ms"] for b in boot_blame()}
    findings = []
    for fid, cat, risk, units in OPT_DEFS:
        if fid == "vm_tools_other":
            applies, params = _applies(fid)
            if applies and params["platform"] in ("kvm", "qemu"):
                units = ("open-vm-tools.service", "vmtoolsd.service", "virtualbox-guest-utils.service", "vboxservice.service")
            elif applies and params["platform"] == "oracle":
                units = ("open-vm-tools.service", "vmtoolsd.service", "qemu-guest-agent.service")
            elif applies and params["platform"] == "vmware":
                units = ("qemu-guest-agent.service", "virtualbox-guest-utils.service", "vboxservice.service")
        else:
            applies, params = _applies(fid)
        if not applies:
            continue
        states = [s for s in (_unit_state(u) for u in units) if s and (s["active"] or s["enabled"])]
        if fid == "wait_online":
            states = [s for s in states if s["enabled"]]
            ms = max([blame.get(s["unit"], 0) for s in states] or [0])
            if not states or ms < 2000:
                continue
            params = dict(seconds=round(ms / 1000.0, 1))
        if not states:
            continue
        findings.append(dict(id=fid, category=cat, risk=risk, params=params, units=[s["unit"] for s in states],
                             action="disable-now", ram=sum(s["ram"] for s in states),
                             boot_ms=sum(blame.get(s["unit"], 0) for s in states)))
    dev = _root_ssd()
    if dev:
        s = _unit_state("fstrim.timer")
        if s and not s["enabled"]:
            findings.append(dict(id="fstrim", category="maintenance", risk="safe", params=dict(device=dev),
                                 units=["fstrim.timer"], action="enable-now", ram=0, boot_ms=0))
    # candidatos: serviços do sistema ativos, no arranque, sem dependentes e sem proteção
    svcs = [s for s in list_services() if s["scope"] == "system"]
    claimed = {u for f in findings for u in f["units"]}
    cands = []
    needed = cheap = idle = sysn = 0
    rc, o, _e = sctl("system", "show", "--type=service", "-p", "Id,WantedBy,RequiredBy,TriggeredBy", "--all", timeout=40)
    deps = {}
    for b in parse_show(o):
        d = [x for x in (b.get("WantedBy", "") + " " + b.get("RequiredBy", "")).split() if not x.endswith(".target")]
        deps[b.get("Id", "")] = (d, b.get("TriggeredBy", ""))
    for s in svcs:
        if s["protected"]:
            sysn += 1
            continue
        d, trig = deps.get(s["name"], ([], ""))
        if s["active"] != "active" and s["boot"] not in ("enabled", "enabled-runtime"):
            idle += 1
            continue
        if d:
            needed += 1
            continue
        if (s["memory"] or 0) < 8 * MIB:
            cheap += 1
            continue
        if s["name"] in claimed or s["boot"] not in ("enabled", "enabled-runtime"):
            continue
        cands.append(dict(name=s["name"], description=s["description"], ram=s["memory"] or 0,
                          boot_ms=blame.get(s["name"], 0), on_demand=bool(trig), scope="system",
                          package=""))
    cands.sort(key=lambda c: -c["ram"])
    cands = cands[:12]
    for c in cands:
        c["package"] = _unit_package(next((s["file"] for s in svcs if s["name"] == c["name"]), ""))
    return dict(findings=findings, candidates=cands,
                coverage=dict(total=len(svcs), system=sysn, needed=needed, cheap=cheap, idle=idle))
