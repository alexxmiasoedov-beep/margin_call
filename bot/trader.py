"""Исполнитель ордеров (BingX USDT-M perpetual). Ключи только из окружения."""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://open-api.bingx.com"
KEY = os.environ.get("BINGX_API_KEY", "")
SECRET = os.environ.get("BINGX_API_SECRET", "")
MODE = os.environ.get("TRADE_MODE", "off").lower()          # off | paper | live
MARGIN_USDT = float(os.environ.get("POSITION_USDT", "50"))   # маржа на сделку
LEVERAGE = int(os.environ.get("LEVERAGE", "2"))
SL_PCT = float(os.environ.get("SL_PCT", "18"))               # стоп: цена выше входа на N %
TP_PCT = float(os.environ.get("TP_PCT", "10"))               # тейк: цена ниже входа на N %
HOLD_H = float(os.environ.get("HOLD_H", "24"))               # принудительный выход через N часов
MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "3"))
DAILY_LOSS_LIMIT_USDT = float(os.environ.get("DAILY_LOSS_LIMIT_USDT", str(MARGIN_USDT * 0.4)))


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "[trader]", *a, flush=True)


# Параметры, которые можно менять из Telegram (/set): имя → (глобальная переменная, тип, минимум, максимум, описание)
PARAMS = {
    "margin": ("MARGIN_USDT", float, 1, 10000, "маржа на сделку, USDT"),
    "lev": ("LEVERAGE", int, 1, 50, "плечо"),
    "tp": ("TP_PCT", float, 0.5, 90, "тейк-профит, % движения цены"),
    "sl": ("SL_PCT", float, 1, 200, "стоп-лосс, % движения цены"),
    "hold": ("HOLD_H", float, 1, 168, "выход по времени, часов"),
    "max": ("MAX_POSITIONS", int, 1, 20, "максимум открытых позиций"),
    "limit": ("DAILY_LOSS_LIMIT_USDT", float, 1, 100000, "дневной лимит убытка, USDT"),
}


def configure(state):
    """Применяет переопределения из state["params"] поверх значений из окружения."""
    for name, val in (state.get("params") or {}).items():
        if name in PARAMS:
            globals()[PARAMS[name][0]] = PARAMS[name][1](val)


def set_param(state, name, value):
    """Меняет параметр из чата. Возвращает текст ответа."""
    name = name.lower()
    if name not in PARAMS:
        return "Неизвестный параметр. Доступны: " + ", ".join(f"{k} ({v[4]})" for k, v in PARAMS.items())
    var, typ, lo, hi, desc = PARAMS[name]
    try:
        v = typ(float(value))
    except ValueError:
        return f"Значение должно быть числом: /set {name} 10"
    if not lo <= v <= hi:
        return f"{desc}: допустимо от {lo:g} до {hi:g}"
    state.setdefault("params", {})[name] = v
    globals()[var] = v
    return f"Ок: {desc} = {v:g}. Действует для новых сделок.\n\n" + params_text()


def params_text():
    return ("Параметры сделок:\n"
            f"  margin — маржа на сделку: {MARGIN_USDT:g} USDT\n"
            f"  lev — плечо: {LEVERAGE}x (номинал {MARGIN_USDT * LEVERAGE:g} USDT)\n"
            f"  tp — тейк-профит: −{TP_PCT:g}% цены ({TP_PCT * LEVERAGE:g}% к марже)\n"
            f"  sl — стоп-лосс: +{SL_PCT:g}% цены ({SL_PCT * LEVERAGE:g}% к марже)\n"
            f"  hold — выход по времени: {HOLD_H:g} ч\n"
            f"  max — максимум позиций: {MAX_POSITIONS}\n"
            f"  limit — дневной лимит убытка: {DAILY_LOSS_LIMIT_USDT:g} USDT\n"
            "Изменить: /set margin 7, /set lev 10, /set tp 8, /set sl 18")


# ------------------------------------------------------------------ API
def _sign(params):
    """Подпись BingX считается по сырой строке k=v&k=v (ключи по алфавиту, значения без кодирования)."""
    raw = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _request(method, path, params=None, signed=True):
    params = dict(params or {})
    if signed:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 10000
        sig = _sign(params)
        # в URL значения обязательно кодируем: в stopLoss/takeProfit лежит JSON с кавычками
        qs = "&".join(f"{k}={urllib.parse.quote(str(params[k]), safe='')}" for k in sorted(params))
        qs += "&signature=" + sig
    else:
        qs = urllib.parse.urlencode(params)
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(url, method=method, headers={"X-BX-APIKEY": KEY, "User-Agent": "margin-call"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode())
        except Exception:
            j = {"code": e.code, "msg": str(e)}
    except Exception as e:
        j = {"code": -1, "msg": repr(e)}
    if j.get("code") not in (0, None):
        log("API error", method, path, j.get("code"), j.get("msg"))
    return j


_contracts = {}


def contract(sym):
    """Параметры контракта SYM-USDT или None, если контракта нет."""
    if not _contracts:
        j = _request("GET", "/openApi/swap/v2/quote/contracts", signed=False)
        for c in j.get("data") or []:
            _contracts[c["symbol"]] = c
    return _contracts.get(f"{sym}-USDT")


def mark_price(sym):
    j = _request("GET", "/openApi/swap/v2/quote/price", {"symbol": f"{sym}-USDT"}, signed=False)
    try:
        return float(j["data"]["price"])
    except Exception:
        return None


def balance():
    j = _request("GET", "/openApi/swap/v2/user/balance")
    try:
        b = j["data"]["balance"]
        return {"asset": b["asset"], "balance": float(b["balance"]), "available": float(b["availableMargin"])}
    except Exception:
        return None


def hedge_mode():
    j = _request("GET", "/openApi/swap/v1/positionSide/dual")
    try:
        return str(j["data"]["dualSidePosition"]).lower() == "true"
    except Exception:
        return True


def position(sym):
    j = _request("GET", "/openApi/swap/v2/user/positions", {"symbol": f"{sym}-USDT"})
    for p in j.get("data") or []:
        if p.get("positionSide") in ("SHORT", "BOTH") and float(p.get("positionAmt", 0)) != 0:
            return p
    return None


def positions_text():
    """Реальные открытые позиции на BingX (все контракты)."""
    if not KEY or not SECRET:
        return "BingX: ключи не заданы"
    j = _request("GET", "/openApi/swap/v2/user/positions")
    if j.get("code") not in (0, None):
        return f"BingX: не удалось получить позиции ({j.get('msg')})"
    rows = [p for p in (j.get("data") or []) if float(p.get("positionAmt", 0) or 0) != 0]
    if not rows:
        return "На BingX открытых позиций нет."
    lines = ["Открытые позиции на BingX:"]
    for p in rows:
        try:
            amt = float(p["positionAmt"]); entry = float(p.get("avgPrice") or 0); mark = float(p.get("markPrice") or 0)
            upnl = float(p.get("unrealizedProfit") or 0); margin = float(p.get("initialMargin") or p.get("margin") or 0)
            pct = f" ({upnl / margin * 100:+.1f}% к марже)" if margin else ""
            lines.append(f"  {p['symbol']} {p.get('positionSide')} {abs(amt):g} шт, вход {entry:.6g}, сейчас {mark:.6g}, "
                         f"плечо {p.get('leverage')}x, PnL {upnl:+.2f} USDT{pct}")
        except (KeyError, ValueError, TypeError):
            lines.append(f"  {p.get('symbol')}: {p}")
    return "\n".join(lines)


def _round(x, prec):
    return f"{x:.{int(prec)}f}"


def qty_for(sym, price):
    c = contract(sym)
    if not c or not price:
        return None
    notional = MARGIN_USDT * LEVERAGE
    q = notional / price
    prec = int(c.get("quantityPrecision", 0))
    q = float(_round(q, prec))
    if q < float(c.get("tradeMinQuantity", 0)):
        return None
    return q


def live_open_short(sym, price):
    c = contract(sym)
    hedge = hedge_mode()
    pside = "SHORT" if hedge else "BOTH"
    _request("POST", "/openApi/swap/v2/trade/marginType", {"symbol": f"{sym}-USDT", "marginType": "CROSSED"})
    _request("POST", "/openApi/swap/v2/trade/leverage",
             {"symbol": f"{sym}-USDT", "side": "SHORT" if hedge else "BOTH", "leverage": LEVERAGE})
    q = qty_for(sym, price)
    if not q:
        return None, "объём меньше минимального для контракта"
    pp = int(c.get("pricePrecision", 4))
    sl = _round(price * (1 + SL_PCT / 100), pp)
    tp = _round(price * (1 - TP_PCT / 100), pp)
    params = {
        "symbol": f"{sym}-USDT", "side": "SELL", "positionSide": pside, "type": "MARKET", "quantity": q,
        "stopLoss": json.dumps({"type": "STOP_MARKET", "stopPrice": float(sl), "workingType": "MARK_PRICE"},
                               separators=(",", ":")),
        "takeProfit": json.dumps({"type": "TAKE_PROFIT_MARKET", "stopPrice": float(tp), "workingType": "MARK_PRICE"},
                                 separators=(",", ":")),
    }
    j = _request("POST", "/openApi/swap/v2/trade/order", params)
    if j.get("code") != 0:
        return None, f"ордер отклонён: {j.get('msg')}"
    order = (j.get("data") or {}).get("order") or {}
    return {"qty": q, "sl": float(sl), "tp": float(tp), "order_id": order.get("orderId"), "pside": pside}, None


def live_close_short(sym, qty, pside):
    params = {"symbol": f"{sym}-USDT", "side": "BUY", "positionSide": pside, "type": "MARKET", "quantity": qty}
    if pside == "BOTH":
        params["reduceOnly"] = "true"
    j = _request("POST", "/openApi/swap/v2/trade/order", params)
    return j.get("code") == 0, j.get("msg")


# ------------------------------------------------------------------ логика сделок
def _day(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _today_pnl(state):
    day = _day(time.time())
    return sum(t.get("pnl_usdt", 0) for t in state["trades"] if t.get("closed") and _day(t["closed"]) == day)


def open_trades(state):
    return [t for t in state["trades"] if not t.get("closed")]


def on_signal(state, sym, price_hint):
    """Вызывается сканером при сигнале. Возвращает текст для чата или None."""
    if MODE == "off":
        return None
    state.setdefault("trades", [])
    if state.get("trading_paused"):
        return f"⏸ {sym}: торговля на паузе (дневной лимит убытка или /pause), сделка не открыта"
    if len(open_trades(state)) >= MAX_POSITIONS:
        return f"⚠️ {sym}: уже {MAX_POSITIONS} открытых позиций, сделка не открыта"
    if any(t["sym"] == sym for t in open_trades(state)):
        return None
    if not contract(sym):
        return f"⚠️ {sym}: на BingX нет бессрочного контракта, сделка не открыта"
    price = mark_price(sym) or price_hint
    if not price:
        return f"⚠️ {sym}: не удалось получить цену BingX, сделка не открыта"
    t = {"sym": sym, "opened": time.time(), "entry": price, "mode": MODE, "margin": MARGIN_USDT, "lev": LEVERAGE,
         "sl": price * (1 + SL_PCT / 100), "tp": price * (1 - TP_PCT / 100)}
    if MODE == "live":
        res, err = live_open_short(sym, price)
        if err:
            return f"❌ {sym}: {err}"
        t.update(res)
    else:
        t["qty"] = qty_for(sym, price) or (MARGIN_USDT * LEVERAGE / price)
    state["trades"].append(t)
    tag = "📝 БУМАЖНАЯ" if MODE == "paper" else "💰 РЕАЛЬНАЯ"
    return (f"{tag} сделка: шорт {sym} по {price:.6g}\n"
            f"маржа {MARGIN_USDT:g} USDT × {LEVERAGE}x, стоп {t['sl']:.6g} (+{SL_PCT:g}%), "
            f"тейк {t['tp']:.6g} (−{TP_PCT:g}%), выход не позже чем через {HOLD_H:g} ч")


def _close(state, t, price, reason):
    t["closed"] = time.time()
    t["exit"] = price
    t["reason"] = reason
    pnl_pct = (t["entry"] / price - 1) * 100 * t["lev"]      # шорт: прибыль при падении, к марже с плечом
    t["pnl_pct"] = pnl_pct
    t["pnl_usdt"] = t["margin"] * pnl_pct / 100
    mark = "✅" if pnl_pct > 0 else "❌"
    return (f"{mark} закрыт шорт {t['sym']} ({t['mode']}): {reason}, вход {t['entry']:.6g} → выход {price:.6g}, "
            f"PnL {pnl_pct:+.1f}% к марже ({t['pnl_usdt']:+.2f} USDT)")


def manage(state):
    """Каждый цикл: стопы/тейки/выход по времени. Возвращает список сообщений для чата."""
    msgs = []
    if MODE == "off":
        return msgs
    state.setdefault("trades", [])
    now = time.time()
    for t in open_trades(state):
        sym = t["sym"]
        price = mark_price(sym)
        if not price:
            continue
        if t["mode"] == "live":
            pos = position(sym)
            if pos is None:
                # позицию закрыла биржа (стоп, тейк или ликвидация) — определяем по цене
                if price > t["entry"]:
                    msgs.append(_close(state, t, min(price, t["sl"]), "стоп-лосс / ликвидация на бирже"))
                else:
                    msgs.append(_close(state, t, max(price, t["tp"]), "тейк-профит на бирже"))
                continue
            if now - t["opened"] >= HOLD_H * 3600:
                ok, msg = live_close_short(sym, t["qty"], t.get("pside", "SHORT"))
                if ok:
                    msgs.append(_close(state, t, price, f"выход по времени ({HOLD_H:g} ч)"))
                else:
                    msgs.append(f"❌ {sym}: не удалось закрыть по времени: {msg}")
        else:
            if price >= t["sl"]:
                msgs.append(_close(state, t, t["sl"], "стоп-лосс"))
            elif price <= t["tp"]:
                msgs.append(_close(state, t, t["tp"], "тейк-профит"))
            elif now - t["opened"] >= HOLD_H * 3600:
                msgs.append(_close(state, t, price, f"выход по времени ({HOLD_H:g} ч)"))
    if _today_pnl(state) <= -DAILY_LOSS_LIMIT_USDT and not state.get("trading_paused"):
        state["trading_paused"] = True
        msgs.append(f"⏸ Дневной убыток {_today_pnl(state):+.2f} USDT достиг лимита {DAILY_LOSS_LIMIT_USDT:g} USDT — "
                    "торговля на паузе. /resume — продолжить.")
    state["trades"] = [t for t in state["trades"] if not t.get("closed") or now - t["closed"] < 30 * 86400]
    return msgs


def summary(state):
    state.setdefault("trades", [])
    ot = open_trades(state)
    closed = [t for t in state["trades"] if t.get("closed")]
    lines = [f"Режим: {MODE}, маржа {MARGIN_USDT:g} USDT × {LEVERAGE}x, стоп +{SL_PCT:g}%, тейк −{TP_PCT:g}%, "
             f"выход {HOLD_H:g} ч" + (" — НА ПАУЗЕ" if state.get("trading_paused") else "")]
    if MODE != "off":
        b = balance() if KEY and SECRET else None
        lines.append(f"BingX: баланс {b['balance']:.2f} {b['asset']}, доступно {b['available']:.2f}" if b
                     else "BingX: ключи не подошли или не заданы — реальные ордера невозможны")
        if MODE == "live":
            lines.append(positions_text())
    if ot:
        lines.append("Открытые:")
        for t in ot:
            p = mark_price(t["sym"])
            cur = f", сейчас {p:.6g} ({(t['entry'] / p - 1) * 100 * t['lev']:+.1f}% к марже)" if p else ""
            lines.append(f"  {t['sym']} шорт по {t['entry']:.6g}, {(time.time() - t['opened']) / 3600:.1f} ч{cur}")
    else:
        lines.append("Открытых позиций нет.")
    if closed:
        wins = sum(1 for t in closed if t["pnl_pct"] > 0)
        tot = sum(t["pnl_usdt"] for t in closed)
        lines.append(f"Закрытых за 30 дней: {len(closed)}, прибыльных {wins}, итог {tot:+.2f} USDT")
        for t in closed[-5:]:
            lines.append(f"  {t['sym']}: {t['reason']}, {t['pnl_pct']:+.1f}%")
    return "\n".join(lines)


def startup_check():
    """Проверка ключей на старте: запрос баланса. Возвращает строку для лога."""
    if MODE == "off":
        return "торговля выключена (TRADE_MODE=off)"
    if not KEY or not SECRET:
        return "BINGX_API_KEY/SECRET не заданы — торговля невозможна"
    b = balance()
    if not b:
        return "BingX: ключи не подошли или API недоступен"
    return f"BingX OK: баланс {b['balance']:.2f} {b['asset']}, доступно {b['available']:.2f}; режим {MODE}"
