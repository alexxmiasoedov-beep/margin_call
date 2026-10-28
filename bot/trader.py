"""Исполнитель ордеров (Binance USDT-M perpetual). Ключи только из окружения."""
import hashlib
import math
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
# Выключатель реальной торговли. Непустая строка — бот работает (канал, сигналы, виртуальные журналы, команды), но ордеров
# на Binance не ставит и реальные позиции не ведёт: режим off, что бы ни стояло в TRADE_MODE. Включить — пустая строка и push в main.
NO_TRADE = "выключена по просьбе владельца 28.10.2026"
if NO_TRADE:
    MODE = "off"
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
STOP_PAUSE_H = float(os.environ.get("STOP_PAUSE_H", "48"))    # после стопа по монете не входить в неё N часов (0 = выкл.)
FUND_EXIT = float(os.environ.get("FUND_EXIT", "0"))          # выйти, если фандинг ≤ −N % в час (0 = выкл.; по бэктесту 0,4)
POLL_SEC = float(os.environ.get("POLL_SEC", "60"))            # опрос канала раз в N секунд (меньше — меньше задержка входа)
PROT_CHECK_SEC = 300                                          # проверка стоп/тейк-ордеров открытых позиций не чаще раза в 5 мин


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
    "pause": ("STOP_PAUSE_H", float, 0, 720, "пауза по монете после стопа, часов (0 = выкл.)"),
    "fexit": ("FUND_EXIT", float, 0, 5, "выход при фандинге ≤ −N %/ч (0 = выкл.)"),
    "poll": ("POLL_SEC", float, 30, 900, "опрос канала, секунд"),
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
            f"  pause — после стопа не входить в ту же монету: {STOP_PAUSE_H:g} ч" + (" (выключено)" if STOP_PAUSE_H <= 0 else "") + "\n"
            f"  fexit — досрочный выход при фандинге ≤ −{FUND_EXIT:g}%/ч" + (" (выключено)" if FUND_EXIT <= 0 else "") + "\n"
            f"  poll — опрос канала раз в {POLL_SEC:g} с\n"
            "Изменить: /set margin 7, /set lev 10, /set tp 8, /set sl 18, /set lsr 1.1, /set dump 0, /set br 5, /set pause 48")


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


NET = {}                                       # хост → [запросов, сбоев, секунд ожидания, максимум] с последней «РЕСУРСЫ»


def net_note(host, dt, ok):
    """Учёт сети для строки «РЕСУРСЫ» раз в час (scanner.log_resources): запросы, сбои и время ожидания по хостам."""
    n = NET.setdefault(host, [0, 0, 0.0, 0.0])
    n[0] += 1; n[1] += 0 if ok else 1; n[2] += dt; n[3] = max(n[3], dt)


BAN = {}                                       # хост → до какого времени не слать запросы (ответ Binance 403/418/429)


def ban_note(host, code, headers):
    """Ответ 418 (бан IP), 429 (превышен лимит веса) или 403 (WAF): до конца паузы (Retry-After) запросов к хосту не шлём —
    запросы во время бана Binance наказывает более долгим баном (от 2 мин до 3 суток). В журнал — один раз на паузу."""
    try:
        sec = int(float(headers.get("Retry-After") or 0))
    except (TypeError, ValueError, AttributeError):
        sec = 0
    sec = max(sec, 120 if code == 418 else 60)
    until = time.time() + sec
    if until > BAN.get(host, 0) + 5:
        BAN[host] = until
        log(f"Binance {code}: " + {418: "IP сервера забанен", 429: "превышен лимит запросов с IP сервера"}.get(code, "отказ WAF")
            + f" — пауза запросов к {host} на {sec} с")


def banned(host):
    """Сколько секунд ещё пауза запросов к хосту после ответа 403/418/429 (0 — можно)."""
    return max(0.0, BAN.get(host, 0) - time.time())


def _request(method, path, params=None, signed=True, _retry=True):
    """Binance USDT-M futures. Ошибка — dict с отрицательным code; успех может быть list, dict или {"code": 200}."""
    wait = banned("fapi.binance.com")
    if wait:
        return {"code": -1003, "msg": f"пауза после ответа Binance 418/429, ещё {wait:.0f} с"}
    params = dict(params or {})
    qs = urllib.parse.urlencode(params)
    if signed:
        params["timestamp"] = int(time.time() * 1000) + _time_offset
        params["recvWindow"] = 20000
        qs = urllib.parse.urlencode(params)
        qs += "&signature=" + hmac.new(SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, method=method, headers={"X-MBX-APIKEY": KEY, "User-Agent": "margin-call"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (403, 418, 429):
            ban_note("fapi.binance.com", e.code, e.headers)
        try:
            j = json.loads(e.read().decode())
        except Exception:
            j = {"code": e.code, "msg": str(e)}
    except Exception as e:
        j = {"code": -1, "msg": repr(e)}
    net_note("fapi.binance.com", time.time() - t0, not (isinstance(j, dict) and j.get("code") == -1))
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
                    "stepSize": float(f.get("MARKET_LOT_SIZE", {}).get("stepSize", 0) or f.get("LOT_SIZE", {}).get("stepSize", 0) or 0),
                    "maxQty": float(f.get("MARKET_LOT_SIZE", {}).get("maxQty", 0) or 0),
                    "minNotional": float(f.get("MIN_NOTIONAL", {}).get("notional", 0) or 0),
                    "onboard": int(c.get("onboardDate") or 0) // 1000,          # когда фьючерс запущен, unix-время
                }
    return _contracts.get(f"{sym}USDT")


def mark_price(sym):
    j = _request("GET", "/fapi/v1/premiumIndex", {"symbol": f"{sym}USDT"}, signed=False)
    try:
        return float(j["markPrice"])
    except Exception:
        return None


_fund_iv = {"ts": 0, "map": {}}


def funding_interval_h(sym):
    """Интервал начисления фандинга, часов (Binance /fapi/v1/fundingInfo; кого там нет — 8 ч). Кэш на час."""
    if time.time() - _fund_iv["ts"] > 3600:
        j = _request("GET", "/fapi/v1/fundingInfo", signed=False)
        if isinstance(j, list):
            _fund_iv["map"] = {str(x.get("symbol")): float(x.get("fundingIntervalHours") or 8) for x in j}
            _fund_iv["ts"] = time.time()
    return _fund_iv["map"].get(f"{sym}USDT", 8.0)


def funding_hourly(sym):
    """Текущая (прогнозная) ставка фандинга в пересчёте на час, доля. Минус — шорт платит. None, если нет данных."""
    j = _request("GET", "/fapi/v1/premiumIndex", {"symbol": f"{sym}USDT"}, signed=False)
    try:
        return float(j["lastFundingRate"]) / funding_interval_h(sym)
    except Exception:
        return None


def funding_paid(sym, since, until=None):
    """Фандинг для шорта на 1 USDT номинала за период (сумма начислений): >0 — получили, <0 — заплатили. None — нет данных."""
    p = {"symbol": f"{sym}USDT", "startTime": int(since * 1000), "limit": 1000}
    if until:
        p["endTime"] = int(until * 1000)
    j = _request("GET", "/fapi/v1/fundingRate", p, signed=False)
    if not isinstance(j, list):
        return None
    try:
        return sum(float(x["fundingRate"]) for x in j)
    except (KeyError, TypeError, ValueError):
        return None


def funding_rates(sym, since):
    """Начисления фандинга с момента since: [(время, ставка в пересчёте на 8 ч)]; None, если Binance не ответил."""
    j = _request("GET", "/fapi/v1/fundingRate", {"symbol": f"{sym}USDT", "startTime": int(since * 1000), "limit": 1000}, signed=False)
    if not isinstance(j, list):
        return None
    iv = funding_interval_h(sym)
    try:
        return [(int(x["fundingTime"]) // 1000, float(x["fundingRate"]) / iv * 8) for x in j]
    except (KeyError, TypeError, ValueError):
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
        u = f"https://api.gateio.ws/api/v4/futures/usdt/contract_stats?contract={urllib.parse.quote(sym)}_USDT&interval=1h&limit=1"
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "margin-call"}), timeout=15) as r:
            g = json.loads(r.read().decode())
        if isinstance(g, list) and g and g[0].get("lsr_taker") is not None:
            return float(g[0]["lsr_taker"])
    except Exception:
        pass
    return None


def _usdt(j):
    if isinstance(j, list):
        for b in j:
            if b.get("asset") == "USDT":
                return {"asset": "USDT", "balance": float(b["balance"]), "available": float(b["availableBalance"])}
    return None


def balance():
    return _usdt(_request("GET", "/fapi/v2/balance"))


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


def close_fills(sym, since_ts):
    """Фактическое закрытие шорта по исполнениям Binance (покупки после since_ts): (средняя цена, был ли лимитный maker) или None."""
    j = _request("GET", "/fapi/v1/userTrades", {"symbol": f"{sym}USDT", "startTime": int(since_ts * 1000), "limit": 1000})
    if not isinstance(j, list):
        return None
    q = v = 0.0; maker = False
    for f in j:
        try:
            if str(f.get("side")).upper() != "BUY":
                continue
            q += float(f["qty"]); v += float(f["qty"]) * float(f["price"]); maker = maker or bool(f.get("maker"))
        except (KeyError, TypeError, ValueError):
            continue
    return (v / q, maker) if q > 0 else None


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
    """Количество монет, чья стоимость ближе всего к марже × плечо: из двух соседних шагов лота (вниз и вверх)
    берётся ближайший, но не дороже 1,5 × цели. Раньше всегда вниз — на монетах с крупным шагом позиция
    получалась сильно меньше (например, 7,7 $ вместо 10 $)."""
    c = contract(sym)
    if not c or not price:
        return None
    target = MARGIN_USDT * LEVERAGE
    prec = c["quantityPrecision"]
    step = c.get("stepSize") or 10 ** -prec
    n = math.floor(target / price / step + 1e-9)
    best = None
    for k in (n, n + 1):
        q = round(k * step, prec)
        if q <= 0 or q < c["minQty"] or q * price < c["minNotional"] or q * price > target * 1.5:
            continue
        if c.get("maxQty") and q > c["maxQty"]:
            continue
        if best is None or abs(q * price - target) < abs(best * price - target):
            best = q
    return best


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
        return None, (f"не удалось подобрать объём около {MARGIN_USDT * LEVERAGE:g} $: шаг лота или минимальный объём контракта "
                      f"не позволяют (цена {price:.6g})")
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
    prot = place_protection(sym, fill, pside, q)
    res = {"qty": q, "order_id": j.get("orderId"), "pside": pside, "quote": price, "entry": fill, **prot}
    return res, None


def place_sl(sym, sl, pside):
    """Стоп: условный рыночный по марк-цене (Algo API, closePosition). Возвращает (algoId, ошибка)."""
    j = _request("POST", "/fapi/v1/algoOrder",
                 {"algoType": "CONDITIONAL", "symbol": f"{sym}USDT", "side": "BUY", "positionSide": pside,
                  "closePosition": "true", "type": "STOP_MARKET", "triggerPrice": sl, "workingType": "MARK_PRICE"})
    return j.get("algoId") if isinstance(j, dict) else None, _err(j)


def place_tp(sym, tp, pside, qty):
    """Тейк: лимитный ордер в стакане на весь объём (без проскальзывания, комиссия мейкера);
    если биржа его не принимает — условный рыночный тейк. Возвращает (id, предупреждение или '')."""
    params = {"symbol": f"{sym}USDT", "side": "BUY", "positionSide": pside, "type": "LIMIT", "timeInForce": "GTC",
              "price": tp, "quantity": qty}
    if pside == "BOTH":
        params["reduceOnly"] = "true"
    j = _request("POST", "/fapi/v1/order", params)
    if not _err(j):
        return j.get("orderId"), ""
    why = _err(j)
    ja = _request("POST", "/fapi/v1/algoOrder",
                  {"algoType": "CONDITIONAL", "symbol": f"{sym}USDT", "side": "BUY", "positionSide": pside,
                   "closePosition": "true", "type": "TAKE_PROFIT_MARKET", "triggerPrice": tp, "workingType": "CONTRACT_PRICE"})
    if not _err(ja):
        return ja.get("algoId"), f"лимитный тейк биржа не приняла ({why}), поставлен рыночный"
    return None, f"тейк НЕ установлен: лимитный — {why}; рыночный — {_err(ja)}"


def place_protection(sym, entry, pside, qty):
    """Ставит стоп и тейк от цены entry по текущим SL_PCT/TP_PCT. Возвращает {sl, tp, sl_order_id, tp_order_id, warn}."""
    c = contract(sym)
    sl = _round_price(c, entry * (1 + SL_PCT / 100))
    tp = _round_price(c, entry * (1 - TP_PCT / 100))
    sl_id, sl_err = place_sl(sym, sl, pside)
    tp_id, tp_warn = place_tp(sym, tp, pside, qty)
    warn = ([f"стоп НЕ установлен: {sl_err}"] if sl_err else []) + ([tp_warn] if tp_warn else [])
    return {"sl": sl, "tp": tp, "sl_order_id": sl_id, "tp_order_id": tp_id, "warn": "; ".join(warn)}


_ACTIVE_ALGO = {"NEW", "WORKING", "TRIGGERING", "ACTIVE", "PENDING"}


def protection_state(sym, entry, since):
    """Какие защитные ордера реально стоят на бирже: {"tp": bool, "sl": bool} или None, если не удалось узнать.
    Тейк — лимитный BUY в открытых ордерах или активный условный ордер с триггером ниже входа;
    стоп — активный условный ордер с триггером выше входа."""
    oo = _request("GET", "/fapi/v1/openOrders", {"symbol": f"{sym}USDT"})
    ja = _request("GET", "/fapi/v1/allAlgoOrders", {"symbol": f"{sym}USDT", "startTime": int((since - 600) * 1000)})
    algo = ja.get("orders") if isinstance(ja, dict) and "orders" in ja else ja
    if not isinstance(oo, list) or not isinstance(algo, list):
        return None
    tp = any(str(o.get("type")) == "LIMIT" and str(o.get("side")) == "BUY" for o in oo)
    sl = False
    for o in algo:
        if str(o.get("algoStatus", o.get("status", ""))).upper() not in _ACTIVE_ALGO or str(o.get("side")) != "BUY":
            continue
        try:
            trig = float(o.get("triggerPrice") or 0)
        except (TypeError, ValueError):
            continue
        if trig > entry:
            sl = True
        elif trig > 0:
            tp = True
    return {"tp": tp, "sl": sl}


def ensure_protection(t, pos):
    """Если у открытой позиции на бирже нет тейка или стопа — переставляет. Возвращает сообщение или None."""
    st = protection_state(t["sym"], t["entry"], t["opened"])
    if st is None or (st["tp"] and st["sl"]):
        return None
    pside = t.get("pside", "SHORT")
    try:
        qty = abs(float(pos.get("positionAmt"))) or t["qty"]
    except (TypeError, ValueError, AttributeError):
        qty = t["qty"]
    done = []
    if not st["sl"]:
        sl_id, err = place_sl(t["sym"], t["sl"], pside)
        if err and "exist" in err.lower():
            # биржа говорит, что стоп с closePosition уже стоит — значит, мы не распознали его статус; не шумим
            log(t["sym"], "стоп уже есть на бирже (статус условного ордера не распознан):", err)
        else:
            done.append(f"стоп {t['sl']:.6g} — " + ("переставлен" if not err else f"НЕ удалось: {err}"))
    if not st["tp"]:
        tp_id, warn = place_tp(t["sym"], t["tp"], pside, qty)
        done.append(f"тейк {t['tp']:.6g} — " + (warn or "переставлен лимитным ордером"))
    if not done:
        return None
    t["protection_fixes"] = t.get("protection_fixes", 0) + 1
    if t["protection_fixes"] > 3 and all("НЕ" in d for d in done):
        return None          # не спамим одной и той же ошибкой каждые 5 минут — она уже была в чате
    return f"🛠 {t['sym']}: на бирже не хватало защитных ордеров. " + "; ".join(done)


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
        prot = place_protection(sym, entry, pside, qty)
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
    pos = position(sym)          # закрываем фактический остаток (тейк мог исполниться частично)
    if pos is None:
        return True, None
    if pos:
        try:
            qty = abs(float(pos.get("positionAmt") or qty)) or qty
        except (TypeError, ValueError):
            pass
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
    if STOP_PAUSE_H > 0:
        now = time.time()
        for t in state["trades"]:
            if t["sym"] == sym and t.get("closed") and "стоп" in str(t.get("reason", "")) and now - t["closed"] < STOP_PAUSE_H * 3600:
                ago = (now - t["closed"]) / 3600
                return (f"⏭ {sym}: сделка не открыта — по монете был стоп {ago:.0f} ч назад, пауза после стопа {STOP_PAUSE_H:g} ч "
                        f"(повторный вход в первые двое суток после стопа даёт 25% стопов против 13%)")
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
    pnl_pct = (1 - price / t["entry"]) * 100 * t["lev"]      # шорт: (вход − выход) / вход, к марже с плечом
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
                # причина — по фактическим исполнениям, а не по текущей цене: к проверке цена могла уже откатиться
                cf = close_fills(sym, t["opened"] + 1)
                xp = cf[0] if cf else price
                if xp >= t["sl"] * 0.99:
                    msgs.append(_close(state, t, xp, "стоп-лосс на бирже" + ("" if cf else " (по текущей цене — исполнения не получены)")))
                elif (cf and cf[1]) or xp <= t["tp"] * 1.01:
                    msgs.append(_close(state, t, xp, "тейк-профит на бирже" + ("" if cf else " (по текущей цене — исполнения не получены)")))
                else:
                    msgs.append(_close(state, t, xp, "закрыта не стопом и не тейком — вручную или авто-делеверидж (ADL); "
                                                     "проверьте /history " + sym))
                continue
            if FUND_EXIT > 0 and now - t["opened"] < HOLD_H * 3600:
                fh = funding_hourly(sym)
                if fh is not None and fh * 100 <= -FUND_EXIT:
                    ok, msg = live_close_short(sym, t["qty"], t.get("pside", "SHORT"))
                    if ok:
                        msgs.append(_close(state, t, price, f"досрочный выход: фандинг {fh * 100:+.2f}%/ч (порог −{FUND_EXIT:g}%)"))
                    else:
                        msgs.append(f"❌ {sym}: не удалось закрыть по фандингу: {msg}")
                    continue
            if now - t["opened"] < HOLD_H * 3600 and now - t["opened"] > 120 and now - t.get("prot_chk", 0) >= PROT_CHECK_SEC:
                t["prot_chk"] = now
                fix = ensure_protection(t, pos)
                if fix:
                    msgs.append(fix)
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
            elif FUND_EXIT > 0:
                fh = funding_hourly(sym)
                if fh is not None and fh * 100 <= -FUND_EXIT:
                    msgs.append(_close(state, t, price, f"досрочный выход: фандинг {fh * 100:+.2f}%/ч (порог −{FUND_EXIT:g}%)"))
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
    off = f" (реальная торговля {NO_TRADE})" if NO_TRADE else ""
    lines = [f"Режим: {MODE}{off}, маржа {MARGIN_USDT:g} USDT × {LEVERAGE}x, стоп +{SL_PCT:g}%, тейк −{TP_PCT:g}%, "
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
        if NO_TRADE and any(t.get("mode") == "live" for t in ot):
            lines.append("Реальные позиции бот сейчас не ведёт: их закроют стоп или тейк на бирже, выхода по времени нет; "
                         "что на самом деле открыто на Binance — /positions")
    else:
        lines.append("Открытых позиций нет.")
    if closed:
        wins = sum(1 for t in closed if t["pnl_pct"] > 0)
        tot = sum(t["pnl_usdt"] for t in closed)
        lines.append(f"Закрытых за 30 дней: {len(closed)}, прибыльных {wins}, итог {tot:+.2f} USDT")
        for t in closed[-5:]:
            lines.append(f"  {t['sym']}: {t['reason']}, {t['pnl_pct']:+.1f}%")
    return "\n".join(lines)


CHECK_HINT = {-2015: "Binance не принял ключ с этого IP: ключ удалён или выключен, у него нет прав на фьючерсы, "
                    "либо IP сервера нет в белом списке ключа",
              -2014: "ключ в неверном формате", -1022: "подпись не сошлась — проверьте секрет ключа",
              -1021: "часы сервера расходятся с Binance",
              -1003: "превышен лимит запросов с IP сервера (лимит общий для всех программ на сервере) — Binance дал паузу",
              -1: "Binance не ответил — сбой сети или DNS на сервере", 451: "Binance не обслуживает страну IP сервера"}


def startup_check():
    """Проверка ключей: запрос баланса (на старте и, если не прошла, раз в 5 мин — scanner.exec_recheck). Возвращает строку
    для журнала и чата; при сбое — код и сообщение Binance и подсказку, что это значит."""
    if MODE == "off":
        return f"реальная торговля {NO_TRADE}" if NO_TRADE else "торговля выключена (TRADE_MODE=off)"
    if not KEY or not SECRET:
        return "BINANCE_API_KEY/SECRET не заданы — торговля невозможна"
    sync_time()
    j = _request("GET", "/fapi/v2/balance")
    b = _usdt(j)
    if not b:
        code = j.get("code") if isinstance(j, dict) else None
        hint = CHECK_HINT.get(code)
        return (f"Binance: ключи не подошли или API недоступен — код {code}: {str(_err(j) or j)[:200]}"
                + (f". {hint}" if hint else ""))
    return f"Binance OK: баланс {b['balance']:.2f} {b['asset']}, доступно {b['available']:.2f}; режим {MODE}"


# ------------------------------------------------------------------ виртуальные журналы (параллельные стратегии, без реальных ордеров)
# key — где хранится журнал в state; params(fh) -> (тейк % или None, стоп %) по ставке фандинга в час (доля) на входе.
VIRTUALS = {
    "virtual": {"title": "без тейка, стоп 25%", "icon": "📓",
                "params": lambda fh: (None, 25.0)},
    "virtual_fund": {"title": "по фандингу: фандинг < −0,03%/ч → тейк 15 / стоп 25, иначе тейк 6 / стоп 20", "icon": "📗",
                     "params": lambda fh: (15.0, 25.0) if fh is not None and fh * 100 < -0.03 else (6.0, 20.0)},
    "virtual_1525": {"title": "тейк 15 / стоп 25 (лучший вариант бэктеста на фьючерсах)", "icon": "📘",
                     "params": lambda fh: (15.0, 25.0)},
    "virtual_1520": {"title": "тейк 15 / стоп 20 (лучший по бэктесту за 19 месяцев с сигналами, как в боте)", "icon": "📕",
                     "params": lambda fh: (15.0, 20.0)},
    "virtual_620": {"title": "тейк 6 / стоп 20 (прежние настройки реальной торговли)", "icon": "📙",
                    "params": lambda fh: (6.0, 20.0)},
    # новые правила по бэктесту за 19 месяцев (research/futures/ВЫВОДЫ.md): свои сигналы на закрытии 15-мин свечи (scanner.new_rules)
    "virtual_D": {"title": "D*: слив за 12 ч ≥ 4%, серия ≥ 2 ч, B/R ≥ 30, объём 24 ч ≥ 20 млн $, BTC за сутки в плюсе; тейк 10 / стоп 20",
                  "icon": "🟦", "params": lambda fh: (10.0, 20.0), "own": True, "cooldown_h": 24},
    "virtual_P": {"title": "P*: памп за 12 ч ≥ 2%, серия ≥ 1 ч, объём 24 ч ≥ 20 млн $, BTC за 30 дней в минусе; тейк 10 / стоп 20",
                  "icon": "🟧", "params": lambda fh: (10.0, 20.0), "own": True, "cooldown_h": 24},
    # корейский шорт (research/mm2/ВЫВОДЫ.md, бэктест за 2 года): свой сигнал на закрытии 15-мин свечи (scanner.korea_rule)
    "virtual_KR": {"title": "корейский шорт: памп +15% за ≤ 2 ч из покоя, Upbit + Bithumb ≥ 20% объёма за час; тейк 10 / стоп 25",
                   "icon": "🇰🇷", "params": lambda fh: (10.0, 25.0), "own": True, "cooldown_h": 24},
    # корейский шорт со счётом условий (research/s6, s7/ВЫВОДЫ.md, бэктест за 2 года): сигнал 🇰🇷 + ≥ 3 из 6 условий (scanner.korea_star)
    "virtual_KRS": {"title": "корейский шорт ⭐: сигнал 🇰🇷 и ≥ 3 из 6 условий — пампов на рынке за сутки ≥ 16, BTC за сутки ≥ 0, "
                             "цена выше максимума 7 дней, покупки тейкеров в пампе ≤ 51%, доля Кореи ≥ 40%, воскресенье (UTC); тейк 7 / стоп 20",
                    "icon": "🇰🇷⭐", "params": lambda fh: (7.0, 20.0), "own": True, "cooldown_h": 24, "pause_h": 0.0},
    # турецкий набег (research/s2/ВЫВОДЫ.md, бэктест за 2 года): свой сигнал на закрытии 15-мин свечи (scanner.turkey_rule)
    "virtual_TR": {"title": "турецкий набег: доля пары к лире за час ≥ 10% и в 3+ раза выше обычной, рост за 4 ч ≥ 10%; тейк 10 / стоп 15",
                   "icon": "🇹🇷", "params": lambda fh: (10.0, 15.0), "own": True, "cooldown_h": 48, "hold_h": 24.0},
    # памп без розницы — ЛОНГ (research/s5/ВЫВОДЫ.md, бэктест за 2 года): свой сигнал на закрытии 15-мин свечи (scanner.korea_rule)
    "virtual_L": {"title": "памп без розницы (ЛОНГ): памп +15% за ≤ 2 ч из покоя, спот Binance < 12% объёма за час, Корея < 20%, "
                           "лира < 10%; тейк 30 / стоп 15", "icon": "🟩", "params": lambda fh: (30.0, 15.0), "own": True,
                  "cooldown_h": 24, "pause_h": 0.0, "side": "long"},
    # отдача займа (research/s9/ВЫВОДЫ.md, бэктест за 20 месяцев): свой сигнал на закрытии 15-мин свечи (scanner.repay_rule)
    "virtual_RP": {"title": "отдача займа: монета в маржинальном канале ≥ 6 ч, отдача (REP) за час резко (первый всплеск за час) "
                            "выросла в 2+ раза и на 20+ тыс. $, цена за сутки ±10% и больше; тейк 10 / стоп 25",
                   "icon": "↩️", "params": lambda fh: (10.0, 25.0), "own": True, "cooldown_h": 24, "pause_h": 0.0},
    # фактор займа (research/s10/ВЫВОДЫ.md, бэктест за 19 месяцев): раз в сутки в 01:00 UTC (scanner.borrow_factor_rule).
    # Плечо ×1: стоп +100% — это ликвидация при ×1; рядом с итогом — тот же итог с лонгом BTC на ту же сумму (хедж)
    "virtual_BF": {"title": "фактор займа: каждый день в 01:00 UTC — 10 монет, чаще всех бывших в маржинальном канале за 7 суток "
                            "(фьючерс старше 30 суток, объём ≥ 10 млн $/сут, фандинг не дешевле −0,1%/8 ч), из них 5 самых "
                            "волатильных; шорт на 7 суток без тейка, стоп +100%, плечо ×1",
                   "icon": "🏦", "params": lambda fh: (None, 100.0), "own": True, "cooldown_h": 0, "pause_h": 0.0,
                   "hold_h": 168.0, "lev": 1, "hedge": "BTC"},
    # первый займ свежего токена (research/s12/ВЫВОДЫ.md, стратегия A): scanner.newtoken_rule
    "virtual_NT": {"title": "первый займ свежего токена: монета впервые в маржинальном канале, спотовый листинг Binance ±10 суток, "
                            "через 24 ч после первого поста (фандинг не дешевле −0,1%/8 ч); шорт на 21 сутки без тейка, стоп +60%, "
                            "выход при фандинге ≤ −0,5%/8 ч два раза подряд, плечо ×1",
                   "icon": "🆕", "params": lambda fh: (None, 60.0), "own": True, "cooldown_h": 0, "pause_h": 0.0,
                   "hold_h": 504.0, "lev": 1, "hedge": "BTC", "fund_exit": -0.005},
    # объявления Binance (research/s12/ВЫВОДЫ.md, стратегия B): scanner.announce_rule
    "virtual_AN": {"title": "объявления Binance: делистинг спота или фьючерса, Monitoring Tag → шорт не позже часа после публикации "
                            "(фандинг не дешевле −0,1%/8 ч); 7 суток без тейка, стоп +25%, плечо ×1",
                   "icon": "📢", "params": lambda fh: (None, 25.0), "own": True, "cooldown_h": 0, "pause_h": 0.0,
                   "hold_h": 168.0, "lev": 1, "hedge": "BTC"},
}
VIRT = {"hold_h": 48.0, "pause_h": 48.0, "start_balance": 20.0,   # стартовый капитал журнала, USDT
        "check_s": 300}                                             # свечи открытых сделок докачиваются раз в 5 мин


def _virt(state, key):
    v = state.setdefault(key, {})
    v.setdefault("trades", []); v.setdefault("started", time.time())
    # баланс ведётся только по сделкам, открытым после его запуска (у них флаг "bal"); старые позиции в него не входят
    v.setdefault("balance", VIRT["start_balance"]); v.setdefault("bal_since", time.time())
    return v


def _virt_scan(t):
    """Проходит минутные свечи Binance после входа по порядку и возвращает первое событие: "стоп" (марк-цена дошла до стопа —
    так срабатывает реальный стоп), "тейк" (цена сделок прошла тейк — так исполняется лимитный тейк) или None.
    Шорт: стоп по максимуму марк-цены, тейк по минимуму цены сделок; лонг — наоборот.
    Стоп и тейк в одной минуте — стоп. Свечи после выхода по времени не смотрим; докачка с места прошлой проверки.
    Свечей просим ровно столько, сколько прошло (вес запроса у Binance 1, а не 10); без тейка цена сделок не нужна."""
    start = int(t.get("v_next") or (t["opened"] // 60 + 1) * 60 * 1000)
    end = int((t["opened"] + t.get("hold_h", VIRT["hold_h"]) * 3600) * 1000)
    long = t.get("side") == "long"
    for _ in range(4):
        last = min(time.time() * 1000 - 60000, end)
        if start > last:
            break
        q = {"symbol": f"{t['sym']}USDT", "interval": "1m", "startTime": start, "limit": int(min(1500, (last - start) // 60000 + 2))}
        m = _request("GET", "/fapi/v1/markPriceKlines", q, signed=False)
        k = _request("GET", "/fapi/v1/klines", q, signed=False) if t.get("tp") else m
        if not isinstance(m, list) or not isinstance(k, list) or not m or not k:
            break
        now_ms = time.time() * 1000
        try:
            mx = {int(x[0]): float(x[3] if long else x[2]) for x in m if int(x[6]) < now_ms and int(x[0]) < end}
            kx = {int(x[0]): float(x[2] if long else x[3]) for x in k if int(x[6]) < now_ms and int(x[0]) < end}
        except (TypeError, ValueError, IndexError):
            break
        mins = sorted(set(mx) & set(kx))
        if not mins:
            break
        for ts in mins:
            if (mx[ts] <= t["sl"]) if long else (mx[ts] >= t["sl"]):
                t["v_next"] = ts + 60000; return "стоп"
            if t.get("tp") and ((kx[ts] > t["tp"]) if long else (kx[ts] < t["tp"])):
                t["v_next"] = ts + 60000; return "тейк"
        start = t["v_next"] = mins[-1] + 60000
        if len(m) < q["limit"] or len(k) < q["limit"]:
            break
    return None


def virt_on_signal(state, sym, price, rule):
    """Открывает виртуальные сделки по сигналу во всех журналах. Возвращает строку для чата или None."""
    now = time.time(); px = None; fh = None; out = []
    if contract(sym) is None and _contracts:
        return None                    # монеты нет на фьючерсах Binance: цены не будет — виртуальную сделку не закрыть
    for key, cfg in VIRTUALS.items():
        if cfg.get("own"):
            continue                                   # у журналов со своими правилами — свои сигналы
        v = _virt(state, key)
        if any(t["sym"] == sym and not t.get("closed") for t in v["trades"]):
            continue
        paused = next((t for t in v["trades"] if t["sym"] == sym and t.get("closed") and t.get("reason") == "стоп"
                       and now - t["closed"] < VIRT["pause_h"] * 3600), None)
        if paused:
            out.append(f"{cfg['icon']} {sym}: пропуск — виртуальный стоп {(now - paused['closed']) / 3600:.0f} ч назад")
            continue
        if px is None:
            px = mark_price(sym) or price
            fh = funding_hourly(sym)
        if not px:
            return None
        tp, sl = cfg["params"](fh)
        if v["balance"] < MARGIN_USDT:
            out.append(f"{cfg['icon']} {sym}: пропуск — на виртуальном балансе {v['balance']:.2f} USDT, меньше маржи {MARGIN_USDT:g}")
            continue
        t = {"sym": sym, "opened": now, "entry": px, "rule": rule, "margin": MARGIN_USDT, "lev": LEVERAGE, "bal": True,
             "sl": px * (1 + sl / 100), "tp": px * (1 - tp / 100) if tp else None, "tp_pct": tp, "sl_pct": sl, "fh_entry": fh}
        v["trades"].append(t)
        out.append(f"{cfg['icon']} виртуально: шорт {sym} по {px:.6g}, " + (f"тейк {tp:g}% " if tp else "без тейка, ") + f"стоп {sl:g}%")
    if not out:
        return None
    fnote = f" (фандинг сейчас {fh * 100:+.3f}%/ч)" if fh is not None else ""
    return "\n".join(out) + fnote


def virt_open(state, key, sym, rule, note, price=None):
    """Открывает виртуальную сделку (шорт, у журнала с side="long" — лонг) в журнале key по его собственному сигналу.
    Возвращает строку для чата или None."""
    cfg = VIRTUALS[key]; v = _virt(state, key); now = time.time()
    long = cfg.get("side") == "long"; pause = cfg.get("pause_h", VIRT["pause_h"])
    mine = [t for t in v["trades"] if t["sym"] == sym]
    if any(not t.get("closed") for t in mine):
        return None
    if any(now - t["opened"] < cfg.get("cooldown_h", 0) * 3600 for t in mine):
        return None
    if any(t.get("reason") == "стоп" and now - t["closed"] < pause * 3600 for t in mine if t.get("closed")):
        return f"{cfg['icon']} {sym}: сигнал {rule}, но пропуск — виртуальный стоп меньше {pause:g} ч назад"
    if v["balance"] < MARGIN_USDT:
        return f"{cfg['icon']} {sym}: сигнал {rule}, но на виртуальном балансе {v['balance']:.2f} USDT — меньше маржи {MARGIN_USDT:g}"
    px = mark_price(sym) or price
    if not px:
        return None
    fh = funding_hourly(sym); tp, sl = cfg["params"](fh)
    sgn = -1 if long else 1                                  # стоп выше входа у шорта, ниже — у лонга
    t = {"sym": sym, "opened": now, "entry": px, "rule": rule, "margin": MARGIN_USDT, "lev": cfg.get("lev", LEVERAGE), "bal": True,
         "sl": px * (1 + sgn * sl / 100), "tp": px * (1 - sgn * tp / 100) if tp else None, "tp_pct": tp, "sl_pct": sl, "fh_entry": fh,
         "note": note, "hold_h": cfg.get("hold_h", VIRT["hold_h"])}
    if long:
        t["side"] = "long"
    if cfg.get("hedge"):                                     # для отчёта: лонг монеты-хеджа на ту же сумму и тот же срок
        hp = mark_price(cfg["hedge"])
        if hp:
            t["hedge_sym"], t["hedge_entry"] = cfg["hedge"], hp
    v["trades"].append(t)
    return (f"{cfg['icon']} сигнал {rule}: виртуально {'ЛОНГ' if long else 'шорт'} {sym} по {px:.6g}, "
            + (f"тейк {tp:g}%" if tp else "без тейка") + f" / стоп {sl:g}%" + (f", плечо ×{t['lev']}" if "lev" in cfg else "")
            + f"\n{cfg['icon']} {note}")


def _virt_close(v, t, px, reason, icon):
    t["closed"] = time.time(); t["exit"] = px; t["reason"] = reason
    notional = t["margin"] * t["lev"]; long = t.get("side") == "long"
    pct = (px / t["entry"] - 1 if long else 1 - px / t["entry"]) * 100 * t["lev"]   # шорт: прибыль = (вход − выход) / вход
    fr = funding_paid(t["sym"], t["opened"], t["closed"])                          # фандинг для шорта; лонгу — с обратным знаком
    t["fund_usdt"] = round((-fr if long else fr) * notional, 4) if fr is not None else 0.0
    t["pnl_usdt"] = round(t["margin"] * pct / 100 + t["fund_usdt"] - notional * 0.0005 * 2, 4)
    t["pnl_pct"] = round(t["pnl_usdt"] / t["margin"] * 100, 2)
    mark = "✅" if t["pnl_usdt"] > 0 else "❌"
    fnote = f", фандинг {t['fund_usdt']:+.2f}" if fr is not None else ", фандинг: нет данных"
    hnote = ""
    if t.get("hedge_entry"):                     # хедж для отчёта: лонг той же суммы на тот же срок, с фандингом и комиссией
        hp = mark_price(t["hedge_sym"]); hfr = funding_paid(t["hedge_sym"], t["opened"], t["closed"])
        if hp:
            t["hedge_exit"] = hp
            t["hedge_usdt"] = round(notional * (hp / t["hedge_entry"] - 1 - (hfr or 0.0) - 0.0005 * 2), 4)
            hnote = (f"; с хеджем {t['hedge_sym']} ({t['hedge_entry']:.6g} → {hp:.6g}) "
                     f"{t['pnl_usdt'] + t['hedge_usdt']:+.2f} USDT")
    if t.get("bal"):
        was = v["balance"]; v["balance"] = round(was + t["pnl_usdt"], 4)
        start = VIRT["start_balance"]
        bnote = (f"\n{icon} баланс: {was:.2f} → {v['balance']:.2f} USDT "
                 f"({v['balance'] - start:+.2f}, {(v['balance'] / start - 1) * 100:+.1f}% от стартовых {start:g})")
    else:
        bnote = f"\n{icon} сделка открыта до запуска баланса — в баланс не входит (баланс {v['balance']:.2f} USDT)"
    return (f"{icon} {mark} виртуально закрыт {'ЛОНГ' if long else 'шорт'} {t['sym']}: {reason}, вход {t['entry']:.6g} → выход {px:.6g}, "
            f"цена {pct:+.1f}% к марже{fnote} → итого {t['pnl_usdt']:+.2f} USDT, держали {(t['closed'] - t['opened']) / 3600:.1f} ч"
            + hnote + bnote)


def virt_manage(state):
    """Виртуальные стоп (марк-цена), тейк (цена сделок) по минутным свечам после входа и выход по времени. Сделка
    проверяется раз в 5 мин (VIRT["check_s"]) и в момент выхода по времени: свечи докачиваются с места прошлой проверки,
    так что стоп и тейк ловятся так же точно, а запросов к Binance в разы меньше. Текущая цена — только для выхода."""
    msgs = []; now = time.time(); cache = {}; dropped = {}

    def price(sym):
        if sym not in cache:
            cache[sym] = mark_price(sym)
        return cache[sym]

    for key, cfg in VIRTUALS.items():
        v = _virt(state, key)
        for t in v["trades"]:
            if t.get("closed"):
                continue
            t_end = t["opened"] + t.get("hold_h", VIRT["hold_h"]) * 3600
            if now < t.get("v_chk", 0) and now < t_end:
                continue
            t["v_chk"] = min(now + VIRT["check_s"], t_end)
            ev = _virt_scan(t)
            fx = cfg.get("fund_exit")                      # досрочный выход: фандинг ≤ fx за 8 ч два начисления подряд
            fbad = False
            if fx is not None and not ev and now >= t.get("f_chk", 0) and price(t["sym"]):
                t["f_chk"] = now + 1800                    # проверяем раз в 30 мин
                fr = funding_rates(t["sym"], t["opened"])
                fbad = bool(fr) and any(a[1] <= fx and b[1] <= fx for a, b in zip(fr, fr[1:]))
            if ev == "стоп":
                msgs.append(_virt_close(v, t, t["sl"], "стоп", cfg["icon"]))
            elif ev == "тейк":
                msgs.append(_virt_close(v, t, t["tp"], "тейк", cfg["icon"]))
            elif fbad:
                msgs.append(_virt_close(v, t, price(t["sym"]), f"фандинг ≤ {fx * 100:g}%/8 ч два раза подряд", cfg["icon"]))
            elif now >= t_end:
                px = price(t["sym"])
                if px:
                    msgs.append(_virt_close(v, t, px, f"выход по времени ({t.get('hold_h', VIRT['hold_h']):g} ч)", cfg["icon"]))
                elif contract(t["sym"]) is None and _contracts:
                    # монеты нет на фьючерсах Binance (вход был по цене из канала): закрыть не по чему — убираем из журнала
                    t["drop"] = True; dropped.setdefault(t["sym"], []).append(cfg["icon"])
        v["trades"] = [t for t in v["trades"] if not t.get("drop") and (not t.get("closed") or now - t["closed"] < 90 * 86400)]
    if dropped:
        msgs.append("Убраны виртуальные сделки по монетам без фьючерса на Binance — цены нет, закрыть их нельзя, "
                    "в статистику они не входят: " + ", ".join(f"{s} {''.join(i)}" for s, i in dropped.items()))
    return msgs


def _virt_block(state, key, cfg):
    v = _virt(state, key); now = time.time()
    op = [t for t in v["trades"] if not t.get("closed")]; cl = [t for t in v["trades"] if t.get("closed")]
    pause = cfg.get("pause_h", VIRT["pause_h"])
    lines = [f"{cfg['icon']} {cfg['title']}, выход {cfg.get('hold_h', VIRT['hold_h']):g} ч, "
             + (f"пауза после стопа {pause:g} ч. " if pause else "без паузы после стопа. ")
             + f"С {time.strftime('%d.%m %H:%M', time.gmtime(v['started']))} UTC.",
             f"  баланс {v['balance']:.2f} USDT (старт {VIRT['start_balance']:g} с {time.strftime('%d.%m %H:%M', time.gmtime(v['bal_since']))} UTC, "
             f"{v['balance'] - VIRT['start_balance']:+.2f}; сделок в балансе {sum(1 for t in v['trades'] if t.get('bal') and t.get('closed'))})"]
    hpx = {}
    for t in op:
        sgn = -1 if t.get("side") == "long" else 1                 # лонг: прибыль от роста цены, фандинг с обратным знаком
        px = mark_price(t["sym"]); cur = f", сейчас {sgn * (1 - px / t['entry']) * 100 * t['lev']:+.1f}% к марже" if px else ""
        fr = funding_paid(t["sym"], t["opened"])
        fund = f", фандинг {sgn * fr * t['margin'] * t['lev']:+.2f}" if fr is not None else ""
        tpn = f"тейк {t['tp_pct']:g}%" if t.get("tp_pct") else "без тейка"
        old = "" if t.get("bal") else " — вне баланса"
        side = " (лонг)" if sgn < 0 else ""
        hedge = ""
        if t.get("hedge_entry"):
            if t["hedge_sym"] not in hpx:
                hpx[t["hedge_sym"]] = mark_price(t["hedge_sym"])
            hp = hpx[t["hedge_sym"]]
            hedge = f", хедж {t['hedge_sym']} {(hp / t['hedge_entry'] - 1) * 100 * t['lev']:+.1f}%" if hp else ""
        lines.append(f"  открыта {t['sym']}{side} по {t['entry']:.6g} ({tpn}, стоп {t.get('sl_pct', 25):g}%), {(now - t['opened']) / 3600:.1f} ч{cur}{fund}{hedge}{old}")
    if cl:
        tot = sum(t["pnl_usdt"] for t in cl); ftot = sum(t.get("fund_usdt", 0) for t in cl)
        cnt = {r: sum(1 for t in cl if t["reason"].startswith(r)) for r in ("тейк", "стоп", "выход")}
        hd = [t for t in cl if "hedge_usdt" in t]
        hsum = (f"; с хеджем {hd[0]['hedge_sym']} {sum(t['pnl_usdt'] + t['hedge_usdt'] for t in hd):+.2f} USDT"
                + (f" (по {len(hd)} сделкам)" if len(hd) < len(cl) else "")) if hd else ""
        lines.append(f"  закрытых {len(cl)}: тейков {cnt['тейк']}, стопов {cnt['стоп']}, по времени {cnt['выход']}; "
                     f"итого {tot:+.2f} USDT ({tot / len(cl):+.3f} на сделку), из них фандинг {ftot:+.2f}{hsum}")
        for t in cl[-6:]:
            lines.append(f"    {time.strftime('%d.%m', time.gmtime(t['closed']))} {t['sym']}: {t['reason']}, {t['pnl_usdt']:+.2f}")
    elif not op:
        lines.append("  сделок пока нет")
    return lines, v["started"]


def virt_text(state):
    own_lev = "".join(f", у {c['icon']} плечо ×{c['lev']}" for c in VIRTUALS.values() if "lev" in c)
    lines = [f"Виртуальные журналы (маржа и плечо как у реальных{own_lev}; фандинг учтён):"]; starts = []
    for key, cfg in VIRTUALS.items():
        bl, st = _virt_block(state, key, cfg); lines += [""] + bl; starts.append((st, cfg["icon"]))
    real_lines = []
    for st, icon in starts:
        real = [t for t in state.get("trades", []) if t.get("closed") and t["closed"] >= st]
        if real:
            real_lines.append(f"Реальные сделки с начала журнала {icon}: {len(real)}, итого {sum(t.get('pnl_usdt', 0) for t in real):+.2f} USDT")
    if real_lines:
        lines += [""] + real_lines
    return "\n".join(lines)             # длинный ответ бот отправит несколькими сообщениями (scanner.send)
