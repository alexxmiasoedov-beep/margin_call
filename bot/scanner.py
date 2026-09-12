#!/usr/bin/env python3
"""Сканер Telegram-канала с уведомлениями подписчикам бота.

Запуск:  python3 scanner.py --once        один проход (для cron / GitHub Actions)
         python3 scanner.py --loop        бесконечный цикл, POLL_SEC между проходами
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
POLL_SEC = int(os.environ.get("POLL_SEC", "300"))
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
    "/positions — открытые позиции на Binance, /params — параметры сделок, /set <параметр> <число> — изменить "
    "(margin, lev, tp, sl, hold, max, limit), /pause и /resume — пауза торговли, /stop — отписаться."
)


def kb(rows):
    """Инлайн-клавиатура: rows = [[(текст, data), ...], ...]."""
    return json.dumps({"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]})


def main_menu(state):
    pause = ("▶️ Возобновить торговлю", "resume") if state.get("trading_paused") else ("⏸ Пауза торговли", "pause")
    return kb([
        [("⚙️ Параметры сделок", "params"), ("📊 Позиции на Binance", "positions")],
        [("📒 Журнал сделок", "trades"), ("🔍 Кандидаты в канале", "status")],
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
    """Последние n 15-минутных закрытий: (source, [close,...]) или None.
    Binance первым — сигналы канала про монеты Binance, и торгуем мы там же."""
    j = http_json(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Binance", [float(k[4]) for k in j]
    j = http_json(f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Binance-spot", [float(k[4]) for k in j]
    j = http_json(f"https://api.mexc.com/api/v3/klines?symbol={sym}USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "MEXC", [float(k[4]) for k in j]
    j = http_json(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}_USDT&interval=15m&limit={n}", 15)
    if isinstance(j, list) and len(j) >= n:
        return "Gate", [float(k[2]) for k in j]
    j = http_json(f"https://api.kucoin.com/api/v1/market/candles?type=15min&symbol={sym}-USDT", 15)
    if isinstance(j, dict) and len(j.get("data") or []) >= n:
        return "KuCoin", [float(k[2]) for k in sorted(j["data"], key=lambda k: int(k[0]))[-n:]]
    return None


def price_and_change(sym):
    r = klines_15m(sym)
    if not r:
        return None
    src, c = r
    return {"src": src, "price": c[-1], "b4h": (c[-1] / c[-17] - 1) * 100}


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


def status_text(cands):
    if not cands:
        return "Сейчас в канале нет монет, которые висят ≥%g ч." % MIN_RUN_H
    lines = ["Монеты, висящие в канале ≥%g ч (рост за 4ч):" % MIN_RUN_H]
    for c in sorted(cands, key=lambda c: -c["b4h"]):
        flag = "🔻" if PUMP_MIN <= c["b4h"] <= PUMP_MAX else "  "
        lines.append(f"{flag} {c['sym']}: {fmt_run(c)}, {c['b4h']:+.1f}%, фандинг {fmt_funding(c.get('funding'))}")
    return "\n".join(lines)


def signal_text(c):
    bor, rep, br = c["info"]
    return (
        f"🔻 <b>ШОРТ-сигнал: {c['sym']}</b>\n"
        f"Цена: {fmt_price(c['price'])} USDT ({c['src']})\n"
        f"Рост за 4 ч: <b>{c['b4h']:+.1f}%</b>\n"
        f"Фандинг: {fmt_funding(c.get('funding'))}\n"
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
    for sym, r in runs.items():
        if r["run_h"] < MIN_RUN_H:
            continue
        pc = price_and_change(sym)
        if not pc:
            log("нет цены для", sym)
            continue
        c = {"sym": sym, "run_h": r["run_h"], "capped": r["capped"], "info": r["info"], "funding": funding(sym), **pc}
        cands.append(c)
        recent = [a for a in state["alerts"] if a["sym"] == sym and now - a["ts"] < COOLDOWN_H * 3600]
        if PUMP_MIN <= c["b4h"] <= PUMP_MAX and not recent:
            log("СИГНАЛ", sym, f"{c['b4h']:+.1f}%", f"{c['run_h']:.1f}ч")
            broadcast(state, signal_text(c), dry)
            state["alerts"].append({"sym": sym, "ts": now, "price": c["price"], "b4h": c["b4h"], "run_h": c["run_h"],
                                    "funding": (c["funding"] or {}).get("rate")})
            try:
                msg = trader.on_signal(state, sym, c["price"])
            except Exception as e:
                msg = f"❌ {sym}: ошибка исполнителя: {e!r}"
            if msg:
                log(msg.replace("\n", " | "))
                broadcast(state, msg, dry)
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
    save_state(state)
    return cands


def run_loop(dry):
    """Сканирование раз в POLL_SEC, а между ними — длинный опрос Telegram, чтобы кнопки отвечали сразу."""
    state = load_state()
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
            next_scan = time.time() + POLL_SEC
            if MAX_RUNTIME_SEC and time.time() - started + POLL_SEC > MAX_RUNTIME_SEC:
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
