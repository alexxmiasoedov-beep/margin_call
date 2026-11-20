#!/usr/bin/env python3
"""Сканер Telegram-канала с уведомлениями подписчикам бота.

Запуск:  python3 scanner.py --once        один проход (для cron / GitHub Actions)
         python3 scanner.py --loop        бесконечный цикл, проход раз в trader.POLL_SEC (/set poll)
         добавьте --dry-run, чтобы ничего не отправлять, а только печатать.
Все настройки — через переменные окружения (см. .env.example). Зависимостей нет.
"""
import bisect
import gzip
import html
import json
import math
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import trader

CHANNEL = os.environ.get("CHANNEL", "cryptocode_margin_data")
TOKEN = os.environ.get("TG_BOT_TOKEN", "")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
MIN_RUN_H = float(os.environ.get("MIN_RUN_H", "4"))
GAP_MIN = float(os.environ.get("GAP_MIN", "30"))
PUMP_MIN = float(os.environ.get("PUMP_MIN", "8"))
PUMP_MAX = float(os.environ.get("PUMP_MAX", "17"))
COOLDOWN_H = float(os.environ.get("COOLDOWN_H", "24"))
MAX_RUNTIME_SEC = int(os.environ.get("MAX_RUNTIME_SEC", "0"))  # --loop: выйти через N секунд (0 = бесконечно)
LOOKBACK_H = MIN_RUN_H + 1.5  # сколько часов постов тянуть из канала
# Выключатель. Непустая строка — бот не работает: не сканирует канал, не торгует, не ходит в сеть, не пишет в Telegram;
# жив только самописец сервера (sys_watch, строка раз в минуту в system.log). Включить обратно — пустая строка и push в main.
HALT = ""
UA = "Mozilla/5.0 (margin-call scanner)"


def log(*a):
    print(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- DNS
# DNS на сервере временами не отвечает («Temporary failure in name resolution»), и каждый такой запрос висит секунды.
# Адреса хостов храним 10 мин (на все запросы процесса, и scanner, и trader); если DNS не ответил — берём последний
# рабочий адрес и спрашиваем DNS снова через минуту. Без маршрута IPv6 спрашиваем только адреса IPv4: запрос AAAA
# у медленного DNS стоит секунды, а соединиться по IPv6 всё равно нельзя («Network is unreachable»).
DNS_TTL, DNS_RETRY = 600, 60
_dns_cache, _dns_logged = {}, {}
_getaddrinfo = socket.getaddrinfo
_v6 = {"t": 0, "ok": True}


def _ipv6_route():
    """Есть ли маршрут IPv6 по умолчанию (не через lo)."""
    try:
        with open("/proc/net/ipv6_route") as f:
            return any(x[0] == "0" * 32 and x[1] == "00" and x[-1] != "lo" for x in (ln.split() for ln in f) if len(x) >= 10)
    except OSError:
        return True


def _cached_getaddrinfo(host, port, *args, **kw):
    now = time.time()
    if now - _v6["t"] > 600:
        _v6.update(t=now, ok=_ipv6_route())
    if not _v6["ok"]:
        if args[:1] == (0,):
            args = (socket.AF_INET,) + args[1:]
        elif not args and not kw.get("family"):
            kw = dict(kw, family=socket.AF_INET)
    key = (host, port, args, tuple(sorted(kw.items())))
    hit = _dns_cache.get(key)
    if hit and now < hit[0]:
        return hit[1]
    try:
        res = _getaddrinfo(host, port, *args, **kw)
        trader.net_note("DNS", time.time() - now, True)
    except socket.gaierror as e:
        trader.net_note("DNS", time.time() - now, False)
        if not hit:
            raise
        _dns_cache[key] = (now + DNS_RETRY, hit[1])
        if now - _dns_logged.get(host, 0) >= DNS_TTL:              # в журнал — не чаще раза в 10 мин на хост
            _dns_logged[host] = now
            log(f"DNS не ответил для {host} ({e}) — беру прежний адрес")
        return hit[1]
    _dns_cache[key] = (now + DNS_TTL, res)
    return res


socket.getaddrinfo = _cached_getaddrinfo


NON_ASCII = re.compile(r"[^\x00-\x7f]+")


def http(url, data=None, timeout=30, ctype=None):
    # Фьючерсы Binance бывают с иероглифами в названии (币安人生USDT): в адресе — %-кодировка UTF-8, иначе urllib падает
    # с «'ascii' codec can't encode», и правила 🇰🇷 🇰🇷⭐ 🟩 молча пропускают такие монеты
    url = NON_ASCII.sub(lambda m: urllib.parse.quote(m.group(0)), url)
    real = urllib.parse.urlsplit(url).hostname or "?"
    host = "telegram getUpdates" if "/getUpdates" in url else real
    wait = trader.banned(real)
    if wait:                                                 # Binance ответил 403/418/429 — до конца паузы не стучимся
        raise urllib.error.URLError(f"пауза после ответа Binance 418/429, ещё {wait:.0f} с")
    t0 = time.time(); ok = False
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **({"Content-Type": ctype} if ctype else {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
        ok = True
        return body
    except urllib.error.HTTPError as e:
        if e.code in (403, 418, 429) and real.endswith("binance.com"):
            trader.ban_note(real, e.code, e.headers)
        raise
    finally:
        trader.net_note(host, time.time() - t0, ok)          # для строки «РЕСУРСЫ» раз в час


def http_json(url, timeout=30):
    try:
        return json.loads(http(url, timeout=timeout))
    except Exception as e:
        if not trader.banned(urllib.parse.urlsplit(url).hostname or ""):   # о паузе после бана уже написано один раз
            log("http_json fail", url.split("?")[0], e)
        return None


# ---------------------------------------------------------------- Telegram
_tg_fail = {"t": 0, "n": 0}


def tg_warn(*a):
    """Сбой Telegram — в журнал не чаще раза в минуту: при обрыве сети ошибки идут подряд."""
    _tg_fail["n"] += 1
    if time.time() - _tg_fail["t"] >= 60:
        log(*a, f"(сбоев Telegram за минуту: {_tg_fail['n']})" if _tg_fail["n"] > 1 else "")
        _tg_fail.update(t=time.time(), n=0)


def tg(method, _timeout=30, **params):
    if not TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        return json.loads(http(url, data=data, timeout=_timeout))
    except Exception as e:
        tg_warn("telegram fail", method, e)
        return None


def chunks(text, limit=4000):
    """Делит текст на сообщения не длиннее limit (у Telegram лимит 4096): по абзацам, слишком длинный абзац — по строкам."""
    out, cur = [], ""
    for block in text.split("\n\n"):
        for i, piece in enumerate([block] if len(block) <= limit else block.split("\n")):
            sep = "\n\n" if i == 0 else "\n"
            if cur and len(cur) + len(sep) + len(piece) > limit:
                out.append(cur); cur = ""
            cur = cur + sep + piece if cur else piece
            while len(cur) > limit:                    # одна строка длиннее лимита
                out.append(cur[:limit]); cur = cur[limit:]
    if cur:
        out.append(cur)
    return out or [text]


# «<», который не открывает тег (например «фандинг < −0,03%»), Telegram в режиме HTML не принимает — и сообщение не уходит целиком
STRAY_LT = re.compile(r"<(?!/?(?:b|strong|i|em|u|ins|s|strike|del|a|code|pre|tg-spoiler|blockquote)[\s>])")


def send(chat_id, text):
    r = None
    for part in chunks(text):
        r = tg("sendMessage", chat_id=chat_id, text=STRAY_LT.sub("&lt;", part), parse_mode="HTML", disable_web_page_preview="true")
    return r


def broadcast(state, text, dry):
    if dry:
        log("DRY-RUN сообщение:\n" + re.sub(r"<[^>]+>", "", text))
        return
    dead = []
    for cid in state["subscribers"]:
        r = send(cid, text)
        if r and not r.get("ok") and r.get("error_code") in (403, 400):
            dead.append(cid)
    for cid in dead:
        state["subscribers"].remove(cid)
        log("отписан (бот заблокирован):", cid)


WELCOME = (
    "Подписка оформлена.\n\n"
    "Команды: /status — текущие кандидаты, /trades — журнал сделок, баланс и позиции, "
    "/positions — открытые позиции на Binance, /virtual — виртуальные журналы (без тейка; по фандингу; 15/25; 15/20; 6/20; новые правила D* и P*; корейский шорт; корейский шорт ⭐ со счётом условий; турецкий набег; памп без розницы — лонг; отдача займа — шорт), /params — параметры сделок, /set <параметр> <число> — изменить "
    "(margin, lev, tp, sl, hold, max, limit, lsr, dump, br, pause, fexit), /pause и /resume — пауза торговли, "
    "/export — выгрузка журналов файлом (раз в неделю — для сверки с бэктестом), /stop — отписаться."
)


def kb(rows):
    """Инлайн-клавиатура: rows = [[(текст, data), ...], ...]."""
    return json.dumps({"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]})


def main_menu(state):
    pause = ("▶️ Возобновить торговлю", "resume") if state.get("trading_paused") else ("⏸ Пауза торговли", "pause")
    return kb([
        [("⚙️ Параметры сделок", "params"), ("📊 Позиции на Binance", "positions")],
        [("📒 Журнал сделок", "trades"), ("🔍 Кандидаты в канале", "status")],
        [("📓📗📘📕📙🟦🟧🇰🇷⭐🇹🇷🟩↩️ Виртуальные журналы", "virtual")],
        [pause],
    ])


def params_menu():
    rows, row = [], []
    for name, (var, typ, lo, hi, desc) in trader.PARAMS.items():
        row.append((f"{desc.split(',')[0]}: {getattr(trader, var):g}", f"p:{name}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([("◀️ Меню", "menu")])
    return kb(rows)


def send_menu(cid, state):
    tg("sendMessage", chat_id=cid, text="Меню бота. Выберите действие:", reply_markup=main_menu(state))


def resume_text():
    """Ответ на «возобновить торговлю»: при выключенной в коде реальной торговле (trader.NO_TRADE) сделок не будет и без паузы."""
    if trader.NO_TRADE:
        return f"Пауза снята, но реальная торговля {trader.NO_TRADE} — сделок на Binance не будет. Чтобы включить, попросите Claude."
    return "Торговля возобновлена."


def setup_commands():
    """Регистрирует команды в меню Telegram (кнопка «/» у поля ввода)."""
    cmds = [("menu", "Меню с кнопками"), ("params", "Параметры сделок"), ("positions", "Открытые позиции на Binance"),
            ("history", "Ордера по монете за 24 ч: /history LSK"),
            ("trades", "Журнал сделок, баланс"), ("virtual", "Виртуальные журналы"), ("status", "Кандидаты в канале"),
            ("export", "Выгрузка журналов файлом"),
            ("pause", "Пауза торговли"), ("resume", "Возобновить торговлю"), ("stop", "Отписаться")]
    tg("setMyCommands", commands=json.dumps([{"command": c, "description": d} for c, d in cmds]))


def handle_callback(state, cq, candidates):
    cid = cq["message"]["chat"]["id"]
    data = cq.get("data", "")
    tg("answerCallbackQuery", callback_query_id=cq["id"])
    if data == "menu":
        send_menu(cid, state)
    elif data == "params":
        tg("sendMessage", chat_id=cid, text=trader.params_text() + "\n\nНажмите параметр, чтобы изменить:",
           reply_markup=params_menu())
    elif data.startswith("p:"):
        name = data[2:]
        if name in trader.PARAMS:
            var, typ, lo, hi, desc = trader.PARAMS[name]
            state.setdefault("awaiting", {})[str(cid)] = name
            tg("sendMessage", chat_id=cid,
               text=f"Введите новое значение — {desc} (сейчас {getattr(trader, var):g}, допустимо {lo:g}–{hi:g}).\n"
                    "Ответьте на это сообщение числом или напишите «отмена».",
               reply_markup=json.dumps({"force_reply": True, "input_field_placeholder": "число"}))
    elif data == "positions":
        send(cid, trader.positions_text())
    elif data == "trades":
        send(cid, trader.summary(state))
    elif data == "virtual":
        send(cid, trader.virt_text(state))
    elif data == "status":
        send(cid, status_text(candidates))
    elif data == "pause":
        state["trading_paused"] = True
        tg("sendMessage", chat_id=cid, text="Торговля на паузе: новые сделки не открываются, открытые ведутся до выхода.",
           reply_markup=main_menu(state))
    elif data == "resume":
        state["trading_paused"] = False
        tg("sendMessage", chat_id=cid, text=resume_text(), reply_markup=main_menu(state))


EXPORT_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "export_signals.py")
EXPORT_FILE = os.path.join(os.path.expanduser("~"), "margin_export_signals.txt")
EXPORT_MAX_S = 600
_exp = {"proc": None, "chat": None, "t": 0.0}


def tg_file(chat_id, name, data, caption=""):
    """sendDocument: байты data файлом name в чат (multipart без сторонних библиотек). Ответ Telegram или None."""
    if not TOKEN:
        return None
    b = "margincall" + os.urandom(8).hex()
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                    for k, v in (("chat_id", str(chat_id)), ("caption", caption)))
    body += (f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{name}"\r\n'
             f"Content-Type: text/plain; charset=utf-8\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
    try:
        return json.loads(http(f"https://api.telegram.org/bot{TOKEN}/sendDocument", data=body, timeout=60,
                               ctype=f"multipart/form-data; boundary={b}"))
    except Exception as e:
        tg_warn("telegram fail sendDocument", e)
        return None


def export_start(cid):
    """/export: tools/export_signals.py — отдельным процессом (проходы сканера его не ждут); файл придёт по готовности
    (export_check). Одна выгрузка за раз."""
    p = _exp["proc"]
    if p is not None and p.poll() is None:
        return "Выгрузка уже собирается — пришлю файл, как только будет готова."
    if not os.path.exists(EXPORT_TOOL):
        return "Рядом с ботом нет tools/export_signals.py — запустите выгрузку на сервере командой из памятки."
    try:
        _exp["proc"] = subprocess.Popen([sys.executable, EXPORT_TOOL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        stdin=subprocess.DEVNULL, cwd=os.path.expanduser("~"))
    except OSError as e:
        return f"Выгрузку запустить не удалось: {e}"
    _exp.update(chat=cid, t=time.time())
    log("ВЫГРУЗКА", "запущена по команде /export")
    return "Собираю выгрузку журналов — пришлю файлом через 2–3 минуты."


def export_check():
    """Готова ли выгрузка: файл — в чат, откуда пришла /export, без пути к домашней папке сервера (в нём имя пользователя);
    дольше 10 мин — процесс останавливается."""
    p = _exp["proc"]
    if p is None:
        return
    rc = p.poll()
    if rc is None:
        if time.time() - _exp["t"] > EXPORT_MAX_S:
            p.kill(); _exp["proc"] = None
            send(_exp["chat"], "Выгрузка не уложилась в 10 минут и остановлена — попробуйте /export позже.")
            log("ВЫГРУЗКА", "не уложилась в 10 мин, остановлена")
        return
    _exp["proc"] = None
    if rc != 0 or not os.path.exists(EXPORT_FILE) or os.path.getmtime(EXPORT_FILE) < _exp["t"] - 5:
        send(_exp["chat"], f"Выгрузка не получилась (код завершения {rc}) — попробуйте /export ещё раз.")
        log("ВЫГРУЗКА", f"ошибка, код завершения {rc}")
        return
    home = os.path.expanduser("~")
    data = open(EXPORT_FILE, "rb").read().replace(home.encode(), b"~")
    r = tg_file(_exp["chat"], "margin_export_signals.txt", data,
                caption=f"Выгрузка журналов {datetime.now(timezone.utc):%d.%m %H:%M} UTC — {len(data) // 1024} КБ")
    ok = bool(r and r.get("ok"))
    log("ВЫГРУЗКА", "файл отправлен" if ok else f"файл не отправлен: {(r or {}).get('description')}")
    if not ok:
        send(_exp["chat"], "Файл выгрузки не отправился — повторите /export.")


def poll_commands(state, candidates, dry, wait=0):
    """Обрабатывает команды, нажатия кнопок и ввод значений параметров.
    wait > 0 — длинный опрос: Telegram держит запрос до wait секунд и отвечает сразу, как придёт событие.
    Возвращает число событий или None, если Telegram не ответил (нет сети, второй экземпляр бота с тем же токеном)."""
    if not TOKEN:
        return None
    r = tg("getUpdates", _timeout=wait + 15, offset=state.get("update_offset", 0), timeout=wait)
    if not r or not r.get("ok"):
        if r:
            tg_warn("telegram getUpdates:", r.get("error_code"), r.get("description"))
        return None
    for u in r["result"]:
        state["update_offset"] = u["update_id"] + 1
        if "callback_query" in u:
            try:
                handle_callback(state, u["callback_query"], candidates)
            except Exception as e:
                log("ошибка кнопки:", repr(e))
            continue
        msg = u.get("message") or u.get("channel_post")
        if not msg or "text" not in msg:
            continue
        cid = msg["chat"]["id"]
        raw = msg["text"].strip()
        text = raw.lower().split("@")[0] if raw.startswith("/") else raw.lower()
        awaiting = state.get("awaiting", {}).get(str(cid))
        if awaiting and not raw.startswith("/"):
            state["awaiting"].pop(str(cid), None)
            if text in ("отмена", "cancel", "нет"):
                tg("sendMessage", chat_id=cid, text="Отменено.", reply_markup=params_menu())
            else:
                reply = trader.set_param(state, awaiting, raw.replace(",", "."))
                log("параметр из чата:", awaiting, raw)
                tg("sendMessage", chat_id=cid, text=reply, reply_markup=params_menu())
            continue
        if text.startswith("/start"):
            if cid not in state["subscribers"]:
                state["subscribers"].append(cid)
                log("новый подписчик", cid)
            send(cid, WELCOME)
            send_menu(cid, state)
        elif text.startswith("/menu"):
            send_menu(cid, state)
        elif text.startswith("/stop"):
            if cid in state["subscribers"]:
                state["subscribers"].remove(cid)
            send(cid, "Отписал. Чтобы вернуться — /start.")
        elif text.startswith("/status"):
            send(cid, status_text(candidates))
        elif text.startswith("/trades"):
            send(cid, trader.summary(state))
        elif text.startswith("/virtual"):
            send(cid, trader.virt_text(state))
        elif text.startswith("/positions"):
            send(cid, trader.positions_text())
        elif text.startswith("/history"):
            parts = raw.split()
            if len(parts) < 2:
                send(cid, "Формат: /history LSK  (ордера и записи счёта по контракту за 24 ч)")
            else:
                hours = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 24
                send(cid, trader.history_text(parts[1].upper().replace("-USDT", "").replace("USDT", ""), hours))
        elif text.startswith("/params"):
            tg("sendMessage", chat_id=cid, text=trader.params_text() + "\n\nНажмите параметр, чтобы изменить:",
               reply_markup=params_menu())
        elif text.startswith("/set"):
            parts = text.split()
            if len(parts) != 3:
                tg("sendMessage", chat_id=cid, text="Формат: /set <параметр> <число>, или выберите кнопкой:",
                   reply_markup=params_menu())
            else:
                reply = trader.set_param(state, parts[1], parts[2])
                log("параметр из чата:", parts[1], parts[2])
                send(cid, reply)
        elif text.startswith("/export"):
            send(cid, export_start(cid) if cid in state["subscribers"] else "Выгрузка — только для подписчиков: сначала /start.")
        elif text.startswith("/pause"):
            state["trading_paused"] = True
            send(cid, "Торговля на паузе: новые сделки не открываются, открытые ведутся до выхода. /resume — продолжить.")
        elif text.startswith("/resume"):
            state["trading_paused"] = False
            send(cid, resume_text())
    return len(r["result"])


# ---------------------------------------------------------------- канал
# строка поста для правил 1 и 2: монета, займ, отдача, B/R, CHNG (CHNG бывает со знаком: -0.02, +0.00)
ROW = re.compile(r"^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+([+-]?[\d.]+)\s*$")
# все строки поста, как в бэктесте, включая B/R = inf (отдачи нет) — только для журнала ↩️; правила 1 и 2 видят rows
ROW_ALL = re.compile(r"^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+(\S+)\s+(\S+)\s*$")


def fetch_posts(lookback_h, max_pages=40):
    """Посты канала за последние lookback_h часов: [{id, ts, rows:{sym:(bor,rep,br)}, rows_all:{sym:(bor,rep,br,chng)}}].
    Страница веб-версии канала — около 20 постов; max_pages ограничивает глубину."""
    now = time.time()
    posts, before, seen = [], None, set()
    for _ in range(max_pages):
        url = f"https://t.me/s/{CHANNEL}" + (f"?before={before}" if before else "")
        try:
            page = http(url)
        except Exception as e:
            log("канал недоступен:", e)
            break
        blocks = re.split(r'(?=<div class="tgme_widget_message_wrap)', page)
        got = []
        for b in blocks:
            m = re.search(rf'data-post="{CHANNEL}/(\d+)"', b)
            t = re.search(r'<time datetime="([^"]+)"', b)
            body = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
            if not (m and t and body):
                continue
            pid = int(m.group(1))
            if pid in seen:
                continue
            seen.add(pid)
            ts = datetime.fromisoformat(t.group(1)).timestamp()
            text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", body.group(1))))
            rows, rows_all = {}, {}
            for ln in text.splitlines():
                r = ROW.match(ln.strip())
                if r:
                    rows[r.group(1)] = (r.group(2), r.group(3), r.group(4))
                r = ROW_ALL.match(ln.strip())
                if r:
                    rows_all[r.group(1)] = (r.group(2), r.group(3), r.group(4), r.group(5))
            got.append({"id": pid, "ts": ts, "rows": rows, "rows_all": rows_all, "ranked": _c4_ranked(text)})
        if not got:
            break
        posts += got
        oldest = min(got, key=lambda p: p["ts"])
        if oldest["ts"] < now - lookback_h * 3600:
            break
        before = oldest["id"]
        time.sleep(0.5)
    posts.sort(key=lambda p: p["ts"], reverse=True)
    return posts


def channel_runs(posts):
    """Для каждой монеты, присутствующей сейчас: сколько часов подряд она в постах."""
    now = time.time()
    gap = GAP_MIN * 60
    if not posts or now - posts[0]["ts"] > gap:
        return {}  # канал молчит — присутствующих нет
    runs = {}
    syms = set().union(*(p["rows"].keys() for p in posts))
    for s in syms:
        times = [p["ts"] for p in posts if s in p["rows"]]
        if not times or now - times[0] > gap:
            continue
        start = times[0]
        for a, b in zip(times, times[1:]):
            if a - b > gap:
                break
            start = b
        latest = next(p for p in posts if s in p["rows"])
        capped = start <= posts[-1]["ts"]  # серия упёрлась в глубину выборки — на самом деле длиннее
        runs[s] = {"run_h": (now - start) / 3600, "capped": capped, "info": latest["rows"][s]}
    return runs


# ---------------------------------------------------------------- цены
def klines_15m(sym, n=17):
    """Последние n 15-минутных свечей: (source, [close,...], [high,...], [low,...]) или None.
    Binance первым — сигналы канала про монеты Binance, и торгуем мы там же."""
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Binance", [float(k[4]) for k in j], [float(k[2]) for k in j], [float(k[3]) for k in j]
    j = http_json(f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Binance-spot", [float(k[4]) for k in j], [float(k[2]) for k in j], [float(k[3]) for k in j]
    j = http_json(f"https://api.mexc.com/api/v3/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "MEXC", [float(k[4]) for k in j], [float(k[2]) for k in j], [float(k[3]) for k in j]
    j = http_json(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}_USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Gate", [float(k[2]) for k in j], [float(k[3]) for k in j], [float(k[4]) for k in j]
    j = http_json(f"https://api.kucoin.com/api/v1/market/candles?type=15min&symbol={sym}-USDT", 15)
    if isinstance(j, dict) and len(j.get("data") or []) >= n:
        d = sorted(j["data"], key=lambda k: int(k[0]))[-n:]
        return "KuCoin", [float(k[2]) for k in d], [float(k[3]) for k in d], [float(k[4]) for k in d]
    return None


def _zigzag(c, th=3.0):
    """Число разворотов (свингов) на закрытиях с порогом th %."""
    n = 0; d = 0; ext = c[0]
    for x in c[1:]:
        if d == 0:
            if (x / ext - 1) * 100 >= th: d = 1; ext = x
            elif (ext / x - 1) * 100 >= th: d = -1; ext = x
        elif d == 1:
            if x > ext: ext = x
            elif (ext / x - 1) * 100 >= th: n += 1; d = -1; ext = x
        else:
            if x < ext: ext = x
            elif (x / ext - 1) * 100 >= th: n += 1; d = 1; ext = x
    return n


def _structure(c, h, l, invert=False):
    """Форма суток до сигнала по 96 завершённым свечам (те же формулы, что в research/shape.py).
    invert=True — для падений график переворачивается (1/цена), и слив выглядит как памп."""
    if len(c) < 97:
        return None
    p = c[-1]
    H, L, C = h[:-1], l[:-1], c[:-1]
    if invert:
        H, L, C, p = [1 / x for x in l[:-1]], [1 / x for x in h[:-1]], [1 / x for x in c[:-1]], 1 / p
    H, L, C = H[-96:], L[-96:], C[-96:]
    prior_h = H[:-16]; prior_ext = max(prior_h); prior_idx = prior_h.index(prior_ext)
    vs_prior = (p / prior_ext - 1) * 100                              # >0 — перехай прежнего экстремума
    pull = (min(L[prior_idx:-16]) / prior_ext - 1) * 100              # откат между прежним экстремумом и 4-часовым окном
    move_prior = (prior_ext / C[0] - 1) * 100                         # рост от начала суток до прежнего экстремума
    rng = max(H) - min(L)
    return {"move_prior": move_prior, "pull": pull, "vs_prior": vs_prior, "swings": _zigzag(C),
            "pos24": (p - min(L)) / rng if rng > 0 else None}


def price_and_change(sym):
    r = klines_15m(sym, 97)                     # сутки свечей: 4 ч для правил + 20 ч до них для паттернов
    if not r:
        r = klines_15m(sym)
        if not r:
            return None
    src, c, h, l = r
    peak = max(h[-17:-1]); low = min(l[-17:-1])
    rise_before = (c[-17] / c[-97] - 1) * 100 if len(c) >= 97 and c[-97] else None
    return {"src": src, "price": c[-1], "b4h": (c[-1] / c[-17] - 1) * 100,
            "from_peak": (c[-1] / peak - 1) * 100 if peak else None, "from_low": (c[-1] / low - 1) * 100 if low else None,
            "rise_before": rise_before, "s_pump": _structure(c, h, l), "s_dump": _structure(c, h, l, invert=True)}


def pattern_line(c):
    """Строки про паттерны формы графика за сутки (только пометка; по бэктесту за полгода, research/shape.py)."""
    rule = c.get("rule")
    if rule == "dump":
        x = c.get("rise_before"); s = c.get("s_dump") or {}
        out = []
        if x is None:
            out.append("Паттерн: нет данных за сутки")
        elif x >= 30:
            out.append(f"Паттерн ✅✅: слив после пампа, за 20 ч до падения рост {x:+.0f}% (по истории тейк 90%, стоп 8%)")
        elif x >= 15:
            out.append(f"Паттерн ✅: слив после пампа, за 20 ч до падения рост {x:+.0f}% (по истории тейк 72%, стоп 8%)")
        elif x >= 5:
            out.append(f"Паттерн ⚠️ не выполнен: до падения рост всего {x:+.0f}% (по истории тейк 49%, половина висит до выхода по времени)")
        else:
            out.append(f"Паттерн ⚠️ не выполнен: пампа не было, за 20 ч до падения {x:+.0f}% (по истории тейк 68%, стоп 16%)")
        if s.get("pos24") is not None:
            pos = 1 - s["pos24"]                                       # доля высоты суточного диапазона, где стоит цена (1 = у максимума)
            if pos >= 0.5:
                out.append(f"Форма ✅: цена ещё в верхней половине диапазона суток ({pos*100:.0f}%), разворотов за сутки {s['swings']} (по истории тейк 87%)")
            elif pos <= 0.2:
                out.append(f"Форма ⚠️: цена у минимума суток ({pos*100:.0f}% диапазона), разворотов {s['swings']} (по истории тейк 59%, стоп 16%)")
            else:
                out.append(f"Форма: цена на {pos*100:.0f}% высоты диапазона суток, разворотов за сутки {s['swings']} (по истории тейк 67%)")
        return "\n".join(out) + "\n"
    if rule != "pump":
        return ""
    s = c.get("s_pump"); fp = c.get("from_peak")
    tail = f"; от пика 4 ч {fp:+.1f}%" if fp is not None else ""
    if not s:
        return "Паттерн: нет данных за сутки\n"
    if s["move_prior"] < 3:
        return f"Структура ⚠️: прямой памп без прежнего максимума за сутки{tail} (по истории тейк 69%, стоп 18%)\n"
    if s["vs_prior"] < -3:
        return f"Структура ⚠️: нижний хай — заход ниже прежнего максимума на {-s['vs_prior']:.0f}%, откат между ними {-s['pull']:.0f}%{tail} (по истории тейк 75%, стоп 21%)\n"
    if s["pull"] > -4:
        return f"Структура ⚠️: откат между максимумами всего {-s['pull']:.0f}%{tail} (по истории тейк 68%, стоп 22%)\n"
    if s["pull"] < -15:
        return f"Структура ⚠️: откат между максимумами {-s['pull']:.0f}%, слишком глубокий{tail} (по истории тейк 76%, стоп 21%)\n"
    kind = "перехай" if s["vs_prior"] > 0.5 else "двойная вершина"
    return (f"Структура ✅: рост → откат {-s['pull']:.0f}% → {kind} ({s['vs_prior']:+.1f}% к прежнему максимуму), "
            f"разворотов за сутки {s['swings']}{tail} (по истории тейк 90%, стоп 8%)\n")


def pattern_ok(c):
    """True/False: правило 1 — структура «прежний хай + откат 4–15% + заход не ниже хая на 3%»;
    правило 2 — рост ≥15% за 20 ч до падения. None, если нет данных."""
    if c.get("rule") == "pump":
        s = c.get("s_pump")
        if not s:
            return None
        return bool(s["move_prior"] >= 3 and -15 <= s["pull"] <= -4 and s["vs_prior"] >= -3)
    if c.get("rule") == "dump":
        return None if c.get("rise_before") is None else bool(c["rise_before"] >= 15)
    return None


def _ratio_change(path, sym, bars=3):
    """Изменение отношения лонг/шорт Binance за bars 5-минутных баров (доля): последнее / bars назад − 1."""
    j = http_json(f"https://fapi.binance.com/futures/data/{path}?symbol={sym}USDT&period=5m&limit={bars + 2}", 15)
    try:
        v = [float(x["longShortRatio"]) for x in sorted(j, key=lambda x: int(x["timestamp"]))]
        return v[-1] / v[-1 - bars] - 1 if len(v) > bars and v[-1 - bars] else None
    except (TypeError, KeyError, ValueError):
        return None


def _efficiency_4h(sym):
    """Ровность хода за 4 ч по минутным закрытиям: |итог| / сумма |шагов| (1 — ровно, около 0 — пила)."""
    import math
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=1m&limit=241", 15)
    try:
        c = [float(k[4]) for k in j[:-1]]
        lr = [math.log(x) for x in c]
        path = sum(abs(b - a) for a, b in zip(lr, lr[1:]))
        return abs(lr[-1] - lr[0]) / path if len(c) > 60 and path else None
    except (TypeError, ValueError, IndexError):
        return None


def _kimchi(sym, price):
    """Кимчи-премия, %: цена на Upbit (KRW → USDT по курсу KRW-USDT) против нашей цены. None — монеты нет на Upbit."""
    j = http_json(f"https://api.upbit.com/v1/ticker?markets=KRW-{sym},KRW-USDT", 15)
    try:
        t = {x["market"]: float(x["trade_price"]) for x in j}
        return (t[f"KRW-{sym}"] / t["KRW-USDT"] / price - 1) * 100 if price else None
    except (TypeError, KeyError, ValueError):
        return None


def risk_marks(c):
    """Пометки-кандидаты в признаки стопов (бэктест на фьючерсах, research/futures/ВЫВОДЫ.md). Только пометка, в торговлю не входит.
    Возвращает (текст, данные для журнала)."""
    rule = c.get("rule"); d = {}; out = []
    if rule == "dump":
        d["toppos15"] = x = _ratio_change("topLongShortPositionRatio", c["sym"])
        if x is None:
            out.append("топ-трейдеры: нет данных")
        elif x > 0.009:
            out.append(f"⚠️ топ-трейдеры за 15 мин нарастили лонги {x * 100:+.1f}% (по истории стопов 22% против 5%)")
        else:
            out.append(f"топ-трейдеры за 15 мин {x * 100:+.1f}% — ок")
    elif rule == "pump":
        d["br"] = br = _num(c["info"][2])
        d["lsr15"] = lsr = _ratio_change("globalLongShortAccountRatio", c["sym"])
        d["eff4h"] = eff = _efficiency_4h(c["sym"])
        d["kimchi"] = km = _kimchi(c["sym"], c.get("price"))
        bad = []; ok = []
        if br is not None:
            (bad if br > 30 else ok).append(f"B/R {br:g}" + (" > 30 (стопов 21% против 14%)" if br > 30 else ""))
        if lsr is not None:
            (bad if lsr < -0.015 else ok).append(f"LSR за 15 мин {lsr * 100:+.1f}%" + (" — набегают шортисты (стопов 23% против 14%)" if lsr < -0.015 else ""))
        if eff is not None:
            (bad if eff < 0.08 else ok).append(f"ровность хода 4 ч {eff:.2f}" + (" — рваный рост (стопов 24% против 15%)" if eff < 0.08 else ""))
        if km is not None:
            (bad if km > 3 else ok).append(f"кимчи-премия {km:+.1f}%" + (" — корейский памп (стопов 24% против 16%)" if km > 3 else ""))
        out += [f"⚠️ {x}" for x in bad]
        if ok:
            out.append("ок: " + ", ".join(ok))
    else:
        return "", d
    d["flags"] = sum(1 for x in out if x.startswith("⚠️"))
    head = f"Риск-пометки ({d['flags']} ⚠️, кандидаты — проверяем вперёд):" if d["flags"] else "Риск-пометки: нет ✅ (кандидаты — проверяем вперёд)"
    return head + "\n" + "\n".join("  " + x for x in out) + "\n", d


def fmt_price(p):
    return f"{p:.6g}"


_funding_hours = {}


def funding(sym):
    """Текущая ставка фандинга на бессрочном контракте: {"rate": % за период, "hours": период, "src"} или None.
    Binance первым — именно эту ставку платит/получает наша позиция."""
    j = http_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}USDT", 15)
    if isinstance(j, dict) and j.get("lastFundingRate") is not None:
        if not _funding_hours:  # интервалы фандинга: в списке только контракты с ненулевой настройкой, прочие — 8 ч
            fi = http_json("https://fapi.binance.com/fapi/v1/fundingInfo", 15)
            for f in fi if isinstance(fi, list) else []:
                _funding_hours[f.get("symbol")] = int(f.get("fundingIntervalHours") or 8)
            _funding_hours.setdefault("_loaded", 8)
        return {"rate": float(j["lastFundingRate"]) * 100, "hours": _funding_hours.get(f"{sym}USDT", 8), "src": "Binance"}
    j = http_json(f"https://contract.mexc.com/api/v1/contract/funding_rate/{sym}_USDT", 15)
    if isinstance(j, dict) and j.get("success") and j.get("data", {}).get("fundingRate") is not None:
        d = j["data"]
        return {"rate": float(d["fundingRate"]) * 100, "hours": int(d.get("collectCycle") or 8), "src": "MEXC"}
    j = http_json(f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{sym}_USDT", 15)
    if isinstance(j, dict) and j.get("funding_rate") is not None:
        return {"rate": float(j["funding_rate"]) * 100, "hours": int(j.get("funding_interval") or 28800) // 3600, "src": "Gate"}
    j = http_json(f"https://api.bitget.com/api/v2/mix/market/current-fund-rate?symbol={sym}USDT&productType=USDT-FUTURES", 15)
    if isinstance(j, dict) and j.get("data"):
        d = j["data"][0]
        return {"rate": float(d["fundingRate"]) * 100, "hours": int(d.get("fundingRateInterval") or 8), "src": "Bitget"}
    return None


def _msk(ts):
    return datetime.fromtimestamp(ts + 3 * 3600, timezone.utc).strftime("%d.%m %H:%M")


def funding_switch_watch(state, every=120):
    """Все фьючерсы USDT-M Binance (не только из канала): уведомление, когда начисление фандинга сменилось
    с раз в 8/4 ч на раз в 1 ч, а ставка и на последней выплате, и сейчас отрицательная. Возвращает сообщения."""
    now = time.time()
    if now - state.get("fsw_ts", 0) < every:
        return []
    state["fsw_ts"] = now
    fi = http_json("https://fapi.binance.com/fapi/v1/fundingInfo", 15)
    pi = http_json("https://fapi.binance.com/fapi/v1/premiumIndex", 15)
    if not isinstance(fi, list) or not isinstance(pi, list) or not pi:
        return []
    iv = {x.get("symbol"): int(float(x.get("fundingIntervalHours") or 8)) for x in fi if x.get("symbol")}
    cur = {}
    for x in pi:
        s = str(x.get("symbol", ""))
        if s.endswith("USDT"):
            try:
                cur[s] = (iv.get(s, 8), float(x.get("lastFundingRate") or 0) * 100, int(x.get("nextFundingTime") or 0) // 1000, float(x.get("markPrice") or 0))
            except (TypeError, ValueError):
                continue
    # свежие интервалы — и для остального бота (ставка в час, фандинг в сигналах)
    _funding_hours.clear(); _funding_hours.update({s: v[0] for s, v in cur.items()}); _funding_hours["_loaded"] = 8
    trader._fund_iv["map"] = {s: float(v[0]) for s, v in cur.items()}; trader._fund_iv["ts"] = now
    prev = state.get("fund_iv") or {}
    state["fund_iv"] = {s: v[0] for s, v in cur.items()}
    if not prev:
        return []                                             # первый запуск — только запоминаем интервалы
    msgs = []
    for s, (h, rate, nxt, mp) in sorted(cur.items()):
        if not (prev.get(s) in (4, 8) and h == 1 and rate < 0):
            continue
        hist = http_json(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={s}&limit=4", 15)
        last = []
        if isinstance(hist, list):
            try:
                last = sorted((int(r["fundingTime"]) // 1000, float(r["fundingRate"]) * 100) for r in hist)
            except (KeyError, TypeError, ValueError):
                last = []
        if last and last[-1][1] >= 0:
            continue                                          # последняя выплата не отрицательная — не наш случай
        t24 = http_json(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={s}", 15)
        ch = f", за 24 ч {float(t24['priceChangePercent']):+.1f}%" if isinstance(t24, dict) and t24.get("priceChangePercent") else ""
        base = s[:-4]
        msgs.append(f"⏱ <b>{base}</b> ({s}): фандинг теперь раз в 1 ч (было раз в {prev[s]} ч)\n"
                    + ("Последние выплаты (МСК): " + ", ".join(f"{_msk(t)} {r:+.3f}%" for t, r in last) + "\n" if last else "")
                    + f"Сейчас ставка {rate:+.3f}% за час" + (f", следующая выплата {_msk(nxt)} МСК" if nxt else "") + "\n"
                    + f"Цена {mp:.6g}{ch}")
        log("СМЕНА ИНТЕРВАЛА ФАНДИНГА", s, prev[s], "→ 1 ч, ставка", rate)
    return msgs


def fmt_funding(f):
    if not f:
        return "нет бессрочного контракта"
    return f"{f['rate']:+.4f}% / {f['hours']} ч ({f['src']})"


# ---------------------------------------------------------------- сигналы
def fmt_run(c):
    return ("≥" if c.get("capped") else "") + f"{c['run_h']:.1f} ч"


def _num(s):
    """Число из ячейки поста: '551.2K', '1,2M', '45.2' → float; иначе None."""
    try:
        s = str(s).strip().replace(",", ".").replace(" ", "")
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1:].upper(), 1)
        return float(s[:-1] if mult != 1 else s) * mult
    except (ValueError, TypeError):
        return None


def rule_for(c):
    """Какое правило даёт сигнал по кандидату: 'pump' (рост 8–17%), 'dump' (падение 8–17% при B/R ≥ порога) или None."""
    if PUMP_MIN <= c["b4h"] <= PUMP_MAX:
        return "pump"
    if trader.DUMP_RULE and -PUMP_MAX <= c["b4h"] <= -PUMP_MIN:
        br = _num(c["info"][2])
        if br is not None and br >= trader.DUMP_BR_MIN:
            return "dump"
    return None


def _closed_15m(sym, T, n=99):
    """Закрытые к моменту T 15-мин свечи фьючерса Binance (последняя — закончилась ровно в T) или None."""
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if not isinstance(j, list):
        return None
    k = [x for x in j if int(x[0]) // 1000 + 900 <= T]
    return k if k and int(k[-1][0]) // 1000 + 900 == T else None


_skip_why = {}   # 15-мин правило → почему последняя свеча ещё не проверена (сбой ключевых данных)


def candle_due(state, key, name, step=900):
    """Время закрытия T свечи, которую 15-мин правило (отметка state[key]) ещё не проверило, если с закрытия прошло ≤ 10 мин;
    иначе None. Свеча, не проверенная за 10 мин, — одна строка в журнал службы: сбой данных или поздний проход.
    step=3600 — то же для часового правила (💸)."""
    T = int(time.time() // step * step)
    if state.get(key) == T:
        return None
    if time.time() - T <= 600:
        return T
    if state.get(key + "_skip") != T:
        state[key + "_skip"] = T
        log(name, f"свеча {datetime.fromtimestamp(T, timezone.utc):%d.%m %H:%M} не проверена: "
            + _skip_why.pop(key, f"проход начался через {(time.time() - T) / 60:.0f} мин после закрытия"))
    return None


def candle_retry(key, why):
    """Ключевые данные свечи не получены: свеча не отмечается, правило повторит её на следующем проходе (до 10 мин)."""
    _skip_why[key] = why
    return []


def candle_done(state, key, T):
    state[key] = T
    _skip_why.pop(key, None)


def new_rules(state, posts):
    """Правила D* и P* (журналы 🟦 🟧, research/futures/ВЫВОДЫ.md): раз в 15 мин, на закрытии свечи, по монетам,
    которые были в постах канала за эту свечу. Только виртуальные сделки. Возвращает сообщения для чата."""
    T = candle_due(state, "nr_last_T", "НОВОЕ ПРАВИЛО")
    if T is None:
        return []
    gap = GAP_MIN * 60; in_bar = {}
    for p in posts:                                            # посты — от новых к старым
        if T - 900 <= p["ts"] < T:
            for s in p["rows"]:
                in_bar.setdefault(s, p)                        # последний пост с монетой внутри свечи
    if not in_bar:
        return candle_retry("nr_last_T", "нет постов канала за свечу")
    b = _closed_15m("BTC", T)
    btc_now = float(b[-1][4]) if b else None
    btc24 = btc_now / float(b[-97][4]) - 1 if b and len(b) >= 97 else None
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=15m&startTime={(T - 30 * 86400 - 900) * 1000}&limit=1", 15)
    btc30 = btc_now / float(j[0][4]) - 1 if btc_now and isinstance(j, list) and j else None
    if btc24 is None or btc30 is None:
        return candle_retry("nr_last_T", "нет свечей BTC с Binance")
    candle_done(state, "nr_last_T", T)
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    msgs = []; miss = []
    for s, p in in_bar.items():
        times = [q["ts"] for q in posts if s in q["rows"] and q["ts"] <= p["ts"]]
        start = times[0]
        for a, c2 in zip(times, times[1:]):
            if a - c2 > gap:
                break
            start = c2
        run_h = (p["ts"] - start) / 3600
        if run_h < 1:
            continue
        k = _closed_15m(s, T)
        if k is None and f"{s}USDT" in trader._contracts:
            miss.append(s)                                     # фьючерс есть, а свечей Binance не отдал
        if not k or len(k) < 97:
            continue
        c = float(k[-1][4]); ch12 = (c / float(k[-49][4]) - 1) * 100; qv = sum(float(x[7]) for x in k[-96:])
        br = _num(p["rows"][s][2])
        is_d = run_h >= 2 and ch12 <= -4 and br is not None and br >= 30 and qv >= 20e6 and btc24 is not None and btc24 > 0
        is_p = run_h >= 1 and ch12 >= 2 and qv >= 20e6 and btc30 is not None and btc30 < 0
        if not (is_d or is_p):
            continue
        note = (f"за 12 ч {ch12:+.1f}%, в канале {run_h:.1f} ч, B/R {p['rows'][s][2]}, объём 24 ч {qv / 1e6:.0f} млн $, "
                + (f"BTC за сутки {btc24 * 100:+.1f}%" if btc24 is not None else "BTC за сутки: нет данных")
                + (f", за 30 дней {btc30 * 100:+.1f}%" if btc30 is not None else ""))
        for key, ok, rule in (("virtual_D", is_d, "D*"), ("virtual_P", is_p, "P*")):
            if ok:
                log("НОВОЕ ПРАВИЛО", rule, s, note)
                m = trader.virt_open(state, key, s, rule, note, price=c)
                if m:
                    msgs.append(m)
    if miss:
        log("НОВОЕ ПРАВИЛО", "D*/P* не проверены — Binance не отдал свечи:", ", ".join(miss))
    return msgs


RP_RUN_H, RP_X, RP_DREP, RP_MOVE = 6.0, 2.0, 20e3, 0.10   # ↩️: серия в канале, рост отдачи за час (раз и $), ход цены за сутки
RP_X0, RP_DREP0 = 1.5, 10e3     # ↩️ всплеск отдачи: первый за час рост ×1,5 и +10 тыс. $ уже должен быть сильным (×2 и +20 тыс. $)
LOOKBACK_RP_H = 10.0            # ↩️: серия ≥ 6 ч и всплески за прошлые часы — посты тянем глубже, но только раз в 15 мин


def _fut_sym(coin):
    """Фьючерс Binance для монеты из маржинального канала: PEPE → 1000PEPE и т. п.; None, если бессрочного контракта нет."""
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    return next((p + coin for p in ("", "1000", "10000", "100000", "1000000") if f"{p}{coin}USDT" in trader._contracts), None)


def repay_due(state):
    """↩️ проверяется раз в 15 мин: первый проход в течение 10 мин после закрытия свечи."""
    T = int(time.time() // 900 * 900)
    return state.get("rp_last_T") != T and time.time() - T <= 600


def repay_rule(state, posts):
    """Отдача займа (журнал ↩️, research/s9/ВЫВОДЫ.md): раз в 15 мин, на закрытии свечи, по монетам из постов маржинального
    канала за эту свечу: монета в канале непрерывно ≥ 6 ч (разрывы ≤ 30 мин), отдача за 24 ч (REP) выросла в ≥ 2 раза к посту
    часовой давности (45–75 мин назад) и не меньше чем на 20 тыс. $, причём резко: это первый за час пост монеты с ростом
    отдачи ×1,5 и +10 тыс. $ (отсчёт часа — от прошлого такого поста, как в бэктесте), цена фьючерса за сутки изменилась
    на ≥ 10% в любую сторону → виртуальный шорт. Только виртуальные сделки. Возвращает сообщения для чата."""
    T = candle_due(state, "rp_last_T", "ОТДАЧА")
    if T is None:
        return []
    if not posts or posts[-1]["ts"] > T - (LOOKBACK_RP_H - 0.5) * 3600:   # проход начался до закрытия свечи или канал не ответил
        return candle_retry("rp_last_T", "посты канала не получены на нужную глубину")
    candle_done(state, "rp_last_T", T)
    gap = GAP_MIN * 60; hits = {}
    for s in {s for q in posts if T - 900 <= q["ts"] < T for s in q.get("rows_all", {})}:
        ser = sorted((q["ts"], q["rows_all"][s]) for q in posts if s in q.get("rows_all", {}) and q["ts"] < T)   # от старых к новым
        times = [ts for ts, _ in ser]; start = times[0]; last_jump = -1e18
        for i, (ts, row) in enumerate(ser):
            if i and ts - times[i - 1] > gap:
                start = ts                                      # разрыв > 30 мин — новая серия
            k = bisect.bisect_right(times, ts - 3600) - 1      # пост часовой давности
            if ts - start < 2 * 3600 or k < 0 or ts - times[k] > 75 * 60:
                continue
            rep, rep1 = _num(row[1]), _num(ser[k][1][1])
            if rep is None or rep1 is None or rep < RP_X0 * max(rep1, 1.0) or rep - rep1 < RP_DREP0:
                continue
            if ts - last_jump < 3600:
                continue                                        # не первый всплеск за час — отдача набиралась постепенно
            last_jump = ts
            run_h = (ts - start) / 3600
            if ts >= T - 900 and run_h >= RP_RUN_H and rep >= RP_X * max(rep1, 1.0) and rep - rep1 >= RP_DREP:
                hits[s] = (row, rep, rep1, run_h, start <= posts[-1]["ts"])   # серия упёрлась в глубину выборки — на деле длиннее
                break
    msgs = []
    for s, (row, rep, rep1, run_h, capped) in hits.items():
        fs = _fut_sym(s)
        k = _closed_15m(fs, T, 98) if fs else None
        if not k or len(k) < 97:
            log("ОТДАЧА", s, "— нет фьючерса Binance или свечей за сутки")
            continue
        c = float(k[-1][4]); r24 = c / float(k[-97][4]) - 1; bor = _num(row[0])
        note = (f"отдача за час {rep1 / 1e3:.0f} → {rep / 1e3:.0f} тыс. $ (×{rep / max(rep1, 1.0):.1f}), займ "
                + (f"{bor / 1e6:.2f} млн $" if bor is not None else row[0]) + f", B/R {row[2]}, CHNG {row[3]}, в канале "
                + ("≥" if capped else "") + f"{run_h:.1f} ч, цена за сутки {r24 * 100:+.1f}%")
        if abs(r24) < RP_MOVE:
            log("ОТДАЧА", fs, note, f"— ход цены за сутки меньше {RP_MOVE * 100:g}%")
            continue
        log("ОТДАЧА", fs, note)
        was = _virt_is_open(state, "virtual_RP", fs), _virt_is_open(state, "virtual_RP7", fs)
        m = trader.virt_open(state, "virtual_RP", fs, "RP", note, price=c)
        m7 = trader.virt_open(state, "virtual_RP7", fs, "RP", note, price=c)   # ↩️⁷: те же входы, выход через 7 суток
        new = not was[0] and _virt_is_open(state, "virtual_RP", fs), not was[1] and _virt_is_open(state, "virtual_RP7", fs)
        if not new[1]:
            log("ОТДАЧА", fs, "↩️⁷ без входа: " + ("сделка ещё открыта" if was[1] else "кулдаун или баланс"))
        if all(new):
            msgs.append(m + "\n↩️⁷ тот же шорт, выход через 7 суток")        # обычно журналы входят вместе — одной строкой
        else:
            msgs += [x for x in (m, m7) if x]
    return msgs


RW_X, RW_REP_MIN, RW_MOVE = 1.5, 20e3, 0.05   # 💸: отдача за 4 ч ×1,5 и не меньше 20 тыс. $, ход цены за 4 ч ±5% (research/s21)
RW_BOR_X, RW_BOR_MIN = 1.5, 50e3              # 💸: займ за 4 ч тоже вырос ×1,5 до 50+ тыс. $ — это набор позиций, а не выход
RW_FRESH = 1800                               # 💸: пост с монетой не старше 30 мин к закрытию часа и к отметке 4 ч назад
RW_STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD"}


def wide_due(state):
    """💸 проверяется раз в час: первый проход в течение 10 мин после закрытия часа."""
    T = int(time.time() // 3600 * 3600)
    return state.get("rw_last_T") != T and time.time() - T <= 600


def repay_wide_rule(state, posts):
    """Широкая отдача (журнал 💸, research/s21/ВЫВОДЫ.md, раздел 4): раз в час, на закрытии часа T, по монетам маржинального
    канала. Пост с монетой есть не раньше T − 30 мин и не раньше чем за 30 мин до T − 4 ч (как в бэктесте — последний пост не
    позже отметки); отдача за 24 ч (REP) выросла к значению 4 ч назад в ≥ 1,5 раза и не меньше 20 тыс. $; займ (BOR) при этом
    не вырос в 1,5 раза до 50+ тыс. $; цена фьючерса за 4 ч изменилась на ≥ 5% в любую сторону; у фьючерса есть свечи за
    сутки → виртуальный шорт на 7 суток без тейка, стоп +50%, плечо ×1. Новая сделка по монете — когда прежняя закрыта и с её
    входа прошло ≥ 24 ч (журнал). Только виртуальные сделки. Возвращает сообщения для чата."""
    T = candle_due(state, "rw_last_T", "ОТДАЧА 4Ч", step=3600)
    if T is None:
        return []
    if not posts or posts[-1]["ts"] > T - 4 * 3600 - RW_FRESH:   # проход начался до закрытия часа или канал не ответил
        return candle_retry("rw_last_T", "посты канала не получены на нужную глубину")
    ser = {}
    for q in sorted(posts, key=lambda p: p["ts"]):              # от старых к новым, только посты не позже закрытия часа
        if q["ts"] <= T:
            for s, row in q.get("rows_all", {}).items():
                ser.setdefault(s, []).append((q["ts"], row))
    T4, cands = T - 4 * 3600, []
    for s, sr in ser.items():
        if s in RW_STABLE or T - sr[-1][0] > RW_FRESH:
            continue
        old = [x for x in sr if x[0] <= T4]
        if not old or T4 - old[-1][0] > RW_FRESH:
            continue
        (_, r1), (_, r0) = sr[-1], old[-1]
        bor, rep, bor0, rep0 = _num(r1[0]), _num(r1[1]), _num(r0[0]), _num(r0[1])
        if None in (bor, rep, bor0, rep0) or rep < RW_X * rep0 or rep < RW_REP_MIN:
            continue
        if bor >= RW_BOR_X * bor0 and bor >= RW_BOR_MIN:
            continue                                            # займ тоже вырос — монету набирают, а не отдают
        cands.append((s, bor0, bor, rep0, rep))
    msgs, flat, nofut, miss = [], [], [], []
    for s, bor0, bor, rep0, rep in cands:
        fs = _fut_sym(s)
        k = _closed_15m(fs, T, 98) if fs else None
        if not fs or (k and len(k) < 97):
            nofut.append(s if not fs else f"{fs} (моложе суток)")
            continue
        if not k:
            miss.append(fs)                                     # сбой сети или свеча ещё не закрыта — повтор
            continue
        c = float(k[-1][4]); r4 = c / float(k[-17][4]) - 1
        if abs(r4) < RW_MOVE:
            flat.append(f"{fs} {r4 * 100:+.1f}%")
            continue
        note = (f"отдача за 4 ч {rep0 / 1e3:.0f} → {rep / 1e3:.0f} тыс. $ "
                + (f"(×{rep / rep0:.1f})" if rep0 >= 1e3 else "(4 ч назад отдачи не было)")
                + f", займ {bor0 / 1e6:.2f} → {bor / 1e6:.2f} млн $, цена за 4 ч {r4 * 100:+.1f}%")
        was = _virt_is_open(state, "virtual_RW", fs)
        m = trader.virt_open(state, "virtual_RW", fs, "RW", note, price=c)
        opened = not was and _virt_is_open(state, "virtual_RW", fs)
        log("ОТДАЧА 4Ч", fs, note + ("" if opened else " — сделка ещё открыта" if was else " — без входа: кулдаун 24 ч или баланс"))
        if m:
            msgs.append(m)
    if miss and time.time() - T < 480:
        # свечи не получены: час не отмечается, следующий проход (до 8 мин после закрытия) повторит проверку; уже открытые
        # сделки повторно не откроются (у монеты открыта сделка), остальные монеты проверятся заново
        _skip_why["rw_last_T"] = "Binance не отдал свечи по " + ", ".join(miss)
    else:
        candle_done(state, "rw_last_T", T)
        hh = f"{datetime.fromtimestamp(T, timezone.utc):%d.%m %H:%M}"
        if flat:
            log("ОТДАЧА 4Ч", f"{hh}: отдача выросла, но ход цены за 4 ч меньше {RW_MOVE * 100:g}% —", ", ".join(flat))
        if nofut:
            log("ОТДАЧА 4Ч", f"{hh}: отдача выросла, но нет фьючерса Binance —", ", ".join(nofut))
        if miss:
            log("ОТДАЧА 4Ч", f"{hh}: Binance так и не отдал свечи —", ", ".join(miss))
    if len(msgs) > 1:                                           # всплески отдачи идут волнами — одно сообщение на час
        return [f"💸 Широкая отдача на закрытии часа {datetime.fromtimestamp(T, timezone.utc):%d.%m %H:%M} UTC: "
                f"{len(msgs)} шорт(ов)\n" + "\n".join(msgs)]
    return msgs


KR_SHARE_MIN = 0.20                    # корейский шорт: доля Upbit + Bithumb в объёме за час (вместе с фьючерсом Binance)
_kr_markets = {"ts": 0, "upbit": set(), "bithumb": set()}


def _kr_list():
    """KRW-рынки Upbit и Bithumb: кэш на 6 ч; если биржа не ответила — прежний список и повтор через 10 мин."""
    if time.time() - _kr_markets["ts"] > 6 * 3600:
        ok = True
        for ex, url in (("upbit", "https://api.upbit.com/v1/market/all"), ("bithumb", "https://api.bithumb.com/v1/market/all")):
            j = http_json(url, 15)
            if isinstance(j, list) and j:
                _kr_markets[ex] = {str(x.get("market", ""))[4:] for x in j if str(x.get("market", "")).startswith("KRW-")}
            else:
                ok = False
        _kr_markets["ts"] = time.time() if ok else time.time() - 6 * 3600 + 600
    return _kr_markets


def _kr_volume(ex, coin, T):
    """Объём KRW-рынка монеты на бирже ex за 4 закрытые 15-мин свечи до T, в долларах (по KRW-USDT той же биржи).
    None — биржа не ответила. Upbit ждёт время в UTC с «Z», Bithumb — в KST без зоны; граница to — не включительно."""
    base = {"upbit": "https://api.upbit.com", "bithumb": "https://api.bithumb.com"}[ex]
    to = (datetime.fromtimestamp(T, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ex == "upbit"
          else datetime.fromtimestamp(T + 9 * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    c = http_json(f"{base}/v1/candles/minutes/15?market=KRW-{coin}&to={to}&count=4", 15)
    fx = http_json(f"{base}/v1/candles/minutes/15?market=KRW-USDT&to={to}&count=1", 15)
    try:
        krw = sum(float(x["candle_acc_trade_price"]) for x in c
                  if T - 3600 <= datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=timezone.utc).timestamp() < T)
        return krw / float(fx[0]["trade_price"])
    except (TypeError, KeyError, ValueError, IndexError, ZeroDivisionError):
        return None


def _pump_at(k):
    """Памп как в бэктесте (research/mm2/load2y.py, detect): последняя закрытая свеча — первая за сутки, где максимум после
    «спокойной» свечи из последних 2 ч (до неё 2 ч цена в пределах ±5%) достиг +15% от её закрытия. Индекс базы или None."""
    c = [float(x[4]) for x in k]; h = [float(x[2]) for x in k]; n = len(k); last = -10**9
    for j in range(9, n):
        if j - last < 96:
            continue
        base = None
        for i in range(max(8, j - 8), j):
            if abs(c[i] / c[i - 8] - 1) <= 0.05 and max(h[i + 1:j + 1]) >= c[i] * 1.15:
                base = i
        if base is not None:
            last = j
            if j == n - 1:
                return base
    return None


def _pump_times(k):
    """Все пампы в свечах k по тому же правилу, что _pump_at: время закрытия свечи-триггера (первой за сутки)."""
    c = [float(x[4]) for x in k]; h = [float(x[2]) for x in k]; last = -10**9; out = []
    for j in range(9, len(k)):
        if j - last < 96:
            continue
        if any(abs(c[i] / c[i - 8] - 1) <= 0.05 and max(h[i + 1:j + 1]) >= c[i] * 1.15 for i in range(max(8, j - 8), j)):
            last = j; out.append(int(k[j][0]) // 1000 + 900)
    return out


KRS_SCORE_MIN = 3                      # 🇰🇷⭐: сколько из шести условий должно выполняться


def korea_star(s, k, i, T, share, n24, btc24):
    """Счёт условий для корейского шорта (журнал 🇰🇷⭐, research/s6/ВЫВОДЫ.md): пампов на рынке за сутки ≥ 16 (ажиотаж),
    BTC за сутки ≥ 0, цена выше максимума 7 дней до базы пампа, покупки тейкеров на фьючерсе в пампе ≤ 51%, доля Кореи ≥ 40%,
    воскресенье по UTC (с 22.10.2026, research/s7/ВЫВОДЫ.md). k — свечи пампа (последняя — триггер), i — индекс базы в k.
    Возвращает (счёт ≥ KRS_SCORE_MIN, пояснение)."""
    k7 = _closed_15m(s, T, 700); hi7 = None
    if k7 and len(k7) >= 673:
        i7 = len(k7) - (len(k) - i)                                  # та же база в недельном окне
        hi7 = float(k7[-1][4]) / max(float(x[2]) for x in k7[len(k7) - 673:i7 + 1]) - 1
    pk = k[i + 1:]; qv = sum(float(x[7]) for x in pk)
    tbp = sum(float(x[10]) for x in pk) / qv if qv > 0 else None
    pct = lambda v, f: f.format(v * 100) if v is not None else "нет данных"
    conds = [("пампов на рынке за сутки", n24 >= 16, str(n24)),
             ("BTC за сутки", btc24 is not None and btc24 >= 0, pct(btc24, "{:+.1f}%")),
             ("к максимуму 7 дней", hi7 is not None and hi7 >= 0, pct(hi7, "{:+.1f}%")),
             ("покупки тейкеров в пампе", tbp is not None and tbp <= 0.51, pct(tbp, "{:.1f}%")),
             ("доля Кореи", share >= 0.4, pct(share, "{:.0f}%")),
             ("воскресенье (UTC)", datetime.fromtimestamp(T, timezone.utc).weekday() == 6, "да" if datetime.fromtimestamp(T, timezone.utc).weekday() == 6 else "нет")]
    sc = sum(ok for _, ok, _ in conds)
    return sc >= KRS_SCORE_MIN, f"счёт {sc}/{len(conds)}: " + ", ".join(f"{nm} {v} {'✓' if ok else '✗'}" for nm, ok, v in conds)


NR_SPOT_MAX, NR_NORM_MIN, NR_KR_MAX, NR_TR_MAX = 0.12, 0.03, 0.20, 0.10   # лонг «памп без розницы»: доли за час и обычная доля спота


def noretail_check(s, coin, T, fut, kr_share, spot):
    """Лонг «памп без розницы» (журнал 🟩, research/s5/ВЫВОДЫ.md) для пампа, найденного korea_rule: у монеты есть спот Binance
    к USDT (торгуется ≥ 8 суток, обычная доля ≥ 3% — медиана часовых долей за 7 суток), а в час пампа спот дал < 12% объёма
    (вместе с фьючерсом), Корея < 20%, пара к лире < 10%. spot — цены спота Binance {пара: цена}. Возвращает (подходит, пояснение)."""
    if kr_share is None:
        return False, "доля Кореи неизвестна"
    name = next((n for n in (s, coin) if f"{n}USDT" in spot), None)
    if not name:
        return False, "нет спота Binance"
    sk = spot_json(f"/api/v3/klines?symbol={name}USDT&interval=15m&endTime={T * 1000 - 1}&limit=1000")
    if not isinstance(sk, list):
        return False, "Binance не отдал свечи спота — проверка не сделана"
    if not sk or int(sk[0][0]) // 1000 > T - 8 * 86400:
        return False, "спот торгуется меньше 8 суток"
    sv = {int(x[0]) // 1000: float(x[7]) for x in sk}
    sp = sum(sv.get(T - 900 * i, 0.0) for i in range(1, 5))
    share = sp / max(sp + fut, 1)
    tr_share, tname = 0.0, next((n for n in (s, coin) if f"{n}TRY" in spot), None)
    if tname:
        tk = spot_json(f"/api/v3/klines?symbol={tname}TRY&interval=15m&endTime={T * 1000 - 1}&limit=4")
        if not isinstance(tk, list):
            return False, "Binance не отдал свечи пары к лире — проверка не сделана"
        try:
            tr = sum(float(x[7]) for x in tk if T - 3600 <= int(x[0]) // 1000 < T) / float(spot["USDTTRY"])
        except (TypeError, KeyError, ValueError, ZeroDivisionError):
            return False, "нет данных по паре к лире"
        tr_share = tr / max(tr + fut, 1)
    why = f"спот Binance {share * 100:.1f}% объёма за час, Корея {kr_share * 100:.0f}%, лира {tr_share * 100:.1f}%"
    if share >= NR_SPOT_MAX or kr_share >= NR_KR_MAX or tr_share >= NR_TR_MAX:
        return False, why
    # обычная доля спота: медиана долей за 167 часов до часа пампа (часы отсчитываются от закрытия свечи пампа, как в бэктесте)
    fk = _closed_15m(s, T, 673)
    if fk is None:
        return False, why + "; Binance не отдал свечи фьючерса за неделю — проверка не сделана"
    if len(fk) < 672:
        return False, why + "; фьючерс торгуется меньше недели"
    fv = {int(x[0]) // 1000: float(x[7]) for x in fk}
    hs = []
    for h in range(1, 168):
        a = T - 3600 * (h + 1)
        sh_, fh_ = (sum(d.get(a + 900 * i, 0.0) for i in range(4)) for d in (sv, fv))
        hs.append(sh_ / max(sh_ + fh_, 1))
    norm = sorted(hs)[len(hs) // 2]
    return norm >= NR_NORM_MIN, why + f"; обычная доля спота {norm * 100:.1f}%"


SP_SHARE_MIN = 0.26                    # 🛒: доля спота Binance в обороте последнего полного часа (research/s49)


def spot_pump_check(s, coin, T, k, spot):
    """Шорт «памп на споте» (журнал 🛒, research/s49/ВЫВОДЫ.md) для пампа, найденного korea_rule: доля спота Binance к USDT
    в обороте за последний полный час по часам (спот / (спот + фьючерс Binance), как в бэктесте: час, который закончился
    не позже закрытия свечи пампа T) ≥ 26%. k — 15-мин свечи фьючерса до T включительно, spot — цены спота {пара: цена}.
    Возвращает (подходит, пояснение)."""
    name = next((n for n in (s, coin) if f"{n}USDT" in spot), None)
    if not name:
        return False, "нет спота Binance"
    H = (T // 3600) * 3600                                         # конец последнего полного часа
    sk = spot_json(f"/api/v3/klines?symbol={name}USDT&interval=15m&endTime={H * 1000 - 1}&limit=4")
    if not isinstance(sk, list):
        return False, "Binance не отдал свечи спота — проверка не сделана"
    sp = sum(float(x[7]) for x in sk if H - 3600 <= int(x[0]) // 1000 < H)
    fut = sum(float(x[7]) for x in k if H - 3600 <= int(x[0]) // 1000 < H)
    share = sp / max(sp + fut, 1.0)
    hh = datetime.fromtimestamp(H - 3600, timezone.utc).strftime("%H:%M")
    return share >= SP_SHARE_MIN, (f"спот Binance {share * 100:.1f}% оборота за час {hh} UTC (спот {sp / 1e6:.2f} млн $, "
                                   f"фьючерс {fut / 1e6:.2f} млн $; порог {SP_SHARE_MIN * 100:.0f}%)")


_t24 = {"t": 0, "data": None}


def ticker24():
    """Цены фьючерсов Binance за сутки (ticker/24hr: ~600 контрактов, вес 40) — один запрос на проход для 🇰🇷 и 🇹🇷."""
    if time.time() - _t24["t"] > 120 or not isinstance(_t24["data"], list):
        _t24["data"] = http_json("https://fapi.binance.com/fapi/v1/ticker/24hr", 20)
        _t24["t"] = time.time()
    return _t24["data"]


KRF_FUND_MIN = -0.001                  # 🇰🇷ᶠ: не входить при фандинге на последнем начислении ниже −0,1% за 8 ч (research/s20)


def _virt_is_open(state, key, sym):
    return any(t["sym"] == sym and not t.get("closed") for t in state.get(key, {}).get("trades", []))


def kr_open(state, s, note, c, T):
    """Вход 🇰🇷 и его двойника 🇰🇷ᶠ (research/s20/ВЫВОДЫ.md). 🇰🇷ᶠ входит в ту же сделку, если фандинг монеты на последнем
    начислении (в пересчёте на 8 ч) не ниже −0,1% или Binance его не отдал (как в бэктесте). Совместный вход — одной
    строкой к сообщению 🇰🇷. Возвращает сообщения для чата."""
    fr = trader.funding_rates(s, T - 2 * 86400)
    f8 = fr[-1][1] if fr else None
    fnote = f"фандинг на последнем начислении {f8 * 100:+.3f}%/8 ч" if f8 is not None else "фандинг: Binance не отдал"
    twin = f8 is None or f8 > KRF_FUND_MIN
    was = _virt_is_open(state, "virtual_KR", s), _virt_is_open(state, "virtual_KRF", s)
    m = trader.virt_open(state, "virtual_KR", s, "KR", note, price=c)
    mf = trader.virt_open(state, "virtual_KRF", s, "KR", f"{note}; {fnote}", price=c) if twin else None
    new = not was[0] and _virt_is_open(state, "virtual_KR", s), not was[1] and _virt_is_open(state, "virtual_KRF", s)
    log("КОРЕЯ ᶠ", s, fnote + (" → 🇰🇷ᶠ вход" if new[1] else " → 🇰🇷ᶠ без входа" if not twin else " → 🇰🇷ᶠ сделка уже открыта"))
    if new[0] and new[1]:
        return [m + f"\n🇰🇷ᶠ тот же шорт ({fnote})"]
    if new[0] and not twin:
        return [m + f"\n🇰🇷ᶠ без входа: {fnote}, ниже −0,1%"]
    return [x for x in (m, mf) if x]


def korea_rule(state):
    """Корейский шорт (журнал 🇰🇷, research/mm2/ВЫВОДЫ.md): раз в 15 мин, на закрытии свечи, по всем фьючерсам Binance —
    памп +15% за ≤ 2 ч из покоя; если за последний час Upbit + Bithumb дали ≥ 20% объёма (вместе с фьючерсом Binance) —
    виртуальный шорт; при ≥ 3 из 6 условий (korea_star) — ещё и шорт 🇰🇷⭐ (тейк 7 / стоп 20). Тот же памп без розницы
    (noretail_check) — виртуальный лонг 🟩. Только виртуальные сделки. Возвращает сообщения для чата."""
    T = candle_due(state, "kr_last_T", "КОРЕЯ")
    if T is None:
        return []
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    tick = ticker24()
    if not isinstance(tick, list):
        return candle_retry("kr_last_T", "Binance не отдал цены фьючерсов за сутки (ticker/24hr)")
    candle_done(state, "kr_last_T", T)
    cands = []
    for x in tick:
        s = str(x.get("symbol", ""))
        try:
            hi, lo = float(x["highPrice"]), float(x["lowPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if s in trader._contracts and lo > 0 and hi >= lo * 1.15:     # памп +15% за 2 ч виден и в размахе за сутки
            cands.append(s[:-4])
    with ThreadPoolExecutor(8) as ex:
        ks = dict(zip(cands, ex.map(lambda s: _closed_15m(s, T, 481), cands)))   # 5 суток: суточная пауза между пампами — как в бэктесте
    # пампы рынка за сутки до T (для 🇰🇷⭐): журнал найденных пампов + пампы в свечах кандидатов (если бот перезапускался)
    plog = [p for p in state.get("pump_log", []) if p[1] >= T - 26 * 3600]
    seen = {(p[0], p[1]) for p in plog if T - 86400 <= p[1] < T}
    for s in cands:
        seen |= {(s, tt) for tt in _pump_times(ks.get(s) or []) if T - 86400 <= tt < T}
    n24 = len(seen); btc24 = None
    kr = _kr_list(); msgs = []; spot = None
    missing = [ex for ex in ("upbit", "bithumb") if not kr[ex]]   # список KRW-рынков биржи не загрузился
    miss = [s for s in cands if ks.get(s) is None]
    if miss:
        log("КОРЕЯ", "пампы не проверены — Binance не отдал свечи:", ", ".join(miss))
    for s in cands:
        k = ks.get(s)
        if not k or len(k) < 20:
            continue
        i = _pump_at(k)
        if i is None:
            continue
        plog.append([s, T])
        coin = re.sub(r"^(1000000|100000|10000|1000)", "", s)
        c0, c = float(k[i][4]), float(k[-1][4]); hi = max(float(x[2]) for x in k[i + 1:])
        fut = sum(float(x[7]) for x in k[-4:])
        head = f"памп {(hi / c0 - 1) * 100:+.0f}% за {(len(k) - 1 - i) * 15} мин из покоя (закрытие {(c / c0 - 1) * 100:+.0f}%)"
        exs = [ex for ex in ("upbit", "bithumb") if coin in kr[ex]]
        if not exs:
            if missing:
                log("КОРЕЯ", s, head, f"— не загружен список рынков {'/'.join(e.capitalize() for e in missing)}, доля Кореи неизвестна")
            else:
                log("КОРЕЯ", s, head, "— монеты нет на Upbit/Bithumb")
            kr_share = None if missing else 0.0
        else:
            vols = {ex: _kr_volume(ex, coin, T) for ex in exs}
            got = sum(v for v in vols.values() if v is not None)
            share = got / (got + fut) if got + fut > 0 else 0.0
            kr_share = share if all(v is not None for v in vols.values()) and not missing else None
            note = (f"{head}; доля Кореи за час {share * 100:.0f}% ("
                    + ", ".join(f"{ex.capitalize()} {v / 1e6:.2f} млн $" if v is not None else f"{ex.capitalize()}: нет данных"
                                for ex, v in vols.items())
                    + f", фьючерс Binance {fut / 1e6:.2f} млн $)")
            log("КОРЕЯ", s, note)
            if share >= KR_SHARE_MIN:
                msgs += kr_open(state, s, note, c, T)
                if btc24 is None:                             # BTC за сутки — один раз за проход (98: текущая незакрытая свеча отбрасывается)
                    kb = _closed_15m("BTC", T, 98)
                    btc24 = float(kb[-1][4]) / float(kb[-97][4]) - 1 if kb and len(kb) >= 97 else float("nan")
                ok, why = korea_star(s, k, i, T, share, n24, btc24 if btc24 == btc24 else None)
                log("КОРЕЯ⭐", s, why + (" → шорт 🇰🇷⭐" if ok else ""))
                if ok:
                    m = trader.virt_open(state, "virtual_KRS", s, "KR⭐", f"{note}; {why}", price=c)
                    if m:
                        msgs.append(m)
        if spot is None:                                      # цены спота Binance — один раз за проход, когда есть памп
            px = spot_json("/api/v3/ticker/price")
            spot = {str(x.get("symbol")): x.get("price") for x in px} if isinstance(px, list) else {}
        if not spot:
            log("РОЗНИЦА", s, f"{head}; Binance не отдал цены спота — проверка не сделана")
            spot = None                                       # у следующего пампа этой свечи — новая попытка
            continue
        try:                                                   # 🛒 памп на споте (research/s49)
            ok_sp, why_sp = spot_pump_check(s, coin, T, k, spot)
            log("СПОТ-ПАМП", s, f"{head}; {why_sp}" + (" → шорт 🛒" if ok_sp else ""))
            if ok_sp:
                m = trader.virt_open(state, "virtual_SP", s, "SP", f"{head}; {why_sp}", price=c)
                if m:
                    msgs.append(m)
        except Exception as e:
            log("СПОТ-ПАМП", s, f"ошибка проверки: {e!r}")
        ok, why = noretail_check(s, coin, T, fut, kr_share, spot)
        log("РОЗНИЦА", s, f"{head}; {why}" + (" → лонг 🟩" if ok else ""))
        if ok:
            m = trader.virt_open(state, "virtual_L", s, "NR", f"{head}; {why}", price=c)
            if m:
                msgs.append(m)
    state["pump_log"] = plog
    return msgs


TR_SHARE_MIN, TR_NORM_X, TR_RISE_4H, TR_VOL_MIN = 0.10, 3.0, 0.10, 200e3   # турецкий набег: доля лиры за час, × к обычной, рост за 4 ч, объём за час $
SPOT_HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")  # второй — публичное зеркало рыночных данных Binance


def spot_json(path, timeout=15):
    """Спот Binance: основной адрес, при сбое — зеркало рыночных данных."""
    for host in SPOT_HOSTS:
        j = http_json(host + path, timeout)
        if j is not None and not (isinstance(j, dict) and j.get("code")):
            return j
    return None


def turkey_rule(state):
    """Турецкий набег (журнал 🇹🇷, research/s2/ВЫВОДЫ.md): раз в 15 мин, на закрытии свечи, по фьючерсам Binance, у которых есть
    спотовая пара к турецкой лире: фьючерс за 4 ч вырос на 10%+, доля пары к лире в объёме за час (спот в $ + фьючерс) ≥ 10%
    и в 3+ раза выше обычной (медиана часовых долей за 7 суток) → виртуальный шорт. Возвращает сообщения для чата."""
    T = candle_due(state, "tr_last_T", "ТУРЦИЯ")
    if T is None:
        return []
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    px = spot_json("/api/v3/ticker/price")
    if not isinstance(px, list):
        return candle_retry("tr_last_T", "Binance не отдал цены спота")
    spot = {str(x.get("symbol")): x.get("price") for x in px}
    try:
        usdtry = float(spot["USDTTRY"])
    except (KeyError, TypeError, ValueError):
        return candle_retry("tr_last_T", "нет курса USDT/TRY")
    tick = ticker24()
    if not isinstance(tick, list):
        return candle_retry("tr_last_T", "Binance не отдал цены фьючерсов за сутки (ticker/24hr)")
    candle_done(state, "tr_last_T", T)
    cands = []
    for x in tick:
        s = str(x.get("symbol", ""))
        if s not in trader._contracts:
            continue
        sym = s[:-4]
        name = next((n for n in (sym, re.sub(r"^(1000000|100000|10000|1000)", "", sym)) if f"{n}TRY" in spot), None)
        try:
            hi, lo = float(x["highPrice"]), float(x["lowPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if name and lo > 0 and hi >= lo * (1 + TR_RISE_4H):        # рост за 4 ч на 10% виден и в размахе за сутки
            cands.append((sym, name))
    with ThreadPoolExecutor(8) as ex:
        ks = dict(zip([s for s, _ in cands], ex.map(lambda c: _closed_15m(c[0], T, 18), cands)))
    msgs = []; H = T // 3600 * 3600; miss_s = []
    miss_f = [sym for sym, _ in cands if ks.get(sym) is None]
    for sym, name in cands:
        k = ks.get(sym)
        if not k or len(k) < 17:
            continue
        c = float(k[-1][4]); r4 = c / float(k[-17][4]) - 1
        if r4 < TR_RISE_4H:
            continue
        fut = sum(float(x[7]) for x in k[-4:])
        sk = spot_json(f"/api/v3/klines?symbol={name}TRY&interval=15m&endTime={T * 1000 - 1}&limit=4")
        if not isinstance(sk, list):
            miss_s.append(sym)
            continue
        tr = sum(float(x[7]) for x in sk if T - 3600 <= int(x[0]) // 1000 < T) / usdtry
        share = tr / (tr + fut) if tr + fut > 0 else 0.0
        head = (f"рост за 4 ч {r4 * 100:+.0f}%, доля лиры за час {share * 100:.1f}% "
                f"(спот {name}/TRY {tr / 1e3:.0f} тыс. $, фьючерс {fut / 1e3:.0f} тыс. $)")
        if share < TR_SHARE_MIN or tr + fut < TR_VOL_MIN:
            if share >= TR_SHARE_MIN / 2:                             # в журнал — только близкие к порогу
                log("ТУРЦИЯ", sym, head, "— меньше порога")
            continue
        # обычная доля — медиана часовых долей за 7 суток до последнего часа; пара к лире должна торговаться ≥ 8 суток
        end = (H - 3600) * 1000 - 1
        sh = spot_json(f"/api/v3/klines?symbol={name}TRY&interval=1h&endTime={end}&limit=192")
        fh = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=1h&endTime={end}&limit=168", 15)
        if not isinstance(sh, list) or not isinstance(fh, list):
            log("ТУРЦИЯ", sym, head, "— Binance не отдал часовые свечи за неделю, проверка не сделана")
            continue
        if not sh or len(fh) < 150 or int(sh[0][0]) // 1000 > H - 192 * 3600:
            log("ТУРЦИЯ", sym, head, "— нет истории за неделю (пара или фьючерс моложе)")
            continue
        sv = {int(x[0]): float(x[7]) / usdtry for x in sh}
        hs = sorted(sv.get(int(x[0]), 0.0) / (sv.get(int(x[0]), 0.0) + float(x[7]) + 1e-9) for x in fh)
        norm = (hs[len(hs) // 2] + hs[(len(hs) - 1) // 2]) / 2
        note = f"{head}; обычно {norm * 100:.1f}%, в {share / max(norm, 1e-4):.1f} раза больше"
        log("ТУРЦИЯ", sym, note)
        if share >= TR_NORM_X * max(norm, 1e-4):
            m = trader.virt_open(state, "virtual_TR", sym, "TR", note, price=c)
            if m:
                msgs.append(m)
    if miss_f:
        log("ТУРЦИЯ", "рост за 4 ч не проверен — Binance не отдал свечи фьючерса:", ", ".join(miss_f))
    if miss_s:
        log("ТУРЦИЯ", "доля лиры не проверена — Binance не отдал свечи пары к лире:", ", ".join(miss_s))
    return msgs


BF_LOOK_D, BF_TOP, BF_KEEP = 7, 10, 5                  # 🏦 фактор займа: окно постов (суток), топ по постам, сколько самых волатильных шортим
BF_VOL_MIN, BF_FUND_MIN, BF_AGE_D = 10e6, -0.001, 30   # объём фьючерса за 7 суток, $/сут; фандинг за 8 ч (доля); возраст фьючерса, суток
BF_HOUR, BF_LATE_H, BF_GAP_H = 1, 3, 2                 # проверка в 01:00 UTC, не позже 04:00; пауза в журнале постов > 2 ч — догрузка канала
BF_FILE = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "margin_posts.json")
_bf_log = None                                         # {id поста: [время, "МОНЕТА МОНЕТА …"]} за 8 суток


def bf_record(posts):
    """Дописывает посты маржинального канала (все монеты поста) в журнал 🏦 — файл margin_posts.json рядом с state.json;
    хранит 8 суток."""
    global _bf_log
    if _bf_log is None:
        try:
            with open(BF_FILE) as f:
                _bf_log = {int(k): v for k, v in json.load(f).items()}
        except Exception:
            _bf_log = {}
    changed = False
    for p in posts:
        if p["id"] not in _bf_log:
            _bf_log[p["id"]] = [int(p["ts"]), " ".join(sorted(p.get("rows_all") or {}))]
            changed = True
    old = time.time() - (BF_LOOK_D + 1) * 86400
    for k in [k for k, v in _bf_log.items() if v[0] < old]:
        del _bf_log[k]
        changed = True
    if changed:
        try:
            with open(BF_FILE + ".tmp", "w") as f:
                f.write(json.dumps(_bf_log, separators=(",", ":")))
            os.replace(BF_FILE + ".tmp", BF_FILE)
        except OSError as e:
            log("ФАКТОР ЗАЙМА", "журнал постов не записан:", e)


def bf_pick(cnt, T, fut, kl, fund):
    """Выбор 🏦 (как в research/s10/journal_sim2.py): монеты по убыванию числа постов за 7 суток; фьючерс старше 30 суток,
    объём за 7 суток до T ≥ 10 млн $/сут, фандинг не дешевле −0,1% за 8 ч → первые 10; из них 5 самых волатильных
    (стандартное отклонение 15-мин лог-доходностей за 7 суток × √96). fut(монета) → (фьючерс, время запуска) или None;
    kl(фьючерс) → 673 закрытые к T 15-мин свечи (меньше — фьючерс моложе) или None при сбое; fund(фьючерс) → фандинг в час
    или None. Возвращает (топ, выбор, сбои): [(монета, фьючерс, постов, объём $/сут, волатильность, фандинг за 8 ч, цена)]."""
    top, miss = [], []
    order = sorted(cnt, key=lambda c: (-cnt[c], c))
    with ThreadPoolExecutor(8) as ex:
        for i in range(0, len(order), 16):
            cand = []
            for c in order[i:i + 16]:
                f = fut(c)
                if f and f[1] <= T - BF_AGE_D * 86400:       # нет бессрочного фьючерса или он моложе 30 суток — мимо
                    cand.append((c, f[0]))
            for (c, fs), k in zip(cand, ex.map(lambda x: kl(x[1]), cand)):
                if k is None:
                    miss.append(fs)
                    continue
                if len(k) < 673:
                    continue
                v7 = sum(float(x[7]) for x in k[-672:]) / 7
                if v7 < BF_VOL_MIN:
                    continue
                fh = fund(fs)
                f8 = fh * 8 if fh is not None else None
                if f8 is not None and f8 < BF_FUND_MIN:
                    continue
                cl = [float(x[4]) for x in k[-673:]]
                lr = [math.log(b / a) for a, b in zip(cl, cl[1:])]
                m = sum(lr) / len(lr)
                top.append((c, fs, cnt[c], v7, math.sqrt(sum((x - m) ** 2 for x in lr) / len(lr) * 96), f8, cl[-1]))
                if len(top) == BF_TOP:
                    break
            if len(top) == BF_TOP:
                break
    return top, sorted(top, key=lambda x: -x[4])[:BF_KEEP], miss


BFM_CAP = 30e6         # 🏦ᵐ: без входа при капитализации свободного оборота (монеты в обращении CMC × цена) < 30 млн $ (s98)


def _bf_open(state, fs, note, px):
    """Вход 🏦 и его двойников: 🏦³ (те же входы, стоп +300%) и 🏦ᵐ (те же входы, кроме монет с капитализацией свободного
    оборота меньше 30 млн $; монеты в обращении — список разлоков CoinMarketCap, state["ul"]["circ"]; нет данных — вход).
    Совместный вход — одной строкой к сообщению 🏦. Возвращает сообщения для чата."""
    def is_open(key):
        return any(t["sym"] == fs and not t.get("closed") for t in state.get(key, {}).get("trades", []))
    circ = (state.get("ul", {}).get("circ") or {}).get(fs)
    cap = circ * px if circ and px else None
    cnote = (f"капитализация свободного оборота {cap / 1e6:.0f} млн $" if cap is not None
             else "капитализация свободного оборота: нет данных CoinMarketCap")
    small = cap is not None and cap < BFM_CAP
    was = is_open("virtual_BF"), is_open("virtual_BF3"), is_open("virtual_BFM")
    m = trader.virt_open(state, "virtual_BF", fs, "BF", note, price=px)
    m3 = trader.virt_open(state, "virtual_BF3", fs, "BF", note, price=px)          # 🏦³: те же входы, стоп +300%
    mm = None if small else trader.virt_open(state, "virtual_BFM", fs, "BF", f"{note}; {cnote}", price=px)
    new = (not was[0] and is_open("virtual_BF"), not was[1] and is_open("virtual_BF3"), not was[2] and is_open("virtual_BFM"))
    log("ФАКТОР ЗАЙМА", fs, note + ("" if new[0] else " — 🏦 уже открыта") + ("" if new[1] else "; 🏦³ уже открыта")
        + (f"; 🏦ᵐ без входа: {cnote} — меньше {BFM_CAP / 1e6:.0f} млн $" if small
           else f"; {cnote}" + ("" if new[2] else ", 🏦ᵐ уже открыта")))
    if new[0] and new[1]:                                     # обычно журналы входят вместе — одной строкой
        line = m + "\n🏦³ тот же шорт, стоп +300%"
        if new[2]:
            line += f"\n🏦ᵐ тот же шорт ({cnote})"
        elif small:
            line += f"\n🏦ᵐ без входа: {cnote} — меньше {BFM_CAP / 1e6:.0f} млн $"
        else:
            line += f"\n🏦ᵐ сделка уже открыта"
        return [line]
    return [x for x in (m, m3, mm) if x]


def borrow_factor_rule(state):
    """Фактор займа (журнал 🏦, research/s10/ВЫВОДЫ.md): раз в сутки, в первый проход после 01:00 UTC (если бот лежал — до 04:00).
    Для каждой монеты — сколько постов маржинального канала за 7 суток до 00:00 UTC её упоминали (журнал margin_posts.json;
    если в нём пауза дольше 2 ч — догружаем 7 суток канала). Среди фьючерсов Binance старше 30 суток с объёмом за 7 суток
    ≥ 10 млн $/сут и фандингом не дешевле −0,1% за 8 ч — 10 монет с наибольшим числом постов, из них 5 самых волатильных →
    виртуальный шорт на 7 суток без тейка, плечо ×1. Если Binance не отдал свечи — повтор через 5 мин (до 4 попыток).
    Возвращает сообщения для чата."""
    now = time.time(); day0 = int(now // 86400 * 86400); T = day0 + BF_HOUR * 3600
    day = datetime.fromtimestamp(day0, timezone.utc).strftime("%d.%m")
    if now < T or state.get("bf_day") == day0:
        return []
    if now > T + BF_LATE_H * 3600:
        state["bf_day"] = day0
        log("ФАКТОР ЗАЙМА", f"{day} не проверен: проход начался в {datetime.fromtimestamp(now, timezone.utc):%H:%M} UTC, "
            f"позже {BF_HOUR + BF_LATE_H:02d}:00")
        return []
    if now - state.get("bf_try", 0) < 300:
        return []
    state["bf_try"] = now
    tries = state["bf_tries"] = state.get("bf_tries", 0) + 1 if state.get("bf_tries_day") == day0 else 1
    state["bf_tries_day"] = day0
    last = tries >= 4 or now > T + BF_LATE_H * 3600 - 600       # последняя попытка — считаем по тому, что есть
    lo = day0 - BF_LOOK_D * 86400
    bf_record([])

    def coverage():
        ts = sorted(v[0] for v in _bf_log.values() if lo <= v[0] < day0)
        return ts, max(b - a for a, b in zip([lo] + ts, ts + [day0]))
    ts, gap = coverage()
    if gap > BF_GAP_H * 3600:
        bf_record(fetch_posts((now - lo) / 3600 + 1, max_pages=250))
        ts, gap = coverage()
        if gap > BF_GAP_H * 3600 and not last:
            log("ФАКТОР ЗАЙМА", f"{day}: в постах канала за 7 суток пауза {gap / 3600:.1f} ч — повтор через 5 мин")
            return []
    cnt = {}
    for t0, coins in _bf_log.values():
        if lo <= t0 < day0:
            for c in coins.split():
                cnt[c] = cnt.get(c, 0) + 1
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    if not ts or not trader._contracts:
        if last:
            state["bf_day"] = day0
        log("ФАКТОР ЗАЙМА", f"{day}: " + ("нет постов канала за 7 суток" if not ts else "Binance не отдал список фьючерсов")
            + ("" if last else " — повтор через 5 мин"))
        return []

    def fut(c):
        fs = _fut_sym(c)
        return (fs, (trader.contract(fs) or {}).get("onboard", 0)) if fs else None

    def kl(fs):
        j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={fs}USDT&interval=15m&endTime={T * 1000 - 1}&limit=673", 20)
        if not isinstance(j, list) or (j and int(j[-1][0]) // 1000 != T - 900):
            return None
        return j
    top, keep, miss = bf_pick(cnt, T, fut, kl, trader.funding_hourly)
    if miss and not last:
        log("ФАКТОР ЗАЙМА", f"{day}: Binance не отдал свечи {', '.join(miss)} — повтор через 5 мин")
        return []
    state["bf_day"] = day0
    n = len(ts); rank = {c: i + 1 for i, c in enumerate(sorted(cnt, key=lambda c: (-cnt[c], c)))}
    log("ФАКТОР ЗАЙМА", f"{day}: постов за 7 суток {n}, самая длинная пауза {gap / 3600:.1f} ч; топ-10 (доля постов / волатильность "
        "за сутки): " + ", ".join(f"{x[1]} {x[2] / n * 100:.0f}%/{x[4] * 100:.1f}%" for x in top)
        + (f"; без свечей Binance: {', '.join(miss)}" if miss else ""))
    msgs = []
    for c, fs, k, v7, vola, f8, px in keep:
        note = (f"в канале {k / n * 100:.0f}% постов за 7 суток ({k} из {n}, место {rank[c]}), объём {v7 / 1e6:.0f} млн $/сут, "
                f"волатильность {vola * 100:.1f}%/сут, фандинг " + (f"{f8 * 100:+.3f}%/8 ч" if f8 is not None else "нет данных"))
        msgs += _bf_open(state, fs, note, px)
    if not msgs:
        return []
    return [f"🏦 Фактор займа на {day}: 5 самых волатильных из 10 монет, чаще всех бывших в маржинальном канале за 7 суток\n"
            + "\n".join(msgs)]


ANN_LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo={page}&pageSize={size}&catalogId={cat}"
ANN_DETAIL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={code}"
ANN_CATS = (48, 49, 161)                   # разделы: новые листинги, новости (там Monitoring Tag), делистинг
AN_FRESH_MIN, AN_FUND_MIN = 60, -0.001     # 📢: объявление не старше 60 мин; не входить при фандинге дешевле −0,1%/8 ч
NT_DELAY_H, NT_LATE_H, NT_WIN_D, NT_FUND_MIN = 24, 72, 10, -0.001   # 🆕: вход через 24 ч после первого поста (до 72 ч),
                                                                     # спотовый листинг ±10 суток, фандинг ≥ −0,1%/8 ч
KNOWN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "margin_known.txt")
_known = None


def _ann_get(url):
    """CMS Binance → data или None."""
    try:
        j = json.loads(http(url, timeout=20))
        return j.get("data") if isinstance(j, dict) and j.get("success", True) else None
    except Exception:
        return None


def _listing_coins(title):
    """Монеты из заголовка спотового листинга: «Binance Will List X (X) …», «Introducing X (X) on Binance HODLer/…»."""
    if re.search(r"^Binance Will List", title) or re.search(r"^Introducing .* on Binance (?:HODLer|Launchpool|Megadrop)", title):
        return re.findall(r"\(([A-Z0-9]{1,15})\)", title)
    return []


def _ann_kind(title):
    """Тип объявления по заголовку: MT — Monitoring Tag, DL — делистинг спота, FD — делистинг фьючерса; иначе None."""
    if re.search(r"Monitoring Tag", title) and re.search(r"Include", title):
        return "MT"
    if re.search(r"^Binance Will Delist", title):
        return "DL"
    if re.search(r"Futures Will Delist", title):
        return "FD"
    return None


def _delist_coins(art):
    """Монеты из объявления о делистинге спота / фьючерса или Monitoring Tag ([] — не нашлись)."""
    t = art["title"]; kind_ = _ann_kind(t)
    if kind_ == "FD":
        syms = re.findall(r"\b([A-Z0-9]{2,20})USDT\b", t)
        for _ in range(0 if syms else 3):                    # «Multiple … Contracts» — список в тексте объявления
            d = _ann_get(ANN_DETAIL.format(code=art["code"]))
            if isinstance(d, dict):
                syms = re.findall(r"\b([A-Z0-9]{2,20})USDT\b", re.sub(r"<[^>]+>", " ", str(d.get("body") or "")))
                break
            time.sleep(3)
        return sorted(set(syms))
    m = (re.search(r"Include (.+?) on \d", t) or re.search(r"Include (.+)$", t)) if kind_ == "MT" else \
        re.search(r"Delist (.+?) on \d", t) if kind_ == "DL" else None
    return [c.strip() for c in re.split(r",|&| and ", m.group(1)) if c.strip()] if m else []


def ann_poll(state, every=55):
    """Раз в минуту — первые страницы трёх разделов объявлений Binance. Новые объявления (по коду) — в ответ; листинги
    запоминаются в state["ann_list"] (монета → время объявления) для 🆕. Первый успешный опрос раздела: 100 последних его
    объявлений помечаются виденными (листинги — запоминаются), в ответ — только опубликованные за последние 60 мин.
    Объявления старше 40 суток не учитываются. Сбой — в журнал не чаще раза в час."""
    now = time.time()
    if now - state.get("ann_try", 0) < every:
        return []
    state["ann_try"] = now
    seen = state.setdefault("ann_seen", {}); lst = state.setdefault("ann_list", {}); init = state.setdefault("ann_init", [])
    new, fail = [], []
    for cat in ANN_CATS:
        first = cat not in init
        arts = []
        for page in ((1, 2) if first else (1,)):
            d = _ann_get(ANN_LIST.format(cat=cat, page=page, size=50 if first else 20))
            got = [dict(code=a["code"], title=a.get("title", ""), ts=(a.get("releaseDate") or 0) / 1000, cat=cat)
                   for c in (d.get("catalogs") or [] if isinstance(d, dict) else [])
                   for a in c.get("articles") or [] if a.get("code") and a.get("releaseDate")]
            if page == 1 and not got:                        # пустая первая страница — сбой или другой формат ответа
                arts = None
                break
            arts += got
        if arts is None:
            fail.append(cat)
            continue
        for a in sorted(arts, key=lambda a: a["ts"]):
            if a["code"] in seen or a["ts"] < now - 40 * 86400:
                continue
            seen[a["code"]] = a["ts"]
            for c in _listing_coins(a["title"]):
                lst[c] = min(lst.get(c, a["ts"]), a["ts"])
            if not first or now - a["ts"] <= AN_FRESH_MIN * 60:      # при первом опросе — только свежие (до 60 мин)
                new.append(a)
        if first:
            init.append(cat)
            log("ОБЪЯВЛЕНИЕ", f"раздел {cat}: просмотрено объявлений {len(arts)}, по старше {AN_FRESH_MIN} мин сделок нет; "
                              f"листингов за 40 суток {len(lst)}")
    if fail and now - state.get("ann_err", 0) >= 3600:
        state["ann_err"] = now
        log("ОБЪЯВЛЕНИЕ", f"Binance не отдал список объявлений (разделы {', '.join(map(str, fail))}) — повтор через минуту")
    for k in [k for k, ts in seen.items() if ts < now - 40 * 86400]:
        del seen[k]
    for k in [k for k, ts in lst.items() if ts < now - 40 * 86400]:
        del lst[k]
    return sorted(new, key=lambda a: a["ts"])


def announce_rule(state, new):
    """Объявления Binance (журнал 📢, research/s12/ВЫВОДЫ.md, стратегия B): делистинг спота («Binance Will Delist …»),
    делистинг фьючерса, Monitoring Tag → виртуальный шорт фьючерса каждой монеты, если объявлению не больше 60 мин и фандинг
    не дешевле −0,1% за 8 ч; 7 суток без тейка, стоп +25%, плечо ×1. Возвращает сообщения для чата."""
    msgs = []
    for a in new:
        kind_ = _ann_kind(a["title"])
        if not kind_:
            continue
        age = (time.time() - a["ts"]) / 60
        name = {"MT": "Monitoring Tag", "DL": "делистинг спота", "FD": "делистинг фьючерса"}[kind_]
        if age > AN_FRESH_MIN:
            log("ОБЪЯВЛЕНИЕ", f"{name}: «{a['title']}» — {age:.0f} мин назад, позже {AN_FRESH_MIN} мин, сделок нет")
            continue
        coins = _delist_coins(a)
        out, skip = [], ([] if coins else ["монеты в объявлении не найдены"])
        for c in coins:
            fs = _fut_sym(c)
            if not fs:
                skip.append(f"{c} (нет фьючерса)")
                continue
            fh = trader.funding_hourly(fs)
            if fh is not None and fh * 8 < AN_FUND_MIN:
                skip.append(f"{fs} (фандинг {fh * 8 * 100:+.3f}%/8 ч)")
                continue
            note = f"{name}: «{a['title']}», опубликовано {age:.0f} мин назад"
            m = trader.virt_open(state, "virtual_AN", fs, kind_, note)
            if m:
                out.append(m)
            else:
                skip.append(f"{fs} (уже открыта)")
        log("ОБЪЯВЛЕНИЕ", f"{name}: «{a['title']}» → шорт: {len(out)}" + (f"; пропуск: {', '.join(skip)}" if skip else ""))
        if out:
            msgs.append(f"📢 Binance: {a['title']}\n" + "\n".join(out))
    return msgs


BL_FRESH_MIN, BL_AGE_D, BL_FIRST_D, BL_LATE_H = 60, 1, 30, 2   # 🅱️: объявление не старше 60 мин, фьючерс старше суток,
                                                                 # первое о монете за 30 суток, вход — до 2 ч после часа
BL_FAM = (("листинг", r"\bWill List\b"), ("аирдроп", r"HODLer Airdrops|Launchpool|Megadrop"),
          ("маржа", r"Will Add .*\bMargin\b|^Binance Adds .*\bMargin\b"))
BL_SKIP = RW_STABLE | {"BTCDOM", "DEFI", "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "COPPER", "CL", "BZ", "AAPL", "AMD", "AMZN",
                       "COIN", "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA"}
                                                # стейблкоины, индексы, металлы, нефть, акции — как в бэктесте (NONCRYPTO)


def _bl_family(title):
    """Семейство объявления для 🅱️ (как в бэктесте research/s22/h10_ann.py) или None; Alpha и запуски фьючерсов — нет."""
    if "Alpha" in title or "Futures" in title:
        return None
    return next((k for k, p in BL_FAM if re.search(p, title)), None)


def _bl_seed(state):
    """Первый запуск 🅱️: объявления трёх семейств за 40 суток (по две страницы разделов 48 и 49, как первый опрос ann_poll)
    → state["bl_first"] — начала серий, как в бэктесте (в ann_list попадают не все: «… Vote to List Results and Will List X»,
    маржа). Сбой Binance — повтор не чаще раза в 10 мин. True — готово."""
    now = time.time()
    if now - state.get("bl_seed_try", 0) < 600:
        return False
    state["bl_seed_try"] = now
    arts = []
    for cat in (48, 49):
        for page in (1, 2):
            d = _ann_get(ANN_LIST.format(cat=cat, page=page, size=50))
            got = [dict(title=a.get("title", ""), ts=(a.get("releaseDate") or 0) / 1000)
                   for c in (d.get("catalogs") or [] if isinstance(d, dict) else []) for a in c.get("articles") or []
                   if a.get("releaseDate")]
            if page == 1 and not got:
                log("ЛИСТИНГ BINANCE", f"первый запуск: Binance не отдал объявления раздела {cat} — повтор через 10 мин, "
                                       "новые объявления ждут")
                return False
            arts += got
    first = state.setdefault("bl_first", {}); n = 0
    for a in sorted(arts, key=lambda a: a["ts"]):
        if a["ts"] < now - 40 * 86400 or not _bl_family(a["title"]):
            continue
        n += 1
        for c in re.findall(r"\(([^()\s,]{1,20})\)", a["title"]):
            if c not in first or a["ts"] - first[c] >= BL_FIRST_D * 86400:
                first[c] = a["ts"]
    state["bl_seeded"] = now
    log("ЛИСТИНГ BINANCE", f"первый запуск: объявлений листинга, аирдропов и маржи за 40 суток {n}, монет {len(first)} — "
                           f"новое объявление о них будет «первым» только через {BL_FIRST_D} суток после первого в серии")
    return True


def spot_listing_rule(state, new):
    """Листинг спота Binance при живом фьючерсе (журнал 🅱️, research/s22/ВЫВОДЫ.md, «Г10 по объявлениям»): объявление
    «Will List X» / «Introducing X on Binance HODLer Airdrops / Launchpool / Megadrop» / «Will Add X on … Margin» (без
    Alpha и запусков фьючерсов), первое о монете за 30 суток, опубликовано не позже 60 мин назад; у монеты есть бессрочный
    фьючерс USDT-M, запущенный не позже чем за сутки до объявления → виртуальный шорт на закрытии ближайшего часа после
    публикации, как в бэктесте (если бот пропустил этот момент или Binance не отдал цену — до 2 ч позже); 30 суток без тейка,
    стоп +50%, плечо ×1. «Первое за 30 суток» — от первого объявления серии, как в бэктесте; объявления до запуска правила —
    из разовой загрузки _bl_seed и state["ann_list"] (листинги и HODLer за 40 суток, ann_poll). Сообщения для чата."""
    now = time.time(); msgs = []
    todo = [a for a in state.get("bl_retry", []) + list(new) if _bl_family(a["title"])]
    if not state.get("bl_seeded") and not _bl_seed(state):  # первые объявления серий ещё не загружены — новые ждут
        if todo:
            state["bl_retry"] = todo
        return msgs
    first = state.setdefault("bl_first", {}); wait = state.setdefault("bl_wait", {}); lst = state.get("ann_list", {})
    retry = []
    if any(now - a["ts"] <= BL_FRESH_MIN * 60 for a in todo):
        trader.contract("BTC")                               # загружает список бессрочных контрактов USDT
    for a in todo:
        fam = _bl_family(a["title"]); age = (now - a["ts"]) / 60
        for c in [a["coin"]] if a.get("coin") else re.findall(r"\(([^()\s,]{1,20})\)", a["title"]):
            prior = [t for t in (first.get(c), lst.get(c)) if t is not None and t < a["ts"] - 60]
            if prior and a["ts"] - max(prior) < BL_FIRST_D * 86400:
                log("ЛИСТИНГ BINANCE", f"{c}: «{a['title']}» — не первое объявление о монете за {BL_FIRST_D} суток, пропуск")
                continue
            if age > BL_FRESH_MIN:
                first[c] = a["ts"]
                log("ЛИСТИНГ BINANCE", f"{c}: «{a['title']}» — {age:.0f} мин назад, позже {BL_FRESH_MIN} мин, сделки нет")
                continue
            fs = None if c in BL_SKIP else _fut_sym(c)
            if not fs and c not in BL_SKIP and trader._contracts and now - state.get("bl_reload", 0) >= 600:
                state["bl_reload"] = now                     # фьючерс мог появиться после загрузки списка — перезагрузка
                trader._contracts.clear()                    # (вес 1) не чаще раза в 10 мин
                fs = _fut_sym(c)
            if not trader._contracts:                        # Binance не отдал список контрактов — повтор на следующем проходе
                if not a.get("coin"):
                    log("ЛИСТИНГ BINANCE", f"{c}: «{a['title']}» — Binance не отдал список контрактов, повтор каждый проход "
                                           f"до {BL_FRESH_MIN} мин после объявления")
                retry.append(dict(a, coin=c))
                continue
            first[c] = a["ts"]
            what = f"{c}: «{a['title']}» ({fam})"
            if c in BL_SKIP:
                log("ЛИСТИНГ BINANCE", f"{what} — стейблкоин, индекс, металл или акция, пропуск")
                continue
            if not fs:
                log("ЛИСТИНГ BINANCE", f"{what} — нет бессрочного фьючерса Binance, пропуск")
                continue
            onb = (trader.contract(fs) or {}).get("onboard") or 0
            if not onb or onb > a["ts"] - BL_AGE_D * 86400:
                log("ЛИСТИНГ BINANCE", f"{what} — фьючерс {fs} запущен " +
                    (f"{datetime.fromtimestamp(onb, timezone.utc):%d.%m %H:%M} UTC, меньше суток до объявления" if onb
                     else "неизвестно когда") + ", пропуск")
                continue
            if fs in wait:
                log("ЛИСТИНГ BINANCE", f"{what} — вход по {fs} уже ждёт закрытия часа")
                continue
            T = int(a["ts"] // 3600 + 1) * 3600
            wait[fs] = {"T": T, "ts": a["ts"], "title": a["title"], "fam": fam, "onb": onb}
            log("ЛИСТИНГ BINANCE", f"{what}, фьючерсу {fs} {(a['ts'] - onb) / 86400:.0f} сут — шорт на закрытии часа "
                                   f"{datetime.fromtimestamp(T, timezone.utc):%H:%M} UTC")
    if retry:
        state["bl_retry"] = retry
    else:
        state.pop("bl_retry", None)
    for fs, w in sorted(wait.items(), key=lambda kv: kv[1]["T"]):
        if now < max(w["T"], w.get("next", 0)):
            continue
        note = (f"Binance ({w['fam']}): «{w['title']}», опубликовано "
                f"{datetime.fromtimestamp(w['ts'], timezone.utc):%d.%m %H:%M} UTC; фьючерс торгуется {(w['ts'] - w['onb']) / 86400:.0f} сут")
        if now > w["T"] + BL_LATE_H * 3600:
            del wait[fs]
            log("ЛИСТИНГ BINANCE", fs, note + f" — к закрытию часа и {BL_LATE_H} ч после него войти не удалось (бот не работал "
                                              "или Binance не отдавал цену), сделки нет")
            continue
        m = trader.virt_open(state, "virtual_BL", fs, "BL", note)
        if m:
            del wait[fs]
            log("ЛИСТИНГ BINANCE", fs, note)
            msgs.append(m)
        elif any(t["sym"] == fs for t in state.get("virtual_BL", {}).get("trades", [])
                 if not t.get("closed") or now - t["opened"] < trader.VIRTUALS["virtual_BL"]["cooldown_h"] * 3600):
            del wait[fs]
            log("ЛИСТИНГ BINANCE", fs, note + " — сделка по монете уже открыта или была недавно, пропуск")
        else:                                                # Binance не отдал цену — повтор через 5 мин (до 2 ч после часа)
            if not w.get("next"):
                log("ЛИСТИНГ BINANCE", fs, note + " — Binance не отдал цену, повтор через 5 мин")
            w["next"] = now + 300
    for k in [k for k, ts in first.items() if ts < now - 60 * 86400]:
        del first[k]
    return msgs


FE_RATE, FE_FROM, FE_TO, FE_HOLD = -0.01, 15, 30, 2.0    # 🌊: ставка начисления ≤ −1%; вход с 15-й по 30-ю минуту после
FE_GRID = 4 * 3600                                         # начисления; держим 2 ч. Начисления с интервалом 4 и 8 ч — на сетке
                                                           # 4 ч от 00:00 UTC (проверено по двум годам истории)


def _fe_try(state, c, w, now):
    """Попытка входа 🌊 по монете c (w — {T, rate}). Возвращает (готово, сообщение): готово=False — повторить в следующем
    проходе (Binance не отдал список контрактов, время следующего начисления или цену)."""
    hh = f"{datetime.fromtimestamp(w['T'], timezone.utc):%d.%m %H:%M}"
    what = f"{c}: начисление {hh} UTC, ставка {w['rate'] * 100:+.2f}%"
    if c in BL_SKIP:
        log("ОТЛИВ", f"{what} — стейблкоин, индекс, металл или акция, пропуск")
        return True, None
    if not trader.contract(c):
        if not trader._contracts:
            return False, None                               # список контрактов не загрузился — повтор
        log("ОТЛИВ", f"{what} — нет бессрочного криптофьючерса USDT (акции и металлы Binance — другой тип контракта), пропуск")
        return True, None
    pi = trader._request("GET", "/fapi/v1/premiumIndex", {"symbol": f"{c}USDT"}, signed=False)
    nft = int(pi.get("nextFundingTime") or 0) // 1000 if isinstance(pi, dict) else 0
    if not nft:
        return False, None
    if nft < now + FE_HOLD * 3600 + 900:
        log("ОТЛИВ", f"{what} — следующее начисление уже в {datetime.fromtimestamp(nft, timezone.utc):%H:%M} UTC, раньше выхода "
                     "(интервал сменили) — шорт заплатил бы фандинг, пропуск")
        return True, None
    note = (f"фандинг начисления {hh} UTC {w['rate'] * 100:+.2f}% (шорты платили), следующее начисление "
            f"{datetime.fromtimestamp(nft, timezone.utc):%H:%M} UTC; выход через {FE_HOLD:g} ч")
    was = _virt_is_open(state, "virtual_FE", c)
    m = trader.virt_open(state, "virtual_FE", c, "FE", note)
    if m or was:
        log("ОТЛИВ", c, note + ("" if m else " — сделка по монете уже открыта"))
        return True, m
    return False, None                                       # Binance не отдал цену — повтор


def funding_ebb_rule(state):
    """Отлив после фандинга (журнал 🌊, research/s23/ВЫВОДЫ.md): выплата фандинга — как дивиденд: за секунды цена фьючерса
    падает на её сумму, потом при сильно отрицательной ставке около двух часов сползает дальше. Через 15 мин после
    начисления на сетке 4 ч (00, 04, …, 20 UTC) — одним запросом ставки всех фьючерсов в этот момент (/fapi/v1/fundingRate).
    Монета со ставкой ≤ −1% (шорты платят лонгам), с бессрочным криптофьючерсом USDT, не стейблкоин и не индекс,
    следующее начисление — не раньше чем через 2 ч 15 мин (интервал 4 или 8 ч, его не сменили на 1–2 ч) → виртуальный шорт
    на 2 ч без тейка, стоп +15%, плечо ×1. Вход — в окне 15–30 мин после начисления; если Binance не ответил — повтор
    в следующем проходе, окно прошло — пропуск. Возвращает сообщения для чата."""
    now = time.time()
    T = int(now // FE_GRID * FE_GRID)
    hh = f"{datetime.fromtimestamp(T, timezone.utc):%d.%m %H:%M}"
    wait = state.setdefault("fe_wait", {}); msgs = []
    if state.get("fe_last_T") != T and now >= T + FE_FROM * 60:
        if now > T + FE_TO * 60:
            if "fe_last_T" in state:                          # при первом запуске правила — молча
                log("ОТЛИВ", f"{hh}: окно входа {FE_FROM}–{FE_TO} мин после начисления прошло без проверки (бот не работал или "
                             "Binance не отвечал) — пропуск")
            state["fe_last_T"] = T
        else:
            j = trader._request("GET", "/fapi/v1/fundingRate", {"startTime": T * 1000, "endTime": (T + 60) * 1000, "limit": 1000},
                                signed=False)
            if isinstance(j, list) and j:
                state["fe_last_T"] = T
                rates = []
                for x in j:
                    try:
                        sym, rate = str(x["symbol"]), float(x["fundingRate"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if sym.endswith("USDT"):
                        rates.append((rate, sym[:-4]))
                rates.sort()
                low = [(r, c) for r, c in rates if r <= FE_RATE]
                log("ОТЛИВ", f"{hh}: начислений {len(rates)}" + (" (ответ упёрся в предел 1000 — часть могла не прийти)" if len(j) >= 1000 else "")
                    + (f", ставка ≤ {FE_RATE * 100:g}% у " + ", ".join(f"{c} {r * 100:+.2f}%" for r, c in low) if low else
                       f", самая низкая ставка {rates[0][1]} {rates[0][0] * 100:+.2f}% — сделок нет" if rates else ""))
                for r, c in low:
                    wait[c] = {"T": T, "rate": r}
            elif state.get("fe_err") != T:
                state["fe_err"] = T
                log("ОТЛИВ", f"{hh}: Binance не отдал ставки начисления — повтор в следующем проходе до {FE_TO} мин")
    for c, w in list(wait.items()):
        if now > w["T"] + FE_TO * 60:
            del wait[c]
            log("ОТЛИВ", f"{c}: начисление {datetime.fromtimestamp(w['T'], timezone.utc):%d.%m %H:%M} UTC — Binance так и не отдал "
                         f"цену или время следующего начисления за {FE_TO} мин, сделки нет")
            continue
        done, m = _fe_try(state, c, w, now)
        if done:
            del wait[c]
        if m:
            msgs.append(m)
    if len(msgs) > 1:                                         # несколько монет на одном начислении — одно сообщение
        return [f"🌊 Отлив после фандинга {hh} UTC: {len(msgs)} шорт(ов)\n" + "\n".join(msgs)]
    return msgs


def nt_track(state):
    """Первое появление монеты в маржинальном канале (для 🆕): монета, которой нет в архиве канала (margin_known.txt)
    и которую бот ещё не видел, запоминается в state["nt_first"] со временем самого раннего поста в журнале постов."""
    global _known
    if _known is None:
        try:
            with open(KNOWN_FILE, encoding="utf-8") as f:
                _known = {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}
        except OSError:                                      # файла нет — известны все монеты журнала постов за 8 суток
            if not _bf_log:
                return
            _known = {c for _, coins in _bf_log.values() for c in coins.split()}
            log("НОВЫЙ ТОКЕН", f"нет файла {os.path.basename(KNOWN_FILE)} — монеты из журнала постов ({len(_known)}) "
                               "считаются известными")
    first = state.setdefault("nt_first", {}); old = state.setdefault("nt_old", [])
    early = {}
    for ts, coins in (_bf_log or {}).values():
        for c in coins.split():
            if c not in _known and c not in first and c not in old:
                early[c] = min(early.get(c, ts), ts)
    for c, ts in early.items():
        first[c] = ts
        log("НОВЫЙ ТОКЕН", f"{c}: впервые в маржинальном канале {datetime.fromtimestamp(ts, timezone.utc):%d.%m %H:%M} UTC")
    for c in [c for c, ts in first.items() if ts < time.time() - 30 * 86400]:
        old.append(c)
        del first[c]


def newtoken_rule(state):
    """Первый займ свежего токена (журнал 🆕, research/s12/ВЫВОДЫ.md, стратегия A): монета впервые появилась в маржинальном
    канале, объявление о её спотовом листинге на Binance вышло в пределах ±10 суток от первого поста (и уже известно);
    через 24 ч после первого поста (если бот лежал — до 72 ч) и при фандинге не дешевле −0,1% за 8 ч — виртуальный шорт
    фьючерса на 21 сутки без тейка, стоп +60%, выход при фандинге ≤ −0,5%/8 ч два раза подряд, плечо ×1."""
    nt_track(state)
    now = time.time(); msgs = []
    done = state.setdefault("nt_done", {}); lst = state.get("ann_list", {})
    for c, t1 in list(state.get("nt_first", {}).items()):
        if c in done or now < t1 + NT_DELAY_H * 3600:
            continue
        sa = lst.get(c)
        fresh = sa is not None and abs(sa - t1) <= NT_WIN_D * 86400
        if not fresh and now <= t1 + NT_LATE_H * 3600:
            continue                                         # объявление о листинге может выйти позже — ждём до 72 ч
        why = None
        if now > t1 + NT_LATE_H * 3600 and fresh:
            why = f"прошло больше {NT_LATE_H} ч после первого поста"
        elif not fresh:
            why = "нет объявления о спотовом листинге Binance в пределах ±10 суток"
        fs = None if why else _fut_sym(c)
        if not why and not fs:
            why = "нет фьючерса Binance"
        fh = trader.funding_hourly(fs) if fs else None
        if not why and fh is not None and fh * 8 < NT_FUND_MIN:
            why = f"фандинг {fh * 8 * 100:+.3f}%/8 ч дешевле −0,1%"
        done[c] = now
        if why:
            log("НОВЫЙ ТОКЕН", f"{c}: пропуск — {why}")
            continue
        note = (f"впервые в маржинальном канале {datetime.fromtimestamp(t1, timezone.utc):%d.%m %H:%M} UTC, спотовый листинг "
                f"объявлен {datetime.fromtimestamp(sa, timezone.utc):%d.%m %H:%M} UTC, фандинг "
                + (f"{fh * 8 * 100:+.3f}%/8 ч" if fh is not None else "нет данных"))
        m = trader.virt_open(state, "virtual_NT", fs, "NT", note)
        log("НОВЫЙ ТОКЕН", fs, note + ("" if m else " — уже открыта"))
        if m:
            msgs.append(m)
    for k in [k for k, ts in done.items() if ts < now - 60 * 86400]:
        del done[k]
    return msgs


KL_EVERY, KL_WAIT_D, KL_LATE_H, KL_BURST, KL_PAGES = 300, 7, 24, 10, 8   # 🇰🇷🆕: опрос раз в 5 мин; ждать первой сделки
# до 7 суток; входить не позже суток после неё; больше 10 «новых» рынков за опрос — сбой списка биржи, а не листинги;
# первая сделка ищется не дальше 8 страниц минутных свечей (1600 минут со сделками)
KL_API = {"upbit": "https://api.upbit.com", "bithumb": "https://api.bithumb.com"}
KL_NAME = {"upbit": "Upbit", "bithumb": "Bithumb"}
KL_STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD"}


def _kl_utc(x):
    return datetime.fromisoformat(str(x["candle_date_time_utc"])).replace(tzinfo=timezone.utc).timestamp()


def _kl_candles(url):
    """Свечи корейской биржи: list; «Code not found» (Upbit — HTTP 404, Bithumb — 200 с ошибкой) → [] — рынок в списке,
    но свечей ещё нет; сбой → None (без строки в журнал — повтор через 5 мин)."""
    try:
        j = json.loads(http(url, timeout=15))
    except urllib.error.HTTPError as e:
        return [] if e.code == 404 else None
    except Exception:
        return None
    if isinstance(j, dict) and str((j.get("error") or {}).get("name")) == "404":
        return []
    return j if isinstance(j, list) else None


def _kl_to(ex, ts):
    """Граница to для свечей: Upbit ждёт UTC с «Z», Bithumb — время Сеула без зоны (с «Z» отвечает 400); не включительно."""
    if ex == "bithumb":
        return datetime.fromtimestamp(ts + 9 * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _kl_first_trade(ex, coin):
    """Время первой сделки KRW-рынка: 0 — торгов ещё нет, −1 — торги идут дольше KL_PAGES × 200 минут со сделками (больше
    суток: рынок не новый или вход опоздал), None — биржа не ответила. Минутные свечи есть только у минут со сделками:
    страница из 200 свечей листается назад, пока не придёт неполная — её самая ранняя свеча и есть первая сделка."""
    url = f"{KL_API[ex]}/v1/candles/minutes/1?market=KRW-{coin}&count=200"
    first, to = None, ""
    for _ in range(KL_PAGES):
        m = _kl_candles(url + to)
        if m is None:
            return None
        if not m:
            return first or 0.0                              # торгов нет или первая сделка — на прошлой странице
        try:
            first = min(_kl_utc(x) for x in m)
        except (KeyError, TypeError, ValueError):
            return None
        if len(m) < 200:
            return first
        to = f"&to={_kl_to(ex, first)}"
    return -1.0


def kr_listing_rule(state):
    """Корейский листинг (журнал 🇰🇷🆕, research/s15/ВЫВОДЫ.md): раз в 5 мин — списки KRW-рынков Upbit и Bithumb. Новый рынок
    ждёт первой сделки (до 7 суток); когда торги начались — если с первой сделки прошло не больше суток и у монеты есть
    бессрочный фьючерс Binance, запущенный не меньше суток назад, — виртуальный шорт фьючерса на 7 суток без тейка, стоп +50%,
    плечо ×1. Первый опрос биржи только запоминает её рынки. Запросы — к корейским биржам, Binance — только цена на входе.
    Возвращает сообщения для чата."""
    now = time.time()
    if now - state.get("kl_try", 0) < KL_EVERY:
        return []
    state["kl_try"] = now
    known = state.setdefault("kl_known", {}); wait = state.setdefault("kl_wait", {})
    for ex, base in KL_API.items():
        j = http_json(f"{base}/v1/market/all", 15)
        cur = {str(x.get("market", ""))[4:] for x in j if isinstance(x, dict) and str(x.get("market", "")).startswith("KRW-")} \
            if isinstance(j, list) else set()
        if not cur:
            continue                                         # биржа не ответила — повтор через 5 мин
        if ex not in known:
            known[ex] = sorted(cur)
            log("КОРЕЯ ЛИСТИНГ", f"{KL_NAME[ex]}: первый опрос — рынков к воне {len(cur)}, они считаются старыми, сделок нет")
            continue
        old = set(known[ex]); new = sorted(cur - old)
        known[ex] = sorted(old | cur)                        # снятые рынки не забываются — их возврат не считается листингом
        if len(new) > KL_BURST:
            log("КОРЕЯ ЛИСТИНГ", f"{KL_NAME[ex]}: сразу {len(new)} новых рынков — похоже на сбой списка, сделок нет: "
                                 + ", ".join(new[:20]))
            continue
        for c in new:
            wait.setdefault(f"{ex}:{c}", now)
            log("КОРЕЯ ЛИСТИНГ", f"{KL_NAME[ex]}: новый рынок KRW-{c} — жду первой сделки")
    msgs = []
    if wait:
        trader.contract("BTC")                               # загружает список бессрочных контрактов USDT
    if wait and not trader._contracts:
        log("КОРЕЯ ЛИСТИНГ", f"Binance не отдал список контрактов — {len(wait)} рынков ждут, повтор через 5 мин")
        return msgs
    for key, seen in sorted(wait.items(), key=lambda kv: kv[1]):
        ex, c = key.split(":", 1)
        name = f"{KL_NAME.get(ex, ex)} KRW-{c}"
        if ex not in KL_API:
            del wait[key]
            continue
        if c in KL_STABLE:
            del wait[key]
            log("КОРЕЯ ЛИСТИНГ", f"{name}: стейблкоин — пропуск")
            continue
        ft = _kl_first_trade(ex, c)
        if ft is None:
            continue                                         # биржа не ответила — повтор через 5 мин
        if ft == 0:
            if now - seen > KL_WAIT_D * 86400:
                del wait[key]
                log("КОРЕЯ ЛИСТИНГ", f"{name}: за {KL_WAIT_D} суток торги не начались — больше не жду")
            continue
        del wait[key]
        if ft < 0:
            log("КОРЕЯ ЛИСТИНГ", f"{name}: торги идут дольше {KL_PAGES * 200} минут со сделками — рынок не новый или вход "
                                 "опоздал, пропуск")
            continue
        age_h = (now - ft) / 3600
        when = f"первая сделка {datetime.fromtimestamp(ft, timezone.utc):%d.%m %H:%M} UTC"
        if age_h > KL_LATE_H:
            log("КОРЕЯ ЛИСТИНГ", f"{name}: {when}, {age_h:.0f} ч назад — позже {KL_LATE_H} ч, пропуск")
            continue
        fs = _fut_sym(c)
        if not fs and now - state.get("kl_reload", 0) >= 600:    # список контрактов грузится при запуске бота — фьючерс
            state["kl_reload"] = now                          # мог появиться позже: перезагрузка (вес 1) не чаще раза в 10 мин
            trader._contracts.clear()
            fs = _fut_sym(c)
            if not trader._contracts:
                wait[key] = seen
                log("КОРЕЯ ЛИСТИНГ", f"{name}: Binance не отдал список контрактов — повтор через 5 мин")
                break
        if not fs:
            log("КОРЕЯ ЛИСТИНГ", f"{name}: {when} — нет фьючерса Binance, пропуск")
            continue
        on = (trader.contract(fs) or {}).get("onboard") or 0
        if on and now - on < 86400:
            log("КОРЕЯ ЛИСТИНГ", f"{name}: {when} — фьючерс {fs} запущен {(now - on) / 3600:.0f} ч назад, моложе суток, пропуск")
            continue
        note = (f"{KL_NAME[ex]}: новая монета к воне KRW-{c}, {when}"
                + (f" ({age_h * 60:.0f} мин назад)" if age_h < 2 else f" ({age_h:.0f} ч назад)"))
        m = trader.virt_open(state, "virtual_KL", fs, "KL", note)
        if m:
            log("КОРЕЯ ЛИСТИНГ", fs, note)
            msgs.append(m)
        elif any(t["sym"] == fs and not t.get("closed") for t in state.get("virtual_KL", {}).get("trades", [])):
            log("КОРЕЯ ЛИСТИНГ", fs, note + " — сделка по монете уже открыта")
        else:                                                # Binance не отдал цену — повтор через 5 мин (до суток)
            wait[key] = seen
            log("КОРЕЯ ЛИСТИНГ", fs, note + " — Binance не отдал цену, повтор через 5 мин")
    return msgs


KT_TOP, KT_NEW_H, KT_WARM_H, KT_CHUNK = 5, 168, 168, 100   # 🔝: пятёрка; «впервые за 7 сут»; первые 7 сут после запуска —
                                                            # только история пятёрки; рынков в одном запросе тикеров (Bithumb
                                                            # на всех 480 рынках отвечает 414 — слишком длинный адрес)
KT_MAJORS = {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB"}   # 10 постоянных лидеров оборота в Корее
                                                                                       # (research/s65, первая половина)


_kt_cache = {"ts": 0.0, "per": None}   # обороты бирж за 24 ч: 🔝 и 👀 в одном проходе берут одни и те же данные


def _kt_fetch():
    """Оборот за 24 ч в $ у монет к воне по биржам (acc_trade_price_24h, перевод по KRW-USDT своей биржи); кэш на 5 мин.
    Возвращает ({"upbit": {монета: $}, "bithumb": {монета: $}}, "") или (None, причина)."""
    if _kt_cache["per"] is not None and time.time() - _kt_cache["ts"] < 300:
        return _kt_cache["per"], ""
    kr = _kr_list(); per = {}
    for ex in ("upbit", "bithumb"):
        coins = sorted(kr.get(ex) or [])
        if not coins:
            return None, f"нет списка рынков {KL_NAME[ex]}"
        rows = []
        for i in range(0, len(coins), KT_CHUNK):
            j = http_json(f"{KL_API[ex]}/v1/ticker?markets=" + ",".join(f"KRW-{c}" for c in coins[i:i + KT_CHUNK]), 15)
            if not isinstance(j, list):
                _kr_markets["ts"] = 0                           # в старом списке мог остаться снятый рынок — перечитать
                return None, f"{KL_NAME[ex]} не отдал обороты за сутки"
            rows += j
        try:
            fx = next(float(x["trade_price"]) for x in rows if isinstance(x, dict) and x.get("market") == "KRW-USDT")
        except (StopIteration, KeyError, TypeError, ValueError):
            return None, f"{KL_NAME[ex]}: нет курса KRW-USDT"
        vol = per.setdefault(ex, {})
        for x in rows:
            m = str(x.get("market", "")) if isinstance(x, dict) else ""
            try:
                v = float(x["acc_trade_price_24h"]) / fx
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            if m.startswith("KRW-") and v > 0:
                vol[m[4:]] = vol.get(m[4:], 0.0) + v
    _kt_cache.update(ts=time.time(), per=per)
    return per, ""


def _kt_volumes():
    """Оборот за 24 ч в $ у монет к воне: Upbit + Bithumb. Возвращает ({монета: $}, "") или (None, причина)."""
    per, why = _kt_fetch()
    if per is None:
        return None, why
    vol = {}
    for d in per.values():
        for c, v in d.items():
            vol[c] = vol.get(c, 0.0) + v
    return vol, ""


def kr_top_rule(state):
    """Пятёрка по обороту в Корее (журнал 🔝, research/s65/ВЫВОДЫ.md): раз в час, в первые 10 мин после закрытия часа T, —
    обороты за 24 ч всех рынков к воне Upbit + Bithumb в $. Монеты с бессрочным фьючерсом Binance, кроме 10 постоянных
    лидеров (KT_MAJORS) и стейблкоинов, — по убыванию оборота. Монета в пятёрке, которой в ней не было 7 суток, фьючерс
    запущен не меньше суток назад → виртуальный шорт, тейк 10 / стоп 25 / 48 ч, одна сделка на монету за 7 суток.
    Первые 7 суток после запуска правила — только история пятёрки (state["kt"]["hist"]: монета → последний час в ней).
    Возвращает сообщения для чата."""
    T = candle_due(state, "kt_last_T", "КОРЕЯ ТОП", step=3600)
    if T is None:
        return []
    vol, why = _kt_volumes()
    if vol is None:
        return candle_retry("kt_last_T", why)
    trader.contract("BTC")                                       # загружает список бессрочных контрактов USDT
    if not trader._contracts:
        return candle_retry("kt_last_T", "Binance не отдал список контрактов")
    candle_done(state, "kt_last_T", T)
    st = state.setdefault("kt", {}); hist = st.setdefault("hist", {}); since = st.setdefault("since", T)
    rows = sorted(((v, c, fs) for c, v in vol.items() if c not in KT_MAJORS and c not in KL_STABLE and (fs := _fut_sym(c))),
                  reverse=True)
    top = rows[:KT_TOP]
    log("КОРЕЯ ТОП", "пятёрка за 24 ч без лидеров: " + ", ".join(f"{c} {v / 1e6:.1f} млн $" for v, c, _ in top))
    msgs = []
    for rank, (v, c, fs) in enumerate(top, 1):
        prev = hist.get(c); hist[c] = T
        if prev is not None and T - prev <= KT_NEW_H * 3600:
            continue                                             # была в пятёрке за 7 суток
        note = (f"{c}: {rank}-е место по обороту Upbit + Bithumb за 24 ч ({v / 1e6:.1f} млн $), в пятёрке впервые за 7 суток "
                "(10 постоянных лидеров не считаются)")
        if T - since < KT_WARM_H * 3600:
            log("КОРЕЯ ТОП", fs, note + " — первые 7 суток журнала: только история пятёрки, сделки нет")
            continue
        on = (trader.contract(fs) or {}).get("onboard") or 0
        if on and T - on < 86400:
            log("КОРЕЯ ТОП", fs, note + f" — фьючерс запущен {(T - on) / 3600:.0f} ч назад, моложе суток, пропуск")
            continue
        was = _virt_is_open(state, "virtual_KT", fs)
        m = trader.virt_open(state, "virtual_KT", fs, "KT", note)
        opened = not was and _virt_is_open(state, "virtual_KT", fs)
        log("КОРЕЯ ТОП", fs, note + (" → шорт 🔝" if opened else " — сделка не открыта (уже есть, кулдаун 7 суток или нет цены)"))
        if m:
            msgs.append(m)
    for c in [c for c, t in hist.items() if T - t > (KT_NEW_H + 24) * 3600]:
        del hist[c]
    return msgs


RT_TOP, RT_NEW_H, RT_WARM_H, RT_KT_H, RT_PAST_H = 5, 168, 168, 168, 24   # 👀: пятёрка; «впервые за 7 сут»; первые 7 сут
                                                    # после запуска — только история; без входа 🔝 за 7 сут; для лиры — без
                                                    # входов 🔝, 🛒, 🇰🇷 за прошлые сутки
RT_MAJORS = {                                       # 👀: у каждого списка свои 10 постоянных лидеров (research/s73 и s67,
    "upbit": {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "SHIB", "XLM"},          # медиана первой половины)
    "bithumb": {"XRP", "BTC", "ETH", "DOGE", "SOL", "WLD", "VIRTUAL", "SUI", "PEPE", "ONDO"},
    "try": {"XRP", "PEPE", "ETH", "BTC", "DOGE", "PNUT", "NEIRO", "SOL", "BONK", "ENA"},
}
RT_NAME = {"upbit": "Upbit", "bithumb": "Bithumb", "try": "пар к лире Binance"}
RT_STABLE = KL_STABLE | {"BUSD", "EUR", "AEUR", "EURI", "USDP"}


def _rt_try_volumes():
    """Оборот за 24 ч в $ у спотовых пар Binance к лире (ticker/24hr всех пар, вес 80): quoteVolume в лирах / цена USDTTRY.
    Возвращает ({монета: $}, "") или (None, причина)."""
    j = spot_json("/api/v3/ticker/24hr?type=MINI", 30)
    if not isinstance(j, list):
        return None, "Binance не отдал обороты спота за сутки"
    try:
        fx = next(float(x["lastPrice"]) for x in j if isinstance(x, dict) and x.get("symbol") == "USDTTRY")
    except (StopIteration, KeyError, TypeError, ValueError):
        return None, "нет курса USDT/TRY"
    vol = {}
    for x in j:
        s = str(x.get("symbol", "")) if isinstance(x, dict) else ""
        if len(s) > 3 and s.endswith("TRY"):
            try:
                v = float(x["quoteVolume"]) / fx
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            if v > 0:
                vol[s[:-3]] = v
    return vol, ""


def _virt_entered(state, key, sym, t0, t1):
    """Был ли вход журнала key по фьючерсу sym в интервале [t0, t1)."""
    return any(t["sym"] == sym and t0 <= t.get("opened", 0) < t1 for t in state.get(key, {}).get("trades", []))


def retail_top_rule(state):
    """Внимание изолированной розницы вне 🔝 (журнал 👀, research/s83/ВЫВОДЫ.md): раз в час, после 🔝 того же часа, — три
    списка по обороту за 24 ч: отдельно Upbit и отдельно Bithumb (те же данные, что у 🔝) и спотовые пары Binance к лире
    (перевод по USDTTRY). У каждого списка свои 10 постоянных лидеров (RT_MAJORS); стейблкоины не считаются; в рейтинге —
    монеты с бессрочным фьючерсом Binance. Монета в пятёрке списка, которой в ней не было 7 суток, фьючерс запущен
    не меньше суток назад, у монеты не было входа 🔝 за 7 суток (для пар к лире — ещё и входов 🔝, 🛒, 🇰🇷 за прошлые
    сутки) → виртуальный шорт, тейк 10 / стоп 25 / 48 ч, одна сделка на монету за 7 суток. Первые 7 суток после запуска
    правила — только история пятёрок (state["rt"][список]: монета → последний час в пятёрке). Возвращает сообщения для чата."""
    T = candle_due(state, "rt_last_T", "ВНИМАНИЕ РОЗНИЦЫ", step=3600)
    if T is None:
        return []
    if state.get("kt_last_T") != T:
        return candle_retry("rt_last_T", "🔝 ещё не проверил этот час")
    per, why = _kt_fetch()
    if per is None:
        return candle_retry("rt_last_T", why)
    tv, why = _rt_try_volumes()
    if tv is None:
        return candle_retry("rt_last_T", why)
    trader.contract("BTC")                                       # загружает список бессрочных контрактов USDT
    if not trader._contracts:
        return candle_retry("rt_last_T", "Binance не отдал список контрактов")
    candle_done(state, "rt_last_T", T)
    st = state.setdefault("rt", {}); since = st.setdefault("since", T)
    msgs = []
    for lst, vol in (("upbit", per.get("upbit") or {}), ("bithumb", per.get("bithumb") or {}), ("try", tv)):
        hist = st.setdefault(lst, {})
        rows = sorted(((v, c, fs) for c, v in vol.items() if c not in RT_MAJORS[lst] and c not in RT_STABLE and (fs := _fut_sym(c))),
                      reverse=True)
        top = rows[:RT_TOP]
        log("ВНИМАНИЕ РОЗНИЦЫ", f"пятёрка {RT_NAME[lst]} за 24 ч без лидеров: "
            + ", ".join(f"{c} {v / 1e6:.1f} млн $" for v, c, _ in top))
        for rank, (v, c, fs) in enumerate(top, 1):
            prev = hist.get(c); hist[c] = T
            if prev is not None and T - prev <= RT_NEW_H * 3600:
                continue                                         # была в пятёрке списка за 7 суток
            note = (f"{c}: {rank}-е место по обороту {RT_NAME[lst]} за 24 ч ({v / 1e6:.1f} млн $), в пятёрке впервые "
                    "за 7 суток (10 постоянных лидеров списка не считаются)")
            if T - since < RT_WARM_H * 3600:
                log("ВНИМАНИЕ РОЗНИЦЫ", fs, note + " — первые 7 суток журнала: только история пятёрок, сделки нет")
                continue
            on = (trader.contract(fs) or {}).get("onboard") or 0
            if on and T - on < 86400:
                log("ВНИМАНИЕ РОЗНИЦЫ", fs, note + f" — фьючерс запущен {(T - on) / 3600:.0f} ч назад, моложе суток, пропуск")
                continue
            if _virt_entered(state, "virtual_KT", fs, T - RT_KT_H * 3600, T + 600):
                log("ВНИМАНИЕ РОЗНИЦЫ", fs, note + " — у монеты был вход 🔝 за 7 суток, пропуск")
                continue
            if lst == "try":
                hit = [trader.VIRTUALS[k]["icon"] for k in ("virtual_KT", "virtual_SP", "virtual_KR")
                       if _virt_entered(state, k, fs, T - RT_PAST_H * 3600, T)]
                if hit:
                    log("ВНИМАНИЕ РОЗНИЦЫ", fs, note + f" — за прошлые сутки был вход {' '.join(hit)}, пропуск")
                    continue
            was = _virt_is_open(state, "virtual_RT", fs)
            m = trader.virt_open(state, "virtual_RT", fs, "RT", note)
            opened = not was and _virt_is_open(state, "virtual_RT", fs)
            log("ВНИМАНИЕ РОЗНИЦЫ", fs, note + (" → шорт 👀" if opened else
                                               " — сделка не открыта (уже есть, кулдаун 7 суток или нет цены)"))
            if m:
                msgs.append(m)
        for c in [c for c, t in hist.items() if T - t > (RT_NEW_H + 24) * 3600]:
            del hist[c]
    return msgs


O9_RISE, O9_SHARE, O9_LATE = 0.05, 0.20, 480   # ⏰: рост фьючерса за час 00–01 UTC ≥ 5%, доля Кореи ≥ 20% (research/s88);
                                                # сбой данных — повтор прохода до 8 мин после 01:00 UTC


def open9_rule(state):
    """«9 утра» — всплеск на открытии дня Upbit (журнал ⏰, research/s88/ВЫВОДЫ.md): раз в сутки, в первые 10 мин после
    01:00 UTC (10:00 по Корее), — фьючерсы Binance монет, которые торгуются к воне на Upbit или Bithumb. Рост за час
    00:00–01:00 UTC (закрытие 15-мин свечи в 01:00 к закрытию в 00:00) ≥ 5%, доля Upbit + Bithumb в обороте этого часа
    вместе с фьючерсом Binance ≥ 20%, фьючерс запущен не меньше суток назад → виртуальный шорт, тейк 10 / стоп 25 / 48 ч,
    плечо ×1. Если Binance или корейская биржа не отдали данные монеты, проход повторяется до 8 мин после 01:00 UTC
    (открытые сделки не дублируются). Возвращает сообщения для чата."""
    T = candle_due(state, "o9_last_T", "9 УТРА", step=3600)
    if T is None:
        return []
    if T % 86400 != 3600:                                        # не час открытия дня Upbit
        candle_done(state, "o9_last_T", T)
        return []
    kr = _kr_list()
    if not kr["upbit"] or not kr["bithumb"]:
        return candle_retry("o9_last_T", "нет списка рынков к воне Upbit или Bithumb")
    tick = ticker24()
    if not isinstance(tick, list):
        return candle_retry("o9_last_T", "Binance не отдал цены фьючерсов за сутки (ticker/24hr)")
    trader.contract("BTC")                                       # загружает список бессрочных контрактов USDT
    if not trader._contracts:
        return candle_retry("o9_last_T", "Binance не отдал список контрактов")
    cands = []
    for x in tick:
        s = str(x.get("symbol", ""))
        try:
            hi, lo = float(x["highPrice"]), float(x["lowPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if s not in trader._contracts or lo <= 0 or hi < lo * (1 + O9_RISE):   # рост ≥ 5% за час виден и в размахе за сутки
            continue
        coin = re.sub(r"^(1000000|100000|10000|1000)", "", s[:-4])
        exs = [e for e in ("upbit", "bithumb") if coin in kr[e]]
        if exs:
            cands.append((s[:-4], coin, exs))
    with ThreadPoolExecutor(8) as ex:
        ks = dict(zip([c[0] for c in cands], ex.map(lambda c: _closed_15m(c[0], T, 7), cands)))
    msgs, fail, n_rise = [], [], 0
    for s, coin, exs in cands:
        k = ks.get(s)
        if not k or len(k) < 5:
            fail.append(s)
            continue
        c0, c = float(k[-5][4]), float(k[-1][4])
        rise = c / c0 - 1 if c0 > 0 else 0.0
        if rise < O9_RISE:
            continue
        n_rise += 1
        fut = sum(float(x[7]) for x in k[-4:])
        vols = {e: _kr_volume(e, coin, T) for e in exs}
        if any(v is None for v in vols.values()):
            fail.append(s)
            log("9 УТРА", s, f"рост за час {rise * 100:+.1f}%, но {'/'.join(e.capitalize() for e, v in vols.items() if v is None)}"
                " не отдал оборот за час")
            continue
        got = sum(vols.values())
        share = got / (got + fut) if got + fut > 0 else 0.0
        note = (f"{coin}: фьючерс за час открытия дня Upbit (00–01 UTC) {rise * 100:+.1f}%, доля Кореи в обороте часа "
                f"{share * 100:.0f}% (" + ", ".join(f"{e.capitalize()} {v / 1e6:.2f} млн $" for e, v in vols.items())
                + f", фьючерс Binance {fut / 1e6:.2f} млн $)")
        if share < O9_SHARE:
            log("9 УТРА", s, note + " — доля Кореи меньше 20%, сделки нет")
            continue
        on = (trader.contract(s) or {}).get("onboard") or 0
        if on and T - on < 86400:
            log("9 УТРА", s, note + f" — фьючерс запущен {(T - on) / 3600:.0f} ч назад, моложе суток, пропуск")
            continue
        was = _virt_is_open(state, "virtual_O9", s)
        m = trader.virt_open(state, "virtual_O9", s, "O9", note, price=c)
        opened = not was and _virt_is_open(state, "virtual_O9", s)
        log("9 УТРА", s, note + (" → шорт ⏰" if opened else " — сделка не открыта (уже есть, кулдаун или нет цены)"))
        if m:
            msgs.append(m)
    if fail and time.time() - T <= O9_LATE:
        candle_retry("o9_last_T", "не получены свечи или корейский оборот: " + ", ".join(fail))
        return msgs
    candle_done(state, "o9_last_T", T)
    log("9 УТРА", f"кандидатов (рынок к воне, размах за сутки ≥ 5%) {len(cands)}, рост за час ≥ 5% у {n_rise}"
        + (f"; не проверены — нет данных: {', '.join(fail)}" if fail else ""))
    return msgs


UL_API ="https://api.coinmarketcap.com/data-api/v3/token-unlock"    # 🔓: публичный data-api сайта CoinMarketCap, без ключа
UL_EVERY, UL_HORIZON_D, UL_ENTRY_D, UL_EXIT_D = 86400, 10, 7, 1   # 🔓: расписание раз в сутки на 10 сут вперёд; шорт за 7 сут
                                                                   # до разлока, выход через сутки после
UL_CLIFF, UL_ANY, UL_GROUP_D = 5.0, 25.0, 2    # разлок с cliff ≥ 5% монет в обращении или любой ≥ 25%; события монеты в пределах
                                               # 2 сут — один разлок (research/s28)
UL_LATE_H, UL_STALE_H, UL_PX = 24, 36, (0.8, 1.25)   # вход — до 24 ч позже срока; расписание монеты — не старше 36 ч; цена
                                                     # фьючерса к цене CMC (у разных монет бывают одинаковые тикеры)
UL_BATCH, UL_PASS_S, UL_TRIES = 15, 15, 3      # за проход — до 15 монет и 15 с запросов к CMC; монету, не отданную 3 раза, — до завтра


def _ul_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _ul_mult(coin, fs):
    """Множитель фьючерса к цене монеты: 1000PEPE → 1000."""
    pre = fs[:-len(coin)] if fs.endswith(coin) else ""
    return float(pre) if pre.isdigit() else 1.0


def _ul_listing():
    """Монеты с расписанием разлоков на CoinMarketCap, у которых есть бессрочный фьючерс Binance:
    {cryptoId: [монета, фьючерс, монет в обращении, цена $]}. None — CMC или Binance не ответили."""
    trader._contracts.clear()                                # раз в сутки — свежий список контрактов (вес 1): новые фьючерсы
    trader.contract("BTC")                                   # появляются и без перезапуска бота
    if not trader._contracts:
        return None
    out, page, pages = {}, 1, 1
    while page <= min(pages, 40):
        j = http_json(f"{UL_API}/listing?start={page}&limit=100", 20)
        d = j.get("data") if isinstance(j, dict) else None
        rows = d.get("tokenUnlockList") if isinstance(d, dict) else None
        if not isinstance(rows, list):
            return None
        if not rows:
            break
        try:
            pages = math.ceil(int(d.get("totalCount") or 0) / 100)
        except (TypeError, ValueError):
            pages = page + 1
        for r in rows:
            try:
                coin, cid = str(r["symbol"]).strip().upper(), int(r["cryptoId"])
                circ = float(r.get("circulatingSupply") or 0)
                px = float(((r.get("quotes") or [{}])[0] or {}).get("price") or 0)
            except (KeyError, TypeError, ValueError, IndexError, AttributeError):
                continue
            if not coin or " " in coin or coin in BL_SKIP:
                continue
            fs = _fut_sym(coin)
            if fs:
                out[str(cid)] = [coin, fs, circ, px]
        page += 1
    return out


def _ul_events(cid):
    """Будущие разлоки монеты на UL_HORIZON_D сут (с запасом на группу): [(время, объём, % общего предложения, cliff,
    получатели)]. None — CMC не ответил."""
    out, horizon = [], time.time() + (UL_HORIZON_D + UL_GROUP_D) * 86400
    for page in (1, 2, 3):                                   # у монет с почасовыми разлоками 100 событий — меньше 10 сут
        j = http_json(f"{UL_API}/event?cryptoId={cid}&type=upcoming&page={page}&limit=100", 15)
        d = j.get("data") if isinstance(j, dict) else None
        if not isinstance(d, dict):
            return None
        ev = d.get("tokenEvent") or []
        if not isinstance(ev, list):
            return None
        last = None
        for e in ev:
            try:
                t, amt = _ul_ts(e["time"]), float(e.get("amount") or 0)
                al = e.get("allocations") or []
                out.append((t, amt, float(e.get("percentage") or 0), any(a.get("vestingType") == "cliff" for a in al),
                            tuple(sorted({str(a.get("allocationName") or "")[:40] for a in al} - {""}))))
                last = t
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        if len(ev) < 100 or last is None or last > horizon:
            break
    return [x for x in out if x[0]]


def _ul_candidates(evs, circ):
    """Крупные разлоки из расписания монеты, как в бэктесте research/s28: разлок — крупнейшее событие в пределах ±2 сут,
    к нему прибавляются события следующих 2 сут; доля — к монетам в обращении (их нет — к общему предложению, как в
    бэктесте); cliff — есть получатель с разлоком одним куском. Крупный: cliff и ≥ 5% или любой ≥ 25%."""
    G = UL_GROUP_D * 86400; out = []
    for t, amt, pct, cl, names in evs:
        if any(abs(x[0] - t) <= G and (x[1] > amt or (x[1] == amt and x[0] < t)) for x in evs):
            continue
        grp = [x for x in evs if t <= x[0] <= t + G]
        size = sum(x[1] for x in grp) / circ * 100 if circ > 0 else sum(x[2] for x in grp)
        cliff = any(x[3] for x in grp)
        if (cliff and size >= UL_CLIFF) or size >= UL_ANY:
            out.append({"T": t, "size": round(size, 2), "cliff": cliff, "by": "circ" if circ > 0 else "total",
                        "names": sorted({n for x in grp for n in x[4]})[:5]})
    return out


def _ul_what(c):
    return (f"{c['fs']}: разлок {datetime.fromtimestamp(c['T'], timezone.utc):%d.%m %H:%M} UTC — {c['size']:.1f}% монет "
            + ("в обращении" if c["by"] == "circ" else "общего предложения (в обращении — нет данных CMC)")
            + (", есть разлок одним куском (cliff)" if c["cliff"] else ""))


def unlock_rule(state):
    """Перед разлоком (журнал 🔓, research/s28/ВЫВОДЫ.md). Раз в сутки — список монет с расписанием разлоков на
    CoinMarketCap (публичный data-api сайта, без ключа); для монет с бессрочным фьючерсом Binance — будущие разлоки на 10 сут,
    по 15 монет за проход (полный круг — около 40 мин). Крупный разлок (_ul_candidates): cliff ≥ 5% монет в обращении или
    любой ≥ 25%. Цена фьючерса сверяется с ценой CMC (0,8–1,25): у разных монет бывают одинаковые тикеры. → Виртуальный
    шорт за 7 сут до разлока (бот опоздал — до 24 ч позже срока), выход через сутки после разлока, без тейка, стоп +50%,
    плечо ×1. Перенос разлока до входа — вход по новой дате; после входа — выход по прежней. Сообщения для чата."""
    now = time.time(); u = state.setdefault("ul", {}); msgs = []
    sched = u.setdefault("sched", {}); done = u.setdefault("done", {}); listed = False
    if not u.get("queue") and now - u.get("list_t", 0) >= UL_EVERY and now >= u.get("next", 0):
        tok = _ul_listing(); listed = True                   # 14 запросов — расписание монет начнётся со следующего прохода
        if tok:
            u.update(tok=tok, queue=sorted(tok, key=int), list_t=now, tries={}, n_ev=0)
            circ = {}                                        # монеты в обращении по фьючерсам — для 🏦ᵐ; живёт до следующей загрузки
            for coin, fs, cs, px in tok.values():
                if cs and cs > 0:
                    circ[fs] = max(circ.get(fs, 0.0), float(cs))
            u["circ"], u["circ_t"] = circ, now
            log("РАЗЛОК", f"CoinMarketCap: монет с разлоками и фьючерсом Binance {len(tok)} — обновляю расписание, "
                          f"по {UL_BATCH} за проход")
        else:
            u["next"] = now + 600
            if now - u.get("err", 0) >= 6 * 3600:
                u["err"] = now
                log("РАЗЛОК", "CoinMarketCap не отдал список монет с разлоками (или Binance — список контрактов), повтор "
                              "через 10 мин")
    q = u.get("queue") or []; tok = u.get("tok") or {}; tries = u.setdefault("tries", {}) if q else {}
    t0 = time.time(); n = fails = 0
    while q and not listed and n < UL_BATCH and time.time() - t0 < UL_PASS_S and fails < 3:
        cid = q.pop(0); n += 1
        if cid not in tok:
            continue
        coin, fs, circ, px = tok[cid]
        evs = _ul_events(cid)
        if evs is None:
            fails += 1; tries[cid] = tries.get(cid, 0) + 1
            if tries[cid] < UL_TRIES:
                q.append(cid)
            else:
                log("РАЗЛОК", f"{fs}: CoinMarketCap {UL_TRIES} раза не отдал расписание — до следующего обновления")
            continue
        u["n_ev"] = u.get("n_ev", 0) + 1
        old = {k: c["T"] for k, c in sched.items() if c["cid"] == cid}
        for k in old:
            del sched[k]                                     # расписание монеты — свежее: разлок могли перенести
        for c in _ul_candidates(evs, circ):
            key = f"{fs}:{int(c['T'])}"
            if key in done or not now < c["T"] <= now + UL_HORIZON_D * 86400:
                continue                                     # дальние разлоки — в следующих обновлениях
            mark = trader.mark_price(fs) if c["T"] - UL_ENTRY_D * 86400 + UL_LATE_H * 3600 > now else None
            c.update(cid=cid, coin=coin, fs=fs, px=px, chk=now,
                     ratio=round(mark / (px * _ul_mult(coin, fs)), 4) if mark and px > 0 else None)
            sched[key] = c
            if key not in old:
                log("РАЗЛОК", _ul_what(c) + f"; получатели: {', '.join(c['names']) or '—'}; шорт "
                    f"{datetime.fromtimestamp(c['T'] - UL_ENTRY_D * 86400, timezone.utc):%d.%m %H:%M} UTC"
                    + (f", цена фьючерса {c['ratio']:.2f} от цены CMC" if c["ratio"] else ""))
    if u.get("queue") is not None and not q and tok:
        log("РАЗЛОК", f"расписание обновлено: монет {u.get('n_ev', 0)} из {len(tok)}; крупных разлоков в ближайшие "
                      f"{UL_HORIZON_D} сут — {len(sched)}")
        for k in ("tok", "tries", "queue", "n_ev"):
            u.pop(k, None)
    for key, c in sorted(sched.items(), key=lambda kv: kv[1]["T"]):
        t_in = c["T"] - UL_ENTRY_D * 86400
        if now < t_in:
            continue
        what = _ul_what(c)
        if now > t_in + UL_LATE_H * 3600:
            del sched[key]; done[key] = now
            log("РАЗЛОК", what + f" — срок входа {datetime.fromtimestamp(t_in, timezone.utc):%d.%m %H:%M} UTC прошёл больше "
                          f"{UL_LATE_H} ч назад (бот не работал или разлок появился в расписании поздно), сделки нет")
            continue
        if now - c["chk"] > UL_STALE_H * 3600:
            if not c.get("stale"):
                c["stale"] = True
                log("РАЗЛОК", what + f" — расписание монеты не обновлялось {(now - c['chk']) / 3600:.0f} ч (CoinMarketCap не "
                                     "отвечал), вход ждёт обновления")
            continue
        if c.get("ratio") is None:
            mark = trader.mark_price(c["fs"])
            if not mark:
                continue                                     # Binance не отдал цену — повтор в следующем проходе
            c["ratio"] = round(mark / (c["px"] * _ul_mult(c["coin"], c["fs"])), 4) if c["px"] > 0 else 1.0
        if not UL_PX[0] <= c["ratio"] <= UL_PX[1]:
            del sched[key]; done[key] = now
            log("РАЗЛОК", what + f" — цена фьючерса {c['ratio']:.2f} от цены CoinMarketCap: похоже, другой токен с тем же "
                                 "тикером или ошибка данных, сделки нет")
            continue
        t_out = c["T"] + UL_EXIT_D * 86400
        note = (f"CoinMarketCap: разлок {datetime.fromtimestamp(c['T'], timezone.utc):%d.%m %H:%M} UTC — {c['size']:.1f}% монет "
                + ("в обращении" if c["by"] == "circ" else "общего предложения")
                + (", есть разлок одним куском (cliff)" if c["cliff"] else "")
                + f"; получатели: {', '.join(c['names']) or '—'}; выход через сутки после разлока, "
                  f"{datetime.fromtimestamp(t_out, timezone.utc):%d.%m %H:%M} UTC")
        was = _virt_is_open(state, "virtual_UL", c["fs"])
        m = None if was else trader.virt_open(state, "virtual_UL", c["fs"], "UL", note, hold_h=round((t_out - now) / 3600, 2))
        if m:
            del sched[key]; done[key] = now
            log("РАЗЛОК", c["fs"], note)
            msgs.append(m)
        elif was:
            del sched[key]; done[key] = now
            log("РАЗЛОК", what + " — сделка по монете уже открыта, пропуск")
        # иначе Binance не отдал цену — повтор в следующем проходе, до 24 ч после срока
    for k in [k for k, ts in done.items() if ts < now - 40 * 86400]:
        del done[k]
    return msgs


IU_LIST = "https://defillama-datasets.llama.fi/emissionsProtocolsList"   # 🔑: расписания разлоков DefiLlama, без ключа
IU_PROJ = "https://defillama-datasets.llama.fi/emissions/{}"
IU_PRICE = "https://coins.llama.fi/prices/current/{}"                   # тикер и цена токена по адресу или id CoinGecko
IU_EVERY, IU_HORIZON_D, IU_ENTRY_D, IU_EXIT_D = 86400, 10, 7, 1   # расписание раз в сутки на 10 сут вперёд; шорт за 7 сут
                                                                   # до разлока, выход через сутки после
IU_MIN, IU_INS, IU_COOL_D = 1.0, ("insiders", "privateSale"), 7   # разлок команде и инвесторам ≥ 1% монет в обращении; одна
                                                                  # сделка на монету за 7 сут (research/s139, U2)
IU_NOT = ("noncirculating", "burned")          # 🔑⁺: все получатели, кроме казны и сожжённого (research/s142, U6)
IU_LATE_H, IU_STALE_H, IU_PX = 24, 36, (0.8, 1.25)   # вход — до 24 ч позже срока; расписание — не старше 36 ч; цена фьючерса
                                                     # к цене DefiLlama (у разных монет бывают одинаковые тикеры)
IU_BATCH, IU_PASS_S, IU_TRIES = 10, 20, 3      # за проход — до 10 проектов и 20 с; проект, не отданный 3 раза, — до завтра


def _http_gz(url, timeout=30):
    """GET со сжатием gzip (файл проекта DefiLlama ~1 МБ, сжатый — в 13 раз меньше) → JSON или None."""
    host = urllib.parse.urlsplit(url).hostname or "?"
    t0 = time.time(); ok = False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
        ok = True
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception as e:
        log("http_json fail", url.split("?")[0], e)
        return None
    finally:
        trader.net_note(host, time.time() - t0, ok)


def _iu_candidates(E, now, who="ins"):
    """Разовые разлоки из файла проекта DefiLlama — как в бэктестах research/s139 (U2, who="ins": команда и инвесторы —
    категории insiders и privateSale) и research/s142 (U6, who="all": все получатели, кроме noncirculating и burned).
    События cliff одних суток UTC складываются (срок — самое раннее); доля — к монетам в обращении по расписанию:
    разлоченное по разделам, кроме noncirculating, на последнюю точку не позже T − 1 сут.
    Возвращает [{T, share (%), names}] для разлоков ≥ 1% в (now, now + IU_HORIZON_D сут]."""
    nonc = set((E.get("categories") or {}).get("noncirculating") or [])
    secs = []
    for sec in (E.get("documentedData") or {}).get("data") or []:
        if not isinstance(sec, dict) or sec.get("label") in nonc:
            continue
        pts = []
        for p in sec.get("data") or []:
            try:
                pts.append((float(p["timestamp"]), float(p.get("unlocked") or 0)))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        if pts:
            secs.append(sorted(pts))
    agg = {}
    for ev in (E.get("metadata") or {}).get("events") or []:
        try:
            cat = ev.get("category")
            if ev.get("unlockType") != "cliff" or (cat not in IU_INS if who == "ins" else cat in IU_NOT):
                continue
            t = int(float(ev["timestamp"])); n = sum(float(x) for x in (ev.get("noOfTokens") or [0]))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if n <= 0:
            continue
        a = agg.setdefault(t // 86400, {"T": t, "n": 0.0, "names": set()})
        a["T"] = min(a["T"], t); a["n"] += n
        m = re.search(r"from (.+?) on \{timestamp\}", str(ev.get("description") or ""))
        a["names"].add(str(m.group(1) if m else ev.get("category"))[:40])
    out = []
    for a in agg.values():
        if not now < a["T"] <= now + IU_HORIZON_D * 86400:
            continue
        lim = a["T"] - 86400
        circ = sum(next((u for ts, u in reversed(pts) if ts <= lim), 0.0) for pts in secs)
        if circ > 0 and a["n"] / circ * 100 >= IU_MIN:
            out.append({"T": a["T"], "share": round(a["n"] / circ * 100, 2), "names": sorted(a["names"])[:5]})
    return out


def _iu_price(E):
    """Тикер и цена токена проекта по coins.llama.fi: сначала адрес из metadata.token («сеть:адрес» или «coingecko:id»),
    не нашлось — id CoinGecko проекта (у токенов Sui с «::» в адресе и у части проектов адрес не находится).
    (тикер, цена $) или None."""
    keys = [(E.get("metadata") or {}).get("token"), f"coingecko:{E['gecko_id']}" if E.get("gecko_id") else None]
    for key in dict.fromkeys(k for k in keys if k):
        j = http_json(IU_PRICE.format(urllib.parse.quote(str(key), safe=":")), 15)
        coins = j.get("coins") if isinstance(j, dict) else None
        c = next(iter(coins.values()), None) if isinstance(coins, dict) and coins else None
        try:
            sym, px = re.sub(r"[^A-Z0-9]", "", str(c["symbol"]).upper()), float(c["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if sym and px > 0:
            return sym, px
    return None


def _iu_what(c):
    who = "команде и инвесторам" if c.get("j", "IU") == "IU" else "всем получателям, кроме казны"
    return (f"{c['fs']}: разлок {who} {datetime.fromtimestamp(c['T'], timezone.utc):%d.%m %H:%M} UTC — "
            f"{c['share']:.1f}% монет в обращении по расписанию DefiLlama")


IU_J = {"IU": ("virtual_IU", "РАЗЛОК ИНСАЙДЕРАМ", "🔑"), "IUA": ("virtual_IUA", "РАЗЛОК ВСЕМ", "🔑⁺")}


def insider_unlock_rule(state):
    """Разлок инсайдерам (журнал 🔑, research/s139/ВЫВОДЫ.md, U2) и его двойник 🔑⁺ — разлок всем получателям, кроме казны
    (research/s142, U6). Раз в сутки — список проектов с расписанием разлоков DefiLlama (без ключа), потом файлы проектов
    по 10 за проход (со сжатием gzip; полный круг ~40 мин). Разлок одним куском ≥ 1% монет в обращении по расписанию
    (_iu_candidates) в ближайшие 10 сут: для 🔑 — команде и инвесторам (insiders, privateSale), для 🔑⁺ — всем, кроме
    noncirculating и burned. → Тикер и цена токена по coins.llama.fi, бессрочный фьючерс Binance, цена фьючерса к цене
    DefiLlama 0,8–1,25. → Виртуальный шорт за 7 сут до разлока (бот опоздал — до 24 ч позже срока), выход через сутки после
    разлока, без тейка, стоп +50%, плечо ×1; в каждом журнале одна сделка на монету за 7 сут. Совместный вход — строкой
    к сообщению 🔑. Перенос разлока до входа — вход по новой дате. Сообщения для чата."""
    now = time.time(); u = state.setdefault("iu", {}); msgs = []
    sched = u.setdefault("sched", {}); done = u.setdefault("done", {}); listed = False
    if not u.get("queue") and now - u.get("list_t", 0) >= IU_EVERY and now >= u.get("next", 0):
        lst = _http_gz(IU_LIST, 20); listed = True
        slugs = sorted({x for x in lst if isinstance(x, str) and x}) if isinstance(lst, list) else []
        if slugs:
            u.update(queue=slugs, list_t=now, tries={}, n_ok=0)
            log("РАЗЛОК ИНСАЙДЕРАМ", f"DefiLlama: проектов с расписанием разлоков {len(slugs)} — обновляю расписание, "
                                     f"по {IU_BATCH} за проход")
        else:
            u["next"] = now + 600
            if now - u.get("err", 0) >= 6 * 3600:
                u["err"] = now
                log("РАЗЛОК ИНСАЙДЕРАМ", "DefiLlama не отдала список проектов с разлоками, повтор через 10 мин")
    q = u.get("queue") or []; tries = u.setdefault("tries", {}) if q else {}
    t0 = time.time(); n = fails = 0
    while q and not listed and n < IU_BATCH and time.time() - t0 < IU_PASS_S and fails < 3:
        slug = q.pop(0); n += 1
        E = _http_gz(IU_PROJ.format(urllib.parse.quote(slug)), 30)
        if not isinstance(E, dict):
            fails += 1; tries[slug] = tries.get(slug, 0) + 1
            if tries[slug] < IU_TRIES:
                q.append(slug)
            else:
                log("РАЗЛОК ИНСАЙДЕРАМ", f"{slug}: DefiLlama {IU_TRIES} раза не отдала расписание — до следующего обновления")
            continue
        u["n_ok"] = u.get("n_ok", 0) + 1
        old = {k for k, c in sched.items() if c["slug"] == slug}
        for k in old:
            del sched[k]                                     # расписание проекта — свежее: разлок могли перенести
        try:
            cands = ([dict(c, j="IU") for c in _iu_candidates(E, now)]
                     + [dict(c, j="IUA") for c in _iu_candidates(E, now, "all")])
        except Exception as e:                               # неожиданная структура файла — проект пропускается до завтра
            log("РАЗЛОК ИНСАЙДЕРАМ", f"{slug}: не разобрать расписание DefiLlama ({e!r}) — до следующего обновления")
            continue
        if not cands:
            continue
        trader.contract("BTC")
        if not trader._contracts:                            # Binance не отдал список контрактов — проект ещё раз в этом
            fails += 1; tries[slug] = tries.get(slug, 0) + 1   # обновлении, не больше 3 раз
            if tries[slug] < IU_TRIES:
                q.append(slug)
            continue
        info = _iu_price(E)
        if not info:
            log("РАЗЛОК ИНСАЙДЕРАМ", f"{slug}: разлок ≥ {IU_MIN:g}% есть, но coins.llama.fi не отдал тикер и цену токена — "
                                     "до следующего обновления")
            continue
        coin, px = info
        fs = _fut_sym(coin) if coin not in BL_SKIP else None
        if not fs:
            continue                                         # у монеты нет бессрочного фьючерса Binance
        mark = None
        for c in cands:
            key = ("+" if c["j"] == "IUA" else "") + f"{fs}:{int(c['T'] // 86400)}"   # 🔑 — «FS:сутки», 🔑⁺ — «+FS:сутки»
            if key in done:
                continue
            if mark is None and c["T"] - IU_ENTRY_D * 86400 + IU_LATE_H * 3600 > now:
                mark = trader.mark_price(fs) or 0.0
            c.update(slug=slug, coin=coin, fs=fs, px=px, chk=now,
                     ratio=round(mark / (px * _ul_mult(coin, fs)), 4) if mark and px > 0 else None)
            sched[key] = c
            if key not in old:
                log(IU_J[c["j"]][1], _iu_what(c) + f"; получатели: {', '.join(c['names']) or '—'}; шорт "
                    f"{datetime.fromtimestamp(c['T'] - IU_ENTRY_D * 86400, timezone.utc):%d.%m %H:%M} UTC"
                    + (f", цена фьючерса {c['ratio']:.2f} от цены DefiLlama" if c["ratio"] else ""))
    if u.get("queue") is not None and not q:
        n_iu = sum(1 for c in sched.values() if c.get("j", "IU") == "IU")
        log("РАЗЛОК ИНСАЙДЕРАМ", f"расписание обновлено: проектов {u.get('n_ok', 0)}; разлоков ≥ {IU_MIN:g}% с фьючерсом Binance "
                                 f"в ближайшие {IU_HORIZON_D} сут: команде и инвесторам — {n_iu}, всем получателям — "
                                 f"{len(sched) - n_iu}")
        for k in ("tries", "queue", "n_ok"):
            u.pop(k, None)
    opened = {}                                              # (монета, сутки) → {журнал: (сообщение, кандидат)}
    for key, c in sorted(sched.items(), key=lambda kv: kv[1]["T"]):
        j = c.get("j", "IU"); vkey, tag, icon = IU_J[j]
        t_in = c["T"] - IU_ENTRY_D * 86400
        if now < t_in:
            continue
        what = f"{icon} " + _iu_what(c)
        if now > t_in + IU_LATE_H * 3600:
            del sched[key]; done[key] = now
            log(tag, what + f" — срок входа {datetime.fromtimestamp(t_in, timezone.utc):%d.%m %H:%M} UTC прошёл больше "
                f"{IU_LATE_H} ч назад (бот не работал или разлок появился в расписании поздно), сделки нет")
            continue
        if now - c["chk"] > IU_STALE_H * 3600:
            if not c.get("stale"):
                c["stale"] = True
                log(tag, what + f" — расписание не обновлялось {(now - c['chk']) / 3600:.0f} ч (DefiLlama не отвечала), "
                                "вход ждёт обновления")
            continue
        if c.get("ratio") is None:
            mark = trader.mark_price(c["fs"])
            if not mark:
                continue                                     # Binance не отдал цену — повтор в следующем проходе
            c["ratio"] = round(mark / (c["px"] * _ul_mult(c["coin"], c["fs"])), 4)
        if not IU_PX[0] <= c["ratio"] <= IU_PX[1]:
            del sched[key]; done[key] = now
            log(tag, what + f" — цена фьючерса {c['ratio']:.2f} от цены DefiLlama: похоже, другой токен с тем же тикером "
                            "или ошибка данных, сделки нет")
            continue
        if _virt_is_open(state, vkey, c["fs"]) or any(t["sym"] == c["fs"] and now - t["opened"] < IU_COOL_D * 86400
                                                       for t in state.get(vkey, {}).get("trades", [])):
            del sched[key]; done[key] = now
            log(tag, what + f" — сделка по монете открыта или была меньше {IU_COOL_D} сут назад, пропуск")
            continue
        t_out = c["T"] + IU_EXIT_D * 86400
        who = "команде и инвесторам" if j == "IU" else "всем получателям, кроме казны"
        note = (f"DefiLlama: разлок {who} {datetime.fromtimestamp(c['T'], timezone.utc):%d.%m %H:%M} UTC — "
                f"{c['share']:.1f}% монет в обращении по расписанию; получатели: {', '.join(c['names']) or '—'}; "
                f"выход через сутки после разлока, {datetime.fromtimestamp(t_out, timezone.utc):%d.%m %H:%M} UTC")
        m = trader.virt_open(state, vkey, c["fs"], j, note, hold_h=round((t_out - now) / 3600, 2))
        if m:
            del sched[key]; done[key] = now
            log(tag, c["fs"], note)
            opened.setdefault((c["fs"], int(c["T"] // 86400)), {})[j] = (m, c)
        # иначе Binance не отдал цену — повтор в следующем проходе, до 24 ч после срока
    for both in opened.values():                             # совместный вход 🔑 и 🔑⁺ — строкой к сообщению 🔑
        if "IU" in both and "IUA" in both:
            msgs.append(both["IU"][0] + f"\n🔑⁺ тот же шорт (все получатели: {both['IUA'][1]['share']:.1f}% монет в обращении)")
        else:
            msgs.extend(m for m, _ in both.values())
    for k in [k for k, ts in done.items() if ts < now - 40 * 86400]:
        del done[k]
    return msgs


WD_RPC = ("https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://ethereum-rpc.publicnode.com",
          "https://eth.llamarpc.com")                              # 🐋: публичные узлы Ethereum без ключа, по очереди
WD_LABELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cex_labels.tsv")   # метки адресов бирж (research/s160)
WD_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"     # событие Transfer у ERC-20
WD_CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|"
                     r"matrixport|ceffu|hex trust|komainu|cobo|paxos|custody", re.I)   # кастоди, прайм-брокеры, ММ — не завод
WD_CMC = ("https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing?start={}&limit=5000&sortBy=market_cap"
          "&sortType=desc&convert=USD&cryptoType=all&tagType=all&audited=false")
WD_CG = "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
WD_MIN, WD_GAP_H, WD_CALM, WD_PX = 0.005, 48, 0.05, (0.8, 1.25)  # завод ≥ 0,5% монет в обращении; первый у монеты за 48 ч;
                                                                 # фьючерс за сутки до входа ±5%; цена фьючерса к цене CMC
WD_EVERY, WD_LIST_EVERY, WD_CONF = 120, 86400, 3   # блоки — раз в 2 мин; список токенов — раз в сутки; 3 блока на перестройку
WD_STEP, WD_BACK, WD_LATE = 300, 1200, 1800        # запрос — до 300 блоков (1 ч); догоняем не больше 1200 блоков (4 ч);
                                                    # вход — не позже 30 мин после закрытия свечи входа
WD_DEC_BATCH, WD_RPC_S = 20, 30                    # знаков после запятой — до 20 токенов за проход; на один вызов узлов — до 30 с
WD_ZERO = "0x" + "0" * 40
WDV_LAM, WDV_K = 0.05, 700                          # 🐋ᵛ: завод ≥ 5% среднесуточного оборота фьючерса за 7 сут (research/s213);
                                                    # 15-мин свечей в запросе входа — 7 сут + запас на опоздание (вес 5)
_wd_lab = {"mtime": None, "cex": {}, "bin": []}
_wd_tmp = {}                                        # список токенов собирается за несколько проходов: CMC, CoinGecko, цены


def _wd_labels():
    """Метки адресов бирж из cex_labels.tsv: {"cex": {адрес: (биржа, название)}, "bin": адреса Binance без кастоди}.
    None — файла нет (после неудачной быстрой перемотки приходят только четыре файла бота)."""
    try:
        mt = os.path.getmtime(WD_LABELS)
    except OSError:
        return None
    if _wd_lab["mtime"] != mt:
        cex = {}
        try:
            with open(WD_LABELS, encoding="utf-8") as f:
                for ln in f:
                    p = ln.rstrip("\n").split("\t")
                    if len(p) >= 2 and p[0].startswith("0x") and len(p[0]) == 42:
                        cex[p[0].lower()] = (p[1], p[2] if len(p) > 2 else "")
        except OSError:
            return None
        _wd_lab.update(mtime=mt, cex=cex, bin=sorted(a for a, (ex, nm) in cex.items()
                                                    if ex == "Binance" and not WD_CUST.search(f"{ex} {nm}")))
    return _wd_lab if _wd_lab["bin"] else None


def _wd_rpc(method, params, timeout=20):
    """JSON-RPC Ethereum: узлы WD_RPC по очереди, пока не ответит один (не дольше WD_RPC_S на вызов).
    (результат, None) или (None, ошибка): «rpc: …» — хотя бы один узел ответил ошибкой (например, откат вызова), иначе
    «net: …» — ни один не ответил."""
    rpc_err = net_err = None; t0 = time.time()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for url in WD_RPC:
        if time.time() - t0 > WD_RPC_S:
            break
        host = urllib.parse.urlsplit(url).hostname
        try:
            j = json.loads(http(url, data=body, timeout=timeout, ctype="application/json"))
        except Exception as e:
            net_err = net_err or f"net: {host}: {e!r}"[:160]
            continue
        if isinstance(j, dict) and j.get("result") is not None:
            return j["result"], None
        rpc_err = rpc_err or f"rpc: {host}: {str(j.get('error') if isinstance(j, dict) else j)}"[:160]
    return None, rpc_err or net_err or "net: узлы не опрошены"


def _wd_base(fs):
    """Монета и множитель фьючерса: 1000PEPE → (PEPE, 1000), 1MBABYDOGE → (BABYDOGE, 1 000 000)."""
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return m.group(2), 1e6 if m.group(1) in ("1M", "1000000") else float(m.group(1))
    return fs, 1.0


def _wd_map(cmc, cg, px):
    """Токены Ethereum у фьючерсов Binance (как набор research/s160): монета CMC с тем же тикером, у которой цена сходится
    с ценой фьючерса (0,8–1,25), а из таких — с наибольшей капитализацией; контракт ERC-20 — основная платформа CMC, если это
    Ethereum, иначе монета CoinGecko с тем же id (slug CMC) или единственная с тем же названием. Стейблкоины и металлы — нет.
    px — {фьючерс: цена}. → {адрес: [фьючерс, монета, монет в обращении по CMC, id CMC]}"""
    by, gid, gname = {}, {}, {}
    for c in cmc:
        if isinstance(c, dict):
            by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    for c in cg:
        try:
            e = str((c.get("platforms") or {}).get("ethereum") or "").lower()
        except AttributeError:
            continue
        if e.startswith("0x") and len(e) == 42:
            gid[c.get("id")] = e
            gname.setdefault(str(c.get("name") or "").lower(), set()).add(e)
    out = {}
    for fs, p in px.items():
        coin, mult = _wd_base(fs)
        if coin in BL_SKIP or fs in BL_SKIP or p <= 0:
            continue
        best = None
        for c in by.get(coin, []):
            try:
                q = (c.get("quotes") or [{}])[0] or {}
                cp, mc = float(q.get("price") or 0), float(q.get("marketCap") or 0)
            except (TypeError, ValueError, IndexError, AttributeError):
                continue
            if cp > 0 and WD_PX[0] <= p / (cp * mult) <= WD_PX[1] and (best is None or mc > best[1]):
                best = (c, mc)
        if not best:
            continue
        c = best[0]; pl = c.get("platform") if isinstance(c.get("platform"), dict) else {}
        e = str(pl.get("token_address") or "").lower() if pl.get("slug") == "ethereum" else ""
        if not (e.startswith("0x") and len(e) == 42):
            e = gid.get(c.get("slug"), "")
        if not e:
            n = gname.get(str(c.get("name") or "").lower(), set())
            e = next(iter(n)) if len(n) == 1 else ""
        try:
            circ = float(c.get("circulatingSupply") or 0)
        except (TypeError, ValueError):
            circ = 0.0
        if e and circ > 0:
            out[e] = [fs, coin, circ, int(c.get("id") or 0)]
    return out


def _wd_refresh(w, now):
    """Раз в сутки — список токенов (_wd_map), по одному запросу за проход: CMC (одна-две страницы по 5000 монет), CoinGecko
    (монеты с адресами контрактов), цены фьючерсов Binance. Сбой — повтор через 10 мин, строка в журнал не чаще раза в 6 ч."""
    t = _wd_tmp
    if not t and (now - w.get("tok_t", 0) < WD_LIST_EVERY or now < w.get("tok_next", 0)):
        return

    def fail(why):
        _wd_tmp.clear(); w["tok_next"] = now + 600
        if now - w.get("tok_err", 0) >= 6 * 3600:
            w["tok_err"] = now
            log("ЗАВОДЫ", f"список токенов не обновлён: {why}; повтор через 10 мин")

    def cmc_rows(start):
        """Страница списка CMC — только нужные поля (между проходами список держится в памяти)."""
        j = http_json(WD_CMC.format(start), 60)
        d = j.get("data") if isinstance(j, dict) else None
        rows = d.get("cryptoCurrencyList") if isinstance(d, dict) else None
        if not isinstance(rows, list):
            return None
        out = []
        for c in rows:
            if not isinstance(c, dict):
                continue
            qs = [q for q in c.get("quotes") or [] if isinstance(q, dict)]
            q = next((q for q in qs if q.get("name") == "USD"), qs[0] if qs else {})
            out.append({"id": c.get("id"), "symbol": c.get("symbol"), "name": c.get("name"), "slug": c.get("slug"),
                        "circulatingSupply": c.get("circulatingSupply"),
                        "quotes": [{"price": q.get("price"), "marketCap": q.get("marketCap")}],
                        "platform": c.get("platform") if isinstance(c.get("platform"), dict) else None})
        return out

    if "cmc" not in t:
        rows = cmc_rows(1)
        if not rows:
            return fail("CoinMarketCap не отдал список монет")
        t.update(cmc=rows, more=len(rows) >= 5000)
        return
    if t.get("more"):
        rows = cmc_rows(5001)
        if rows is None:
            return fail("CoinMarketCap не отдал вторую страницу списка монет")
        t["cmc"] += rows; t["more"] = False
        return
    if "cg" not in t:
        j = http_json(WD_CG, 60)
        if not isinstance(j, list) or not j:
            return fail("CoinGecko не отдал список монет с адресами контрактов")
        t["cg"] = [{"id": c.get("id"), "name": c.get("name"), "platforms": {"ethereum": c["platforms"]["ethereum"]}}
                   for c in j if isinstance(c, dict) and isinstance(c.get("platforms"), dict)
                   and c["platforms"].get("ethereum")]               # нужны только монеты с адресом в Ethereum
        return
    trader.contract("BTC")
    j = http_json("https://fapi.binance.com/fapi/v1/ticker/price", 20)
    if not isinstance(j, list) or not trader._contracts:
        return fail("Binance не отдал цены фьючерсов или список контрактов")
    px = {}
    for x in j:
        s = str(x.get("symbol") or "") if isinstance(x, dict) else ""
        try:
            if s in trader._contracts and s.endswith("USDT"):
                px[s[:-4]] = float(x["price"])
        except (KeyError, TypeError, ValueError):
            continue
    tok = _wd_map(t["cmc"], t["cg"], px)
    _wd_tmp.clear()
    if not tok:
        return fail("ни одного токена Ethereum с фьючерсом Binance")
    old = set(w.get("tok") or {})
    new = sorted(tok[a][0] for a in tok if a not in old)
    w.update(tok=tok, tok_t=now)
    log("ЗАВОДЫ", f"список токенов Ethereum с фьючерсом Binance обновлён: {len(tok)}"
        + (f"; новые: {', '.join(new[:30])}" if old and new else ""))


def _wd_decimals(w):
    """Знаки после запятой у токенов (eth_call decimals(), не меняются): до WD_DEC_BATCH новых за проход.
    Токен без decimals() (узел ответил ошибкой или пустым ответом) — −1, такие не смотрим."""
    dec = w.setdefault("dec", {})
    for a in [a for a in w.get("tok") or {} if a not in dec][:WD_DEC_BATCH]:
        r, err = _wd_rpc("eth_call", [{"to": a, "data": "0x313ce567"}, "latest"], 15)
        try:
            d = int(r, 16) if isinstance(r, str) and len(r) > 2 else None
        except ValueError:
            d = None
        if d is not None and 0 <= d <= 36:
            dec[a] = d
        elif r is not None or (err or "").startswith("rpc:"):
            dec[a] = -1
        else:
            _wd_err(w, time.time(), f"узлы Ethereum не ответили на decimals() ({err})")
            break                                            # узлы не ответили — после паузы


def _wd_err(w, now, why):
    """Сбой узлов Ethereum: строка в журнал не чаще раза в час; пауза до следующей попытки растёт 2 → 4 → … → 30 мин,
    чтобы при обрыве сети проходы бота не удлинялись каждые 2 мин."""
    w["rpc_wait"] = min(1800, max(WD_EVERY, w.get("rpc_wait", WD_EVERY // 2) * 2))
    w["rpc_next"] = now + w["rpc_wait"]
    if now - w.get("err", 0) >= 3600:
        w["err"] = now
        log("ЗАВОДЫ", why + f" — повтор через {w['rpc_wait'] // 60} мин")


def _wd_block_time(x, cache):
    """Время блока перевода: поле blockTimestamp в логе (Tenderly), иначе eth_getBlockByNumber (кэш на проход)."""
    try:
        if x.get("blockTimestamp"):
            return int(x["blockTimestamp"], 16)
        b = int(x["blockNumber"], 16)
    except (KeyError, TypeError, ValueError):
        return None
    if b not in cache:
        r, _ = _wd_rpc("eth_getBlockByNumber", [hex(b), False], 15)
        try:
            cache[b] = int(r["timestamp"], 16)
        except (KeyError, TypeError, ValueError):
            cache[b] = None
    return cache[b]


def _wd_event(w, lab, tok, dec, x, cache):
    """Перевод токена на адрес Binance → событие, если: отправитель не биржа и не чеканка, сумма ≥ 0,5% монет в обращении
    и у монеты не было события 48 ч. Событие ждёт входа в w["pend"]."""
    try:
        a = str(x["address"]).lower()
        frm, to = ("0x" + str(x["topics"][i])[-40:].lower() for i in (1, 2))
        data = str(x.get("data") or "0x")
        amt = int(data, 16) if data not in ("0x", "") else 0
    except (KeyError, IndexError, TypeError, ValueError):
        return
    t, d = tok.get(a), dec.get(a, -1)
    if not t or d < 0 or to not in lab["cex"] or frm in lab["cex"] or frm == WD_ZERO:
        return                                               # перекладка с биржи, чеканка
    n = amt / 10 ** d; share = n / t[2]
    if share < WD_MIN:
        return
    fs, coin = t[0], t[1]
    ts = _wd_block_time(x, cache)
    if not ts:
        return log("ЗАВОДЫ", f"{fs}: перевод {share * 100:.2f}% монет в обращении, но узлы не отдали время блока — пропуск")
    tx = str(x.get("transactionHash") or "")
    what = (f"{fs}: {f'{n:,.0f}'.replace(',', ' ')} {coin} ({share * 100:.2f}% монет в обращении) на "
            f"{lab['cex'][to][1] or 'Binance'} с {frm[:10]}…, tx {tx[:12]}…, блок "
            f"{datetime.fromtimestamp(ts, timezone.utc):%d.%m %H:%M} UTC")
    last = w.setdefault("last", {})
    if ts - last.get(fs, 0) < WD_GAP_H * 3600:
        return log("ЗАВОДЫ", what + f" — событие монеты было {(ts - last[fs]) / 3600:.0f} ч назад, без сделки")
    last[fs] = ts
    te = int(-(-(ts + 900) // 900) * 900)                   # закрытие первой 15-мин свечи не раньше чем через 15 мин
    w.setdefault("pend", {})[fs] = {"t": ts, "te": te, "share": round(share * 100, 3), "n": n, "what": what}   # n — монет (🐋ᵛ)
    log("ЗАВОДЫ", what + f" — событие; вход в {datetime.fromtimestamp(te, timezone.utc):%H:%M} UTC, если фьючерс за сутки "
                         f"сдвинулся не больше чем на ±{WD_CALM * 100:g}%")


def _wd_poll(w, lab, tok, now):
    """Новые блоки Ethereum (с отставанием WD_CONF): переводы токенов из списка на адреса Binance, кусками до WD_STEP блоков,
    не больше 25 с за проход; догоняем не больше WD_BACK блоков."""
    head, err = _wd_rpc("eth_blockNumber", [], 10)
    try:
        head = int(head, 16) - WD_CONF
    except (TypeError, ValueError):
        return _wd_err(w, now, f"узлы Ethereum не отдали номер блока ({err})")
    frm = int(w.get("block") or head - 10) + 1
    if head - frm + 1 > WD_BACK:
        log("ЗАВОДЫ", f"пропущено {head - frm + 1 - WD_BACK} блоков (бот не работал или узлы не отвечали) — смотрю последние "
                      f"{WD_BACK}")
        frm = head - WD_BACK + 1
    dec = w.get("dec") or {}
    addrs = sorted(a for a in tok if dec.get(a, -1) >= 0)
    if not addrs:
        return
    topic_to = ["0x" + "0" * 24 + a[2:] for a in lab["bin"]]
    cache, t0 = {}, time.time()
    while frm <= head and time.time() - t0 < 25:
        to = min(head, frm + WD_STEP - 1)
        logs, err = _wd_rpc("eth_getLogs", [{"fromBlock": hex(frm), "toBlock": hex(to), "address": addrs,
                                             "topics": [WD_TRANSFER, None, topic_to]}], 20)
        if not isinstance(logs, list):
            return _wd_err(w, now, f"узлы Ethereum не отдали переводы блоков {frm}–{to} ({err})")
        try:
            logs.sort(key=lambda x: (int(x["blockNumber"], 16), int(x["logIndex"], 16)))
        except (KeyError, TypeError, ValueError):
            pass
        for x in logs:
            if isinstance(x, dict) and not x.get("removed"):
                _wd_event(w, lab, tok, dec, x, cache)
        w["block"] = to; frm = to + 1
    w.pop("rpc_wait", None); w.pop("rpc_next", None)        # узлы ответили — паузы нет


def _wd_usd(x):
    return f"{x / 1e6:.2f} млн $" if x >= 1e6 else f"{x / 1e3:.0f} тыс. $"


def _wdv_lambda(k, n, fs):
    """λ двойника 🐋ᵛ (research/s213): стоимость завода по цене входа (закрытие свечи входа с поправкой на множитель
    фьючерса) / средний суточный оборот фьючерса за 7 сут до свечи входа (сумма оборота 672 15-мин свечей перед ней / 7).
    k — закрытые 15-мин свечи, последняя — свеча входа; n — монет в заводе. → (λ, завод в $, оборот в $ за сутки) или None:
    нет суммы завода, свечей меньше чем на 7 сут (фьючерс моложе — в бэктесте такие события не считались), нет оборота."""
    try:
        n = float(n or 0)
        if n <= 0 or not k:
            return None
        lo = int(k[-1][0]) // 1000 - 7 * 86400              # начало окна: открытие свечи входа − 7 сут
        if int(k[0][0]) // 1000 > lo:
            return None
        vbar = sum(float(x[7]) for x in k[:-1] if int(x[0]) // 1000 >= lo) / 7.0
        usd = n * float(k[-1][4]) / _wd_base(fs)[1]
    except (IndexError, TypeError, ValueError):
        return None
    return (usd / vbar, usd, vbar) if vbar > 0 and usd > 0 else None


def _wd_enter(state, w, now):
    """Вход по событиям w["pend"]: в момент закрытия свечи входа (опоздание — до WD_LATE). Фьючерс за 24 ч до входа
    (закрытие свечи входа к закрытию свечи сутками раньше) ±5% и торгуется больше суток → виртуальный шорт 🐋. Двойник 🐋ᵛ
    входит в ту же сделку, если завод ≥ 5% среднесуточного оборота фьючерса за 7 сут (_wdv_lambda); совместный вход — одной
    строкой к сообщению 🐋."""
    msgs, pend = [], w.setdefault("pend", {})
    for fs, p in sorted(pend.items(), key=lambda kv: kv[1]["te"]):
        if now < p["te"]:
            continue
        if now > p["te"] + WD_LATE:
            del pend[fs]
            log("ЗАВОДЫ", p["what"] + f" — вход опоздал больше чем на {WD_LATE // 60} мин (бот не работал или Binance не отдал "
                                      "свечи), сделки нет")
            continue
        k = _closed_15m(fs, p["te"], WDV_K)                  # 7 сут свечей — для 🐋ᵛ, последние сутки — для 🐋
        if not k or len(k) < 97 or int(k[-97][0]) // 1000 + 900 != p["te"] - 86400:
            continue                                         # Binance не отдал свечи — повтор в следующем проходе
        c, c0 = float(k[-1][4]), float(k[-97][4])
        r24 = c / c0 - 1 if c0 > 0 else 0.0
        if abs(r24) > WD_CALM:
            del pend[fs]
            log("ЗАВОДЫ", p["what"] + f" — фьючерс за сутки {r24 * 100:+.1f}%, рынок не спокойный, сделки нет")
            continue
        on = (trader.contract(fs) or {}).get("onboard") or 0
        if on and p["te"] - on < 86400:
            del pend[fs]
            log("ЗАВОДЫ", p["what"] + f" — фьючерс запущен {(p['te'] - on) / 3600:.0f} ч назад, моложе суток, сделки нет")
            continue
        note = f"завод на Binance: {p['what']}; фьючерс за сутки {r24 * 100:+.1f}%; выход через 24 ч"
        lam = _wdv_lambda(k, p.get("n"), fs)
        big = lam is not None and lam[0] >= WDV_LAM
        vnote = (f"завод {_wd_usd(lam[1])} — {lam[0] * 100:.1f}% среднесуточного оборота фьючерса за 7 сут ({_wd_usd(lam[2])})"
                 if lam else "оборот фьючерса за 7 сут не посчитан (фьючерс моложе 7 сут или нет суммы завода)")
        was = _virt_is_open(state, "virtual_WD", fs), _virt_is_open(state, "virtual_WDV", fs)
        m = trader.virt_open(state, "virtual_WD", fs, "WD", note)
        if not (m or was[0]):
            continue                                         # Binance не отдал цену — повтор в следующем проходе, до WD_LATE
        mv = trader.virt_open(state, "virtual_WDV", fs, "WD", f"{note}; {vnote}", price=c) if big else None
        opened = not was[0] and _virt_is_open(state, "virtual_WD", fs)
        opened_v = not was[1] and _virt_is_open(state, "virtual_WDV", fs)
        del pend[fs]
        log("ЗАВОДЫ", fs, note + (" → шорт 🐋" if opened else " — сделка не открыта (уже есть или мало виртуального баланса)")
            + f"; {vnote}" + (" → шорт 🐋ᵛ" if opened_v else " — 🐋ᵛ не открыта (уже есть или мало виртуального баланса)" if big
                              else f" — 🐋ᵛ без входа (порог {WDV_LAM * 100:g}%)"))
        if opened and (opened_v or not big):                 # обычно журналы решают вместе — одной строкой
            msgs.append(m + (f"\n🐋ᵛ тот же шорт: {vnote}" if opened_v
                             else f"\n🐋ᵛ без входа: {vnote}" + (f" — меньше {WDV_LAM * 100:g}%" if lam else "")))
        else:
            msgs.extend(x for x in (m, mv) if x)
    return msgs


def whale_deposit_rule(state):
    """Заводы на Binance (журнал 🐋, research/s160 и s167/ВЫВОДЫ.md: пограничный кандидат, по «да» владельца 19.11.2026 —
    для живой проверки). Раз в 2 мин — новые блоки Ethereum (eth_getLogs через публичные узлы без ключа): переводы токенов
    ERC-20 с фьючерсом Binance на адреса Binance из cex_labels.tsv (кастоди и маркетмейкеры не считаются); отправитель —
    не адрес биржи и не чеканка. Перевод ≥ 0,5% монет в обращении (CoinMarketCap) — событие, если у монеты не было события
    48 ч (_wd_event). Вход — на закрытии первой 15-мин свечи, закрывшейся не раньше чем через 15 мин после блока (опоздание —
    до 30 мин), если фьючерс за 24 ч до входа сдвинулся не больше чем на ±5% и торгуется больше суток → виртуальный шорт на
    24 ч без тейка, стоп +25%, плечо ×1 (_wd_enter). Двойник 🐋ᵛ (research/s213, по «да» владельца 20.11.2026) — те же
    входы, только если завод по цене входа ≥ 5% среднесуточного оборота фьючерса за 7 сут до входа. Список токенов — раз
    в сутки (_wd_refresh). Нет файла меток — правило молчит. Строки журнала службы — «ЗАВОДЫ». Сообщения для чата."""
    now = time.time(); w = state.setdefault("wd", {})
    lab = _wd_labels()
    if not lab:
        if now - w.get("nolab", 0) >= 86400:
            w["nolab"] = now
            log("ЗАВОДЫ", f"нет файла меток бирж {os.path.basename(WD_LABELS)} — правило 🐋 молчит (обновление пришло не полностью?)")
        return []
    _wd_refresh(w, now)
    tok = w.get("tok") or {}
    if not tok:
        return []
    rpc_ok = now >= w.get("rpc_next", 0)                     # после сбоя узлов — пауза (_wd_err)
    if rpc_ok:
        _wd_decimals(w)
    msgs = _wd_enter(state, w, now)
    if rpc_ok and now - w.get("poll_t", 0) >= WD_EVERY:
        w["poll_t"] = now
        _wd_poll(w, lab, tok, now)
    last = w.setdefault("last", {})
    for k in [k for k, ts in last.items() if ts < now - 3 * 86400]:
        del last[k]
    return msgs


MR_URL = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/list-all"
MR_DIR = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "margin_rates")


def margin_rates_watch(state):
    """Сборщик ставок маржи Binance (research/s10/ВЫВОДЫ.md): раз в час, в первый проход после HH:02 UTC — публичная
    VIP-спецификация маржи (без ключа): дневная ставка и лимит займа VIP 0 по ~490 активам → строки «час,актив,ставка,лимит»
    в margin_rates/ГГГГ-ММ.csv.gz рядом с state.json. Только запись для будущей проверки «выкачки пула»: сделок и сообщений
    в чат нет. Сбой — в журнал службы не чаще раза в 6 ч; раз в сутки — сводка «СТАВКИ» за прошлые сутки."""
    now = time.time(); H = int(now // 3600 * 3600)
    if state.get("mr_H") == H or now - H < 120 or now - state.get("mr_try", 0) < 300:
        return
    state["mr_try"] = now
    rows, err = [], None
    try:
        for a in json.loads(http(MR_URL, timeout=20)).get("data") or []:
            spec = next((x for x in a.get("specs") or [] if str(x.get("vipLevel")) == "0"), None)
            if a.get("assetName") and spec:
                rows.append(f"{H},{a['assetName']},{spec.get('dailyInterestRate')},{spec.get('borrowLimit')}")
    except Exception as e:
        err = repr(e)
    if len(rows) < 50:
        if now - state.get("mr_err", 0) >= 6 * 3600:
            state["mr_err"] = now
            log("СТАВКИ", "снимок ставок маржи не получен:", err or f"активов в ответе {len(rows)}")
        return
    os.makedirs(MR_DIR, exist_ok=True)
    fn = os.path.join(MR_DIR, datetime.fromtimestamp(H, timezone.utc).strftime("%Y-%m") + ".csv.gz")
    with gzip.open(fn, "at", encoding="utf-8") as f:            # в списке есть активы с нелатинскими именами
        f.write("\n".join(rows) + "\n")
    state["mr_H"] = H
    if state.get("mr_day") != H // 86400:
        if state.get("mr_day") is not None:
            log("СТАВКИ", f"за прошлые сутки снимков {state.get('mr_cnt', 0)} из 24; сейчас активов {len(rows)}, файл {fn}")
        state["mr_day"], state["mr_cnt"] = H // 86400, 0
    state["mr_cnt"] = state.get("mr_cnt", 0) + 1


MP_DIR = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "margin_pool")
MP_EVERY = 600                          # пул займа — раз в 10 мин (вес запроса 50 из 12 000 в минуту на IP у api.binance.com)
_mp = {"last": None, "nokey": False}    # прошлый снимок пула в памяти: после перезапуска бота — снова полный снимок


def margin_pool_watch(state):
    """Доступный пул займа на кросс-марже Binance («выкачка пула», research/s21): раз в 10 мин — подписанный запрос
    /sapi/v1/margin/available-inventory?type=MARGIN ключом бота: сколько каждого актива ещё можно занять. Строки
    «время,время Binance,актив,доступно» в margin_pool/ГГГГ-ММ.csv.gz рядом с state.json: после запуска бота и в первом
    снимке суток — все активы, иначе только изменившиеся (пропавший актив — пустое «доступно»). Только запись для
    проверки: сделок и сообщений в чат нет. Сбой — в журнал службы не чаще раза в 6 ч; раз в сутки — сводка «ПУЛ»."""
    now = time.time()
    if now - state.get("mp_try", 0) < MP_EVERY:
        return
    state["mp_try"] = now
    if not trader.KEY or not trader.SECRET:
        if not _mp["nokey"]:
            _mp["nokey"] = True
            log("ПУЛ", "ключа Binance нет — пул займа не пишется")
        return
    j = trader.sapi_get("/sapi/v1/margin/available-inventory", {"type": "MARGIN"})
    assets = j.get("assets") if isinstance(j, dict) else None
    cur = {}
    for a, v in (assets.items() if isinstance(assets, dict) else ()):
        try:
            cur[str(a)] = float(v)
        except (TypeError, ValueError):
            pass
    if len(cur) < 20:
        if now - state.get("mp_err", 0) >= 6 * 3600:
            state["mp_err"] = now
            why = f"{j.get('code')} {j.get('msg')}" if isinstance(j, dict) and j.get("code") else f"активов в ответе {len(cur)}"
            log("ПУЛ", "доступный пул займа не получен:", why)
        return
    day, last = int(now // 86400), _mp["last"]
    full = last is None or state.get("mp_day") != day
    upd = j.get("updateTime") or ""
    rows = [f"{now:.0f},{upd},{a},{x:.10g}" for a, x in sorted(cur.items()) if full or last.get(a) != x]
    rows += [f"{now:.0f},{upd},{a}," for a in sorted(set(last or {}) - set(cur))]
    if rows:
        os.makedirs(MP_DIR, exist_ok=True)
        fn = os.path.join(MP_DIR, datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m") + ".csv.gz")
        with gzip.open(fn, "at", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    _mp["last"] = cur
    if state.get("mp_day") != day:
        if state.get("mp_day") is not None:
            log("ПУЛ", f"за прошлые сутки снимков {state.get('mp_cnt', 0)} из {86400 // MP_EVERY}; сейчас активов {len(cur)}")
        state["mp_day"], state["mp_cnt"] = day, 0
    state["mp_cnt"] = state.get("mp_cnt", 0) + 1


TK_DIR = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "kr_ticks")
TK_JOURNALS = ("virtual_KT", "virtual_RT", "virtual_O9", "virtual_KR", "virtual_KL")   # 🔝 👀 ⏰ 🇰🇷 🇰🇷🆕
TK_BEFORE, TK_AFTER = 2 * 3600, 6 * 3600          # окно записи сделок: [вход − 2 ч, вход + 6 ч]
TK_BUDGET, TK_PASS_S, TK_KEEP = 25, 20, 6.5 * 86400   # за проход — до 25 запросов и 20 с; биржи хранят сделки 7 суток
TK_API = {"upbit": "https://api.upbit.com", "bithumb": "https://api.bithumb.com"}
TK_TZ = {"upbit": 0, "bithumb": 9 * 3600}         # сутки и параметр to: у Upbit — UTC, у Bithumb — время Сеула


def _tk_page(ex, coin, pos, cursor):
    """До 500 сделок рынка KRW-coin не позже момента pos в пределах суток биржи (новые первыми); [] — сделок нет или
    рынка нет (404), None — сбой."""
    sh = TK_TZ[ex]
    day, today = int((pos + sh) // 86400), int((time.time() + sh) // 86400)
    q = {"market": f"KRW-{coin}", "count": 500, "to": datetime.fromtimestamp(pos + sh, timezone.utc).strftime("%H:%M:%S")}
    if today > day:
        q["daysAgo"] = today - day
    if cursor:
        q["cursor"] = cursor
    try:
        j = json.loads(http(f"{TK_API[ex]}/v1/trades/ticks?" + urllib.parse.urlencode(q), timeout=15))
    except urllib.error.HTTPError as e:
        return [] if e.code == 404 else None
    except Exception:
        return None
    return j if isinstance(j, list) else None


def _tk_close(j, tmp, why=None):
    """Окно записано (why=None) — сделки по возрастанию времени в kr_ticks/ГГГГ-ММ/<биржа>_<монета>_<начало окна>.csv.gz;
    иначе — запись брошена, причина в журнал службы."""
    span = (f"{datetime.fromtimestamp(j['a'], timezone.utc):%d.%m %H:%M}–"
            f"{datetime.fromtimestamp(j['b'], timezone.utc):%d.%m %H:%M} UTC")
    if why is None:
        try:
            rows = sorted(set(open(tmp, encoding="utf-8").read().split()), key=lambda r: int(r.split(",")[0]))
        except OSError:
            rows = []
        d = os.path.join(TK_DIR, datetime.fromtimestamp(j["a"], timezone.utc).strftime("%Y-%m"))
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, f"{j['ex']}_{j['coin']}_{j['a']}.csv.gz")
        with gzip.open(fn, "wt", encoding="utf-8") as f:
            f.write("ts_ms,price,volume,side\n" + "".join(r + "\n" for r in rows))
        log("ТИКИ", f"{KL_NAME[j['ex']]} {j['coin']}: {len(rows)} сделок за {span}")
    else:
        log("ТИКИ", f"{KL_NAME[j['ex']]} {j['coin']} {span}: запись брошена — {why}")
    try:
        os.remove(tmp)
    except OSError:
        pass


def kr_ticks_watch(state):
    """Сделки Upbit и Bithumb с направлением тейкера вокруг входов корейских журналов 🔝 👀 ⏰ 🇰🇷 🇰🇷🆕 (по «да» владельца
    17.11): окно [вход − 2 ч, вход + 6 ч] по каждой бирже, где у монеты есть рынок к воне; пересекающиеся окна одной монеты
    сливаются. После конца окна сделки докачиваются от конца к началу по курсору (/v1/trades/ticks; биржи хранят 7 суток),
    за проход — до 25 запросов и 20 с; недокачанное продолжается в следующих проходах и после перезапуска (state["tk"],
    временный файл kr_ticks/tmp/). Итог — kr_ticks/ГГГГ-ММ/<биржа>_<монета>_<начало окна>.csv.gz рядом с state.json:
    «время мс,цена,объём,сторона» (B — покупка тейкера, A — продажа). Только запись: сделок и сообщений в чат нет."""
    st = state.setdefault("tk", {})
    jobs, seen = st.setdefault("jobs", []), st.setdefault("seen", {})
    now = time.time()
    kr = _kr_list()
    for key in TK_JOURNALS:
        for t in state.get(key, {}).get("trades", []):
            op = float(t.get("opened") or 0)
            sid = f"{key}|{t.get('sym')}|{op:.0f}"
            if now - op > TK_KEEP or sid in seen:
                continue
            seen[sid] = op
            coin = re.sub(r"^(1000000|100000|10000|1000)", "", str(t.get("sym")))
            a, b = int(op - TK_BEFORE), int(op + TK_AFTER)
            for ex in ("upbit", "bithumb"):
                if coin not in kr.get(ex, ()):
                    continue
                j = next((j for j in jobs if j["coin"] == coin and j["ex"] == ex and j["pos"] is None
                          and j["a"] <= b and a <= j["b"]), None)
                if j:
                    j["a"], j["b"] = min(j["a"], a), max(j["b"], b)
                else:
                    jobs.append({"coin": coin, "ex": ex, "a": a, "b": b, "pos": None, "cur": None, "n": 0, "fail": 0})
    for sid in [k for k, op in seen.items() if now - op > 8 * 86400]:
        del seen[sid]
    t_stop, budget, bad = time.time() + TK_PASS_S, TK_BUDGET, set()
    for j in list(jobs):
        if budget <= 0 or time.time() >= t_stop:
            break
        if j["b"] > now - 300 or j["ex"] in bad:                 # окно ещё не кончилось или биржа сбоит в этом проходе
            continue
        tmp = os.path.join(TK_DIR, "tmp", f"{j['ex']}_{j['coin']}_{j['a']}.csv")
        if now - j["a"] > TK_KEEP:
            jobs.remove(j); _tk_close(j, tmp, "окно старше 6,5 суток, биржа его уже не отдаёт")
            continue
        if j["pos"] is None or not os.path.exists(tmp):
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            open(tmp, "w").close()
            j.update(pos=j["b"], cur=None, n=0)
        while budget > 0 and time.time() < t_stop:
            page = _tk_page(j["ex"], j["coin"], j["pos"], j["cur"]); budget -= 1
            if page is None:
                bad.add(j["ex"]); j["fail"] += 1
                if j["fail"] % 30 == 1:
                    log("ТИКИ", f"{KL_NAME[j['ex']]} {j['coin']}: биржа не отдала сделки, повтор в следующих проходах")
                break
            rows, oldest = [], None
            for x in page:
                try:
                    ts, px, v = int(x["timestamp"]), float(x["trade_price"]), float(x["trade_volume"])
                except (KeyError, TypeError, ValueError):
                    continue
                oldest = ts if oldest is None else min(oldest, ts)
                if j["a"] * 1000 <= ts <= j["b"] * 1000:
                    rows.append(f"{ts},{px:.10g},{v:.10g},{'B' if x.get('ask_bid') == 'BID' else 'A'}")
            if rows:
                with open(tmp, "a", encoding="utf-8") as f:
                    f.write("\n".join(rows) + "\n")
                j["n"] += len(rows)
            if oldest is not None and oldest < j["a"] * 1000:   # дошли до начала окна
                jobs.remove(j); _tk_close(j, tmp)
                break
            cur = page[-1].get("sequential_id") if page else None
            if len(page) < 500 or not cur:                       # сутки биржи кончились — к предыдущим
                sh = TK_TZ[j["ex"]]
                j["pos"], j["cur"] = int((j["pos"] + sh) // 86400) * 86400 - sh - 1, None
                if j["pos"] < j["a"]:
                    jobs.remove(j); _tk_close(j, tmp)
                    break
            else:
                j["cur"] = cur


PR_DIR = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "usdt_premium")
PR_EVERY, PR_FX_EVERY = 600, 6 * 3600              # снимок премий — раз в 10 мин; официальные курсы — раз в 6 ч
PR_COLS = ("cny_okx_best", "cny_okx_med10", "try_bid", "try_ask", "krw_upbit", "krw_bithumb")
PR_OKX = ("https://www.okx.com/v3/c2c/tradingOrders/books?quoteCurrency=cny&baseCurrency=usdt&side=sell&paymentMethod=all"
          "&userType=all&showTrade=false&showFollow=false&showAlreadyTraded=false&isAbleFilter=false")


def _pr_json(url):
    try:
        return json.loads(http(url, timeout=15))
    except Exception:
        return None


def usdt_premium_watch(state):
    """Премии USDT к местным валютам (по «да» владельца 17.11): раз в 10 мин — внебиржевая цена покупки USDT за юани
    на OKX C2C (лучшая и медиана 10 лучших объявлений), USDTTRY Binance (спрос и предложение), KRW-USDT Upbit и Bithumb;
    официальные курсы USD → CNY, TRY, KRW (frankfurter.app, данные ЕЦБ) — раз в 6 ч. Строки — в usdt_premium/ГГГГ-ММ.csv
    рядом с state.json; пустое поле — источник не ответил. Только запись: сделок и сообщений в чат нет. Сбой всех
    источников — строка «ПРЕМИЯ» не чаще раза в 6 ч; раз в сутки — сводка «ПРЕМИЯ»."""
    st = state.setdefault("pr", {})
    now = time.time()
    if now - st.get("last", 0) < PR_EVERY:
        return
    st["last"] = now
    if now - st.get("fx_t", 0) >= PR_FX_EVERY:
        j = _pr_json("https://api.frankfurter.app/latest?from=USD&to=CNY,TRY,KRW")
        try:
            st["fx"] = {k: float(j["rates"][k]) for k in ("CNY", "TRY", "KRW")}
            st["fx_date"], st["fx_t"] = str(j.get("date", "")), now
        except (TypeError, KeyError, ValueError):
            st["fx_t"] = now - PR_FX_EVERY + 1800                # повтор через 30 мин
    v = {}
    j = _pr_json(PR_OKX)
    try:
        p = sorted(float(x["price"]) for x in j["data"]["sell"])[:10]
        if p:
            v["cny_okx_best"], v["cny_okx_med10"] = p[0], p[len(p) // 2]
    except (TypeError, KeyError, ValueError):
        pass
    j = spot_json("/api/v3/ticker/bookTicker?symbol=USDTTRY", 15)
    try:
        v["try_bid"], v["try_ask"] = float(j["bidPrice"]), float(j["askPrice"])
    except (TypeError, KeyError, ValueError):
        pass
    for ex in ("upbit", "bithumb"):
        j = _pr_json(f"{TK_API[ex]}/v1/ticker?markets=KRW-USDT")
        try:
            v[f"krw_{ex}"] = float(j[0]["trade_price"])
        except (TypeError, KeyError, ValueError, IndexError):
            pass
    if not v:
        if now - st.get("err", 0) >= 6 * 3600:
            st["err"] = now
            log("ПРЕМИЯ", "ни один источник премии USDT не ответил (OKX, Binance, Upbit, Bithumb)")
        return
    fx = st.get("fx") or {}
    os.makedirs(PR_DIR, exist_ok=True)
    fn = os.path.join(PR_DIR, datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m") + ".csv")
    new = not os.path.exists(fn)
    with open(fn, "a", encoding="utf-8") as f:
        if new:
            f.write("ts," + ",".join(PR_COLS) + ",fx_date,usd_cny,usd_try,usd_krw\n")
        f.write(f"{now:.0f}," + ",".join(f"{v[c]:.6g}" if c in v else "" for c in PR_COLS)
                + f",{st.get('fx_date', '')}," + ",".join(f"{fx[k]:.6g}" if k in fx else "" for k in ("CNY", "TRY", "KRW")) + "\n")
    day = int(now // 86400)
    if st.get("day") != day:
        if st.get("day") is not None:
            log("ПРЕМИЯ", f"за прошлые сутки снимков {st.get('cnt', 0)} из {86400 // PR_EVERY}; сейчас: "
                + ", ".join(f"{c} {v[c]:.6g}" for c in PR_COLS if c in v))
        st["day"], st["cnt"] = day, 0
    st["cnt"] = st.get("cnt", 0) + 1


UPBIT_FLAGS = ("warning", "PRICE_FLUCTUATIONS", "TRADING_VOLUME_SOARING", "DEPOSIT_AMOUNT_SOARING",
               "GLOBAL_PRICE_DIFFERENCES", "CONCENTRATION_OF_SMALL_ACCOUNTS")   # warning — «предупреждение», остальные — «внимание»
# смены флагов — ещё и в файл рядом с state.json: журнал службы на сервере хранит около недели (research/s17/ВЫВОДЫ.md)
UPF_FILE = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "upbit_flags.csv")
UPF_HEAD = "ts,sign,flag,coin,fut,price,held_h,gap_min\n"


def upbit_flags_watch(state, every=300):
    """Флаги Upbit по KRW-рынкам (research/s3/ВЫВОДЫ.md): предупреждение, скачки цены, всплеск объёма, всплеск депозитов,
    разница с мировой ценой, концентрация мелких счетов. Раз в 5 мин — /v1/market/all?is_details=true; в журнал службы —
    строки «UPBIT»: появление (+) и снятие (−) флага с ценой фьючерса Binance; если прошлых флагов нет — снимок (=).
    Те же смены — строками в upbit_flags.csv рядом с state.json (UPF_FILE; выгрузка — tools/upbit_flags.py).
    Только запись для будущей проверки: сделок и сообщений в чат нет."""
    now = time.time()
    if now - state.get("upf_try", 0) < every:
        return
    state["upf_try"] = now
    j = http_json("https://api.upbit.com/v1/market/all?is_details=true", 15)
    if not isinstance(j, list) or not j:
        return
    cur = {}
    for x in j:
        m = str(x.get("market", ""))
        ev = x.get("market_event") or {}
        on = [f for f in UPBIT_FLAGS if (ev.get("warning") if f == "warning" else (ev.get("caution") or {}).get(f))]
        if m.startswith("KRW-") and on:
            cur[m[4:]] = on
    old, last = state.get("upbit_flags"), state.get("upf_ok", 0)
    state["upf_ok"] = now
    if old is None:                                           # прошлых флагов нет — снимок того, что уже стоит
        ch = [("=", c, f, None) for c, fl in sorted(cur.items()) for f in fl]
        state["upbit_flags"] = {c: {f: None for f in fl} for c, fl in cur.items()}
    else:                                                     # {монета: {флаг: когда появился}}
        ch, new = [], {}
        for c in sorted(set(old) | set(cur)):
            was, on = old.get(c, {}), cur.get(c, [])
            ch += [("+", c, f, None) for f in on if f not in was] + [("−", c, f, t) for f, t in was.items() if f not in on]
            if on:
                new[c] = {f: was.get(f, now) for f in on}
        state["upbit_flags"] = new
    if not ch:
        return
    trader.contract("BTC")                                     # загружает список бессрочных контрактов USDT
    perp = {re.sub(r"^(1000000|100000|10000|1000)", "", s[:-4]): s for s in trader._contracts if s.endswith("USDT")}
    px = http_json("https://fapi.binance.com/fapi/v1/ticker/price", 15)
    price = {x.get("symbol"): x.get("price") for x in px} if isinstance(px, list) else {}
    gap = f", прошлый опрос {(now - last) / 60:.0f} мин назад" if old is not None and now - last > 900 else ""
    rows = []
    for sign, c, f, since in ch:
        s = perp.get(c)
        fut = (f"фьючерс {s} {price[s]}" if price.get(s) else f"фьючерс {s}") if s else "фьючерса нет"
        log("UPBIT", f"{sign}{f}", f"KRW-{c}", "|", fut + (f", держался {(now - since) / 3600:.1f} ч" if since else "") + gap)
        rows.append(",".join((f"{now:.0f}", "-" if sign == "−" else sign, f, c, s or "", str(price.get(s) or ""),
                              f"{(now - since) / 3600:.2f}" if since else "", f"{(now - last) / 60:.0f}" if gap else "")))
    try:
        head = not os.path.exists(UPF_FILE)
        with open(UPF_FILE, "a", encoding="utf-8") as fh:
            fh.write((UPF_HEAD if head else "") + "\n".join(rows) + "\n")
    except OSError as e:
        log("UPBIT", "файл флагов не записан:", repr(e))


def status_text(cands):
    if not cands:
        return "Сейчас в канале нет монет, которые висят ≥%g ч." % MIN_RUN_H
    lines = ["Монеты, висящие в канале ≥%g ч (движение за 4ч):" % MIN_RUN_H]
    for c in sorted(cands, key=lambda c: -c["b4h"]):
        flag = {"pump": "🔻", "dump": "🔽"}.get(rule_for(c), "  ")
        lines.append(f"{flag} {c['sym']}: {fmt_run(c)}, {c['b4h']:+.1f}%, фандинг {fmt_funding(c.get('funding'))}")
    return "\n".join(lines)


def signal_text(c):
    bor, rep, br = c["info"]
    lsr = c.get("lsr")
    lsr_line = f"LSR тейкеров (1 ч): {lsr:.2f}\n" if isinstance(lsr, (int, float)) else "LSR тейкеров: нет данных\n"
    title = "🔽 <b>ШОРТ-сигнал (правило 2, после падения): " if c.get("rule") == "dump" else "🔻 <b>ШОРТ-сигнал: "
    return (
        f"{title}{c['sym']}</b>\n"
        f"Цена: {fmt_price(c['price'])} USDT ({c['src']})\n"
        f"Движение за 4 ч: <b>{c['b4h']:+.1f}%</b>\n"
        f"{pattern_line(c)}"
        f"{c.get('risk_text', '')}"
        f"Фандинг: {fmt_funding(c.get('funding'))}\n"
        f"{lsr_line}"
        f"В канале непрерывно: {fmt_run(c)} (BOR {bor}, REP {rep}, B/R {br})"
    )


def followups(state, dry):
    now = time.time()
    for a in state["alerts"]:
        for key, hours in (("fu4", 4), ("fu24", 24)):
            if a.get(key) or now - a["ts"] < hours * 3600:
                continue
            pc = price_and_change(a["sym"])
            if not pc:
                continue
            ch = (pc["price"] / a["price"] - 1) * 100
            a[key] = ch
            mark = "✅" if ch < 0 else "❌"
            broadcast(state, f"{mark} {a['sym']}: через {hours} ч {ch:+.1f}% "
                             f"(вход {fmt_price(a['price'])} → {fmt_price(pc['price'])})", dry)
    state["alerts"] = [a for a in state["alerts"] if now - a["ts"] < 72 * 3600]


CH_CONFIRM_H, CH_MIN = 6.0, 1.0       # 📘ᶜ: у монеты был CHNG ≥ 1 за 6 ч до сигнала канала (research/s41, Г6)


def chng_recent(sym, posts, now, hours=CH_CONFIRM_H):
    """Наибольший CHNG монеты в постах за hours ч до now: (CHNG, время поста) или None. CHNG — 4-е поле строки поста
    (бывает со знаком: +0.00, -0.64)."""
    best = None
    for q in posts:
        if not now - hours * 3600 <= q["ts"] <= now:
            continue
        row = (q.get("rows_all") or {}).get(sym)
        if not row or len(row) < 4:
            continue
        try:
            ch = float(row[3])
        except (TypeError, ValueError):
            continue
        if best is None or ch > best[0]:
            best = (ch, q["ts"])
    return best


def chng_confirm(state, sym, price, rule, posts, now):
    """📘ᶜ — двойник 📘: открывается по тому же сигналу канала, только если за 6 ч до сигнала у монеты был CHNG ≥ 1.
    Посты прохода тянутся на LOOKBACK_H (5,5 ч): если они не покрывают 6 ч и подтверждения в них нет — догружаются один раз."""
    hit = chng_recent(sym, posts, now)
    oldest = min((q["ts"] for q in posts), default=now)
    if (hit is None or hit[0] < CH_MIN) and oldest > now - CH_CONFIRM_H * 3600:
        more = fetch_posts(CH_CONFIRM_H + 0.5)
        if more:
            hit = chng_recent(sym, more, now)
    if hit is None or hit[0] < CH_MIN:
        return None
    note = (f"подтверждение: CHNG {hit[0]:g} в {time.strftime('%H:%M', time.gmtime(hit[1]))} UTC "
            f"(за {CH_CONFIRM_H:g} ч до сигнала был CHNG ≥ {CH_MIN:g})")
    return trader.virt_open(state, "virtual_1525C", sym, rule, note, price=price)


# ---------------------------------------------------------------- 🗳 комитет «шорт 4 ч» (research/s225)
# Комитет из 100 правил (1–3 условия) на 47 признаках: займ канала MarginData (объём, набор, отдача, удержание), ставка займа
# Binance, цена, оборот, фандинг, OI, лонг/шорт — и те же величины относительно 30 сут самой монеты. Правила и порог k = 3
# отобраны на 20.02.2025–31.03.2026; проверка 01.04–21.10.2026: 417 сделок в месяц, +0,33% на сделку с хеджем индексом
# альтов (t 3,1); свежий отрезок 22.10–19.11.2026: +0,32% (t 1,1), вместе t 3,2 (research/s225/ВЫВОДЫ.md, s224/ВЫВОДЫ.md).
# Каждые 4 ч (00, 04, …, 20 UTC) — монеты канала (пост не старше 30 мин) с бессрочным фьючерсом старше суток: голосов ≥ 3 →
# виртуальный шорт на 4 ч без тейка, стоп +10%, плечо ×1; доход с хеджем корзиной альтов — третий баланс журнала.
# Признаки считаются как в research/s216/features.py и research/s225/features.py (сверка — research/s225/c4_fidelity.py).
C4_K, C4_HOLD_H, C4_GRID, C4_LATE = 3, 4.0, 4 * 3600, 20 * 60     # голосов; срок, ч; сетка 4 ч; вход не позже 20 мин
C4_KEEP_D, C4_NEED_D, C4_BACK_PAGES = 33, 31, 40                   # панель канала хранит 33 сут, торгует при покрытии 31 сут;
                                                                   # догрузка истории — до 40 страниц t.me за проход
C4_STABLE = ("DAI", "USDC", "FDUSD", "TUSD", "USDP", "BUSD")
C4_ALT_VOL, C4_WORKERS = 5e6, 4                                    # корзина альтов: оборот за 24 ч ≥ 5 млн $; потоков запросов
C4_RULES = (
    (("qv24", "ge", 34653457.98749999), ("bmc", "le", 0.0431298012), ("zr4", "ge", 0.9512845554)),
    (("r72", "le", -0.0656418402), ("dlsr24", "ge", 0.022122454), ("zoi4", "ge", 0.6309575267)),
    (("r4x", "ge", 1.0), ("dlsr24", "ge", 0.022122454), ("zoi4", "ge", 0.6309575267)),
    (("dlsr24", "ge", 0.130121822), ("btc24", "le", 0.0043257379), ("zoi4", "ge", 0.6309575267)),
    (("r4x", "ge", 0.9166431095), ("dlsr24", "ge", 0.022122454), ("zoi4", "ge", 0.6309575267)),
    (("qv24", "ge", 4358821.0888671875), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("qvx", "ge", 2.6747527009), ("wave", "le", 12.0), ("zrep", "ge", 1.1077390316)),
    (("pres7", "le", 8.0), ("btc24", "ge", -0.0023792619), ("zqv", "ge", 2.1282652418)),
    (("vol24", "ge", 0.0055259055), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("hold", "ge", 59.7620505151), ("r24", "ge", 0.027151031), ("ux", "le", 1.5356245649)),
    (("vol24", "ge", 0.0120592732), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("qvx", "ge", 2.6747527009), ("zrep", "ge", 1.1077390316), ("znet", "ge", 1.0316063107)),
    (("r24", "ge", 0.078076153), ("lsr_top", "ge", 1.2425532), ("wave", "le", 9.0)),
    (("qv24", "ge", 11735977.438671876), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("place", "le", 11.0), ("tb4", "ge", 0.4993410556), ("zrep", "ge", 1.1077390316)),
    (("doi24", "ge", 0.164626883), ("lsr_top", "ge", 1.2425532), ("wave", "le", 9.0)),
    (("dlsr24", "ge", 0.130121822), ("oiq", "le", 0.3748533987), ("zoi4", "ge", 0.6309575267)),
    (("rep", "ge", 374900.0), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("net7", "ge", 27515900.0), ("ux", "le", 1.5356245649), ("lsr_acc", "le", 1.475470248)),
    (("qv24", "ge", 34653457.98749999), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("hold", "ge", 59.7620505151), ("ux", "le", 1.5356245649), ("zr24", "ge", 0.4832788382)),
    (("bmc", "ge", 0.1492735031), ("zrate", "le", 0.0164276652), ("zr24", "ge", 1.2577623681)),
    (("tb4", "ge", 0.5151002522), ("lsr_top", "ge", 1.0615464), ("zf", "le", -1.5067433638)),
    (("dlsr24", "ge", 0.130121822), ("znet", "ge", -0.1565213519), ("zoi4", "ge", 0.6309575267)),
    (("qvx", "ge", 0.9747696777), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("r4x", "ge", 1.0), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("dlsr24", "ge", 0.130121822), ("tkr", "ge", 0.8631278), ("zoi4", "ge", 0.6309575267)),
    (("run", "ge", 23.0), ("bmc", "le", 0.1492735031), ("zf", "le", -1.5067433638)),
    (("qvx", "ge", 1.4319920258), ("lsr_top", "ge", 1.2425532), ("zrep", "le", -1.1969645901)),
    (("dlsr24", "ge", 0.022122454), ("znet", "ge", -0.1565213519), ("zoi4", "ge", 0.6309575267)),
    (("zbor", "le", 0.2336148512), ("zrate", "le", 0.0164276652), ("zr24", "ge", 1.2577623681)),
    (("f8", "le", -0.001114878), ("zr4", "ge", 0.9512845554), ("zlsrt", "ge", -0.5956906616)),
    (("rate", "ge", 0.001550382), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("doi4", "ge", 0.0044402727), ("zrep", "ge", 1.1077390316), ("znet", "ge", 1.0316063107)),
    (("qvx", "ge", 0.6833150037), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("doi24", "ge", 0.164626883), ("zbor", "ge", 1.0556064946), ("zlsr", "ge", 0.1980581847)),
    (("dlsr24", "ge", 0.130121822), ("tkr", "le", 1.445549), ("zoi4", "ge", 0.6309575267)),
    (("run", "ge", 23.0), ("ux", "le", 1.5356245649), ("zf", "le", -1.5067433638)),
    (("place", "le", 4.0), ("run", "le", 6.0), ("f24", "le", -0.003897142)),
    (("zbor", "ge", 1.0556064946), ("zrate", "le", -0.0765585691), ("zlsr", "ge", -1.3181832104)),
    (("r24", "ge", 0.027151031), ("ux", "le", 1.5356245649), ("bmc", "ge", 0.1492735031)),
    (("r4x", "ge", 1.0831794905), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("net", "ge", 10456919.999999987), ("run", "le", 6.0), ("btc24", "ge", -0.0023792619)),
    (("r4x", "ge", 1.0831794905), ("f24", "ge", -0.000847178), ("znet", "ge", 1.0316063107)),
    (("r4", "ge", 0.0067558621), ("f8", "le", -0.001114878), ("zrate", "le", 0.0164276652)),
    (("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822), ("znet", "ge", -0.1565213519)),
    (("net", "ge", 10456919.999999987), ("wave", "ge", 7.0), ("zrate", "le", -0.0765585691)),
    (("qvx", "ge", 0.9747696777), ("tb4", "ge", 0.4993410556), ("zrep", "ge", 1.1077390316)),
    (("net", "ge", 92200.0), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("qvx", "ge", 1.4319920258), ("zrep", "le", -1.1969645901), ("zlsrt", "ge", -0.5956906616)),
    (("dlsr24", "ge", 0.130121822), ("wave", "ge", 5.0), ("zoi4", "ge", 0.6309575267)),
    (("run", "ge", 23.0), ("zr24", "le", 1.2577623681), ("zf", "le", -1.5067433638)),
    (("bor", "ge", 117800.0), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("tb4", "le", 0.5151002522), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("bmc", "ge", 0.0009207144), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("r4", "ge", 0.0067558621), ("f8", "le", -0.001114878), ("ux", "le", 1.5356245649)),
    (("r24", "ge", -0.0025033677), ("ux", "le", 1.0679239392), ("bmc", "ge", 0.1492735031)),
    (("ux", "le", 1.0679239392), ("bmc", "ge", 0.1492735031), ("zr24", "ge", -0.0477615703)),
    (("dlsr24", "ge", 0.022122454), ("zqv", "ge", 2.1282652418), ("zoi4", "ge", 0.6309575267)),
    (("hold", "le", 14.229600779), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("net", "ge", 10456919.999999987), ("zrate", "le", -0.0765585691), ("zf", "le", 0.215375671)),
    (("znet", "le", 1.0316063107), ("zrate", "le", 0.0164276652), ("zr24", "ge", 1.2577623681)),
    (("tb4", "ge", 0.4993410556), ("f8", "le", -0.001114878), ("zrep", "ge", 1.1077390316)),
    (("rep", "le", 374900.0), ("net", "ge", 10456919.999999987), ("ux", "le", 1.5356245649)),
    (("r4x", "ge", 1.0831794905), ("r24x", "ge", 1.8305465951), ("vol24", "ge", 0.0120592732)),
    (("r24", "ge", 0.078076153), ("lsr_top", "ge", 1.2425532), ("zbor", "le", 0.2336148512)),
    (("bor", "ge", 12400000.0), ("zrate", "le", -0.0765585691), ("zf", "le", 0.215375671)),
    (("r24", "ge", 0.027151031), ("zbor", "ge", 1.0556064946), ("zlsr", "ge", 0.1980581847)),
    (("r24", "ge", 0.078076153), ("lsr_top", "ge", 1.2425532), ("zrep", "le", 0.3677247801)),
    (("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822), ("wave", "ge", 5.0)),
    (("pres7", "le", 8.0), ("qvx", "ge", 2.6747527009), ("btc24", "ge", -0.0023792619)),
    (("vol24", "ge", 0.0120592732), ("tb4", "ge", 0.4993410556), ("zrep", "ge", 1.1077390316)),
    (("qv24", "ge", 110920761.12148443), ("lsr_acc", "ge", 1.10032409), ("zr4", "ge", 0.9512845554)),
    (("pres7", "le", 8.0), ("dr24", "ge", 1.3049377657), ("zoi24", "ge", 1.4140015538)),
    (("place", "le", 4.0), ("zrep", "ge", 1.1077390316), ("zlsr", "le", -1.3181832104)),
    (("bqv", "le", 0.0330324893), ("doi24", "ge", 0.164626883), ("lsr_top", "ge", 1.2425532)),
    (("r4x", "ge", 1.0831794905), ("f24", "ge", -0.000847178), ("zbor", "ge", 1.0556064946)),
    (("qv24", "ge", 110920761.12148443), ("qvx", "ge", 2.6747527009), ("zrep", "ge", 1.1077390316)),
    (("pres7", "le", 30.0), ("doi24", "ge", 0.164626883), ("wave", "le", 7.0)),
    (("bor", "ge", 12400000.0), ("lim", "le", 0.0), ("zrate", "le", 0.0164276652)),
    (("net", "ge", 10456919.999999987), ("f8", "le", -0.000225256), ("zrate", "le", -0.0765585691)),
    (("dr24", "ge", 1.3049377657), ("zoi4", "ge", 0.6309575267), ("zlsr", "ge", 1.0493297498)),
    (("net", "ge", 10456919.999999987), ("zrate", "le", -0.0765585691), ("zlsr", "le", 0.1980581847)),
    (("oiq", "le", 0.1885212594), ("zoi4", "ge", 0.6309575267), ("zlsr", "ge", 1.0493297498)),
    (("vol24", "ge", 0.0077652701), ("zoi4", "ge", 0.6309575267), ("zlsr", "ge", 1.0493297498)),
    (("r24", "ge", 0.078076153), ("lsr_top", "ge", 1.2425532), ("zrep", "le", -1.1969645901)),
    (("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822), ("btc24", "le", 0.0043257379)),
    (("oiq", "le", 0.3748533987), ("zoi4", "ge", 0.6309575267), ("zlsr", "ge", 1.0493297498)),
    (("rep", "ge", 1300000.0), ("dr24", "ge", 1.3049377657), ("zrate", "le", 0.1614775555)),
    (("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822), ("tkr", "le", 1.445549)),
    (("hold", "le", 5.4365902965), ("dlsr24", "ge", 0.130121822), ("zoi4", "ge", 0.6309575267)),
    (("rb", "ge", 0.0558447705), ("vol24", "ge", 0.0077652701), ("zqv", "le", -0.3366578062)),
    (("qv24", "ge", 110920761.12148443), ("lsr_acc", "ge", 1.475470248), ("zr4", "ge", 0.2858790762)),
    (("r4x", "ge", 1.0), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("doi24", "ge", 0.164626883), ("wave", "ge", 5.0), ("wave", "le", 7.0)),
    (("tb4", "ge", 0.4993410556), ("tb4", "le", 0.5151002522), ("zrep", "ge", 1.1077390316)),
    (("qv24", "ge", 110920761.12148443), ("tb4", "ge", 0.4993410556), ("zrep", "ge", 1.1077390316)),
    (("net7", "ge", 1396840.0), ("doi4", "ge", 0.0265674927), ("dlsr24", "ge", 0.130121822)),
    (("net", "ge", 10456919.999999987), ("run", "le", 6.0), ("btc24", "ge", 0.0043257379)),
    (("net", "ge", 10456919.999999987), ("ux", "le", 1.5356245649), ("znet", "ge", 1.0316063107)),
)
C4_FILE = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "c4_panel.json")
C4_RATES = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/history-interest-rate"
_c4 = None                                   # панель канала: {"rows": {час: {монета: [время, займ, отдача, место, пост]}},
                                             #  "hours": {монета: [часы с постами]}, "lo": пост, "hi": пост, "back": история
                                             #  догружена, "gaps": [[пост, пост), …] — дыры после простоя}
_c4_cmc = {"t": 0, "rows": None}             # список CMC (раз в сутки): {тикер: [(цена, капитализация), …]}


def _c4_num(x):
    """Число из поста канала: 1.2M, 931.4K, 0 (как research/s7/margin_ev.py)."""
    x = x.strip().replace(",", ".")
    m = {"K": 1e3, "M": 1e6, "B": 1e9}.get(x[-1:].upper(), 1)
    try:
        return float(x[:-1] if m != 1 else x) * m
    except ValueError:
        return float("nan")


def _c4_ranked(text):
    """Строки поста займов в порядке поста (как research/s7/margin_ev.py): [(монета, займ, отдача, место)]."""
    if "B/R" not in text[:60]:
        return []
    out, rank = [], 0
    for ln in text.split("\n")[2:]:
        p = ln.split()
        if len(p) < 4 or ln.startswith("MarginData"):
            continue
        sym = re.sub(r"[^\w]", "", p[0])
        if not sym:
            continue
        rank += 1
        out.append((sym, _c4_num(p[1]), _c4_num(p[2]), rank))
    return out


def _c4_load():
    global _c4
    if _c4 is None:
        try:
            with open(C4_FILE) as f:
                d = json.load(f)
            _c4 = {"rows": d.get("rows") or {}, "hours": {k: set(v) for k, v in (d.get("hours") or {}).items()},
                   "lo": d.get("lo"), "hi": d.get("hi"), "back": bool(d.get("back")), "gaps": d.get("gaps") or [],
                   "dirty": False}
        except Exception:
            _c4 = {"rows": {}, "hours": {}, "lo": None, "hi": None, "back": False, "gaps": [], "dirty": False}
    return _c4


def _c4_save():
    st = _c4
    if not st or not st.get("dirty"):
        return
    old = int(time.time() // 3600 * 3600 - C4_KEEP_D * 86400)
    for h in [h for h in st["rows"] if int(h) < old]:
        del st["rows"][h]
    oh = old // 3600
    for c in list(st["hours"]):
        st["hours"][c] = {h for h in st["hours"][c] if h >= oh}
        if not st["hours"][c]:
            del st["hours"][c]
    try:
        with open(C4_FILE + ".tmp", "w") as f:
            f.write(json.dumps({"rows": st["rows"], "hours": {k: sorted(v) for k, v in st["hours"].items()},
                                "lo": st["lo"], "hi": st["hi"], "back": st["back"], "gaps": st["gaps"]}, separators=(",", ":")))
        os.replace(C4_FILE + ".tmp", C4_FILE)
        st["dirty"] = False
    except OSError as e:
        log("КОМИТЕТ", "панель канала не записана:", e)


def _c4_add(st, pid, ts, ranked):
    """Пост канала в панель: строка монеты в ближайшей отметке часа не раньше поста, если пост не старше 30 мин к ней
    (из нескольких — последний), и час поста — в часы присутствия монеты (research/s21/borrow_study.py, s216 pres7/run)."""
    if not ranked:
        return
    T = int(math.ceil(ts / 3600) * 3600)
    row = st["rows"].setdefault(str(T), {}) if T - ts <= 1800 else None
    for sym, b, r, k in ranked:
        if row is not None:
            cur = row.get(sym)
            if cur is None or (ts, pid) > (cur[0], cur[4]):
                row[sym] = [ts, b, r, k, pid]
        st["hours"].setdefault(sym, set()).add(int(ts // 3600))
    st["lo"] = pid if st["lo"] is None else min(st["lo"], pid)
    st["hi"] = pid if st["hi"] is None else max(st["hi"], pid)
    st["dirty"] = True


def _c4_page(before):
    """Страница веб-версии канала до поста before: [(номер, время, строки займов)]; None — сбой или страница без постов."""
    try:
        page = http(f"https://t.me/s/{CHANNEL}?before={before}")
    except Exception as e:
        log("КОМИТЕТ", "канал не отдал страницу истории:", e)
        return None
    if "tgme_widget_message" not in page:                     # страница без постов — сбой t.me, а не конец истории
        log("КОМИТЕТ", f"страница истории канала до поста {before} пустая — повтор в следующем проходе")
        return None
    out = []
    for b in re.split(r'(?=<div class="tgme_widget_message_wrap)', page):
        m = re.search(rf'data-post="{CHANNEL}/(\d+)"', b)
        t = re.search(r'<time datetime="([^"]+)"', b)
        body = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if not (m and t and body):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", body.group(1))))
        out.append((int(m.group(1)), datetime.fromisoformat(t.group(1)).timestamp(), _c4_ranked(text)))
    return out


def c4_record(posts):
    """Свежие посты канала — в панель 🗳. Дыры по номерам постов (бот стоял) встают в очередь и догружаются страницами t.me;
    потом — история за 32 сут вниз от самого старого поста панели. Всего до C4_BACK_PAGES страниц за проход."""
    st = _c4_load()
    fresh = [p for p in posts if p.get("ranked")]
    if fresh and st["hi"] is not None:
        m = min(p["id"] for p in fresh)
        if m - 1 > st["hi"]:
            st["gaps"].append([st["hi"], m]); st["dirty"] = True
    for p in fresh:
        _c4_add(st, p["id"], p["ts"], p["ranked"])
    pages, keep = 0, time.time() - C4_KEEP_D * 86400
    for g in st["gaps"]:                                      # [нижний известный пост, верхний известный пост)
        while g[1] - 1 > g[0] and pages < C4_BACK_PAGES:
            got = _c4_page(g[1]); pages += 1
            if not got:
                break
            for pid, ts, rk in got:
                if pid > g[0]:
                    _c4_add(st, pid, ts, rk)
            g[1] = min(x[0] for x in got)
            if min(x[1] for x in got) < keep:                 # глубже хранимых 33 сут дыра не нужна
                g[1] = g[0]
            st["dirty"] = True
            time.sleep(0.5)
    st["gaps"] = [g for g in st["gaps"] if g[1] - 1 > g[0]]
    if not st["back"] and st["lo"] is not None:               # история за 32 сут — вниз от самого старого поста панели
        cur = st["lo"]
        while pages < C4_BACK_PAGES:
            got = _c4_page(cur); pages += 1
            if not got:
                break
            for pid, ts, rk in got:
                _c4_add(st, pid, ts, rk)
            cur = min(g[0] for g in got)
            if min(g[1] for g in got) < time.time() - (C4_NEED_D + 1) * 86400:
                st["back"] = True; st["dirty"] = True
                log("КОМИТЕТ", "история канала за 32 сут догружена")
                break
            time.sleep(0.5)
    _c4_save()


def _c4_ready(st, now):
    """Панель годится для признаков за 30 сут: история догружена на 31 сут назад и нет недогруженных дыр по номерам постов
    (часы, когда сам канал молчал, — не дыра: так было и в бэктесте)."""
    if not st["back"] or st["gaps"]:
        return False
    hs = [int(h) for h, r in st["rows"].items() if r]
    return bool(hs) and min(hs) <= now - C4_NEED_D * 86400


def _c4_live(fs, h):
    """Фьючерс жив на отметку часа h (запущен не меньше чем за сутки до свечи, закрывающейся в h)."""
    on = (trader.contract(fs) or {}).get("onboard") or 0
    return bool(on) and h - 900 >= on + 86400


def _c4_series(st, coin, fs, T):
    """Строки панели монеты (как research/s21: только часы, когда фьючерс жив) — {час: (займ, отдача, место)}
    за [T − 31 сут, T]."""
    out = {}
    for h in range(T - 31 * 86400, T + 1, 3600):
        v = (st["rows"].get(str(h)) or {}).get(coin)
        if v is not None and _c4_live(fs, h):
            out[h] = (v[1], v[2], v[3])
    return out


def _c4_wave(st, T, fut):
    """Сколько монет канала за сутки до T ускорили займ: строка в отметке часа из (T − 24 ч, T], монета была в канале
    4 ч назад, займ ≥ 1,5 × займа 4 ч назад и ≥ 50 тыс. $ (research/s216/features.py, wave)."""
    seen = set()
    for h in range(T - 23 * 3600, T + 1, 3600):
        row = st["rows"].get(str(h)) or {}; row4 = st["rows"].get(str(h - 4 * 3600)) or {}
        for coin, v in row.items():
            if coin in seen or coin in C4_STABLE:
                continue
            v4 = row4.get(coin)
            fs = fut(coin)
            if v4 is not None and v[1] >= 1.5 * v4[1] and v[1] >= 50e3 and fs and _c4_live(fs, h):
                seen.add(coin)
    return len(seen)


def _c4_std(x):
    x = [v for v in x if v == v and abs(v) != float("inf")]
    if len(x) < 48:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def _c4_mean_std(x):
    x = [v for v in x if v == v and abs(v) != float("inf")]
    if len(x) < 48:
        return None, None
    m = sum(x) / len(x)
    return m, math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def _c4_median(x):
    x = sorted(x)
    n = len(x)
    return (x[n // 2] if n % 2 else (x[n // 2 - 1] + x[n // 2]) / 2) if n else None


def _c4_quantile(x, q):
    """Квантиль с линейной интерполяцией (как numpy и pandas по умолчанию)."""
    x = sorted(x)
    if not x:
        return None
    pos = (len(x) - 1) * q; lo = int(math.floor(pos)); hi = min(lo + 1, len(x) - 1)
    return x[lo] + (x[hi] - x[lo]) * (pos - lo)


def c4_features(T, coin, fs, st, kl15, kl1h, fund, met, tkr, rates, mcap, btc, wave):
    """47 признаков комитета в момент T (сетка 4 ч) — точно как research/s216/features.py и research/s225/features.py.
    kl15 — 15-мин свечи Binance (списки как у /fapi/v1/klines), последняя закрывается в T (≥ 673); kl1h — часовые свечи
    за 31+ сут до T; fund — [(время начисления, с; ставка)] за 31 сут; met — {час: (OI, OI $, топ-позиции, все счета)}
    за 31 сут до T − 1 ч; tkr — отношение агрессивных объёмов на T − 1 ч (5-мин окно перед ним); rates — [(время, с;
    дневная ставка)] за 31+ сут; mcap — капитализация CMC или None; btc — (закрытие BTC в T, за сутки до T); wave — число.
    Нет данных — признака нет (условие с ним не выполняется)."""
    H, D = 3600, 86400
    F = {}
    ser = _c4_series(st, coin, fs, T)
    cur = ser.get(T)
    if cur is None:
        return None
    bor, rep, rank = cur
    F["bor"], F["rep"], F["net"] = bor, rep, bor - rep
    F["rb"] = rep / bor if bor > 0 else None
    r4row = (st["rows"].get(str(T - 4 * H)) or {}).get(coin)             # in4 — по постам, без проверки фьючерса
    if r4row is not None and r4row[2] > 0:
        F["r4x"] = rep / r4row[2]
    b24 = ser.get(T - D)
    if b24 is not None and b24[1] > 0:
        F["r24x"] = rep / b24[1]
    F["net7"] = sum((ser[T - k * D][0] - ser[T - k * D][1]) if (T - k * D) in ser else 0.0 for k in range(7))
    F["place"] = rank
    hs = st["hours"].get(coin) or set()
    h0 = T // H - 1
    F["pres7"] = sum(1 for k in range(168) if (h0 - k) in hs)
    run = 0
    while (h0 - run) in hs and run < 24 * 60:
        run += 1
    F["run"] = run
    F["hold"] = min(1000.0, max(-1000.0, F["net7"] / max(rep, 1e3)))
    win = [ser[h] for h in sorted(ser) if T - 30 * D <= h < T]
    if len(win) >= 48:
        mb = _c4_median([w[0] for w in win]); mr = _c4_median([w[1] for w in win])
        F["zbor"] = math.log(bor / mb) if bor > 0 and mb > 0 else None
        F["zrep"] = math.log(rep / mr) if rep > 0 and mr > 0 else None
        nets = [w[0] - w[1] for w in win]; mn = sum(nets) / len(nets)
        sd = math.sqrt(sum((x - mn) ** 2 for x in nets) / len(nets))
        F["znet"] = (bor - rep - mn) / sd if sd > 0 else None
    # цена и оборот: 15-мин свечи, последняя закрывается в T
    if kl15 and len(kl15) >= 673 and int(kl15[-1][0]) // 1000 + 900 == T:
        c = [float(k[4]) for k in kl15]; qv = [float(k[7]) for k in kl15]; tb = [float(k[10]) for k in kl15]
        i = len(c) - 1
        F["r4"] = c[i] / c[i - 16] - 1; F["r24"] = c[i] / c[i - 96] - 1; F["r72"] = c[i] / c[i - 288] - 1
        lr = [math.log(c[j] / c[j - 1]) for j in range(i - 95, i + 1)]
        m = sum(lr) / len(lr); F["vol24"] = math.sqrt(sum((x - m) ** 2 for x in lr) / len(lr))
        q24 = sum(qv[i - 95:i + 1]); q7 = sum(qv[i - 671:i + 1]) / 7
        F["qv24"] = q24; F["qvx"] = q24 / q7 if q7 > 0 else None
        q4 = sum(qv[i - 15:i + 1]); F["tb4"] = sum(tb[i - 15:i + 1]) / q4 if q4 > 0 else None
        F["bqv"] = bor / q24 if q24 > 0 else None
    # фандинг — как в s216 только вместе с ценой (фьючерсу ≥ 7 сут свечей)
    if fund and F.get("qv24") is not None:
        ft = [x[0] for x in fund]; fr = [x[1] for x in fund]
        k = max((j for j in range(len(ft)) if ft[j] <= T), default=-1)
        if k >= 1:
            gap = (ft[k] - ft[k - 1]) / H
            F["f8"] = fr[k] * 8 / gap if gap > 0 else None
            F["f24"] = sum(fr[j] for j in range(len(ft)) if T - D < ft[j] <= T)
            f8s = [fr[j] * 8 / ((ft[j] - ft[j - 1]) / H) for j in range(1, len(ft))
                   if T - 30 * D < ft[j] <= T and ft[j] > ft[j - 1]]
            mz, sz = _c4_mean_std(f8s)
            if sz and F.get("f8") is not None:
                F["zf"] = (F["f8"] - mz) / sz
    # ставка займа: почасовой ряд (последняя запись не позже часа), час T − 1 ч
    if rates:
        rt = [x[0] for x in rates]; rv = [x[1] for x in rates]
        h_first = rt[0] // H * H; h_last = max(rt[-1] // H * H, (T - H) // H * H)   # последнее значение тянется до T − 1 ч
        hrs = list(range(h_first, h_last + H, H))
        v, j = [], 0
        for h in hrs:
            while j + 1 < len(rt) and rt[j + 1] <= h:
                j += 1
            v.append(rv[j])
        k = max((n for n in range(len(hrs)) if hrs[n] <= T - H), default=-1)
        if k >= 24:
            w = v[max(0, k - 719):k + 1]
            if len(w) >= 120:
                q10 = _c4_quantile(w, 0.1); mx = max(w)
                F["rate"] = v[k]
                F["ux"] = v[k] / q10 if q10 else None
                F["dr24"] = v[k] / v[k - 24] if v[k - 24] else None
                F["lim"] = 1.0 if (F["ux"] is not None and v[k] >= 0.9 * mx and F["ux"] >= 3) else 0.0
            else:
                F["rate"] = v[k]
                F["dr24"] = v[k] / v[k - 24] if v[k - 24] else None
            if k >= 48:
                med = _c4_median(v[max(k - 720, 0):k])
                F["zrate"] = math.log(v[k] / med) if v[k] > 0 and med and med > 0 else None
    # капитализация
    if mcap:
        F["bmc"] = bor / mcap
    # позиции: строка на T − 1 ч
    T1 = T - H
    if met:
        def mv(x, col):
            r = met.get(x)
            return r[col] if r is not None else None
        o, o4, o24 = mv(T1, 0), mv(T1 - 4 * H, 0), mv(T1 - D, 0)
        if o is not None and o4:
            F["doi4"] = o / o4 - 1
        if o is not None and o24:
            F["doi24"] = o / o24 - 1
        oiv = mv(T1, 1)
        F["lsr_top"] = mv(T1, 2); F["lsr_acc"] = mv(T1, 3)
        a, b = mv(T1, 3), mv(T1 - D, 3)
        F["dlsr24"] = a - b if a is not None and b is not None else None
        if oiv is not None and F.get("qv24"):
            F["oiq"] = oiv / F["qv24"]
        mt = sorted(met)                                   # сдвиг на 4 и 24 строки ряда с проверкой времени — как в s225
        hh = [h for h in mt if T1 - 30 * D <= h < T1]
        pos = {h: n for n, h in enumerate(mt)}
        o4s, o24s = [], []
        for h in hh:
            n = pos[h]; a0 = met[h][0]
            if n >= 4 and mt[n - 4] == h - 4 * H and a0 and a0 > 0 and met[mt[n - 4]][0] and met[mt[n - 4]][0] > 0:
                o4s.append(math.log(a0 / met[mt[n - 4]][0]))
            if n >= 24 and mt[n - 24] == h - D and a0 and a0 > 0 and met[mt[n - 24]][0] and met[mt[n - 24]][0] > 0:
                o24s.append(math.log(a0 / met[mt[n - 24]][0]))
        s4, s24 = _c4_std(o4s), _c4_std(o24s)
        if s4 and F.get("doi4") is not None and F["doi4"] > -1:
            F["zoi4"] = math.log1p(F["doi4"]) / s4
        if s24 and F.get("doi24") is not None and F["doi24"] > -1:
            F["zoi24"] = math.log1p(F["doi24"]) / s24
        if len(hh) >= 48:
            for col, name, curk in ((3, "zlsr", "lsr_acc"), (2, "zlsrt", "lsr_top")):
                m, s = _c4_mean_std([met[h][col] for h in hh if met[h][col] is not None])
                if s and F.get(curk) is not None:
                    F[name] = (F[curk] - m) / s
    if tkr is not None:
        F["tkr"] = tkr
    # часовые свечи: разброс 4- и 24-часовых ходов за 30 сут и медиана суточного оборота
    if kl1h:
        th = [int(k[0]) // 1000 + H for k in kl1h]; ch = [float(k[4]) for k in kl1h]; qh = [float(k[7]) for k in kl1h]
        idx = [n for n in range(len(th)) if T - 30 * D <= th[n] < T]
        l4 = [math.log(ch[n] / ch[n - 4]) for n in idx if n >= 4 and th[n] - th[n - 4] == 4 * H]
        l24 = [math.log(ch[n] / ch[n - 24]) for n in idx if n >= 24 and th[n] - th[n - 24] == D]
        s4, s24 = _c4_std(l4), _c4_std(l24)
        if s4 and F.get("r4") is not None:
            F["zr4"] = math.log1p(F["r4"]) / s4
        if s24 and F.get("r24") is not None:
            F["zr24"] = math.log1p(F["r24"]) / s24
        pos = {t: n for n, t in enumerate(th)}
        qs = []
        for kd in range(1, 31):
            n = pos.get(T - kd * D)
            if n is not None and n >= 23 and th[n] - th[n - 23] == 23 * H:
                q = sum(qh[n - 23:n + 1])
                if q > 0:
                    qs.append(q)
        if len(qs) >= 20 and F.get("qv24"):
            F["zqv"] = math.log(F["qv24"] / _c4_median(qs))
    if btc and btc[0] and btc[1]:
        F["btc24"] = btc[0] / btc[1] - 1
    F["wave"] = wave
    return F


def c4_votes(F):
    """Сколько из 100 правил комитета выполнено: правило — все его условия (признак есть и ≤ / ≥ порога)."""
    n = 0
    for rule in C4_RULES:
        ok = True
        for f, op, q in rule:
            x = F.get(f)
            if x is None or x != x or not (x <= q if op == "le" else x >= q):
                ok = False
                break
        n += ok
    return n


def _c4_klines(fs, interval, n, end_ts):
    """Закрытые свечи фьючерса, последняя закрывается не позже end_ts. None — сбой."""
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={fs}USDT&interval={interval}"
                  f"&endTime={end_ts * 1000 - 1}&limit={n}", 20)
    return j if isinstance(j, list) else None


def _c4_funding(fs, T):
    j = http_json(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={fs}USDT&startTime={(T - 31 * 86400) * 1000}"
                  f"&endTime={T * 1000 + 999}&limit=1000", 20)
    if not isinstance(j, list):
        return None
    try:
        return sorted((int(x["fundingTime"]) // 1000, float(x["fundingRate"])) for x in j)
    except (KeyError, TypeError, ValueError):
        return None


def _c4_metrics(fs, T, now):
    """Почасовые OI, OI $, лонг/шорт топ-трейдеров по позициям и всех счетов за ~30 сут до T − 1 ч (Binance отдаёт только
    30 сут); отношение агрессивных объёмов — 5-мин окно перед T − 1 ч (как строки архива data.binance.vision)."""
    T1 = T - 3600; a0 = max(T1 - 31 * 86400, int(now) - 30 * 86400 + 300)
    base = "https://fapi.binance.com/futures/data"
    out = {}
    for path, key in (("openInterestHist", "oi"), ("topLongShortPositionRatio", "top"), ("globalLongShortAccountRatio", "acc")):
        rows, start = [], a0
        for _ in range(3):
            j = http_json(f"{base}/{path}?symbol={fs}USDT&period=1h&startTime={start * 1000}&endTime={T1 * 1000}&limit=500", 20)
            if not isinstance(j, list):
                return None, None
            rows += j
            if len(j) < 500:
                break
            start = int(j[-1]["timestamp"]) // 1000 + 1
        for x in rows:
            try:
                t = int(x["timestamp"]) // 1000
                if key == "oi":
                    out.setdefault(t, [None, None, None, None])[0:2] = [float(x["sumOpenInterest"]), float(x["sumOpenInterestValue"])]
                else:
                    out.setdefault(t, [None, None, None, None])[2 if key == "top" else 3] = float(x["longShortRatio"])
            except (KeyError, TypeError, ValueError):
                continue
    j = http_json(f"{base}/takerlongshortRatio?symbol={fs}USDT&period=5m&startTime={(T1 - 300) * 1000}"
                  f"&endTime={(T1 - 300) * 1000}&limit=1", 20)
    tkr = None
    if isinstance(j, list) and j:
        try:
            if int(j[0]["timestamp"]) // 1000 == T1 - 300:
                tkr = float(j[0]["buySellRatio"])
        except (KeyError, TypeError, ValueError):
            tkr = None
    return {t: tuple(v) for t, v in out.items() if v[0] is not None}, tkr


def _c4_rates(asset, T):
    j = http_json(f"{C4_RATES}?asset={urllib.parse.quote(asset)}&vipLevel=0&startTime={(T - 31 * 86400) * 1000}"
                  f"&endTime={T * 1000}", 20)
    if not (isinstance(j, dict) and j.get("success") and isinstance(j.get("data"), list)):
        return None
    try:
        return sorted((int(x["timestamp"]) // 1000, float(x["dailyInterestRate"])) for x in j["data"])
    except (KeyError, TypeError, ValueError):
        return None


def _c4_cmc_refresh(now):
    """Список CMC раз в сутки (те же две страницы, что у 🐋): {тикер: [(цена, капитализация), …]}."""
    if _c4_cmc["rows"] is not None and now - _c4_cmc["t"] < 86400:
        return
    rows = {}
    for start in (1, 5001):
        j = http_json(WD_CMC.format(start), 60)
        d = j.get("data") if isinstance(j, dict) else None
        lst = d.get("cryptoCurrencyList") if isinstance(d, dict) else None
        if not isinstance(lst, list):
            if start == 1:
                return
            break
        for c in lst:
            try:
                qs = [q for q in c.get("quotes") or [] if isinstance(q, dict)]
                q = next((q for q in qs if q.get("name") == "USD"), qs[0] if qs else {})
                p, mc = float(q.get("price") or 0), float(q.get("marketCap") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if p > 0 and mc > 0:
                rows.setdefault(str(c.get("symbol") or "").upper(), []).append((p, mc))
        if len(lst) < 5000:
            break
    _c4_cmc.update(t=now, rows=rows)


def _c4_mcap(coin, px):
    """Капитализация CMC монеты фьючерса: тот же тикер, цена CMC к цене фьючерса (с множителем) 0,8–1,25, из таких —
    наибольшая капитализация (как research/s216 mcap_table)."""
    base, mult = _wd_base(coin)
    best = None
    for p, mc in (_c4_cmc["rows"] or {}).get(base, []):
        if 0.8 <= px / (p * mult) <= 1.25 and (best is None or mc > best):
            best = mc
    return best


def _c4_alt_basket():
    """Корзина альтов для хеджа: бессрочные фьючерсы USDT с оборотом за 24 ч ≥ 5 млн $, кроме BTC — {фьючерс: цена}."""
    j = http_json("https://fapi.binance.com/fapi/v1/ticker/24hr", 20)
    if not isinstance(j, list):
        return None
    trader.contract("BTC")
    out = {}
    for x in j:
        try:
            s = str(x.get("symbol") or "")
            if s in trader._contracts and s != "BTCUSDT" and float(x.get("quoteVolume") or 0) >= C4_ALT_VOL:
                out[s] = float(x["lastPrice"])
        except (TypeError, ValueError, AttributeError):
            continue
    return out or None


def c4_rule(state):
    """🗳: раз в 4 ч (00, 04, …, 20 UTC), в первые 20 мин после закрытия свечи — признаки монет канала и голосование.
    Сбой данных по монете — повтор в следующем проходе того же окна. Пока панель канала не покрывает 31 сут — без сделок."""
    now = time.time(); T = int(now // C4_GRID * C4_GRID)
    if now - T < 60 or now - T > C4_LATE:
        return []
    c = state.setdefault("c4", {})
    if c.get("T") == T and c.get("done"):
        return []
    st = _c4_load()
    if not _c4_ready(st, now):
        if c.get("wait_log", 0) < now - 6 * 3600:
            c["wait_log"] = now
            log("КОМИТЕТ", "панель канала ещё не покрывает 31 сут — сделок нет, догружаю историю")
        return []
    if c.get("T") != T:
        c.update(T=T, done=False, seen=[], tries=0)
    c["tries"] = c.get("tries", 0) + 1
    trader.contract("BTC")
    fut = {}

    def fut_of(coin):
        if coin not in fut:
            fut[coin] = _fut_sym(coin)
        return fut[coin]
    row = st["rows"].get(str(T)) or {}
    cand = []
    for coin in sorted(row):
        if coin in C4_STABLE or coin in BL_SKIP:
            continue
        fs = fut_of(coin)
        if fs and fs not in BL_SKIP and _c4_live(fs, T) and coin not in c["seen"]:
            cand.append((coin, fs))
    _c4_cmc_refresh(now)
    btc15 = _c4_klines("BTC", "15m", 100, T)
    if not btc15 or int(btc15[-1][0]) // 1000 + 900 != T:
        if c["tries"] >= 6:
            c["done"] = True; log("КОМИТЕТ", "нет свечей BTC — окно пропущено")
        return []
    bt = [int(k[0]) // 1000 + 900 for k in btc15]
    jj = max((n for n in range(len(bt)) if bt[n] <= T - 86400), default=None)
    btc = (float(btc15[-1][4]), float(btc15[jj][4]) if jj is not None else None)
    wave = _c4_wave(st, T, fut_of)

    def one(cf):
        try:
            return one_(cf)
        except Exception as e:                                # странные данные одной монеты не срывают окно
            log("КОМИТЕТ", f"{cf[1]}: ошибка признаков {e!r}")
            return cf[0], cf[1], None, None

    def one_(cf):
        coin, fs = cf
        kl15 = _c4_klines(fs, "15m", 700, T); kl1h = _c4_klines(fs, "1h", 750, T)
        fund = _c4_funding(fs, T); met, tkr = _c4_metrics(fs, T, now)
        asset = re.sub(r"^(1000000|1000|1M)", "", fs) if not re.match(r"^(1000000|1000|1M)\d", fs) else fs
        rates = _c4_rates(asset, T)
        if kl15 is None or kl1h is None or fund is None or met is None:
            return coin, fs, None, None
        px = float(kl15[-1][4]) if kl15 else None
        F = c4_features(T, coin, fs, st, kl15, kl1h, fund, met, tkr, rates or [],
                        _c4_mcap(fs, px) if px else None, btc, wave)
        return coin, fs, F, px
    with ThreadPoolExecutor(C4_WORKERS) as ex:
        res = list(ex.map(one, cand))
    basket, msgs, miss = None, [], []
    for coin, fs, F, px in res:
        if F is None:
            miss.append(fs); continue
        c["seen"].append(coin)
        v = c4_votes(F)
        if v < C4_K:
            continue
        if basket is None:
            basket = _c4_alt_basket() or {}
        note = (f"комитет: выполнено правил {v} из 100 (нужно ≥ {C4_K}); займ {F['bor'] / 1e6:.2f} млн $, OI за 4 ч "
                + (f"{F['doi4'] * 100:+.1f}%" if F.get("doi4") is not None else "—")
                + ", лонг/шорт счетов за сутки " + (f"{F['dlsr24']:+.2f}" if F.get("dlsr24") is not None else "—"))
        m = trader.virt_open(state, "virtual_C4", fs, "🗳", note, price=px, hold_h=C4_HOLD_H)
        if m:
            t = state["virtual_C4"]["trades"][-1]
            if t.get("sym") == fs and not t.get("closed") and basket:
                t["alt_px"] = basket
            msgs.append(m)
        log("КОМИТЕТ", f"{fs}: голосов {v} → вход" + ("" if m else " (не открыт: занято, баланс или нет цены)"))
    if miss and c["tries"] < 6:
        log("КОМИТЕТ", f"нет данных Binance по {len(miss)} монетам ({', '.join(miss[:10])}) — повтор в следующем проходе")
    else:
        c["done"] = True
        log("КОМИТЕТ", f"{time.strftime('%H:%M', time.gmtime(T))} UTC: монет в канале {len(row)}, проверено {len(c['seen'])}"
            + (f", без данных {len(miss)}" if miss else "") + f", волна {wave}")
    if msgs:
        return ["🗳 комитет «шорт 4 ч»:\n" + "\n".join(msgs)]
    return []


def scan(state, dry):
    posts = fetch_posts(max(LOOKBACK_H, LOOKBACK_RP_H) if repay_due(state) or wide_due(state) else LOOKBACK_H)
    try:
        bf_record(posts)                                    # журнал постов для 🏦 (фактор займа)
    except Exception as e:
        log("ошибка журнала постов:", repr(e))
    try:
        c4_record(posts)                                    # панель канала для 🗳 (займ, отдача, место по часам за 33 сут)
    except Exception as e:
        log("ошибка панели канала 🗳:", repr(e))
    runs = channel_runs(posts)
    log(f"постов {len(posts)}, монет в канале сейчас {len(runs)}, "
        f"висят ≥{MIN_RUN_H:g}ч: {sum(1 for r in runs.values() if r['run_h'] >= MIN_RUN_H)}")
    now = time.time()
    cands = []
    long_runs = [sym for sym, r in runs.items() if r["run_h"] >= MIN_RUN_H]
    with ThreadPoolExecutor(8) as ex:                       # цены и фандинг параллельно — проход короче, вход раньше
        pcs = dict(zip(long_runs, ex.map(price_and_change, long_runs)))
        fds = dict(zip(long_runs, ex.map(funding, long_runs)))
    for sym, r in runs.items():
        if r["run_h"] < MIN_RUN_H:
            continue
        pc = pcs.get(sym)
        if not pc:
            log("нет цены для", sym)
            continue
        c = {"sym": sym, "run_h": r["run_h"], "capped": r["capped"], "info": r["info"], "funding": fds.get(sym), **pc}
        cands.append(c)
        recent = [a for a in state["alerts"] if a["sym"] == sym and now - a["ts"] < COOLDOWN_H * 3600]
        rule = rule_for(c)
        if rule and not recent:
            c["rule"] = rule
            try:
                c["lsr"] = trader.taker_lsr(sym)
            except Exception:
                c["lsr"] = None
            try:
                c["risk_text"], c["risk"] = risk_marks(c)
            except Exception as e:
                c["risk_text"], c["risk"] = "", {}; log("ошибка риск-пометок:", repr(e))
            log("СИГНАЛ", rule, sym, f"{c['b4h']:+.1f}%", f"{c['run_h']:.1f}ч", f"B/R {c['info'][2]}", f"LSR {c['lsr']}",
                f"от пика {c.get('from_peak')}", f"паттерн {pattern_ok(c)}", f"риск {c.get('risk')}")
            broadcast(state, signal_text(c), dry)
            state["alerts"].append({"sym": sym, "ts": now, "price": c["price"], "b4h": c["b4h"], "run_h": c["run_h"],
                                    "funding": (c["funding"] or {}).get("rate"), "lsr": c["lsr"], "rule": rule,
                                    "br": _num(c["info"][2]), "from_peak": c.get("from_peak"), "from_low": c.get("from_low"),
                                    "rise_before": c.get("rise_before"), "pattern": pattern_ok(c),
                                    "s_pump": c.get("s_pump"), "s_dump": c.get("s_dump"), "risk": c.get("risk")})
            try:
                msg = trader.on_signal(state, sym, c["price"], lsr=c["lsr"], rule=rule)
            except Exception as e:
                msg = f"❌ {sym}: ошибка исполнителя: {e!r}"
            if msg:
                log(msg.replace("\n", " | "))
                broadcast(state, msg, dry)
            try:
                vmsg = trader.virt_on_signal(state, sym, c["price"], rule)
            except Exception as e:
                vmsg = None; log("ошибка виртуального журнала:", repr(e))
            try:
                cmsg = chng_confirm(state, sym, c["price"], rule, posts, now)     # 📘ᶜ: тот же сигнал, если был CHNG ≥ 1
            except Exception as e:
                cmsg = None; log("ошибка двойника CHNG:", repr(e))
            if cmsg:
                vmsg = f"{vmsg}\n{cmsg}" if vmsg else cmsg
            if vmsg:
                log(vmsg); broadcast(state, vmsg, dry)
    try:
        for msg in new_rules(state, posts):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка новых правил:", repr(e))
    try:
        for msg in repay_rule(state, posts):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила отдачи займа:", repr(e))
    try:
        for msg in repay_wide_rule(state, posts):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила широкой отдачи:", repr(e))
    try:
        for msg in korea_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка корейского правила:", repr(e))
    try:
        for msg in turkey_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка турецкого правила:", repr(e))
    try:
        for msg in borrow_factor_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила фактора займа:", repr(e))
    anns = []
    try:
        anns = ann_poll(state)
        for msg in announce_rule(state, anns):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила объявлений:", repr(e))
    try:
        for msg in spot_listing_rule(state, anns):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила листинга Binance:", repr(e))
    try:
        for msg in funding_ebb_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила отлива после фандинга:", repr(e))
    try:
        for msg in newtoken_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила нового токена:", repr(e))
    try:
        for msg in kr_listing_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила корейского листинга:", repr(e))
    try:
        for msg in kr_top_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила корейской пятёрки:", repr(e))
    try:
        for msg in retail_top_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила внимания розницы:", repr(e))
    try:
        for msg in open9_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила «9 утра»:", repr(e))
    try:
        for msg in unlock_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила разлоков:", repr(e))
    try:
        for msg in insider_unlock_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила разлоков инсайдерам:", repr(e))
    try:
        for msg in whale_deposit_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила заводов на Binance:", repr(e))
    try:
        for msg in c4_rule(state):                          # 🗳 комитет «шорт 4 ч» (research/s225)
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка комитета 🗳:", repr(e))
    if cands:
        log(status_text(cands).replace("\n", " | "))
    return cands


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("subscribers", [])
    s.setdefault("alerts", [])
    s.setdefault("update_offset", 0)
    return s


_saved = [None]                                         # последний записанный текст state.json


def save_state(s):
    """state.json: одной строкой (быстрый кодировщик json вместо медленного с отступами) и только если что-то изменилось —
    раньше файл целиком переписывался после каждого опроса Telegram, 3–4 раза в минуту."""
    text = json.dumps(s, ensure_ascii=False, separators=(",", ":"))
    if text == _saved[0]:
        return
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, STATE_FILE)
    _saved[0] = text


def log_resources(durs):
    """Раз в час — строка «РЕСУРСЫ»: память процесса (сейчас и пик), потоки, проходы за час (медиана и максимум), сеть
    по хостам — запросов, секунд ожидания, максимум, сбоев (DNS — поиск адресов; длинный опрос Telegram не считается).
    Для поиска причин долгих проходов и перегрузки сервера (tools/server_health.py)."""
    st = {}
    try:
        with open("/proc/self/status") as f:
            st = dict(ln.split(":", 1) for ln in f if ":" in ln)
    except OSError:
        pass
    mb = lambda k: f"{int(st[k].split()[0]) / 1024:.0f}" if k in st else "?"
    d = sorted(durs)
    net = sorted(((v[2], h, v) for h, v in trader.NET.items() if h != "telegram getUpdates"), reverse=True)
    log("РЕСУРСЫ", f"память {mb('VmRSS')} МБ (пик {mb('VmHWM')} МБ), потоков {st.get('Threads', '?').strip()}; проходов за час "
        f"{len(d)}" + (f", медиана {d[len(d) // 2]:.0f} с, максимум {d[-1]:.0f} с" if d else "")
        + "; сеть за час: " + ", ".join(f"{h} {v[0]} запр. {v[2]:.0f} с (макс {v[3]:.1f} с, сбоев {v[1]})" for _, h, v in net[:7]))
    trader.NET.clear()


_exec = {"bad": False, "t": 0, "said": 0}                # проверка ключей Binance не прошла: когда проверяли и писали в чат


def exec_recheck(state, dry):
    """Проверка ключей на старте не прошла — повтор раз в 5 мин. Binance ответил — одно сообщение в чат; всё ещё нет —
    напоминание раз в 6 ч с текущей причиной."""
    now = time.time()
    if not _exec["bad"] or now - _exec["t"] < 300:
        return
    _exec["t"] = now
    check = trader.startup_check()
    log(check)
    if check.startswith("Binance OK"):
        _exec["bad"] = False
        state.pop("exec_bad", None)
        broadcast(state, f"✅ Исполнитель сделок снова на связи: {check}", dry)
    elif now - _exec["said"] >= 6 * 3600:
        _exec["said"] = now
        broadcast(state, f"⚠️ Исполнитель сделок всё ещё без связи с Binance: {check}", dry)


def cycle(dry, state=None):
    """Один проход: канал → сигналы/сделки → отчёты → сопровождение позиций. Возвращает кандидатов."""
    state = state if state is not None else load_state()
    trader.configure(state)
    try:
        exec_recheck(state, dry)
    except Exception as e:
        log("ошибка повторной проверки ключей:", repr(e))
    cands = scan(state, dry)
    followups(state, dry)
    try:
        for msg in funding_switch_watch(state):
            broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка наблюдения за фандингом:", repr(e))
    try:
        upbit_flags_watch(state)
    except Exception as e:
        log("ошибка флагов Upbit:", repr(e))
    try:
        margin_rates_watch(state)
    except Exception as e:
        log("ошибка сборщика ставок:", repr(e))
    try:
        margin_pool_watch(state)
    except Exception as e:
        log("ошибка сборщика пула займа:", repr(e))
    try:
        usdt_premium_watch(state)
    except Exception as e:
        log("ошибка записи премий USDT:", repr(e))
    try:
        kr_ticks_watch(state)
    except Exception as e:
        log("ошибка записи корейских сделок:", repr(e))
    try:
        for msg in trader.manage(state):
            log(msg)
            broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка исполнителя:", repr(e))
    try:
        for msg in trader.virt_manage(state):
            log(msg)
            broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка виртуального журнала:", repr(e))
    save_state(state)
    return cands


def run_loop(dry):
    """Сканирование раз в trader.POLL_SEC (от начала прохода), а между ними — длинный опрос Telegram, чтобы кнопки отвечали сразу."""
    state = load_state()
    if "poll" not in (state.get("params") or {}):           # разовый переход на опрос раз в минуту (задержка входа, 04.10.2026)
        state.setdefault("params", {})["poll"] = 60.0
        save_state(state)
    trader.configure(state)
    cands = []
    started = time.time()
    next_scan = 0
    durs, res_t = [], time.time()
    while True:
        now = time.time()
        if now >= next_scan:
            try:
                cands = cycle(dry, state)
            except Exception as e:
                log("ошибка цикла:", repr(e))
            took = time.time() - now
            durs.append(took)
            if took > trader.POLL_SEC * 0.8:
                log(f"проход занял {took:.0f} с — дольше периода опроса {trader.POLL_SEC:g} с")
            if time.time() - res_t >= 3600:
                log_resources(durs)
                durs, res_t = [], time.time()
            next_scan = max(now + trader.POLL_SEC, time.time() + 5)
            if MAX_RUNTIME_SEC and time.time() - started + trader.POLL_SEC > MAX_RUNTIME_SEC:
                log("достигнут MAX_RUNTIME_SEC, выхожу")
                break
        wait = max(1, min(25, int(next_scan - time.time())))
        try:
            trader.configure(state)
            got = poll_commands(state, cands, dry, wait=wait)
            export_check()                                   # /export: готовый файл выгрузки — в чат
            save_state(state)
            if got is None:
                # Telegram не ответил: без паузы цикл крутился бы вхолостую сотни раз в секунду (при обрыве сети ошибка
                # приходит сразу) — каждый раз строка в журнал и запись state.json, сервер вставал
                time.sleep(max(0.5, min(10, next_scan - time.time())))
        except Exception as e:
            log("ошибка обработки команд:", repr(e))
            time.sleep(3)


# ---------------------------------------------------------------- самописец сервера
SYS_LOG = os.path.join(os.path.dirname(os.path.abspath(STATE_FILE)), "system.log")


def _proc_name(cmd):
    """Имя программы для сводки памяти: chrome — одно на все процессы; python — по скрипту или модулю."""
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


_net_prev = {}                                          # счётчики сети на прошлом снимке самописца


def net_snapshot():
    """Сеть всего сервера с прошлого снимка: приём и отдача (Мбит/с) по интерфейсам, кроме lo; доля TCP-сегментов,
    отправленных повторно (потери пакетов — на них виснут удалённый стол и SSH), повторы SYN (соединение не открылось
    с первого раза). Первый снимок и сбой чтения — пустая строка."""
    try:
        c = {"t": time.time(), "rx": 0, "tx": 0}
        with open("/proc/net/dev") as f:
            for ln in f.readlines()[2:]:
                name, _, v = ln.partition(":")
                v = v.split()
                if name.strip() != "lo" and len(v) >= 9:
                    c["rx"] += int(v[0]); c["tx"] += int(v[8])
        for path, sect in (("/proc/net/snmp", "Tcp:"), ("/proc/net/netstat", "TcpExt:")):
            with open(path) as f:
                rows = [ln.split() for ln in f if ln.startswith(sect)]
            if len(rows) >= 2:
                c.update(zip(rows[0][1:], (int(x) for x in rows[1][1:])))
    except (OSError, ValueError):
        return ""
    p = dict(_net_prev); _net_prev.clear(); _net_prev.update(c)
    dt = c["t"] - p.get("t", c["t"])
    if dt <= 0:
        return ""
    d = lambda k: max(0, c.get(k, 0) - p.get(k, 0))
    out = d("OutSegs")
    return (f"сеть: приём {d('rx') * 8 / dt / 1e6:.2f} Мбит/с, отдача {d('tx') * 8 / dt / 1e6:.2f}, "
            f"повторы TCP {d('RetransSegs') / out * 100 if out else 0:.1f}% из {out}, SYN {d('TCPSynRetrans')}; ")


def sys_snapshot():
    """Состояние сервера одной строкой: память и подкачка, нехватка памяти/диска/процессора (PSI за 10 с, % времени),
    нагрузка, сеть (net_snapshot), программы, больше всех занимающие память (RSS в МБ, процессы одной программы — суммой).
    Возвращает (строка, памяти меньше 10%)."""
    mi = {}
    with open("/proc/meminfo") as f:
        for ln in f:
            k, _, v = ln.partition(":")
            mi[k] = int(v.split()[0]) // 1024 if v.split() else 0
    psi = []
    for res in ("memory", "io", "cpu"):
        try:
            with open(f"/proc/pressure/{res}") as f:
                psi.append(f"{res} {f.readline().split()[1].split('=')[1]}")
        except (OSError, IndexError):
            pass
    with open("/proc/loadavg") as f:
        load = f.read().split()
    page = os.sysconf("SC_PAGE_SIZE"); mem = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().split(b"\0")
            if not cmd[0]:
                continue                                         # потоки ядра
            with open(f"/proc/{pid}/statm") as f:
                rss = int(f.read().split()[1]) * page
        except (OSError, IndexError, ValueError):
            continue
        n = _proc_name(cmd)
        mem[n] = mem.get(n, 0) + rss
    top = sorted(mem.items(), key=lambda x: -x[1])[:6]
    av, tot = mi.get("MemAvailable", 0), mi.get("MemTotal", 0)
    return (f"доступно {av} МБ из {tot}, подкачка {mi.get('SwapTotal', 0) - mi.get('SwapFree', 0)} МБ из {mi.get('SwapTotal', 0)}, "
            f"ждёт записи {mi.get('Dirty', 0)} МБ; PSI {' '.join(psi)}; нагрузка {' '.join(load[:3])}, процессов {load[3]}; "
            + net_snapshot() + "память, МБ: " + ", ".join(f"{n} {b // 1048576}" for n, b in top)), av < tot * 0.1


def sys_watch():
    """Самописец сервера (отдельный поток): раз в минуту, при нехватке памяти — раз в 15 с, строка sys_snapshot в system.log
    рядом с state.json с fsync — запись переживёт зависание и жёсткую перезагрузку; раз в 10 мин та же строка в журнал
    службы («СИСТЕМА»). После зависания видно, что к нему привело: кончилась память (и кто её занял), диск, процессор —
    или сервер встал целиком (тогда в файле пропуск по времени). Записи перед перезагрузками — tools/server_health.py."""
    n = 0
    while True:
        low = False
        try:
            text, low = sys_snapshot()
            if os.path.exists(SYS_LOG) and os.path.getsize(SYS_LOG) > 5 * 1048576:
                os.replace(SYS_LOG, SYS_LOG + ".1")
            fd = os.open(SYS_LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
            try:
                os.write(fd, f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {text}\n".encode())
                os.fsync(fd)
            finally:
                os.close(fd)
            if n % 10 == 0 or low:
                log("СИСТЕМА", text)
        except Exception as e:
            if n % 60 == 0:
                log("СИСТЕМА: снимок не записан:", repr(e))
        n += 1
        time.sleep(15 if low else 60)


def main():
    dry = "--dry-run" in sys.argv
    try:
        os.nice(10)                     # процессор — сначала SSH и системе: бот почти всё время ждёт сеть, ему хватит
    except OSError:
        pass
    if HALT:
        log("БОТ ОСТАНОВЛЕН:", HALT, "— сделок, сканирования, сети и сообщений нет, пишет только самописец сервера")
        if "--loop" in sys.argv:
            if TOKEN and not dry:       # одно сообщение при запуске — подтверждение, что выключатель дошёл до сервера
                try:
                    broadcast(load_state(), f"⏸ Бот остановлен: {HALT}. Сделок, сканирования и сообщений нет — пишет только "
                                            "самописец сервера. Позиции на Binance под стоп- и тейк-ордерами биржи. "
                                            "Чтобы включить, попросите Claude.", dry)
                except Exception as e:
                    log("сообщение об остановке не отправлено:", repr(e))
            sys_watch()                 # раз в минуту строка о сервере в system.log; процесс живёт, чтобы systemd не перезапускал
        return
    if not TOKEN and not dry:
        sys.exit("TG_BOT_TOKEN не задан (или используйте --dry-run)")
    check = trader.startup_check()
    log(check)
    if TOKEN and not dry:
        setup_commands()
    if trader.MODE != "off" and not dry:
        st = load_state()
        if not check.startswith("Binance OK"):
            broadcast(st, f"⚠️ Исполнитель сделок: {check}. Проверю снова через 5 мин и напишу, когда Binance ответит", dry)
            _exec.update(bad=True, t=time.time(), said=time.time())
            st["exec_bad"] = True
            save_state(st)
        elif st.pop("exec_bad", None):                       # до перезапуска связи не было — сообщаем, что появилась
            broadcast(st, f"✅ Исполнитель сделок снова на связи: {check}", dry)
            save_state(st)
    if TOKEN and not dry:
        st = load_state()
        if st.get("no_trade_said", "") != trader.NO_TRADE:   # одно сообщение, когда выключатель торговли поставлен или снят
            broadcast(st, f"▶️ Бот работает: канал, сигналы, виртуальные журналы и команды. Реальная торговля {trader.NO_TRADE}: "
                          "новых сделок и ордеров на Binance нет; открытые позиции, если есть, бот не ведёт — их закроют стоп- и "
                          "тейк-ордера биржи, выхода по времени нет (что открыто — /positions). Чтобы включить, попросите Claude."
                      if trader.NO_TRADE else f"💰 Реальная торговля снова включена: {check}", dry)
            if trader.NO_TRADE:
                st["no_trade_said"] = trader.NO_TRADE
            else:
                st.pop("no_trade_said", None)
            save_state(st)
    if "--loop" in sys.argv:
        threading.Thread(target=sys_watch, name="sys_watch", daemon=True).start()
        run_loop(dry)
    else:
        state = load_state()
        cands = cycle(dry, state)
        poll_commands(state, cands, dry)
        save_state(state)


if __name__ == "__main__":
    main()
