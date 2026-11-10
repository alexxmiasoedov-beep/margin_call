"""Сквиз-вето для шорт-журналов (research/s19, проверка 1). На входе каждой сделки — признаки «шорт на монете, которую
некому откупить» из китайских разборов (s19, пороги заданы заранее, не подбирались):
  F  фандинг на последнем начислении, пересчитанный на 8 ч, ≤ −0,1%            (Jonas, Odaily 2023; s11)
  FX минимум фандинга за сутки ≤ −0,75% за 8 ч                                (Jonas: «рост ускоряется»)
  OI рост открытого интереса за 24 ч ≥ +50%                                   (Jonas)
  I  интервал фандинга укорочен за последние 72 ч (8 → 4 → 1 ч)               (s3, s11)
  S  у монеты нет спота Binance к USDT на момент входа                        (PANews, s3)
  B  открытый интерес в монетах ≥ остатка токена на кошельках Binance (DefiLlama), поисково: только если токен
     отслеживается ≥ 30 суток до сделки и остаток > 0                         (разбор RAVE, 102,9%)
Журналы (бэктесты прошлых раундов): 🇰🇷🆕 (s15), 🇰🇷 (s15/s16, тейк 10 / стоп 25 / 48 ч), сигнал канала (s16, 15 / 25 / 24 ч),
📢 и 🆕 (s12), 🏦 (s13, только шорт). Для каждого — сделки с вето и без: число, средняя, итог, доля стопов, худшие 5%,
просадка, половины. Хорошее вето срезает хвост убытков, не роняя итог.

Данные: s2/k2y.pkl, s2/fund2y.pkl (+ фандинг 09–10.2026, common.funding), 5-мин метрики фьючерсов data.binance.vision
(кэш s20/metrics/), остатки Binance — DefiLlama protocol/binance-cex (s20/binance_cex.json), даты спота — список файлов
архива спота (кэш s20/spot_first.json). Запуск из папки с данными: python3 s20/veto.py"""
import datetime
import io
import json
import os
import pickle
import re
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s16", "s13"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import BAR, K, funding, fut_of, live, trade

UTC = datetime.timezone.utc
DAY = 86400
PREF = re.compile(r"^(1000000|100000|10000|1000)")


# ---------------------------------------------------------------- сделки журналов
def journals():
    J = {}
    r = pd.read_pickle("s15/kr_journal.pkl")
    J["🇰🇷🆕"] = pd.DataFrame(dict(s=r.sym, te=r.t0, net=r.net, stop=r.why == "стоп"))
    import kr_raid
    S = kr_raid.kr_signals(); S = S[S.share >= 0.20]
    rows = [dict(s=e.s, te=float(K[e.s]["t"][e.j]) + BAR, net=x["net"], stop=x["why"] == "стоп")
            for e in S.itertuples() if (x := trade(e.s, e.j, tp=0.10, sl=0.25, hold_h=48))]
    J["🇰🇷"] = pd.DataFrame(rows)
    import channel_korea
    E = channel_korea.channel_signals()
    rows = [dict(s=e.s, te=float(K[e.s]["t"][e.j]) + BAR, net=x["net"], stop=x["why"] == "стоп")
            for e in E.itertuples() if (x := trade(e.s, e.j, tp=0.15, sl=0.25, hold_h=24))]
    J["канал"] = pd.DataFrame(rows)
    f = pd.read_pickle("s12/final_journals.pkl")
    J["📢"] = pd.DataFrame(dict(s=f["B"].s, te=f["B"].te, net=f["B"].sp, stop=f["B"].sp <= -0.24))
    J["🆕"] = pd.DataFrame(dict(s=f["A"].s, te=f["A"].te, net=f["A"].sp, stop=f["A"].sp <= -0.59))
    import bf_take
    b = bf_take.journal(tp=None, policy="A", stop_on=True)
    J["🏦"] = pd.DataFrame(dict(s=b.s, te=b["T"], net=b.p, stop=b.why == "стоп"))
    return {k: v.reset_index(drop=True) for k, v in J.items()}


# ---------------------------------------------------------------- открытый интерес (5 мин)
def metrics_day(sym, day):
    path = f"s20/metrics/{sym}/{day}.npy"
    if os.path.exists(path):
        return np.load(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day}.zip"
    arr = np.zeros((0, 3))
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                p = ln.split(",")
                if len(p) >= 4 and p[2] and p[3]:
                    t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                    rows.append((t, float(p[2]), float(p[3])))
            arr = np.array(rows) if rows else arr
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break
        except Exception:
            pass
    np.save(path, arr)
    return arr


def oi_series(sym, t0, t1):
    days = sorted({datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d") for t in list(np.arange(t0, t1, DAY)) + [t1]})
    a = [metrics_day(sym, d) for d in days]
    a = [x for x in a if len(x)]
    return np.concatenate(a) if a else np.zeros((0, 3))


def oi_at(arr, t):
    """Последнее значение, известное к t: строка с меткой create_time описывает 5 мин до create_time + 300 с."""
    k = int(np.searchsorted(arr[:, 0] + 300, t, side="right")) - 1 if len(arr) else -1
    return arr[k] if k >= 0 and t - arr[k, 0] < 3 * 3600 else None


# ---------------------------------------------------------------- спот Binance, остатки DefiLlama
def spot_first(coins):
    path = "s20/spot_first.json"
    have = json.load(open(path)) if os.path.exists(path) else {}
    todo = [c for c in coins if c not in have]

    def first(c):
        for name in (c, PREF.sub("", c)):
            url = f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/spot/monthly/klines/{name}USDT/1d/&max-keys=3"
            try:
                xml = urllib.request.urlopen(url, timeout=60).read().decode()
            except Exception:
                return None
            keys = re.findall(r"<Key>[^<]*-1d-(\d{4}-\d{2})\.zip</Key>", xml)
            if keys:
                return min(keys)
        return ""

    with ThreadPoolExecutor(12) as pool:
        for c, v in zip(todo, pool.map(first, todo)):
            if v is not None:
                have[c] = v
    json.dump(have, open(path, "w"))
    return have


def balances():
    d = json.load(open("s20/binance_cex.json"))
    pts = d["tokens"]
    T = np.array([p["date"] for p in pts], dtype=float)
    first, ser = {}, {}
    for i, p in enumerate(pts):
        for k, v in p["tokens"].items():
            first.setdefault(k, T[i])
            ser.setdefault(k, {})[i] = v
    return T, first, ser


# ---------------------------------------------------------------- признаки на входе
def features(J):
    pairs = sorted({(s, te) for j in J.values() for s, te in zip(j.s, j.te)})
    syms = sorted({s for s, _ in pairs})
    need = sorted({(s, datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")) for s, te in pairs
                   for t in (te - DAY - 3600, te - DAY, te)})
    print(f"сделок {sum(len(j) for j in J.values())}, пар монета-время {len(pairs)}, файлов метрик {len(need)}", flush=True)
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(lambda x: metrics_day(*x), need))
    SP = spot_first(sorted({PREF.sub("", s) for s in syms} | set(syms)))
    BT, BF, BS = balances()
    out = {}
    for s, te in pairs:
        fr = funding(s)                                       # [время, ставка] по 10.2026
        ft = fr[:, 0] if len(fr) else np.zeros(0)
        k = int(np.searchsorted(ft, te, side="right")) - 1
        f8 = fmin = np.nan; short = False
        if k >= 1:
            gap = lambda i: max(1.0, round((ft[i] - ft[i - 1]) / 3600))
            f8 = fr[k, 1] * 8 / gap(k)
            ks = np.flatnonzero((ft > te - DAY) & (ft <= te))
            fmin = min(fr[i, 1] * 8 / gap(i) for i in ks if i >= 1) if len(ks) else f8
            k3 = int(np.searchsorted(ft, te - 3 * DAY, side="right")) - 1
            short = k3 >= 1 and gap(k) < gap(k3)
        arr = oi_series(s, te - DAY - 3600, te)
        o0, o24 = oi_at(arr, te), oi_at(arr, te - DAY)
        oi24 = o0[1] / o24[1] - 1 if o0 is not None and o24 is not None and o24[1] > 0 else np.nan
        coin = PREF.sub("", s); mult = float(s[:len(s) - len(coin)] or 1)
        ratio = np.nan
        if o0 is not None and coin in BF and BF[coin] <= te - 30 * DAY:
            i = int(np.searchsorted(BT, te - DAY, side="right")) - 1
            bal = BS[coin].get(i, 0.0)
            if bal > 0:
                ratio = o0[1] * mult / bal
        sp = SP.get(s) or SP.get(coin) or ""
        has_spot = bool(sp) and sp <= datetime.datetime.fromtimestamp(te, UTC).strftime("%Y-%m")
        out[(s, te)] = dict(f8=f8, fmin=fmin, short_int=short, oi24=oi24, oib=ratio, spot=has_spot, oi_ok=o0 is not None)
    return out


VETO = {
    "F фандинг ≤ −0,1%/8 ч": lambda x: x.f8 <= -0.001,
    "FX минимум за сутки ≤ −0,75%": lambda x: x.fmin <= -0.0075,
    "OI рост за 24 ч ≥ +50%": lambda x: x.oi24 >= 0.5,
    "I интервал фандинга укорочен": lambda x: x.short_int,
    "S нет спота Binance": lambda x: ~x.spot,
    "B OI ≥ остатка на Binance": lambda x: x.oib >= 1.0,
}


def stats(d):
    if not len(d):
        return dict(n=0)
    v = d.net.sort_values()
    eq = d.sort_values("te").net.cumsum()
    return dict(n=len(d), mean=d.net.mean(), total=d.net.sum(), stops=d.stop.mean(), worst5=v.iloc[:max(1, len(v) // 20)].mean(),
                dd=float((eq - np.maximum.accumulate(np.r_[0, eq.values])[1:]).min()))


def fmt(st):
    if not st.get("n"):
        return "нет сделок"
    return (f"n={st['n']:4d} | {st['mean'] * 100:+5.2f}% | итог {st['total']:+6.2f} | стопов {st['stops']:4.0%} | "
            f"худшие 5% {st['worst5'] * 100:+6.1f}% | просадка {st['dd']:+5.2f}")


if __name__ == "__main__":
    J = journals()
    FE = features(J)
    rows = []
    for name, j in J.items():
        X = pd.DataFrame([FE[(s, te)] for s, te in zip(j.s, j.te)])
        j = pd.concat([j, X], axis=1)
        cut = j.te.median()
        print(f"\n===== {name}: {fmt(stats(j))}; есть OI у {j.oi_ok.mean():.0%}, мера B у {j.oib.notna().mean():.0%} сделок")
        for vn, f in list(VETO.items()) + [("любое из F, FX, OI, I, S", None), ("любое, включая B", None)]:
            if f is None:
                m = np.zeros(len(j), bool)
                for k2, g in VETO.items():
                    if k2.startswith("B") and vn.startswith("любое из"):
                        continue
                    m |= np.asarray(g(j).fillna(False), bool)
            else:
                m = np.asarray(f(j).fillna(False) if hasattr(f(j), "fillna") else f(j), bool)
            kept, cut_ = j[~m], j[m]
            h1, h2 = kept[kept.te < cut], kept[kept.te >= cut]
            print(f"  вето {vn:30s} убрано {m.sum():4d}: у убранных {cut_.net.mean() * 100 if len(cut_) else float('nan'):+6.2f}% "
                  f"(стопов {cut_.stop.mean() if len(cut_) else float('nan'):.0%}) | осталось: {fmt(stats(kept))} | "
                  f"половины {h1.net.mean() * 100:+.2f}/{h2.net.mean() * 100:+.2f}%")
            rows.append(dict(journal=name, veto=vn, removed=int(m.sum()), removed_mean=cut_.net.mean() if len(cut_) else np.nan,
                             **{f"kept_{k}": v for k, v in stats(kept).items()}, **{f"all_{k}": v for k, v in stats(j).items()}))
    pd.DataFrame(rows).to_pickle("s20/veto_results.pkl")
