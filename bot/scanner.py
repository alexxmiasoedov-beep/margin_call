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
import sys
import time
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


def http(url, data=None, timeout=30):
    real = urllib.parse.urlsplit(url).hostname or "?"
    host = "telegram getUpdates" if "/getUpdates" in url else real
    wait = trader.banned(real)
    if wait:                                                 # Binance ответил 403/418/429 — до конца паузы не стучимся
        raise urllib.error.URLError(f"пауза после ответа Binance 418/429, ещё {wait:.0f} с")
    t0 = time.time(); ok = False
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
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
    "(margin, lev, tp, sl, hold, max, limit, lsr, dump, br, pause, fexit), /pause и /resume — пауза торговли, /stop — отписаться."
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


def setup_commands():
    """Регистрирует команды в меню Telegram (кнопка «/» у поля ввода)."""
    cmds = [("menu", "Меню с кнопками"), ("params", "Параметры сделок"), ("positions", "Открытые позиции на Binance"),
            ("history", "Ордера по монете за 24 ч: /history LSK"),
            ("trades", "Журнал сделок, баланс"), ("virtual", "Виртуальные журналы"), ("status", "Кандидаты в канале"),
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
        tg("sendMessage", chat_id=cid, text="Торговля возобновлена.", reply_markup=main_menu(state))


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
        elif text.startswith("/pause"):
            state["trading_paused"] = True
            send(cid, "Торговля на паузе: новые сделки не открываются, открытые ведутся до выхода. /resume — продолжить.")
        elif text.startswith("/resume"):
            state["trading_paused"] = False
            send(cid, "Торговля возобновлена.")
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
            got.append({"id": pid, "ts": ts, "rows": rows, "rows_all": rows_all})
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


def candle_due(state, key, name):
    """Время закрытия T свечи, которую 15-мин правило (отметка state[key]) ещё не проверило, если с закрытия прошло ≤ 10 мин;
    иначе None. Свеча, не проверенная за 10 мин, — одна строка в журнал службы: сбой данных или поздний проход."""
    T = int(time.time() // 900 * 900)
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
        m = trader.virt_open(state, "virtual_RP", fs, "RP", note, price=c)
        if m:
            msgs.append(m)
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


_t24 = {"t": 0, "data": None}


def ticker24():
    """Цены фьючерсов Binance за сутки (ticker/24hr: ~600 контрактов, вес 40) — один запрос на проход для 🇰🇷 и 🇹🇷."""
    if time.time() - _t24["t"] > 120 or not isinstance(_t24["data"], list):
        _t24["data"] = http_json("https://fapi.binance.com/fapi/v1/ticker/24hr", 20)
        _t24["t"] = time.time()
    return _t24["data"]


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
                m = trader.virt_open(state, "virtual_KR", s, "KR", note, price=c)
                if m:
                    msgs.append(m)
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
        m = trader.virt_open(state, "virtual_BF", fs, "BF", note, price=px)
        log("ФАКТОР ЗАЙМА", fs, note + ("" if m else " — уже открыта"))
        if m:
            msgs.append(m)
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


UPBIT_FLAGS = ("warning", "PRICE_FLUCTUATIONS", "TRADING_VOLUME_SOARING", "DEPOSIT_AMOUNT_SOARING",
               "GLOBAL_PRICE_DIFFERENCES", "CONCENTRATION_OF_SMALL_ACCOUNTS")   # warning — «предупреждение», остальные — «внимание»


def upbit_flags_watch(state, every=300):
    """Флаги Upbit по KRW-рынкам (research/s3/ВЫВОДЫ.md): предупреждение, скачки цены, всплеск объёма, всплеск депозитов,
    разница с мировой ценой, концентрация мелких счетов. Раз в 5 мин — /v1/market/all?is_details=true; в журнал службы —
    строки «UPBIT»: появление (+) и снятие (−) флага с ценой фьючерса Binance; если прошлых флагов нет — снимок (=).
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
    for sign, c, f, since in ch:
        s = perp.get(c)
        fut = (f"фьючерс {s} {price[s]}" if price.get(s) else f"фьючерс {s}") if s else "фьючерса нет"
        log("UPBIT", f"{sign}{f}", f"KRW-{c}", "|", fut + (f", держался {(now - since) / 3600:.1f} ч" if since else "") + gap)


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


def scan(state, dry):
    posts = fetch_posts(max(LOOKBACK_H, LOOKBACK_RP_H) if repay_due(state) else LOOKBACK_H)
    try:
        bf_record(posts)                                    # журнал постов для 🏦 (фактор займа)
    except Exception as e:
        log("ошибка журнала постов:", repr(e))
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
    try:
        for msg in announce_rule(state, ann_poll(state)):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила объявлений:", repr(e))
    try:
        for msg in newtoken_rule(state):
            log(msg.replace("\n", " | ")); broadcast(state, msg, dry)
    except Exception as e:
        log("ошибка правила нового токена:", repr(e))
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
            save_state(state)
            if got is None:
                # Telegram не ответил: без паузы цикл крутился бы вхолостую сотни раз в секунду (при обрыве сети ошибка
                # приходит сразу) — каждый раз строка в журнал и запись state.json, сервер вставал
                time.sleep(max(0.5, min(10, next_scan - time.time())))
        except Exception as e:
            log("ошибка обработки команд:", repr(e))
            time.sleep(3)


def main():
    dry = "--dry-run" in sys.argv
    try:
        os.nice(10)                     # процессор — сначала SSH и системе: бот почти всё время ждёт сеть, ему хватит
    except OSError:
        pass
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
    if "--loop" in sys.argv:
        run_loop(dry)
    else:
        state = load_state()
        cands = cycle(dry, state)
        poll_commands(state, cands, dry)
        save_state(state)


if __name__ == "__main__":
    main()
