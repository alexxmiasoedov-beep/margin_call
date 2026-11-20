"""Тест журнала 🗳 «комитет шорт 4 ч» (scanner.c4_rule, c4_record, c4_features, c4_votes; trader: третий баланс с хеджем
корзиной альтов, закрытия одним сообщением) с подменой Binance, CoinMarketCap и t.me:
разбор постов (новый и старый формат, «inf», не пост займов); панель канала — строка в отметке часа (последний пост не
старше 30 мин), часы присутствия; дыра после простоя и история за 32 сут догружаются страницами t.me; готовность панели
(покрытие 31 сут, дыра > 3 ч — не готова); признаки на пустых и неполных данных без падений и на известных данных;
голосование; вход раз в окно 4 ч (00, 04, …), только в первые 20 мин и при готовой панели; стейблкоины, молодой фьючерс
и монета без фьючерса — мимо; сбой данных по монете — повтор, после 6 попыток окно закрыто; хедж корзиной альтов; выход
через 4 ч одним сообщением с балансами; стоп +10%; нет цен корзины при закрытии; блок 🗳 в /virtual.
Запуск: python3 research/s225/c4_test.py"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

D, H = 86400, 3600
T = 1795132800 + 4 * H                          # отметка сетки 4 ч (04:00 UTC)
CLOCK = [T + 120.0]
scanner.time.time = lambda: CLOCK[0]
trader.time.time = lambda: CLOCK[0]
scanner.time.sleep = lambda s: None
LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
trader.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
scanner.C4_FILE = os.path.join(TMP, "c4_panel.json")


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG[-30:])); raise SystemExit(1)


# ---------------------------------------------------------------- 1. разбор постов
new = "SYM   BOR    REP     B/R CHNG\n-------------------------------\nALICE 106.5K 4.5K   23.5    0\nDODO  12.9K  0     inf      0\nDEXE  4.9K   616.2   8      0\n\nMarginData | CryptoCode"
old = "ASSET   BOR.D   REP.D     B/R\n----------------------------\nAXS     51.3M   6.7M      7.7\n🆕FORM   2.3M    779.0K    3\n"
check(scanner._c4_ranked(new) == [("ALICE", 106500.0, 4500.0, 1), ("DODO", 12900.0, 0.0, 2), ("DEXE", 4900.0, 616.2, 3)],
      "новый формат поста: монеты, займ, отдача, место; «inf» и подпись канала не мешают")
check(scanner._c4_ranked(old) == [("AXS", 51.3e6, 6.7e6, 1), ("FORM", 2.3e6, 779e3, 2)], "старый формат и значок 🆕 у монеты")
check(scanner._c4_ranked("Обычный пост без таблицы\nстрока\nAAA 1 2 3") == [], "пост без B/R — не пост займов")

# ---------------------------------------------------------------- Binance, CMC, t.me — подмена
PERP = {"AAA": 1.0, "1000CCC": 0.02, "YNG": 2.0, "BBB": 5.0, "USDC": 1.0, "BTC": 90000.0, "ETH": 3000.0, "SOL": 150.0}
ONBOARD = {s: T - 400 * D for s in PERP}
ONBOARD["YNG"] = T - 12 * H                    # фьючерс моложе суток
MOVE = {}                                      # фьючерс → множитель цены после входа
PAGES = {}                                     # t.me: before → html страницы
NODATA = set()                                 # фьючерсы, по которым Binance «не отдаёт» свечи
BASKET_DOWN = [False]


def page_html(posts):
    out = []
    for pid, ts, text in posts:
        iso = scanner.datetime.fromtimestamp(ts, scanner.timezone.utc).isoformat()
        out.append(f'<div class="tgme_widget_message_wrap"><div data-post="{scanner.CHANNEL}/{pid}"><time datetime="{iso}">'
                   f'</time><div class="tgme_widget_message_text js-message_text">{text.replace(chr(10), "<br/>")}</div></div></div>')
    return "".join(out)


def post_text(rows):
    return "SYM BOR REP B/R CHNG\n------\n" + "\n".join(f"{c} {b} {r} 1 0" for c, b, r in rows)


GAPR = [None]                                  # (нижний, верхний) номера большой дыры — страницы по запросу


def fake_http(url, data=None, timeout=30, ctype=None):
    if url.startswith(f"https://t.me/s/{scanner.CHANNEL}?before="):
        x = int(url.rsplit("=", 1)[1])
        if GAPR[0] and GAPR[0][0] < x <= GAPR[0][1] + 1:
            lo_, hi_ = GAPR[0]
            return page_html([(i, T - 3 * H + (i - lo_) * 10, post_text([("GAP", "1K", "1")])) for i in range(max(lo_ - 5, x - 20), x)])
        return PAGES.get(x, "")
    raise AssertionError(url)


def kl(sym, interval, n, end_ms):
    step = 900 if interval == "15m" else H
    last_open = (end_ms + 1) // 1000 - step
    out = []
    for k in range(n - 1, -1, -1):
        o = last_open - k * step
        if o < ONBOARD.get(sym, 0):
            continue
        c = PERP[sym]
        out.append([o * 1000, c, c, c, c, 1, (o + step) * 1000 - 1, 1e6, 10, 0.5, 5e5, 0])
    return out


def fake_http_json(url, timeout=30):
    path, _, q = url.partition("?")
    p = dict(x.split("=", 1) for x in q.split("&")) if q else {}
    if path == "https://fapi.binance.com/fapi/v1/klines":
        s = p["symbol"][:-4]
        if s in NODATA:
            return None
        return kl(s, p["interval"], int(p["limit"]), int(p["endTime"]))
    if path == "https://fapi.binance.com/fapi/v1/fundingRate":
        st = int(p["startTime"]) // 1000
        return [{"fundingTime": (st // 28800 + k) * 28800 * 1000 + 1, "fundingRate": "0.0001"} for k in range(1, 94)]
    if path.startswith("https://fapi.binance.com/futures/data/"):
        name = path.rsplit("/", 1)[1]
        a, b = int(p["startTime"]) // 1000, int(p["endTime"]) // 1000
        step = 300 if p["period"] == "5m" else H
        hrs = list(range(a // step * step + (step if a % step else 0), b + 1, step))[:int(p["limit"])]
        if name == "openInterestHist":
            return [{"timestamp": h * 1000, "sumOpenInterest": "1000", "sumOpenInterestValue": "1000"} for h in hrs]
        if name == "takerlongshortRatio":
            return [{"timestamp": h * 1000, "buySellRatio": "1.1"} for h in hrs]
        return [{"timestamp": h * 1000, "longShortRatio": "1.5"} for h in hrs]
    if path == scanner.C4_RATES:
        a = int(p["startTime"]) // 1000
        return {"success": True, "data": [{"timestamp": (a // H + k) * H * 1000, "dailyInterestRate": "0.0002"}
                                          for k in range(0, 31 * 24)]}
    if path.startswith("https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"):
        return {"data": {"cryptoCurrencyList": [{"symbol": "AAA", "quotes": [{"name": "USD", "price": 1.0, "marketCap": 5e8}]},
                                                 {"symbol": "CCC", "quotes": [{"name": "USD", "price": 2e-5, "marketCap": 1e8}]}]}}
    if path == "https://fapi.binance.com/fapi/v1/ticker/24hr":
        return [{"symbol": f"{s}USDT", "quoteVolume": "1e8", "lastPrice": str(PERP[s])} for s in PERP]
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int(ONBOARD[s] * 1000), "filters": []} for s in PERP]}
    if path == "/fapi/v1/premiumIndex":
        s = params["symbol"][:-4]
        return {"markPrice": str(PERP[s] * MOVE.get(s, 1.0)), "lastFundingRate": "0.0001",
                "nextFundingTime": int((CLOCK[0] + H) * 1000)}
    if path == "/fapi/v1/ticker/price":
        if BASKET_DOWN[0]:
            return {"code": -1, "msg": "сбой"}
        return [{"symbol": f"{s}USDT", "price": str(PERP[s] * (1.02 if s not in ("AAA", "1000CCC") else MOVE.get(s, 1.0)))}
                for s in PERP]
    if path == "/fapi/v1/fundingInfo":
        return []
    if path == "/fapi/v1/fundingRate":
        return []
    if path in ("/fapi/v1/markPriceKlines", "/fapi/v1/klines"):
        s = params["symbol"][:-4]; st = int(params["startTime"]); n = int(params["limit"]); pr = PERP[s] * MOVE.get(s, 1.0)
        return [[st + i * 60000, pr, pr, pr, pr, 0, st + i * 60000 + 59999] for i in range(n)
                if st + i * 60000 + 59999 < CLOCK[0] * 1000]
    raise AssertionError(path)


scanner.http = fake_http
scanner.http_json = fake_http_json
trader._request = fake_request

# ---------------------------------------------------------------- 2. панель канала, дыра и история
P0 = T - 2 * H
fresh = [{"id": 1000 + k, "ts": P0 + 2100 + k * 300, "ranked": scanner._c4_ranked(post_text([("AAA", "1M", "100K"), ("CCC", "2M", "0")]))}
         for k in range(6)]
st = scanner._c4_load()
st["hi"] = 990                                 # бот стоял: в панели последний пост 990, свежие — с 1000
PAGES[1000] = page_html([(990 + k, P0 - (10 - k) * 300, post_text([("DDD", "5K", "1K")])) for k in range(10)])
for pid in range(1000, 900, -10):
    PAGES.setdefault(pid, "")
scanner.c4_record(fresh)
row = st["rows"].get(str(P0 + H)) or {}
check(row.get("AAA", [None])[0] == P0 + H and row["AAA"][3] == 1 and row["CCC"][3] == 2,
      "строка в отметке часа — последний пост не старше 30 мин (здесь ровно в отметку), место в посте")
check("AAA" not in (st["rows"].get(str(P0)) or {}), "посты за 35–60 мин до отметки P0 + 1 ч в отметку P0 не попадают")
check("DDD" in st["hours"] and st["hi"] == 1005, "дыра после простоя (посты 991–999) догружена со страницы t.me")
check(not st["back"], "история за 32 сут ещё не догружена — панель не готова")

# история: страницы вниз до 32 сут назад (по 20 постов, раз в час)
lo = st["lo"]; pid = lo; ts = P0 - 10 * 300 - 1200 + H    # посты в :50 — попадают в следующую отметку часа
while ts > T - 33 * D:
    rows = [(pid - 1 - k, ts - (k + 1) * H, post_text([("ZZZ", "50K", "10K"), ("AAA", "1M", "100K")])) for k in range(20)]
    PAGES[pid] = page_html(rows); pid -= 20; ts -= 20 * H
scanner.C4_BACK_PAGES = 100
scanner.c4_record([])
check(st["back"] and scanner._c4_ready(st, CLOCK[0]), "история за 32 сут догружена, панель готова")
check(os.path.exists(scanner.C4_FILE) and json.load(open(scanner.C4_FILE))["back"], "панель записана в c4_panel.json")
old_rows = {h: r for h, r in st["rows"].items() if int(h) < T - 30 * D}
for h in old_rows:
    del st["rows"][h]
check(not scanner._c4_ready(st, CLOCK[0]), "история короче 31 сут — не готова")
st["rows"].update(old_rows)
st["gaps"].append([5, 9])
check(not scanner._c4_ready(st, CLOCK[0]), "недогруженная дыра по номерам постов — не готова")
st["gaps"].clear()
quiet = [h for h in st["rows"] if T - 10 * D <= int(h) < T - 9 * D]
saved_q = {h: st["rows"].pop(h) for h in quiet}
check(scanner._c4_ready(st, CLOCK[0]), "канал молчал сутки (нет строк) — панель всё равно готова, как в бэктесте")
st["rows"].update(saved_q)
# большая дыра после простоя: больше страниц, чем за один проход, — догружается за несколько проходов
hi0 = st["hi"]; base = hi0 + 200
GAPR[0] = (hi0, base)
scanner.C4_PAGE_S = 0
scanner.c4_record([{"id": base + 1, "ts": T - 30 * 60, "ranked": scanner._c4_ranked(post_text([("AAA", "1M", "100K")]))}])
check(st["gaps"] == [[hi0, base + 1]] and st["hi"] == base + 1,
      "время на страницы за проход вышло — дыра целиком в очереди, свежий пост записан")
scanner.C4_PAGE_S = 20
scanner.C4_BACK_PAGES = 4
scanner.c4_record([{"id": base + 1, "ts": T - 30 * 60, "ranked": scanner._c4_ranked(post_text([("AAA", "1M", "100K")]))}])
check(st["gaps"] and st["gaps"][0][0] == hi0, "дыра больше 4 страниц — за проход заполнена частично, осталась в очереди")
scanner.c4_record([])
scanner.c4_record([])
check(not st["gaps"] and json.load(open(scanner.C4_FILE))["gaps"] == [], "следующие проходы догрузили дыру до конца")
scanner.C4_BACK_PAGES = 100

# ---------------------------------------------------------------- 3. признаки и голоса
c4f = scanner.c4_features
st["rows"].setdefault(str(T), {})["AAA"] = [T - 60, 1e6, 1e5, 1, 1]
F0 = c4f(T, "AAA", "AAA", st, None, None, None, None, None, [], None, None, 0)
check(F0 is not None and "r4" not in F0 and "doi4" not in F0 and F0.get("wave") == 0, "пустые данные — признаки без падения")
check(c4f(T, "NONE", "NONE", st, None, None, None, None, None, [], None, None, 0) is None, "монеты нет в отметке T — None")
for h in range(T - 30 * D, T + 1, H):
    st["rows"].setdefault(str(h), {})["AAA"] = [h - 60, 1e6, 1e5, 1, 1]
    st["hours"].setdefault("AAA", set()).add((h - 60) // H)
k15 = kl("AAA", "15m", 700, T * 1000 - 1); k1h = kl("AAA", "1h", 750, T * 1000 - 1)
fund = [(T - k * 8 * H, 0.0001) for k in range(93, -1, -1)]
met = {h: (1000.0, 1000.0, 1.5, 1.5) for h in range(T - H - 31 * D, T, H)}
rates = [(T - 31 * D + k * H, 0.0002) for k in range(31 * 24)]
F = c4f(T, "AAA", "AAA", st, k15, k1h, fund, met, 1.1, rates, 5e8, (90000.0, 88000.0), 3)
check(F["r4x"] == 1.0 and F["r24x"] == 1.0 and abs(F["net7"] - 7 * 9e5) < 1e-6 and F["pres7"] == 168 and F["run"] >= 168,
      "займ: отдача к 4 ч и суткам назад, набор за 7 сут, часы в канале")
check(F["r4"] == 0 and F["qvx"] == 1.0 and F["tb4"] == 0.5 and abs(F["bmc"] - 1e6 / 5e8) < 1e-12 and F["doi4"] == 0
      and F["dlsr24"] == 0 and abs(F["btc24"] - 90000 / 88000 + 1) < 1e-12 and F["f8"] == 0.0001 and F["tkr"] == 1.1,
      "цена, оборот, покупки, капитализация, OI, лонг/шорт, BTC, фандинг, тейкеры")
check(F.get("zbor") == 0.0 and F.get("ux") == 1.0 and F.get("zrate") == 0.0 and F.get("lim") == 0.0,
      "признаки к 30 сут монеты и загрузка пула")


def satisfying(nv):
    """Признаки, при которых выполнены первые подходящие правила (без противоречий), — пока голосов не станет nv."""
    f = {}
    for rule in scanner.C4_RULES:
        g = dict(f)
        ok = True
        for name, op, q in rule:
            v = q + (1e-3 + abs(q) * 1e-3) * (1 if op == "ge" else -1)
            if name in g and not (g[name] >= q if op == "ge" else g[name] <= q):
                ok = False; break
            g.setdefault(name, v)
        if ok:
            f = g
        if scanner.c4_votes(f) >= nv:
            return f
    return f


good = satisfying(3)
check(scanner.c4_votes(good) >= 3 and scanner.c4_votes({}) == 0, "голосование: ≥ 3 правил выполнено; пусто — 0")

# ---------------------------------------------------------------- 4. правило: окно, вход, повтор
FEATS = {"AAA": dict(good, bor=1e6, doi4=0.03, dlsr24=0.2), "1000CCC": dict(good, bor=2e6), "BBB": {"bor": 1.0}}
scanner.c4_features = lambda T_, coin, fs, st_, *a: FEATS.get(fs, {"bor": 1.0})
for c in ("CCC", "BBB", "USDC", "YNG", "NOFUT"):
    st["rows"][str(T)][c] = [T - 60, 1e6, 1e5, 3, 1]
CLOCK[0] = T + 30
check(scanner.c4_rule({}) == [], "раньше 1 мин после отметки — не проверяем")
state = {}
CLOCK[0] = T + 25 * 60
check(scanner.c4_rule(state) == [], "позже 20 мин после отметки — окно прошло")
CLOCK[0] = T + 120
NODATA.add("BBB")
msgs = scanner.c4_rule(state)
tr = {t["sym"]: t for t in state.get("virtual_C4", {}).get("trades", [])}
check(len(msgs) == 1 and set(tr) == {"AAA", "1000CCC"} and "🗳" in msgs[0], "вход по AAA и 1000CCC одним сообщением")
check(all(t["hold_h"] == 4.0 and abs(t["sl"] / t["entry"] - 1.10) < 1e-9 and t.get("alt_px") for t in tr.values()),
      "шорт 4 ч, стоп +10%, корзина альтов записана в сделку")
check("YNG" not in tr and "USDC" not in tr and not state["c4"]["done"], "молодой фьючерс и стейблкоин — мимо; BBB без данных — ждём")
check(len(tr["AAA"]["alt_px"]) == len([s for s in PERP if s != "BTC"]) and "BTCUSDT" not in tr["AAA"]["alt_px"],
      "корзина — все фьючерсы с оборотом ≥ 5 млн $, кроме BTC")
for _ in range(6):
    CLOCK[0] += 60; scanner.c4_rule(state)
check(state["c4"]["done"] and len(state["virtual_C4"]["trades"]) == 2, "после 6 попыток окно закрыто, повторных входов нет")
NODATA.clear()
CLOCK[0] += 60
check(scanner.c4_rule(state) == [], "окно отработано — второй проход ничего не делает")

# ---------------------------------------------------------------- 5. выход через 4 ч, балансы, стоп, нет цен корзины
MOVE["1000CCC"] = 0.97                         # шорт в плюсе на 3%, корзина +2%
CLOCK[0] = T + 120 + 4 * H + 10
out = trader.virt_manage(state)
v = state["virtual_C4"]
cl = [t for t in v["trades"] if t.get("closed")]
check(len(cl) == 2 and len([m for m in out if "🗳 закрыто виртуально" in m]) == 1, "два выхода по времени — одно сообщение")
m = next(m for m in out if "🗳 закрыто виртуально" in m)
check("с хеджем корзиной альтов" in m and "баланс" in m.splitlines()[-1], "в сообщении — хедж корзиной и балансы")
t = next(t for t in cl if t["sym"] == "1000CCC")
bs = [s for s in PERP if s != "BTC"]
exp = sum((1.02 if s not in ("AAA", "1000CCC") else MOVE.get(s, 1.0)) - 1 for s in bs) / len(bs)   # корзина — и сами монеты
check(abs(t["alt_ret"] - exp) < 1e-9 and abs(t["alt_usdt"] - 1 * (exp - 0.001)) < 1e-9 and "alt_px" not in t,
      "хедж корзиной: среднее изменение цен корзины минус комиссия; цены корзины из сделки убраны")
start = trader.VIRT["start_balance"]
check(abs(v["balance_a"] - (start + sum(x["pnl_usdt"] + x["alt_usdt"] for x in cl))) < 1e-6 and "balance_h" in v,
      "третий баланс = старт + доход сделок + хедж корзиной; второй (BTC) ведётся")
blk = trader.virt_text(state)
check("🗳" in blk and "баланс с хеджем корзиной альтов" in blk, "блок 🗳 в /virtual с третьим балансом")
# стоп +10% и нет цен корзины при закрытии
MOVE.clear(); CLOCK[0] = T + 8 * H + 120
st["rows"][str(T + 8 * H)] = {"AAA": [T + 8 * H - 60, 1e6, 1e5, 1, 2]}
for h in range(T + H, T + 8 * H, H):
    st["rows"].setdefault(str(h), {"ZZZ": [h - 60, 5e4, 1e4, 1, 3]})
scanner.c4_rule(state)
op = [t for t in state["virtual_C4"]["trades"] if not t.get("closed")]
check(len(op) == 1 and op[0]["sym"] == "AAA", "следующее окно (08:00) — новый вход по AAA")
MOVE["AAA"] = 1.12; BASKET_DOWN[0] = True
CLOCK[0] += 600
out = trader.virt_manage(state)
t = op[0]
check(t.get("closed") and t["reason"] == "стоп" and t.get("alt_na") and not t.get("a_bal"),
      "цена +12% — стоп; цен корзины нет — сделка без хеджа корзиной")
check("без хеджа корзиной (нет цен) сделок 1" in trader.virt_text(state), "в /virtual — сколько сделок без хеджа корзиной")
print("Все проверки пройдены.")
