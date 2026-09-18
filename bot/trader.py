"""Исполнитель ордеров (Binance USDT-M perpetual). Ключи только из окружения."""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://fapi.binance.com"
KEY = os.environ.get("BINANCE_API_KEY", "")
SECRET = os.environ.get("BINANCE_API_SECRET", "")
MODE = os.environ.get("TRADE_MODE", "off").lower()          # off | paper | live
MARGIN_USDT = float(os.environ.get("POSITION_USDT", "50"))   # маржа на сделку
LEVERAGE = int(os.environ.get("LEVERAGE", "2"))
SL_PCT = float(os.environ.get("SL_PCT", "18"))               # стоп: цена выше входа на N %
TP_PCT = float(os.environ.get("TP_PCT", "10"))               # тейк: цена ниже входа на N %
HOLD_H = float(os.environ.get("HOLD_H", "24"))               # принудительный выход через N часов
MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "0"))    # 0 = без ограничения, ограничивает только баланс
DAILY_LOSS_LIMIT_USDT = float(os.environ.get("DAILY_LOSS_LIMIT_USDT", str(MARGIN_USDT * 0.4)))
LSR_MAX = float(os.environ.get("LSR_MAX", "1.1"))            # не входить, если LSR тейкеров >= этого (0 = фильтр выключен)
DUMP_RULE = int(os.environ.get("DUMP_RULE", "1"))            # правило 2: шорт после падения 8–17% за 4 ч в серии (1 = вкл.)
DUMP_BR_MIN = float(os.environ.get("DUMP_BR_MIN", "5"))      # правило 2 только при B/R >= этого


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "[trader]", *a, flush=True)


# Параметры, которые можно менять из Telegram (/set): имя → (глобальная переменная, тип, минимум, максимум, описание)
PARAMS = {
    "margin": ("MARGIN_USDT", float, 1, 10000, "маржа на сделку, USDT"),
    "lev": ("LEVERAGE", int, 1, 50, "плечо"),
    "tp": ("TP_PCT", float, 0.5, 90, "тейк-профит, % движения цены"),
    "sl": ("SL_PCT", float, 1, 200, "стоп-лосс, % движения цены"),
    "hold": ("HOLD_H", float, 1, 168, "выход по времени, часов"),
    "max": ("MAX_POSITIONS", int, 0, 100, "максимум открытых позиций (0 = без лимита)"),
    "limit": ("DAILY_LOSS_LIMIT_USDT", float, 1, 100000, "дневной лимит убытка, USDT"),
    "lsr": ("LSR_MAX", float, 0, 100, "порог LSR тейкеров (вход только ниже; 0 = выкл.)"),
    "dump": ("DUMP_RULE", int, 0, 1, "правило 2 — шорт после падения 8–17% (1 = вкл., 0 = выкл.)"),
    "br": ("DUMP_BR_MIN", float, 0, 1000000, "мин. B/R для правила 2"),
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
            f"  max — максимум позиций: {MAX_POSITIONS if MAX_POSITIONS > 0 else 'без лимита (0)'}\n"
            f"  limit — дневной лимит убытка: {DAILY_LOSS_LIMIT_USDT:g} USDT\n"
            f"  lsr — фильтр тейкеров: вход только при LSR < {LSR_MAX:g}" + (" (выключен)" if LSR_MAX <= 0 else "") + "\n"
            f"  dump — правило 2 (шорт после падения 8–17% в серии): {'включено' if DUMP_RULE else 'выключено'}\n"
            f"  br — правило 2 только при B/R ≥ {DUMP_BR_MIN:g}\n"
            "Изменить: /set margin 7, /set lev 10, /set tp 8, /set sl 18, /set lsr 1.1, /set dump 0, /set br 5")


# ------------------------------------------------------------------ API
_time_offset = 0   # серверное время Binance минус локальное, мс


def sync_time():
    """Сверяет часы с Binance, чтобы подписанные запросы не отбрасывались по recvWindow."""
    global _time_offset
    j = _request("GET", "/fapi/v1/time", signed=False)
    try:
        _time_offset = int(j["serverTime"]) - int(time.time() * 1000)
        log(f"часы: смещение относительно Binance {_time_offset:+d} мс")
    except (KeyError, TypeError, ValueError):
        pass


def _request(method, path, params=None, signed=True, _retry=True):
    """Binance USDT-M futures. Ошибка — dict с отрицательным code; успех может быть list, dict или {"code": 200}."""
    params = dict(params or {})
    qs = urllib.parse.urlencode(params)
    if signed:
        params["timestamp"] = int(time.time() * 1000) + _time_offset
        params["recvWindow"] = 20000
        qs = urllib.parse.urlencode(params)
        qs += "&signature=" + hmac.new(SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, method=method, headers={"X-MBX-APIKEY": KEY, "User-Agent": "margin-call"})
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
    if _err(j):
        log("API error", method, path, j.get("code"), j.get("msg"))
        if signed and _retry and j.get("code") == -1021:      # часы разошлись — сверяем и повторяем один раз
            sync_time()
            return _request(method, path, params={k: v for k, v in params.items() if k not in ("timestamp", "recvWindow")},
                            signed=True, _retry=False)
    return j


def _err(j):
    """Текст ошибки Binance или None. Успех: list, либо dict без code, либо code 200."""
    if isinstance(j, dict) and j.get("code") not in (None, 200):
        return j.get("msg") or str(j.get("code"))
    return None


_contracts = {}


def contract(sym):
    """Параметры контракта SYMUSDT или None, если бессрочного контракта нет."""
    if not _contracts:
        j = _request("GET", "/fapi/v1/exchangeInfo", signed=False)
        for c in (j.get("symbols") or []) if isinstance(j, dict) else []:
            if c.get("contractType") == "PERPETUAL" and c.get("status") == "TRADING" and c.get("quoteAsset") == "USDT":
                f = {x["filterType"]: x for x in c.get("filters", [])}
                _contracts[c["symbol"]] = {
                    "quantityPrecision": int(c.get("quantityPrecision", 0)),
                    "pricePrecision": int(c.get("pricePrecision", 4)),
                    "tickSize": float(f.get("PRICE_FILTER", {}).get("tickSize", 0) or 0),
                    "minQty": float(f.get("LOT_SIZE", {}).get("minQty", 0) or 0),
                    "minNotional": float(f.get("MIN_NOTIONAL", {}).get("notional", 0) or 0),
                }
    return _contracts.get(f"{sym}USDT")


def mark_price(sym):
    j = _request("GET", "/fapi/v1/premiumIndex", {"symbol": f"{sym}USDT"}, signed=False)
    try:
        return float(j["markPrice"])
    except Exception:
        return None


def taker_lsr(sym):
    """Соотношение объёмов тейкеров покупка/продажа за последний завершённый час: >1 — агрессивно покупают.
    Binance (takerlongshortRatio), резерв — Gate (lsr_taker). None, если данных нет."""
    j = _request("GET", "/futures/data/takerlongshortRatio", {"symbol": f"{sym}USDT", "period": "1h", "limit": 1},
                 signed=False)
    try:
        if isinstance(j, list) and j:
            return float(j[-1]["buySellRatio"])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        u = f"https://api.gateio.ws/api/v4/futures/usdt/contract_stats?contract={sym}_USDT&interval=1h&limit=1"
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "margin-call"}), timeout=15) as r:
            g = json.loads(r.read().decode())
        if isinstance(g, list) and g and g[0].get("lsr_taker") is not None:
            return float(g[0]["lsr_taker"])
    except Exception:
        pass
    return None


def balance():
    j = _request("GET", "/fapi/v2/balance")
    if isinstance(j, list):
        for b in j:
            if b.get("asset") == "USDT":
                return {"asset": "USDT", "balance": float(b["balance"]), "available": float(b["availableBalance"])}
    return None


def hedge_mode():
    j = _request("GET", "/fapi/v1/positionSide/dual")
    try:
        return str(j["dualSidePosition"]).lower() == "true"
    except Exception:
        return False


def position(sym):
    """Открытая позиция по контракту: dict; None — позиции нет; False — запрос не удался (НЕ значит, что закрыта)."""
    j = _request("GET", "/fapi/v2/positionRisk", {"symbol": f"{sym}USDT"})
    if not isinstance(j, list):
        return False
    for p in j:
        if p.get("positionSide") in ("SHORT", "BOTH") and float(p.get("positionAmt", 0)) != 0:
            return p
    return None


def all_short_positions():
    """Все открытые шорты на бирже: {SYM: позиция} или None, если запрос не удался."""
    j = _request("GET", "/fapi/v2/positionRisk")
    if not isinstance(j, list):
        return None
    out = {}
    for p in j:
        try:
            amt = float(p.get("positionAmt") or 0)
        except (TypeError, ValueError):
            continue
        s = str(p.get("symbol", ""))
        if amt < 0 and p.get("positionSide") in ("SHORT", "BOTH") and s.endswith("USDT"):
            out[s[:-4]] = p
    return out


def realized(sym, since_ts):
    """Фактический результат по контракту с момента since_ts по данным Binance:
    {"pnl": реализованный PnL, "fee": комиссии, "funding": фандинг} в USDT или None."""
    j = _request("GET", "/fapi/v1/income",
                 {"symbol": f"{sym}USDT", "startTime": int(since_ts * 1000), "limit": 1000})
    if not isinstance(j, list):
        return None
    out = {"pnl": 0.0, "fee": 0.0, "funding": 0.0, "types": set()}
    for r in j:
        try:
            t, v = str(r.get("incomeType", "")).upper(), float(r.get("income", 0))
        except (TypeError, ValueError):
            continue
        out["types"].add(t)
        if "REALIZED" in t or "ADL" in t or "DELEVERAG" in t or "LIQUIDAT" in t or "INSURANCE" in t:
            out["pnl"] += v
        elif "COMMISSION" in t or ("FEE" in t and "FUNDING" not in t):
            out["fee"] += v
        elif "FUNDING" in t:
            out["funding"] += v
    out["types"] = ", ".join(sorted(out["types"]))
    return out


def history_text(sym, hours=24):
    """Ордера и записи счёта по контракту за последние hours часов — чтобы видеть, чем закрылась позиция."""
    if not KEY or not SECRET:
        return "Binance: ключи не заданы"
    since = int((time.time() - hours * 3600) * 1000)
    lines = [f"История {sym}USDT за {hours} ч (UTC):"]
    j = _request("GET", "/fapi/v1/allOrders", {"symbol": f"{sym}USDT", "startTime": since, "limit": 50})
    if not isinstance(j, list):
        lines.append(f"  ордера: не удалось получить ({_err(j)})")
    elif not j:
        lines.append("  ордеров нет")
    else:
        lines.append("Ордера:")
        for o in sorted(j, key=lambda o: int(o.get("updateTime") or o.get("time") or 0)):
            ts = time.strftime("%d.%m %H:%M:%S", time.gmtime(int(o.get("updateTime") or o.get("time") or 0) / 1000))
            extra = []
            if o.get("stopPrice") not in (None, "", "0", 0):
                extra.append(f"триггер {o['stopPrice']}")
            if o.get("workingType"):
                extra.append(str(o["workingType"]))
            if str(o.get("reduceOnly")).lower() == "true" or str(o.get("closePosition")).lower() == "true":
                extra.append("reduceOnly")
            lines.append(f"  {ts} {o.get('type')} {o.get('side')}/{o.get('positionSide')} {o.get('status')}: "
                         f"объём {o.get('executedQty')}/{o.get('origQty')}, ср. цена {o.get('avgPrice')}"
                         + (f" ({', '.join(extra)})" if extra else "") + f", id {o.get('orderId')}")
    j = _request("GET", "/fapi/v1/allAlgoOrders", {"symbol": f"{sym}USDT", "startTime": since})
    rows = (j.get("orders") if isinstance(j, dict) else j) or []
    if rows:
        lines.append("Условные ордера (стопы/тейки):")
        for o in rows:
            lines.append(f"  algoId {o.get('algoId')} {o.get('side')}: триггер {o.get('triggerPrice')} "
                         f"({o.get('workingType')}), статус {o.get('algoStatus')}")
    j = _request("GET", "/fapi/v1/income", {"symbol": f"{sym}USDT", "startTime": since, "limit": 100})
    if isinstance(j, list) and j:
        lines.append("Записи счёта:")
        for r in sorted(j, key=lambda r: int(r.get("time") or 0)):
            ts = time.strftime("%d.%m %H:%M:%S", time.gmtime(int(r.get("time") or 0) / 1000))
            lines.append(f"  {ts} {r.get('incomeType')}: {r.get('income')} {r.get('asset', '')} {r.get('info', '') or ''}")
    elif isinstance(j, list):
        lines.append("Записей счёта нет")
    else:
        lines.append(f"Записи счёта: не удалось получить ({_err(j)})")
    text = "\n".join(lines)
    return text if len(text) < 3900 else text[:3850] + "\n…(обрезано)"


def positions_text():
    """Реальные открытые позиции на Binance (все контракты)."""
    if not KEY or not SECRET:
        return "Binance: ключи не заданы"
    j = _request("GET", "/fapi/v2/positionRisk")
    if not isinstance(j, list):
        return f"Binance: не удалось получить позиции ({_err(j)})"
    rows = [p for p in j if float(p.get("positionAmt", 0) or 0) != 0]
    if not rows:
        return "На Binance открытых позиций нет."
    lines = ["Открытые позиции на Binance:"]
    for p in rows:
        try:
            amt = float(p["positionAmt"]); entry = float(p.get("entryPrice") or 0); mark = float(p.get("markPrice") or 0)
            upnl = float(p.get("unRealizedProfit") or 0); lev = int(float(p.get("leverage") or 0) or 1)
            margin = abs(float(p.get("notional") or 0)) / lev if lev else 0
            pct = f" ({upnl / margin * 100:+.1f}% к марже)" if margin else ""
            lines.append(f"  {p['symbol']} {p.get('positionSide')} {abs(amt):g} шт, вход {entry:.6g}, сейчас {mark:.6g}, "
                         f"плечо {lev}x, PnL {upnl:+.2f} USDT{pct}")
        except (KeyError, ValueError, TypeError):
            lines.append(f"  {p.get('symbol')}: {p}")
    return "\n".join(lines)


def _round(x, prec):
    return f"{x:.{int(prec)}f}"


def _round_price(c, price):
    """Цена, кратная шагу tickSize, в строковом виде с точностью контракта."""
    if not c:
        return float(f"{price:.6g}")
    tick = c.get("tickSize") or 0
    if tick:
        price = round(price / tick) * tick
    return float(_round(price, c.get("pricePrecision", 4)))


def qty_for(sym, price):
    c = contract(sym)
    if not c or not price:
        return None
    notional = MARGIN_USDT * LEVERAGE
    q = notional / price
    step = 10 ** c["quantityPrecision"]
    q = int(q * step) / step  # вниз, чтобы номинал не превысил маржу × плечо
    if q < c["minQty"] or q * price < c["minNotional"]:
        return None
    return q


def fill_price(sym, order_id, fallback):
    """Фактическая средняя цена исполнения ордера (по ордеру, затем по позиции), иначе fallback."""
    for _ in range(3):
        j = _request("GET", "/fapi/v1/order", {"symbol": f"{sym}USDT", "orderId": order_id})
        try:
            p = float(j.get("avgPrice") or 0)
            if p > 0:
                return p
        except (TypeError, ValueError):
            pass
        time.sleep(1)
    pos = position(sym)
    try:
        p = float((pos or {}).get("entryPrice") or 0)
        if p > 0:
            return p
    except (TypeError, ValueError):
        pass
    return fallback


def cancel_orders(sym):
    """Снимает все открытые ордера по контракту: обычные и условные (algo — стопы/тейки)."""
    j = _request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": f"{sym}USDT"})
    ja = _request("DELETE", "/fapi/v1/algoOpenOrders", {"symbol": f"{sym}USDT"})
    return not _err(j) and not _err(ja)


def live_open_short(sym, price):
    """Рыночный шорт; стоп и тейк ставятся отдельными ордерами от ФАКТИЧЕСКОЙ цены исполнения."""
    c = contract(sym)
    hedge = hedge_mode()
    pside = "SHORT" if hedge else "BOTH"
    # -4046 "No need to change margin type" — не ошибка
    _request("POST", "/fapi/v1/marginType", {"symbol": f"{sym}USDT", "marginType": "CROSSED"})
    _request("POST", "/fapi/v1/leverage", {"symbol": f"{sym}USDT", "leverage": LEVERAGE})
    q = qty_for(sym, price)
    if not q:
        return None, "объём меньше минимального для контракта"
    j = _request("POST", "/fapi/v1/order",
                 {"symbol": f"{sym}USDT", "side": "SELL", "positionSide": pside, "type": "MARKET",
                  "quantity": q, "newOrderRespType": "RESULT"})
    if _err(j):
        return None, f"ордер отклонён: {_err(j)}"
    try:
        fill = float(j.get("avgPrice") or 0)
    except (TypeError, ValueError):
        fill = 0
    if not fill:
        fill = fill_price(sym, j.get("orderId"), price)
    prot = place_protection(sym, fill, pside)
    res = {"qty": q, "order_id": j.get("orderId"), "pside": pside, "quote": price, "entry": fill, **prot}
    return res, None


def place_protection(sym, entry, pside):
    """Ставит стоп и тейк от цены entry по текущим SL_PCT/TP_PCT. Возвращает {sl, tp, sl_order_id, tp_order_id, warn}."""
    c = contract(sym)
    sl = _round_price(c, entry * (1 + SL_PCT / 100))
    tp = _round_price(c, entry * (1 - TP_PCT / 100))
    # условные ордера с 12.2025 идут через Algo API (/fapi/v1/algoOrder, триггер — triggerPrice);
    # closePosition=true — закрыть всю позицию по срабатыванию, объём не нужен
    close_side = {"algoType": "CONDITIONAL", "symbol": f"{sym}USDT", "side": "BUY", "positionSide": pside,
                  "closePosition": "true"}
    # стоп — по марк-цене (защита от одиночных проколов), тейк — по цене сделок, как и вход
    js = _request("POST", "/fapi/v1/algoOrder",
                  {**close_side, "type": "STOP_MARKET", "triggerPrice": sl, "workingType": "MARK_PRICE"})
    jt = _request("POST", "/fapi/v1/algoOrder",
                  {**close_side, "type": "TAKE_PROFIT_MARKET", "triggerPrice": tp, "workingType": "CONTRACT_PRICE"})
    warn = []
    if _err(js):
        warn.append(f"стоп не установлен: {_err(js)}")
    if _err(jt):
        warn.append(f"тейк не установлен: {_err(jt)}")
    return {"sl": sl, "tp": tp, "sl_order_id": js.get("algoId"), "tp_order_id": jt.get("algoId"), "warn": "; ".join(warn)}


def adopt_positions(state, allpos):
    """Шорты, которые есть на бирже, но не в журнале бота (забытые после сбоя или открытые вручную):
    берём под управление — заново ставим стоп/тейк и включаем выход по времени."""
    msgs = []
    known = {t["sym"] for t in open_trades(state)}
    for sym, p in allpos.items():
        if sym in known:
            continue
        try:
            entry = float(p.get("entryPrice") or 0); qty = abs(float(p.get("positionAmt") or 0))
            lev = int(float(p.get("leverage") or 0) or LEVERAGE)
            margin = abs(float(p.get("notional") or 0)) / lev if lev else MARGIN_USDT
            opened = int(p.get("updateTime") or 0) / 1000 or time.time()
        except (TypeError, ValueError):
            continue
        if not entry or not qty:
            continue
        pside = p.get("positionSide") or "BOTH"
        cancel_orders(sym)
        prot = place_protection(sym, entry, pside)
        t = {"sym": sym, "opened": opened, "entry": entry, "mode": "live", "margin": round(margin, 4) or MARGIN_USDT,
             "lev": lev, "qty": qty, "pside": pside, "adopted": True, "rule": "adopted", **prot}
        state["trades"].append(t)
        warn = f"\n⚠️ {t['warn']}" if t.get("warn") else ""
        msgs.append(f"🔁 {sym}: на бирже есть шорт, которого нет в журнале бота — беру под управление. "
                    f"Вход {entry:.6g}, объём {qty:g}, открыт {time.strftime('%d.%m %H:%M', time.gmtime(opened))} UTC. "
                    f"Стоп {t['sl']:.6g} (+{SL_PCT:g}%), тейк {t['tp']:.6g} (−{TP_PCT:g}%), выход по времени через {HOLD_H:g} ч от открытия{warn}")
    return msgs


def live_close_short(sym, qty, pside):
    cancel_orders(sym)
    params = {"symbol": f"{sym}USDT", "side": "BUY", "positionSide": pside, "type": "MARKET", "quantity": qty}
    if pside == "BOTH":
        params["reduceOnly"] = "true"
    j = _request("POST", "/fapi/v1/order", params)
    return not _err(j), _err(j)


# ------------------------------------------------------------------ логика сделок
def _day(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _today_pnl(state):
    day = _day(time.time())
    return sum(t.get("pnl_usdt", 0) for t in state["trades"] if t.get("closed") and _day(t["closed"]) == day)


def open_trades(state):
    return [t for t in state["trades"] if not t.get("closed")]


def on_signal(state, sym, price_hint, lsr=None, rule="pump"):
    """Вызывается сканером при сигнале (rule: pump — памп, dump — падение). Возвращает текст для чата или None."""
    if MODE == "off":
        return None
    state.setdefault("trades", [])
    if state.get("trading_paused"):
        return f"⏸ {sym}: торговля на паузе (дневной лимит убытка или /pause), сделка не открыта"
    if MAX_POSITIONS > 0 and len(open_trades(state)) >= MAX_POSITIONS:
        return f"⚠️ {sym}: уже {MAX_POSITIONS} открытых позиций, сделка не открыта"
    if any(t["sym"] == sym for t in open_trades(state)):
        return None
    if not contract(sym):
        return f"⚠️ {sym}: на Binance нет бессрочного контракта, сделка не открыта"
    lsr_note = ""
    if LSR_MAX > 0:
        if lsr is None:
            lsr = taker_lsr(sym)
        if lsr is None:
            lsr_note = "\nLSR тейкеров: нет данных, фильтр пропущен"
        elif lsr >= LSR_MAX:
            state.setdefault("skipped", []).append({"sym": sym, "ts": time.time(), "lsr": lsr, "price": price_hint})
            state["skipped"] = state["skipped"][-200:]
            return (f"⏭ {sym}: сделка не открыта — LSR тейкеров {lsr:.2f} ≥ {LSR_MAX:g}, "
                    "покупатели ещё давят по рынку (в такой группе за полгода 25% стопов и минус по итогу)")
        else:
            lsr_note = f"\nLSR тейкеров: {lsr:.2f} (порог {LSR_MAX:g})"
    price = mark_price(sym) or price_hint
    if not price:
        return f"⚠️ {sym}: не удалось получить цену Binance, сделка не открыта"
    t = {"sym": sym, "opened": time.time(), "entry": price, "mode": MODE, "margin": MARGIN_USDT, "lev": LEVERAGE,
         "sl": price * (1 + SL_PCT / 100), "tp": price * (1 - TP_PCT / 100), "lsr": lsr, "rule": rule}
    if MODE == "live":
        res, err = live_open_short(sym, price)
        if err:
            return f"❌ {sym}: {err}"
        t.update(res)
    else:
        t["qty"] = qty_for(sym, price) or (MARGIN_USDT * LEVERAGE / price)
    state["trades"].append(t)
    tag = "📝 БУМАЖНАЯ" if MODE == "paper" else "💰 РЕАЛЬНАЯ"
    note = ""
    if t.get("quote") and abs(t["entry"] / t["quote"] - 1) > 0.0005:
        note = f" (котировка была {t['quote']:.6g}, проскальзывание {(t['entry'] / t['quote'] - 1) * 100:+.2f}%)"
    warn = f"\n⚠️ {t['warn']}" if t.get("warn") else ""
    kind = " (правило 2, после падения)" if rule == "dump" else ""
    return (f"{tag} сделка: шорт {sym} по {t['entry']:.6g}{note}{kind}\n"
            f"маржа {MARGIN_USDT:g} USDT × {LEVERAGE}x, стоп {t['sl']:.6g} (+{SL_PCT:g}% от входа), "
            f"тейк {t['tp']:.6g} (−{TP_PCT:g}% от входа), выход не позже чем через {HOLD_H:g} ч{lsr_note}{warn}")


def _close(state, t, price, reason):
    t["closed"] = time.time()
    t["exit"] = price
    t["reason"] = reason
    pnl_pct = (t["entry"] / price - 1) * 100 * t["lev"]      # шорт: прибыль при падении, к марже с плечом
    t["pnl_pct"] = pnl_pct
    t["pnl_usdt"] = t["margin"] * pnl_pct / 100
    extra = ""
    if t["mode"] == "live":
        r = realized(t["sym"], t["opened"] - 60)
        if r and (r["pnl"] or r["fee"] or r["funding"]):
            net = r["pnl"] + r["fee"] + r["funding"]
            t["pnl_usdt"] = net
            t["pnl_pct"] = net / t["margin"] * 100
            extra = (f"\nПо данным биржи: PnL {r['pnl']:+.2f}, комиссии {r['fee']:+.2f}, фандинг {r['funding']:+.2f} "
                     f"→ итого {net:+.2f} USDT ({t['pnl_pct']:+.1f}% к марже); записи: {r['types']}")
    mark = "✅" if t["pnl_usdt"] > 0 else "❌"
    return (f"{mark} закрыт шорт {t['sym']} ({t['mode']}): {reason}, вход {t['entry']:.6g} → выход ≈{price:.6g}, "
            f"расчётный PnL {pnl_pct:+.1f}% к марже ({t['margin'] * pnl_pct / 100:+.2f} USDT){extra}")


def manage(state):
    """Каждый цикл: стопы/тейки/выход по времени. Возвращает список сообщений для чата."""
    msgs = []
    if MODE == "off":
        return msgs
    state.setdefault("trades", [])
    now = time.time()
    allpos = None
    if MODE == "live":
        allpos = all_short_positions()
        if allpos is None:
            log("позиции с биржи не получены — сопровождение реальных сделок пропущено в этом цикле")
        else:
            msgs += adopt_positions(state, allpos)
    for t in open_trades(state):
        sym = t["sym"]
        price = mark_price(sym)
        if not price:
            continue
        if t["mode"] == "live":
            if allpos is None:
                continue
            pos = allpos.get(sym)
            if pos is None:
                # в общем списке позиции нет — перепроверяем отдельным запросом, чтобы не принять сбой за закрытие
                time.sleep(2)
                pos = position(sym)
                if pos is False:
                    continue
            if pos is None:
                # позицию закрыла биржа (стоп, тейк или ликвидация) — снимаем оставшийся условный ордер
                cancel_orders(sym)
                if price >= t["sl"] * 0.99:
                    msgs.append(_close(state, t, min(price, t["sl"]), "стоп-лосс / ликвидация на бирже"))
                elif price <= t["tp"] * 1.01:
                    msgs.append(_close(state, t, max(price, t["tp"]), "тейк-профит на бирже"))
                else:
                    msgs.append(_close(state, t, price, "закрыта биржей ДО стопа/тейка — вероятно, авто-делеверидж (ADL) "
                                                        "или ручное закрытие; проверьте историю ордеров"))
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
        lines.append(f"Binance: баланс {b['balance']:.2f} {b['asset']}, доступно {b['available']:.2f}" if b
                     else "Binance: ключи не подошли или не заданы — реальные ордера невозможны")
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
        return "BINANCE_API_KEY/SECRET не заданы — торговля невозможна"
    sync_time()
    b = balance()
    if not b:
        return "Binance: ключи не подошли или API недоступен"
    return f"Binance OK: баланс {b['balance']:.2f} {b['asset']}, доступно {b['available']:.2f}; режим {MODE}"
