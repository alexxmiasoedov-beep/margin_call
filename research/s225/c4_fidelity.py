"""Сверка журнала 🗳 (scanner.c4_features, c4_votes, панель канала _c4_add/_c4_wave) с бэктестом s225 на архиве.

Бот строит панель канала из тех же строк постов (s7/margin.pkl: время, займ, отдача, место), получает архивные данные
в виде ответов Binance (15-мин и часовые свечи из s2/k2y.pkl, фандинг s15/common.funding, метрики s22/metrics_full,
ставки s11/rates) и капитализацию бэктеста (займ / bmc). Для выборки наблюдений s225_feat.pkl сравниваются все 47
признаков комитета и голоса (выполнено ≥ 3 правил).
Запуск из /home/user/mc_data: python3 <repo>/research/s225/c4_fidelity.py [число наблюдений]"""
import glob
import os
import pickle
import random
import sys
import tempfile

import numpy as np
import pandas as pd

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
for p in ("s15", "s216"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import scanner, trader  # noqa: E402
scanner.log = lambda *a: None

H, D = 3600, 86400
K = pickle.load(open("s2/k2y.pkl", "rb"))
import common  # noqa: E402  (фандинг)
LIVE = {s: common.live(s)[0] for s in K}
LIVE = {s: v for s, v in LIVE.items() if np.isfinite(v)}        # без единой свечи с оборотом — фьючерса «нет»


def fut_of(coin):
    """Фьючерс монеты канала как в research/s15/common.fut_of."""
    for p in ("", "1000", "1000000"):
        if p + coin in K:
            return p + coin
    return None


trader.contract = lambda fs: {"onboard": int(LIVE[fs])} if fs in LIVE else None   # «жив с» — первая свеча с оборотом


def build_panel():
    M = pickle.load(open("s7/margin.pkl", "rb"))["G"]
    posts = {}
    for coin, g in M.items():
        for t, b, r, br, rank in g:
            posts.setdefault(float(t), []).append((coin, float(b), float(r), int(rank)))
    st = {"rows": {}, "hours": {}, "lo": None, "hi": None, "back": True, "dirty": False}
    for pid, t in enumerate(sorted(posts)):
        rk = sorted(posts[t], key=lambda x: x[3])
        scanner._c4_add(st, pid, t, rk)
    return st


def klines(s, T):
    a = K[s]; t = a["t"].astype(np.int64)
    i = int(np.searchsorted(t, T - 900))
    if i >= len(t) or t[i] != T - 900:
        return None, None
    k15 = [[int(t[j]) * 1000, 0, 0, 0, float(a["c"][j]), 0, 0, float(a["qv"][j]), 0, 0, float(a["tb"][j]), 0]
           for j in range(max(0, i - 699), i + 1)]
    # часовые свечи из 15-мин: закрытие часа — закрытие 15-мин свечи на отметке часа, оборот — сумма четырёх
    k1h = []
    for j in range(max(0, i - 750 * 4), i + 1):
        if (int(t[j]) + 900) % H == 0:
            k1h.append([int(t[j]) + 900 - H, 0, 0, 0, float(a["c"][j]), 0, 0, float(a["qv"][max(0, j - 3):j + 1].sum()), 0, 0, 0, 0])
    k1h = [[x[0] * 1000] + x[1:] for x in k1h]
    return k15, k1h


_met = {}


def metrics(s, T):
    if s not in _met:
        fl = sorted(glob.glob(f"s22/metrics_full/{s}/*.npy"))
        arr = [x for x in (np.load(f) for f in fl) if len(x)]
        _met[s] = np.vstack(arr)[np.argsort(np.vstack(arr)[:, 0])] if arr else np.zeros((0, 7))
    a = _met[s]
    m = (a[:, 0] <= T - H) & (a[:, 0] >= T - H - 32 * D)
    met = {int(r[0]): (r[1], r[2], r[4], r[5]) for r in a[m]}
    met = {k: tuple(None if (x is None or x != x) else float(x) for x in v) for k, v in met.items()}
    met = {k: v for k, v in met.items() if v[0] is not None}
    row = a[a[:, 0] == T - H]
    tkr = float(row[0, 6]) if len(row) and row[0, 6] == row[0, 6] else None
    return met, tkr


def rates(s, T):
    c = scanner.re.sub(r"^(1000000|1000|1M)", "", s) if not scanner.re.match(r"^(1000000|1000|1M)\d", s) else s
    p = f"s11/rates/{c}.csv"
    if not os.path.exists(p):
        return []
    a = np.loadtxt(p, delimiter=",", ndmin=2)
    if not len(a):
        return []
    m = (a[:, 0] >= T - 31 * D) & (a[:, 0] <= T)
    prev = a[a[:, 0] < T - 31 * D]
    rows = ([(int(prev[-1, 0]), float(prev[-1, 1]))] if len(prev) else []) + [(int(x), float(y)) for x, y in a[m]]
    return rows


def main(n):
    F = pd.read_pickle("s225_feat.pkl")
    FE = sorted({f for r in scanner.C4_RULES for f, _, _ in r})
    st = build_panel()
    inv = {}
    for coin in st["hours"]:
        fs = fut_of(coin)
        if fs:
            inv.setdefault(fs, coin)
    random.seed(7)
    idx = random.sample(range(len(F)), min(n, len(F)))
    bt = K["BTC"]["t"].astype(np.int64) + 900; bc = K["BTC"]["c"].astype(float)
    res, vb, vr = [], [], []
    for i in idx:
        r = F.iloc[i]; s, T = r.s, int(r["T"])
        coin = inv.get(s)
        if coin is None or s not in K:
            continue
        k15, k1h = klines(s, T)
        fr = common.funding(s)
        fund = [(int(x), float(y)) for x, y in fr if T - 31 * D <= x <= T]
        met, tkr = metrics(s, T)
        mcap = r.bor / r.bmc if r.bmc == r.bmc and r.bmc and r.bmc > 0 else None
        ib = int(np.searchsorted(bt, T, "right")) - 1; jb = int(np.searchsorted(bt, T - D, "right")) - 1
        wave = scanner._c4_wave(st, T, fut_of)
        Fb = scanner.c4_features(T, coin, s, st, k15, k1h, fund, met, tkr, rates(s, T), mcap, (bc[ib], bc[jb]), wave)
        if Fb is None:
            res.append({"s": s, "T": T, "none": True}); continue
        row = {"s": s, "T": T}
        for f in FE:
            a, b = Fb.get(f), r[f]
            a = np.nan if a is None else float(a)
            row[f] = (np.isnan(a) and np.isnan(b)) or (np.isfinite(a) and np.isfinite(b) and abs(a - b) <= 1e-6 * max(1.0, abs(b)))
        res.append(row)
        vb.append(scanner.c4_votes(Fb))
        vr.append(scanner.c4_votes({f: (None if r[f] != r[f] else float(r[f])) for f in FE}))
    R = pd.DataFrame(res)
    print(f"наблюдений {len(R)}, без строки панели в боте {int(R.get('none', pd.Series(dtype=bool)).fillna(False).sum())}")
    ok = R.drop(columns=[c for c in ("s", "T", "none") if c in R]).dropna(how="all")
    for f in FE:
        if f in ok:
            print(f"  {f:8s} совпало {ok[f].mean():6.1%}")
    vb, vr = np.array(vb), np.array(vr)
    print(f"голоса: совпали {np.mean(vb == vr):.1%}; вход (≥ 3): бот {int((vb >= 3).sum())}, бэктест {int((vr >= 3).sum())}, "
          f"совпали решения {np.mean((vb >= 3) == (vr >= 3)):.1%}")
    R.to_pickle(os.path.join(TMP, "fid.pkl"))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
