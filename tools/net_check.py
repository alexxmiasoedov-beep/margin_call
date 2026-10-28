"""Проверка сети сервера: где теряются пакеты и кто занимает канал — когда виснут удалённый стол, SSH и запросы бота.
Трафик и потери за 20 с обычной работы (по интерфейсу, по программам, ваш удалённый стол xrdp), ping до шлюза и публичных
DNS, время ответа DNS, этапы HTTPS до Binance, Telegram, Upbit, Google и Cloudflare, MTU, очередь интерфейса.

Запуск на сервере одной строкой из любой папки (около полутора минут):
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/net_check.py | python3

Только читает и шлёт пробные запросы (ping, DNS, HTTPS) — ничего не меняет. Логины, имя сервера и IP-адреса не печатаются,
вывод можно целиком вставить в чат. Копия вывода — в ~/margin_net_check.txt.
"""
import datetime
import os
import pwd
import random
import re
import socket
import ssl
import struct
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

home = os.path.expanduser("~")
out = []
WINDOW = 20                                                 # секунд наблюдения за обычной работой сервера

# Маска как в server_health.py: логины людей и имя сервера — «***», домашние папки — «~», IP: локальные — первые две части,
# публичные — «x.x.x.x» (кроме известных DNS), IPv6 и MAC — «x:x»
try:
    _people = [u for u in pwd.getpwall() if 1000 <= u.pw_uid < 65534]
except OSError:
    _people = []
HOMES = sorted({u.pw_dir.rstrip("/") for u in _people if len(u.pw_dir.rstrip("/")) > 1}
               | ({home.rstrip("/")} if home.rstrip("/") not in ("", "/root") else set()), key=len, reverse=True)
_host = socket.gethostname()
_names = {u.pw_name for u in _people if len(u.pw_name) > 1} | {h for h in (_host, _host.split(".")[0]) if len(h) > 2 and h.lower()
                                                               not in ("localhost", "ubuntu", "debian", "server", "desktop", "linux")}
NAMES = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(sorted(map(re.escape, _names), key=len, reverse=True))
                   + r")(?![A-Za-z0-9_])") if _names else None
IP4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
HEXC = re.compile(r"[0-9A-Fa-f:]{2,}")
DNS_OK = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112", "77.88.8.8", "77.88.8.1",
          "208.67.222.222", "208.67.220.220"}


def _ip4(m):
    ip = m.group(0); a, b = (int(x) for x in ip.split(".")[:2])
    if ip in DNS_OK or a == 127 or ip == "0.0.0.0" or max(int(x) for x in ip.split(".")) > 255:
        return ip
    local = a == 10 or (a, b) in ((192, 168), (169, 254)) or (a == 172 and 16 <= b <= 31) or (a == 100 and 64 <= b <= 127)
    return f"{a}.{b}.x.x" if local else "x.x.x.x"


def _hexc(m):
    s = m.group(0)
    return "x:x" if s not in ("::", "::1") and ("::" in s or s.count(":") >= 3) else s


def mask(line):
    for h in HOMES:
        line = line.replace(h + "/", "~/").replace(h, "~")
    if NAMES:
        line = NAMES.sub("***", line)
    line = IP4.sub(_ip4, re.sub(r"::ffff:(?=\d)", "", line))
    return HEXC.sub(_hexc, line)


def p(line=""):
    line = mask(str(line))
    out.append(line)
    print(line, flush=True)


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.stdout.strip() else r.stderr
    except Exception as e:
        return f"({cmd[0]}: {e.__class__.__name__})"


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def _proc_name(cmd):
    """Как в самописце бота: chrome — одно имя на все процессы; python — по скрипту или модулю."""
    exe = os.path.basename(cmd[0].decode("utf-8", "replace"))
    if "chrome" in exe or "chromium" in exe:
        return "chrome"
    if exe.startswith("python"):
        args = [a.decode("utf-8", "replace") for a in cmd[1:] if a]
        if "-m" in args and args.index("-m") + 1 < len(args):
            return "python -m " + args[args.index("-m") + 1]
        script = next((a for a in args if not a.startswith("-")), "")
        return "python " + os.path.basename(script) if script else exe
    return exe


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


# ---------------------------------------------------------------- счётчики
_dflt = [ln.split() for ln in read("/proc/net/route").splitlines()[1:] if ln.split()[1:2] == ["00000000"]]   # маршрут по умолчанию
DEV = _dflt[0][0] if _dflt else next((ln.split(":")[0].strip() for ln in read("/proc/net/dev").splitlines()[2:]
                                      if ln.split(":")[0].strip() != "lo"), "eth0")
GW = socket.inet_ntoa(struct.pack("<I", int(_dflt[0][2], 16))) if _dflt and int(_dflt[0][2], 16) else None


def counters():
    """Счётчики всей машины: интерфейс DEV (байты, ошибки, отброшенные) и TCP (Tcp: из snmp, TcpExt: из netstat)."""
    c = {"t": time.time()}
    for ln in read("/proc/net/dev").splitlines()[2:]:
        name, _, v = ln.partition(":")
        v = v.split()
        if name.strip() == DEV and len(v) >= 12:
            c.update(rx=int(v[0]), rx_err=int(v[2]), rx_drop=int(v[3]), tx=int(v[8]), tx_err=int(v[10]), tx_drop=int(v[11]))
    for path, sect in (("/proc/net/snmp", "Tcp:"), ("/proc/net/netstat", "TcpExt:")):
        rows = [ln.split() for ln in read(path).splitlines() if ln.startswith(sect)]
        if len(rows) >= 2:
            c.update(zip(rows[0][1:], (int(x) for x in rows[1][1:])))
    q = run(["tc", "-s", "qdisc", "show", "dev", DEV], 10)
    m = re.search(r"dropped (\d+), overlimits (\d+)", q)              # первая строка Sent — корневая очередь
    if m:
        c.update(q_drop=int(m.group(1)), q_over=int(m.group(2)))
    b = re.search(r"backlog (\S+) (\d+)p", q)
    c["q_backlog"] = f"{b.group(1)}, {b.group(2)} пакетов" if b else "?"
    return c


def tcp_line(a, b):
    d = lambda k: max(0, b.get(k, 0) - a.get(k, 0))
    seg = d("OutSegs")
    return (f"отправлено сегментов {seg}, повторно {d('RetransSegs')} ({d('RetransSegs') / seg * 100 if seg else 0:.1f}% — "
            f"это потери пакетов), повторов SYN {d('TCPSynRetrans')}, тайм-аутов {d('TCPTimeouts')}, новых соединений "
            f"{d('ActiveOpens')}, не открылось {d('AttemptFails')}")


def ss_sample():
    """TCP-соединения сервера (кроме внутренних 127.x): (локальный, удалённый) → [pid, порт, получено, отправлено, rtt мс,
    повторов]. Процесс виден только у своих программ; чужие узнаём по порту (3389 — xrdp, 22 — ssh)."""
    socks, cur = {}, None
    for ln in run(["ss", "-tinpHn", "state", "established"], 20).splitlines():
        if not ln.strip():
            continue
        if not ln[0].isspace():
            ad = [x for x in ln.split() if re.search(r":\d+$", x)]           # локальный и удалённый адрес:порт
            cur = None
            if len(ad) >= 2 and not re.match(r"\[?(::ffff:)?127\.|\[::1\]", ad[1]):
                m = re.search(r"pid=(\d+)", ln)
                cur = socks[(ad[0], ad[1])] = [m.group(1) if m else None, ad[0].rsplit(":", 1)[-1], 0, 0, None, 0]
        elif cur is not None:
            for key, i in (("bytes_received", 2), ("bytes_acked", 3)):
                m = re.search(rf"\b{key}:(\d+)", ln)
                if m:
                    cur[i] = int(m.group(1))
            m = re.search(r"\brtt:([\d.]+)/", ln)
            cur[4] = float(m.group(1)) if m else cur[4]
            m = re.search(r"\bretrans:\d+/(\d+)", ln)
            cur[5] = int(m.group(1)) if m else cur[5]
    return socks


def who(pid, port):
    if pid:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().split(b"\0")
            if cmd[0]:
                return _proc_name(cmd)
        except OSError:
            pass
    return {"3389": "xrdp — ваш удалённый стол", "22": "ssh"}.get(port, "чужие процессы (система, другие пользователи)")


def traffic():
    a, sa = counters(), ss_sample()
    time.sleep(WINDOW)
    b, sb = counters(), ss_sample()
    dt = b["t"] - a["t"]
    d = lambda k: max(0, b.get(k, 0) - a.get(k, 0))
    p(f"  интерфейс {DEV}: приём {d('rx') * 8 / dt / 1e6:.2f} Мбит/с, отдача {d('tx') * 8 / dt / 1e6:.2f} Мбит/с; "
      f"за {dt:.0f} с ошибок {d('rx_err') + d('tx_err')}, отброшено {d('rx_drop') + d('tx_drop')}; с загрузки принято "
      f"{b.get('rx', 0) / 1e9:.1f} ГБ, отдано {b.get('tx', 0) / 1e9:.1f} ГБ, отброшено {b.get('rx_drop', 0) + b.get('tx_drop', 0)}")
    p(f"  TCP всего сервера за {dt:.0f} с: " + tcp_line(a, b))
    if "q_drop" in b:
        p(f"  очередь отправки интерфейса: отброшено за {dt:.0f} с {d('q_drop')}, переполнений {d('q_over')}, "
          f"сейчас в очереди {b['q_backlog']} (отбросы — канал сервера забит своей же отдачей)")
    g = {}
    for k, (pid, port, rx, tx, rtt, ret) in sb.items():
        o = sa.get(k)
        r = g.setdefault(who(pid, port), [0, 0, 0, [], 0])
        r[0] += rx - (o[2] if o else 0); r[1] += tx - (o[3] if o else 0); r[2] += 1; r[4] += ret - (o[5] if o else 0)
        if rtt is not None:
            r[3].append(rtt)
    p(f"  по программам (TCP за {dt:.0f} с; rtt — время до собеседника и обратно, повторы — потерянные пакеты):")
    for name, (rx, tx, n, rtts, ret) in sorted(g.items(), key=lambda x: -(x[1][0] + x[1][1]))[:12]:
        p(f"    {name}: приём {max(rx, 0) / dt / 1024:.1f} КБ/с, отдача {max(tx, 0) / dt / 1024:.1f} КБ/с, соединений {n}"
          + (f", rtt медиана {med(rtts):.0f} мс, макс {max(rtts):.0f}" if rtts else "") + f", повторов {max(ret, 0)}")
    if not g:
        p("    соединений не видно (нет программы ss)")


def ping(target, n=25, size=None):
    cmd = ["ping", "-n", "-c", str(n), "-i", "0.2", "-W", "2"] + (["-M", "do", "-s", str(size)] if size else []) + [target]
    r = run(cmd, n * 2 + 15)
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received", r)
    t = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", r)
    if not m:
        return None, r.strip().splitlines()[-1][:120] if r.strip() else "нет ответа"
    sent, got = int(m.group(1)), int(m.group(2))
    return got, (f"потеряно {(sent - got) / sent * 100:.0f}% ({sent - got} из {sent})"
                 + (f", задержка мин {float(t.group(1)):.0f} / средн {float(t.group(2)):.0f} / макс {float(t.group(3)):.0f} мс, "
                    f"разброс {float(t.group(4)):.0f}" if t else ""))


def dns_once(server, name="fapi.binance.com", timeout=2.0):
    """Один запрос A по UDP мимо кэшей системы. Время ответа в секундах или None — ответа нет за timeout."""
    q = (struct.pack(">HHHHHH", random.randrange(65536), 0x0100, 1, 0, 0, 0)
         + b"".join(bytes([len(x)]) + x.encode() for x in name.split(".")) + b"\0\0\1\0\1")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.sendto(q, (server, 53))
        while time.time() - t0 < timeout:
            if s.recv(4096)[:2] == q[:2]:
                return time.time() - t0
    except OSError:
        pass
    finally:
        s.close()
    return None


def dns(server, n=12):
    ts = []
    for _ in range(n):
        ts.append(dns_once(server))
        time.sleep(0.25)
    ok = [t for t in ts if t is not None]
    return (f"без ответа {n - len(ok)} из {n}" + (f", ответ медиана {med(ok) * 1000:.0f} мс, макс {max(ok) * 1000:.0f} мс" if ok else ""))


HOSTS = (("fapi.binance.com", "/fapi/v1/ping"), ("api.binance.com", "/api/v3/ping"), ("api.telegram.org", "/"),
         ("t.me", "/"), ("api.upbit.com", "/v1/ticker?markets=KRW-BTC"), ("www.google.com", "/generate_204"),
         ("one.one.one.one", "/cdn-cgi/trace"))
FIXED_IP = {"one.one.one.one": "1.1.1.1"}                   # Cloudflare — без поиска адреса: сеть без DNS


def https_once(host, path, timeout=10):
    """Один HTTPS-запрос по этапам: поиск адреса, TCP, TLS, первый байт ответа. ({этап: секунды}, сбой или None)."""
    t = {}; t0 = time.time(); s = None
    try:
        ip = FIXED_IP.get(host) or socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        t["адрес"] = time.time() - t0; t1 = time.time()
        s = socket.create_connection((ip, 443), timeout=timeout)
        t["TCP"] = time.time() - t1; t2 = time.time()
        s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
        t["TLS"] = time.time() - t2; t3 = time.time()
        s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: margin-call net_check\r\nConnection: close\r\n\r\n".encode())
        if not s.recv(64):
            raise ConnectionError("пустой ответ")
        t["ответ"] = time.time() - t3
        return t, None
    except Exception as e:
        return t, next(k for k in ("адрес", "TCP", "TLS", "ответ") if k not in t) + f" — {e.__class__.__name__}"
    finally:
        if s:
            s.close()


def https(host, path, n=4):
    rows = [https_once(host, path) for _ in range(n)]
    fails = [f for _, f in rows if f]
    ph = {k: [t[k] for t, _ in rows if k in t] for k in ("адрес", "TCP", "TLS", "ответ")}
    st = " / ".join(f"{k} {med(v) * 1000:.0f}" + (f" (макс {max(v) * 1000:.0f})" if max(v) > med(v) * 2 and max(v) > 0.3 else "")
                    for k, v in ph.items() if v)
    return ((st + " мс" if st else "ни один этап не прошёл")
            + (f"; сбоев {len(fails)} из {n}: " + ", ".join(sorted(set(fails))) if fails else f"; без сбоев ({n} из {n})"))


def main():
    virt = (run(["systemd-detect-virt"], 10).strip().splitlines() or ["?"])[0]
    p(f"NET-CHECK v1 | сейчас {datetime.datetime.now(datetime.timezone.utc):%d.%m %H:%M} UTC | интерфейс {DEV}, MTU "
      f"{read(f'/sys/class/net/{DEV}/mtu').strip() or '?'} | шлюз {'есть' if GW else 'не найден'} | "
      + ("свой компьютер" if virt == "none" else f"виртуалка: {virt}"))
    ns = [x for x in re.findall(r"^nameserver\s+(\S+)", read("/etc/resolv.conf"), re.M) if ":" not in x]
    p(f"DNS сервера (/etc/resolv.conf): {', '.join(ns) or 'нет'}")
    start = counters()
    p()
    p(f"# ТРАФИК И ПОТЕРИ ЗА {WINDOW} С ОБЫЧНОЙ РАБОТЫ (проверка ещё ничего не шлёт)")
    traffic()
    targets = ([("шлюз провайдера", GW)] if GW else []) + [("Cloudflare 1.1.1.1", "1.1.1.1"), ("Google 8.8.8.8", "8.8.8.8"),
                                                          ("Яндекс 77.88.8.8", "77.88.8.8")]
    servers = list(dict.fromkeys(ns + ["1.1.1.1", "8.8.8.8", "77.88.8.8"]))
    with ThreadPoolExecutor(24) as ex:
        f_ping = [(name, ex.submit(ping, ip)) for name, ip in targets]
        f_dns = [(s, ex.submit(dns, s)) for s in servers]
        f_https = [(h, ex.submit(https, h, path)) for h, path in HOSTS]
        f_mtu = [(size, ex.submit(ping, "1.1.1.1", 3, size)) for size in (1472, 1452, 1420, 1400, 1300)]
    p()
    p("# ПОТЕРИ ПАКЕТОВ И ЗАДЕРЖКА (ping, 25 пакетов)")
    for name, f in f_ping:
        p(f"  {name}: {f.result()[1]}")
    p()
    p("# DNS: 12 запросов адреса fapi.binance.com к каждому серверу, ответ ждём 2 с (норма — десятки мс, без потерь)")
    for s, f in f_dns:
        p(f"  {s}{' (из resolv.conf)' if s in ns else ''}: {f.result()}")
    p()
    p("# HTTPS по 4 раза: медиана этапов — поиск адреса / TCP / TLS / ответ")
    for h, f in f_https:
        p(f"  {h}: {f.result()}")
    p()
    p("# MTU: проходят ли до 1.1.1.1 пакеты без дробления (размер пакета в байтах)")
    p("  " + ", ".join(f"{size + 28} — " + ("да" if f.result()[0] else "нет" if f.result()[0] == 0 else "?") for size, f in f_mtu)
      + ("" if any(f.result()[0] is not None for _, f in f_mtu) else f" ({f_mtu[0][1].result()[1]})"))
    p()
    p("# TCP ЗА ВСЮ ПРОВЕРКУ (вместе с её запросами)")
    p("  " + tcp_line(start, counters()))
    try:
        with open(os.path.join(home, "margin_net_check.txt"), "w") as f:
            f.write("\n".join(out) + "\n")
        print(mask(f"\nкопия: {os.path.join(home, 'margin_net_check.txt')}"))
    except OSError:
        pass


main()
