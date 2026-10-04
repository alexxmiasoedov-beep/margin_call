#!/usr/bin/env python3
"""Сканер Telegram-канала с уведомлениями подписчикам бота.

Запуск:  python3 scanner.py --once        один проход (для cron / GitHub Actions)
         python3 scanner.py --loop        бесконечный цикл, проход раз в trader.POLL_SEC (/set poll)
         добавьте --dry-run, чтобы ничего не отправлять, а только печатать.
Все настройки — через переменные окружения (см. .env.example). Зависимостей нет.
"""
import html
import json
import os
import re
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


def http(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def http_json(url, timeout=30):
    try:
        return json.loads(http(url, timeout=timeout))
    except Exception as e:
        log("http_json fail", url.split("?")[0], e)
        return None


# ---------------------------------------------------------------- Telegram
def tg(method, _timeout=30, **params):
    if not TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        return json.loads(http(url, data=data, timeout=_timeout))
    except Exception as e:
        log("telegram fail", method, e)
        return None


def send(chat_id, text):
    return tg("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview="true")


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
    "/positions — открытые позиции на Binance, /virtual — виртуальные журналы (без тейка; по фандингу; 15/25), /params — параметры сделок, /set <параметр> <число> — изменить "
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
        [("📓📗📘 Виртуальные журналы", "virtual")],
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
            ("trades", "Журнал сделок, баланс"), ("status", "Кандидаты в канале"), ("pause", "Пауза торговли"),
            ("resume", "Возобновить торговлю"), ("stop", "Отписаться")]
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
    wait > 0 — длинный опрос: Telegram держит запрос до wait секунд и отвечает сразу, как придёт событие."""
    if not TOKEN:
        return
    r = tg("getUpdates", _timeout=wait + 15, offset=state.get("update_offset", 0), timeout=wait)
    if not r or not r.get("ok"):
        return
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


# ---------------------------------------------------------------- канал
ROW = re.compile(r"^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+(-?[\d.]+)\s*$")


def fetch_posts(lookback_h):
    """Посты канала за последние lookback_h часов: [{id, ts, rows:{sym:(bor,rep,br)}}]."""
    now = time.time()
    posts, before, seen = [], None, set()
    for _ in range(40):
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
            rows = {}
            for ln in text.splitlines():
                r = ROW.match(ln.strip())
                if r:
                    rows[r.group(1)] = (r.group(2), r.group(3), r.group(4))
            got.append({"id": pid, "ts": ts, "rows": rows})
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
    posts = fetch_posts(LOOKBACK_H)
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
    if cands:
        log(status_text(cands).replace("\n", " | "))
    return cands


def load_state():
    try:
        s = json.load(open(STATE_FILE))
    except Exception:
        s = {}
    s.setdefault("subscribers", [])
    s.setdefault("alerts", [])
    s.setdefault("update_offset", 0)
    return s


def save_state(s):
    tmp = STATE_FILE + ".tmp"
    json.dump(s, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def cycle(dry, state=None):
    """Один проход: канал → сигналы/сделки → отчёты → сопровождение позиций. Возвращает кандидатов."""
    state = state if state is not None else load_state()
    trader.configure(state)
    cands = scan(state, dry)
    followups(state, dry)
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
    while True:
        now = time.time()
        if now >= next_scan:
            try:
                cands = cycle(dry, state)
            except Exception as e:
                log("ошибка цикла:", repr(e))
            took = time.time() - now
            if took > trader.POLL_SEC * 0.8:
                log(f"проход занял {took:.0f} с — дольше периода опроса {trader.POLL_SEC:g} с")
            next_scan = max(now + trader.POLL_SEC, time.time() + 5)
            if MAX_RUNTIME_SEC and time.time() - started + trader.POLL_SEC > MAX_RUNTIME_SEC:
                log("достигнут MAX_RUNTIME_SEC, выхожу")
                break
        wait = max(1, min(25, int(next_scan - time.time())))
        try:
            trader.configure(state)
            poll_commands(state, cands, dry, wait=wait)
            save_state(state)
        except Exception as e:
            log("ошибка обработки команд:", repr(e))
            time.sleep(3)


def main():
    dry = "--dry-run" in sys.argv
    if not TOKEN and not dry:
        sys.exit("TG_BOT_TOKEN не задан (или используйте --dry-run)")
    check = trader.startup_check()
    log(check)
    if TOKEN and not dry:
        setup_commands()
    if trader.MODE != "off" and not check.startswith("Binance OK") and not dry:
        broadcast(load_state(), f"⚠️ Исполнитель сделок: {check}", dry)
    if "--loop" in sys.argv:
        run_loop(dry)
    else:
        state = load_state()
        cands = cycle(dry, state)
        poll_commands(state, cands, dry)
        save_state(state)


if __name__ == "__main__":
    main()
