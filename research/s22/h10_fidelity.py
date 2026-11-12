"""Сверка журнала 🅱️ в боте с бэктестом h10_ann.py. Правило бота (scanner.spot_listing_rule) идёт по архиву объявлений
s10/ann.pkl (те же разделы 48/49/161, что опрашивает бот): каждое объявление бот «видит» через минуту после публикации,
state["ann_list"] ведётся как в ann_poll, проход на закрытии часа — через 30 с. Список фьючерсов — как в боте: загружается
один раз и перезагружается, если фьючерс монеты не найден (не чаще раза в 10 мин); фьючерс в списке — пока по нему есть
свечи с объёмом (s2/k2y.pkl), «onboard» — первая такая свеча (в бэктесте — она же). Сделка закрывается через 30 суток.
Сравниваются входы (фьючерс, час) с событиями s22/h10_ann.pkl. Второй прогон — «холодный старт»: правило включается в
разные дни; о прошлом бот знает из ann_list (листинги и HODLer за 40 суток) и разовой загрузки двух страниц разделов 48
и 49 (_bl_seed) — сколько входов за первые 30 суток расходятся с бэктестом. Запуск из папки с данными: python3 <репозиторий>/research/s22/h10_fidelity.py"""
import os
import sys
import tempfile
import time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json"); os.environ["POSITION_USDT"] = "1"
from common22 import DAY, H, K, live                                 # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner, trader                                               # noqa: E402

CLOCK = [0.0]
time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append((CLOCK[0], " ".join(map(str, a))))
LIVE = {s: live(s) for s in K}
LOADS = [0]


def fake_request(method, path, params=None, signed=True, **kw):
    assert path == "/fapi/v1/exchangeInfo", path
    LOADS[0] += 1
    return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                         "onboardDate": int(lo * 1000), "filters": []} for s, (lo, hi) in LIVE.items() if lo <= CLOCK[0] <= hi]}


def fake_open(state, key, sym, rule, note, price=None):
    v = state.setdefault(key, {"trades": []}); now = CLOCK[0]
    for t in v["trades"]:
        if not t.get("closed") and now >= t["opened"] + 720 * H:
            t["closed"] = t["opened"] + 720 * H
    lo, hi = LIVE.get(sym, (np.inf, -np.inf))
    if any(t["sym"] == sym and not t.get("closed") for t in v["trades"]) or not lo <= now <= hi:
        return None                                                  # сделка открыта / фьючерс не торгуется — нет цены
    v["trades"].append({"sym": sym, "opened": now})
    return f"🅱️ {sym}"


trader._request = fake_request
trader.virt_open = fake_open
BYCAT = {}                                                           # раздел → объявления от новых к старым (для _bl_seed)


def fake_ann_get(url):
    q = dict(kv.split("=") for kv in url.split("?", 1)[1].split("&"))
    cat, page, size = int(q["catalogId"]), int(q["pageNo"]), int(q["pageSize"])
    arts = [a for a in BYCAT.get(cat, []) if a["ts"] <= CLOCK[0]][(page - 1) * size:page * size]
    return {"catalogs": [{"articles": [{"code": a["code"], "title": a["title"], "releaseDate": int(a["ts"] * 1000)} for a in arts]}]}


scanner._ann_get = fake_ann_get


def replay(arts, state, t_end=np.inf):
    """Прогон правила по объявлениям arts (по времени); возвращает входы [(фьючерс, час)]."""
    lst = state.setdefault("ann_list", {})
    def pending():
        ts = [max(w["T"], w.get("next", 0)) for w in state.get("bl_wait", {}).values()]
        return min(ts) + 30 if ts else np.inf
    for a in arts:
        ta = a["ts"] + 60
        while pending() <= ta:
            CLOCK[0] = pending(); scanner.spot_listing_rule(state, [])
        CLOCK[0] = ta
        for c in scanner._listing_coins(a["title"]):                 # как ann_poll: листинги и HODLer, 40 суток
            lst[c] = min(lst.get(c, a["ts"]), a["ts"])
        for k in [k for k, ts in lst.items() if ts < ta - 40 * DAY]:
            del lst[k]
        scanner.spot_listing_rule(state, [a])
    while pending() < min(t_end, np.inf):
        CLOCK[0] = pending(); scanner.spot_listing_rule(state, [])
    return [(t["sym"], int(t["opened"] // H * H)) for t in state.get("virtual_BL", {}).get("trades", [])]


if __name__ == "__main__":
    A = pd.read_pickle("s10/ann.pkl")
    arts = sorted(({"code": a["code"], "title": a["title"], "ts": int(a["ts"]) / 1000, "cat": a["cat"]} for a in A.values()),
                  key=lambda a: a["ts"])
    E = pd.read_pickle("s22/h10_ann.pkl")
    bt = set(zip(E.s, E["T"].astype(int)))
    for a in sorted(arts, key=lambda a: -a["ts"]):
        BYCAT.setdefault(a["cat"], []).append(a)
    trader._contracts.clear()
    got = replay(arts, {"bl_seeded": 1})                             # с начала архива — как бот, работающий всё время
    bot = set(got)
    print(f"объявлений {len(arts)} ({pd.to_datetime(arts[0]['ts'], unit='s'):%d.%m.%Y}–{pd.to_datetime(arts[-1]['ts'], unit='s'):%d.%m.%Y}), "
          f"загрузок списка фьючерсов {LOADS[0]}")
    print(f"входов бота {len(got)}, событий бэктеста {len(bt)}, совпали {len(bot & bt)}")
    for nm, d in (("только в боте", sorted(bot - bt, key=lambda x: x[1])), ("только в бэктесте", sorted(bt - bot, key=lambda x: x[1]))):
        for s, T in d:
            why = [l for t, l in LOG if s.lstrip("0123456789") in l or s in l][-3:]
            print(f"  {nm}: {s} {pd.to_datetime(T, unit='s'):%d.%m.%Y %H:%M}" + "".join(f"\n      {w}" for w in why))
    # холодный старт: правило включено в день D — о прошлом знает ann_list (как вёл бы ann_poll за 40 суток до D) и разовая
    # загрузка _bl_seed (две страницы разделов 48 и 49 на момент первого прохода)
    t0 = max(arts[0]["ts"], min(lo for lo, hi in LIVE.values())) + 45 * DAY        # с начала архива свечей (10.2024)
    t1 = arts[-1]["ts"] - 31 * DAY
    diff, n_ev = [], 0
    for D in np.arange(t0, t1, 7 * DAY):
        lst = {}
        for a in arts:
            if D - 40 * DAY <= a["ts"] < D:
                for c in scanner._listing_coins(a["title"]):
                    lst[c] = min(lst.get(c, a["ts"]), a["ts"])
        trader._contracts.clear()
        g = set(replay([a for a in arts if D <= a["ts"] < D + 30 * DAY], {"ann_list": lst}))
        b = {(s, T) for s, T in bt if D + 60 <= T and T < D + 30 * DAY + H}
        g = {(s, T) for s, T in g if T < D + 30 * DAY + H}
        n_ev += len(b)
        if g != b:
            diff.append((pd.to_datetime(D, unit="s").strftime("%d.%m.%Y"), sorted(g - b), sorted(b - g)))
    print(f"\nхолодный старт: запусков {len(np.arange(t0, t1, 7 * DAY))}, событий бэктеста в первые 30 суток {n_ev}, "
          f"запусков с расхождением {len(diff)}")
    for D, extra, miss in diff[:15]:
        print(f"  {D}: лишние {[(s, pd.to_datetime(T, unit='s').strftime('%d.%m %H:%M')) for s, T in extra]} "
              f"пропущены {[(s, pd.to_datetime(T, unit='s').strftime('%d.%m %H:%M')) for s, T in miss]}")
