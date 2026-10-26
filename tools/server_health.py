"""Проверка сервера бота: почему виснет и обрывает SSH — память и подкачка, процессор, диск, сеть, события ядра,
нагрузка от бота по дням.

Запуск на сервере одной строкой из любой папки (около минуты):
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/server_health.py | python3

Только читает: ничего не меняет и не перезапускает. Ключи и токены не печатаются. Копия вывода — в ~/margin_server_health.txt.
"""
import collections
import datetime
import json
import os
import re
import subprocess
import time

home = os.path.expanduser("~")
out = []
SECRET = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|(?<=://)[^/@\s]+(?=@)")   # токены бота, GitHub, логин в URL
SINCE_D = 6                                                 # сутки журнала для разбора


def p(line=""):
    line = SECRET.sub("***", str(line))
    out.append(line)
    print(line, flush=True)


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.stdout.strip() else r.stderr
    except Exception as e:
        return f"({cmd[0]}: {e.__class__.__name__})"


def section(name, fn):
    p()
    p(f"# {name}")
    try:
        fn()
    except Exception as e:
        p(f"  не получилось: {e!r}")


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def mb(x):
    return f"{x / 1048576:.0f} МБ" if x < 10 * 1073741824 else f"{x / 1073741824:.1f} ГБ"


def fmt(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%d.%m %H:%M")


def read_env(path):
    env = {}
    for line in read(path).splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


user_sc = subprocess.run(["systemctl", "--user", "cat", "margin-scanner"], capture_output=True).returncode == 0
SC = ["systemctl", "--user"] if user_sc else ["systemctl"]


def unit_props(unit, props):
    return dict(x.split("=", 1) for x in run(SC + ["show", unit, "-p", props], 15).splitlines() if "=" in x)


bot = next((c for c in (os.path.join(home, "projects", "margin_call-live", "bot"), "/opt/margin_call/bot")
            if os.path.exists(os.path.join(c, "trader.py"))), None)
env = read_env(os.path.join(home, ".config", "margin-call.env"))
for line in run(SC + ["show", "-p", "EnvironmentFiles", "margin-scanner"], 15).splitlines():
    path = line.split("=", 1)[-1].split(" (")[0].strip()
    if path:
        env.update(read_env(path))
state_path = env.get("STATE_FILE") or "state.json"
if not os.path.isabs(state_path):
    state_path = os.path.join(bot or ".", state_path)
state_dir = os.path.dirname(os.path.abspath(state_path))

up = float(read("/proc/uptime").split()[0] or 0) if read("/proc/uptime") else 0
osr = dict(re.findall(r'^(\w+)="?([^"\n]*)"?', read("/etc/os-release"), re.M))
p(f"SERVER-HEALTH v1 | сейчас {fmt(time.time())} UTC | работает без перезагрузки {up / 86400:.1f} сут | загрузка "
  f"{' '.join(read('/proc/loadavg').split()[:3])} | ядер {os.cpu_count()} | {os.uname().machine} | {osr.get('PRETTY_NAME', '?')}")
p(f"бот: {bot or 'папка не найдена'} | state: {state_path}")


def mem():
    mi = {k: int(v) * 1024 for k, v in re.findall(r"^(\w+):\s+(\d+) kB", read("/proc/meminfo"), re.M)}
    p(f"  память {mb(mi.get('MemTotal', 0))}, доступно {mb(mi.get('MemAvailable', 0))}; подкачка {mb(mi.get('SwapTotal', 0))}, "
      f"занято {mb(mi.get('SwapTotal', 0) - mi.get('SwapFree', 0))}; ждёт записи на диск {mb(mi.get('Dirty', 0))}")
    for res in ("cpu", "memory", "io"):
        t = read(f"/proc/pressure/{res}").strip().replace("\n", " | ")
        if t:
            p(f"  нехватка {res} (PSI, % времени): {t}")
    p("  vmstat раз в секунду (si/so — подкачка, wa — ожидание диска, st — отнято гипервизором):")
    for ln in run(["vmstat", "1", "5"], 20).splitlines():
        p("    " + ln)


def disk():
    seen = set()
    for ln in run(["df", "-h", "/", home, state_dir], 15).splitlines():
        if ln not in seen:
            seen.add(ln); p("  " + ln)
    ino = run(["df", "-i", "/"], 15).splitlines()
    p("  иноды /: " + (ino[-1] if ino else "?"))
    if os.path.isdir(state_dir):
        for name in sorted(os.listdir(state_dir)):
            fp = os.path.join(state_dir, name)
            size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(fp) for f in fs) if os.path.isdir(fp) \
                else os.path.getsize(fp)
            p(f"  {name}: {mb(size) if size >= 1048576 else f'{size / 1024:.0f} КБ'}, изменён {fmt(os.path.getmtime(fp))}")
    p("  журналы systemd: пользователь — " + run(["journalctl", "--user", "--disk-usage"], 30).strip()[-80:]
      + "; система — " + run(["journalctl", "--disk-usage"], 30).strip()[-80:])


def procs():
    p("  больше всего памяти:")
    for ln in run(["ps", "-eo", "pid,user,stat,pcpu,pmem,rss,etime,args", "--sort=-rss"], 15).splitlines()[:12]:
        p("    " + ln[:170])
    p("  больше всего процессора (с запуска процесса):")
    for ln in run(["ps", "-eo", "pid,user,stat,pcpu,pmem,rss,etime,args", "--sort=-pcpu"], 15).splitlines()[:8]:
        p("    " + ln[:170])
    allp = run(["ps", "-eo", "stat,nlwp,args"], 15).splitlines()[1:]
    p(f"  процессов {len(allp)}, потоков {sum(int(x.split()[1]) for x in allp if len(x.split()) > 1 and x.split()[1].isdigit())}, "
      f"зомби {sum(1 for x in allp if x.startswith('Z'))}; scanner.py запущен {sum(1 for x in allp if 'scanner.py' in x)} раз, "
      f"git — {sum(1 for x in allp if re.search(r' git( |$)', x))}")


def service():
    pr = unit_props("margin-scanner", "ActiveState,SubState,ActiveEnterTimestamp,NRestarts,MainPID,MemoryCurrent,MemoryPeak,"
                                      "CPUUsageNSec,TasksCurrent,IOReadBytes,IOWriteBytes")
    if not pr:
        p("  служба margin-scanner не найдена")
        return
    p("  " + "; ".join(f"{k}={v}" for k, v in pr.items()))
    keep = re.compile(r"^(ExecStart|Restart|RestartSec|Memory\w*|CPU\w*|Nice|IO\w*|TasksMax|Slice|OOM\w*)=")
    p("  настройки службы: " + "; ".join(ln.strip() for ln in run(SC + ["cat", "margin-scanner"], 15).splitlines() if keep.match(ln.strip())))
    pid = pr.get("MainPID", "0")
    if pid and pid != "0":
        st = dict(re.findall(r"^(\w+):\s+(.+)$", read(f"/proc/{pid}/status"), re.M))
        io = dict(re.findall(r"^(\w+): (\d+)$", read(f"/proc/{pid}/io"), re.M))
        started = os.path.getmtime(f"/proc/{pid}") if os.path.exists(f"/proc/{pid}") else time.time()
        hours = max((time.time() - started) / 3600, 0.01)
        try:
            fds = len(os.listdir(f"/proc/{pid}/fd"))
        except OSError:
            fds = "?"
        p(f"  процесс {pid}: память {st.get('VmRSS', '?')} (пик {st.get('VmHWM', '?')}), потоков {st.get('Threads', '?')}, "
          f"открытых файлов и соединений {fds}, nice {(read(f'/proc/{pid}/stat').split() or ['?'] * 19)[18]}")
        if io:
            p(f"  запись на диск {mb(int(io.get('write_bytes', 0)) / hours)}/ч, чтение {mb(int(io.get('read_bytes', 0)) / hours)}/ч; "
              f"по сети и файлам передано {mb(int(io.get('wchar', 0)) / hours)}/ч, принято {mb(int(io.get('rchar', 0)) / hours)}/ч "
              f"(за {hours:.1f} ч)")
    for unit, props in (("margin-autoupdate.timer", "ActiveState,LastTriggerUSec"),
                        ("margin-autoupdate.service", "Result,ExecMainStatus,ExecMainExitTimestamp")):
        p(f"  {unit}: " + "; ".join(f"{k}={v}" for k, v in unit_props(unit, props).items()))


DENIED = re.compile(r"not seeing messages|insufficient permissions|Operation not permitted|password is required|No journal files")


def journal(args, timeout=90):
    """Системный журнал: сначала от своего имени, при нехватке прав — через sudo без пароля (если настроен)."""
    r = run(["journalctl"] + args, timeout)
    if DENIED.search(r) or not r.strip():
        r2 = run(["sudo", "-n", "journalctl"] + args, timeout)
        if r2.strip() and not DENIED.search(r2):
            return r2, True
        return r, not DENIED.search(r)
    return r, True


def events():
    since = f"-{SINCE_D}d"
    pat = re.compile(r"out of memory|oom|killed process|hung_task|blocked for more than|I/O error|EXT4-fs error|link is down|"
                     r"link is up|carrier|soft lockup|segfault|thrott", re.I)
    k, ok = journal(["-k", "--since", since, "-o", "short-iso", "--no-pager", "-q"])
    if not ok:
        k = run(["dmesg", "-T"], 30)
        ok = not DENIED.search(k) and bool(k.strip())
    hits = [ln for ln in k.splitlines() if pat.search(ln)] if ok else []
    p(f"  ядро за {SINCE_D} сут (память, зависания, диск, сеть): " + (f"{len(hits)} строк" if ok else "нет доступа (нужен sudo)"))
    for ln in hits[-25:]:
        p("    " + ln[:220])
    for title, units, pt in (("systemd-oomd (убийца процессов при нехватке памяти)", ["systemd-oomd"], r"."),
                             ("сеть", ["NetworkManager", "systemd-networkd", "wpa_supplicant", "dhcpcd", "networking", "netplan"],
                              r"down|lost|disconnect|deactivat|carrier|lease|fail|timeout|unreachable"),
                             ("SSH", ["ssh", "sshd"], r"timeout|Timeout|disconnect|Disconnect|broken|reset|closed|Killed|killed")):
        args = ["--since", since, "-o", "short-iso", "--no-pager", "-q"]
        for u in units:
            args += ["-u", u]
        r, ok = journal(args)
        lines = [ln for ln in r.splitlines() if re.search(pt, ln) and not DENIED.search(ln)] if ok else []
        p(f"  {title}: " + (f"{len(lines)} строк" if ok else "нет доступа (нужен sudo)"))
        for ln in lines[-12:]:
            p("    " + ln[:220])
    r, ok = journal(["--since", since, "-u", "systemd-journald", "-o", "short-iso", "--no-pager", "-q"])
    sup = [ln for ln in r.splitlines() if "Suppressed" in ln] if ok else []
    n = sum(int(m.group(1)) for ln in sup for m in [re.search(r"Suppressed (\d+)", ln)] if m)
    p("  журнал systemd не успевал записывать (Suppressed): " + (f"{len(sup)} раз, отброшено строк {n}" if ok else "нет доступа (нужен sudo)"))
    for ln in [ln for ln in sup if "margin" in ln][-5:]:
        p("    " + ln[:220])
    boots, ok = journal(["--list-boots", "--no-pager", "-q"], 30)
    if ok:
        p("  последние загрузки системы: " + " | ".join(" ".join(b.split()[2:5]) for b in boots.splitlines()[-4:]))


LOG_KEYS = (("канал недоступен", r"канал недоступен"), ("сеть недоступна", r"Network is unreachable"),
            ("таймаут", r"timed out|TimeoutError"), ("DNS", r"DNS не ответил|name resolution"), ("API error", r"API error"),
            ("http_json fail", r"http_json fail"), ("telegram fail", r"telegram fail"), ("ошибка", r"ошибка"),
            ("запуск", r"Started margin-scanner"), ("убит", r"code=killed|status=9|SIGKILL|oom"))


def log_stats(lines):
    """Строки журнала службы (journalctl -o short-iso) → таблица по дням."""
    D = collections.defaultdict(collections.Counter)
    took = collections.defaultdict(list)
    codes = collections.Counter(); res = []
    for ln in lines:
        m = re.match(r"(\d{4}-\d\d-\d\d)T", ln)
        if not m:
            continue
        day = m.group(1)[5:]; d = D[day]
        d["строк"] += 1
        t = re.search(r"проход занял (\d+) с", ln)
        if t:
            took[day].append(int(t.group(1)))
        for key, rx in LOG_KEYS:
            if re.search(rx, ln):
                d[key] += 1
        c = re.search(r"API error \w+ (\S+) (-?\d+)", ln)
        if c:
            codes[f"{c.group(1)} {c.group(2)}"] += 1
        if "РЕСУРСЫ" in ln:
            res.append(ln)
    keys = ("строк",) + tuple(k for k, _ in LOG_KEYS)
    p("  день  | проходов > 48 с, медиана, максимум | " + " | ".join(keys))
    for day in sorted(D):
        tk = sorted(took.get(day, []))
        p(f"  {day} | {len(tk)}, {tk[len(tk) // 2] if tk else 0} с, {tk[-1] if tk else 0} с | "
          + " | ".join(str(D[day][k]) for k in keys))
    if codes:
        p("  ошибки Binance (путь и код): " + ", ".join(f"{k} ×{v}" for k, v in codes.most_common(8)))
    for ln in res[-6:]:
        p("  " + ln.split(": ", 1)[-1][:220])


def bot_log():
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=SINCE_D)).strftime("%Y-%m-%d %H:%M:%S")
    for cmd in (["journalctl", "--user", "-u", "margin-scanner"], ["journalctl", "--user-unit", "margin-scanner"],
                ["journalctl", "-u", "margin-scanner"]):
        test = run(cmd + ["--since", since, "-n", "3", "--no-pager", "-q"], 60)
        if test.strip() and not DENIED.search(test):
            proc = subprocess.Popen(cmd + ["--since", since, "--utc", "-o", "short-iso", "--no-pager", "-q"],
                                    stdout=subprocess.PIPE, text=True, errors="replace")
            log_stats(proc.stdout)
            proc.wait()
            return
    p("  журнал службы не найден")


def state_info():
    if not os.path.exists(state_path):
        p("  state.json не найден")
        return
    s = json.load(open(state_path))
    sizes = sorted(((len(json.dumps(v, ensure_ascii=False)), k) for k, v in s.items()), reverse=True)
    p(f"  state.json {os.path.getsize(state_path) / 1024:.0f} КБ; крупнее всего: "
      + ", ".join(f"{k} {n / 1024:.0f} КБ" for n, k in sizes[:6]))
    vj = [(k, v) for k, v in s.items() if k.startswith("virtual") and isinstance(v, dict) and "trades" in v]
    op = sum(1 for _, v in vj for t in v["trades"] if not t.get("closed"))
    p(f"  виртуальные журналы: {len(vj)}, открытых сделок {op}: "
      + ", ".join(f"{k} {sum(1 for t in v['trades'] if not t.get('closed'))}/{len(v['trades'])}" for k, v in vj))
    mp = os.path.join(state_dir, "margin_posts.json")
    if os.path.exists(mp):
        p(f"  margin_posts.json {os.path.getsize(mp) / 1024:.0f} КБ, постов {len(json.load(open(mp)))}")


def net():
    for ln in run(["ss", "-s"], 15).splitlines()[:4]:
        p("  " + ln)
    ct = read("/proc/sys/net/netfilter/nf_conntrack_count").strip()
    if ct:
        p(f"  conntrack {ct} из {read('/proc/sys/net/netfilter/nf_conntrack_max').strip()}")
    p("  интерфейсы: " + " | ".join(" ".join(x.split()[:2]) for x in run(["ip", "-br", "link"], 15).splitlines()))
    p("  маршрут по умолчанию: " + re.sub(r"via \S+", "via *", run(["ip", "route", "show", "default"], 15).strip()).replace("\n", " | ")
      + "; IPv6: " + (re.sub(r"via \S+", "via *", run(["ip", "-6", "route", "show", "default"], 15).strip()) or "нет"))
    wifi = run(["iw", "dev"], 15)
    if "Interface" in wifi:
        p("  Wi-Fi: " + " ".join(re.findall(r"Interface \S+|type \S+", wifi)))
    nm = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], 15).strip()
    if nm and "nmcli" not in nm:
        p("  NetworkManager: " + nm.replace("\n", " | "))
    t0 = time.time()
    r = run(["getent", "ahosts", "t.me"], 20)
    p(f"  DNS t.me за {time.time() - t0:.1f} с: " + " ".join(sorted(set(x.split()[0] for x in r.splitlines() if x.strip())))[:150])


section("ПАМЯТЬ И ПРОЦЕССОР", mem)
section("ДИСК", disk)
section("ПРОЦЕССЫ", procs)
section("СЛУЖБА БОТА", service)
section(f"СОБЫТИЯ СИСТЕМЫ ЗА {SINCE_D} СУТ", events)
section(f"ЖУРНАЛ БОТА ПО ДНЯМ (UTC) ЗА {SINCE_D} СУТ", bot_log)
section("СОСТОЯНИЕ БОТА", state_info)
section("СЕТЬ", net)
try:
    with open(os.path.join(home, "margin_server_health.txt"), "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"\nкопия: {os.path.join(home, 'margin_server_health.txt')}")
except OSError:
    pass
