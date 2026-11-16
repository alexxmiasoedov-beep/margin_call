"""s34 — «знающие» счета Hyperliquid: открывают ли счета пулов s27 позиции в нужную сторону до объявлений (гипотезы —
ВЫВОДЫ.md, записаны до проверки). Позиции — s27/pos.pkl (hl_positions.py): открытия (время, монета, сторона, счёт).
События (с 01.12.2024, монета есть на Hyperliquid хотя бы сутки и на фьючерсах Binance):
- объявления Binance (s10/ann.pkl): листинг спота, HODLer, Launchpool, Megadrop, «Will Add … Margin» → лонг;
  делистинг спота и фьючерса, Monitoring Tag → шорт; окно — 24 ч до публикации;
- корейские листинги (s15/kr_listings.pkl) → лонг, окно с T − 24 ч до T − 4 ч от первой сделки;
- корейские предупреждения и делистинги (s26/events.pkl) → шорт, окно — 24 ч до поста.
Попадание — открытие в нужную сторону в окне; ожидание — те же окна на 7/14/21 сут раньше; контроль — обратная сторона.
Г4а — суммы; Г4б — отбор счетов в первой половине (≥ 3 попаданий, Пуассон p < 1%), проверка во второй, плацебо отбора
(«событие» на 7 сут раньше, ожидание — 14/21/28 сут). Г4в — следование за отобранными во второй половине (24 и 72 ч к рынку).
Запуск из папки с данными, после hl_positions.py. Итог — s34/insiders.pkl."""
import os
import pickle
import re
import sys
import numpy as np, pandas as pd
from scipy.stats import poisson

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import fut_of  # noqa: E402

DAY, H = 86400, 3600
CUT = 1764547200
T_FROM = 1733011200                                         # 01.12.2024
SHIFTS = (0, 7, 14, 21, 28)
P = pickle.load(open("s27/pos.pkl", "rb"))
CIDX = P["cidx"]; FIRST = P["first"]; ADDRS = P["addrs"]
CSTART = {}
for (_a, _s), (_tt, _pp) in P["series"].items():
    CSTART[_s] = min(CSTART.get(_s, np.inf), float(_tt[1]))
OPEN = {}                                                   # (счёт, монета, сторона) → времена открытий
for t, ci, d, ai in P["opens"]:
    OPEN.setdefault((int(ai), int(ci), int(d)), []).append(t)
OPEN = {k: np.sort(np.array(v)) for k, v in OPEN.items()}
BY_COIN = {}
for (ai, ci, d) in OPEN:
    BY_COIN.setdefault((ci, d), []).append(ai)
FIRST_I = {i: FIRST.get(a, np.inf) for i, a in enumerate(ADDRS)}


def tickers_after(title, word):
    part = title.split(word, 1)[1]
    part = re.split(r"\bon\b|\bPerpetual\b|\(", part)[0]
    out = []
    for x in re.findall(r"\b[0-9A-Z]{2,20}\b", part):
        x = re.sub(r"USDT$", "", x)
        if x and x not in ("USD", "M", "USDⓈ"):
            out.append(x)
    return out


def events():
    rows = []
    A = pickle.load(open("s10/ann.pkl", "rb"))
    for a in A.values():
        t, ts = a["title"], (a["ts"] or 0) / 1000
        if ts < T_FROM:
            continue
        if re.search(r"Will Delist", t):
            for x in tickers_after(t, "Delist"):
                rows.append(("bin_delist", x, ts, -1, 24 * H, 0))
        elif "Monitoring Tag" in t and "Include" in t:
            for x in tickers_after(t, "Include"):
                rows.append(("bin_monitor", x, ts, -1, 24 * H, 0))
        elif (re.search(r"Will List|HODLer Airdrops|Launchpool|Megadrop|Will Add .*Margin", t)
              and not re.search(r"Binance Futures Will|Alpha", t)):
            for x in re.findall(r"\(([0-9A-Z]{2,20})\)", t):
                rows.append(("bin_list", x, ts, +1, 24 * H, 0))
    for k in pickle.load(open("s15/kr_listings.pkl", "rb")):
        if k["t"] >= T_FROM:
            rows.append(("kr_list", k["base"], float(k["t"]), +1, 24 * H, 4 * H))
    ev = pd.read_pickle("s26/events.pkl")
    for r in ev[ev.kind.isin(["предупреждение", "делистинг"]) & (ev.ts >= T_FROM)].itertuples():
        rows.append(("kr_warn", r.tok, float(r.ts), -1, 24 * H, 0))
    E = pd.DataFrame(rows, columns=["kind", "coin", "T", "d", "win", "buf"])
    E["s"] = [fut_of(c)[0] for c in E.coin]
    E = E[E.s.notna() & E.s.isin(list(CIDX))].copy()
    E = E[[CSTART.get(s, np.inf) <= T - DAY for s, T in zip(E.s, E.T)]].copy()
    E = E.drop_duplicates(["kind", "s", "T"]).sort_values("T").reset_index(drop=True)
    E["ci"] = [CIDX[s] for s in E.s]
    return E


def hits(E):
    """Таблица: событие × счёт × сдвиг → было ли открытие в нужную (и обратную) сторону в окне."""
    rows = []
    for e in E.itertuples():
        for side, tag in ((e.d, "hit"), (-e.d, "ctl")):
            for ai in BY_COIN.get((e.ci, side), []):
                if FIRST_I[ai] > e.T - 29 * DAY - e.win:
                    continue
                tt = OPEN[(ai, e.ci, side)]
                for k in SHIFTS:
                    a, b = e.T - k * DAY - e.win, e.T - k * DAY - e.buf
                    n = int(np.searchsorted(tt, b) - np.searchsorted(tt, a))
                    if n:
                        rows.append((e.Index, ai, k, tag))
    return pd.DataFrame(rows, columns=["e", "ai", "k", "tag"])


def g4a(E, X):
    print("Г4а: открытия в нужную сторону за окно до события против тех же окон на 7/14/21 сут раньше")
    X = X.merge(E[["kind", "T"]], left_on="e", right_index=True)
    for lab, sel in [("все", X)] + [(k, X[X.kind == k]) for k in sorted(E.kind.unique())] + \
                    [("1-я половина", X[X["T"] < CUT]), ("2-я половина", X[X["T"] >= CUT])]:
        h = sel[sel.tag == "hit"]; c = sel[sel.tag == "ctl"]
        h0 = (h.k == 0).sum(); hp = h.k.isin([7, 14, 21]).sum() / 3
        c0 = (c.k == 0).sum(); cp = c.k.isin([7, 14, 21]).sum() / 3
        ne = E[E.kind == lab].shape[0] if lab in E.kind.values else np.nan
        print(f"  {lab:14s}: попаданий {h0:5d} против {hp:7.1f} (×{h0 / max(hp, 1e-9):.2f}) | обратная сторона {c0:5d} "
              f"против {cp:7.1f} (×{c0 / max(cp, 1e-9):.2f})" + (f" | событий {ne}" if ne == ne else ""))


def select(E, X, k0, kp, half):
    """Счета первой половины: ≥ 3 попаданий в окне k0 при ожидании из окон kp, Пуассон p < 1%."""
    X = X[X.tag == "hit"].merge(E[["T"]], left_on="e", right_index=True)
    X = X[(X["T"] < CUT) if half == 1 else (X["T"] >= CUT)]
    h0 = X[X.k == k0].groupby("ai").size()
    hp = X[X.k.isin(kp)].groupby("ai").size() / len(kp)
    idx = h0.index.union(hp.index)
    return h0.reindex(idx).fillna(0).astype(float), hp.reindex(idx).fillna(0).astype(float)


def g4b(E, X):
    out = {}
    for lab, k0, kp in (("отбор по событиям", 0, (7, 14, 21)), ("плацебо отбора", 7, (14, 21, 28))):
        h0, hp = select(E, X, k0, kp, 1)
        h0, hp = h0.astype(float), hp.astype(float)
        pv = poisson.sf(h0.values - 1, np.maximum(hp.values, 0.1))
        sel = h0.index[(h0.values >= 3) & (pv < 0.01)]
        h2, p2 = select(E, X, k0, kp, 2)
        h2, p2 = h2.astype(float), p2.astype(float)
        a, b = h2.reindex(sel).fillna(0).sum(), p2.reindex(sel).fillna(0).sum()
        print(f"  {lab}: отобрано счетов {len(sel)} (в 1-й половине попаданий {h0.reindex(sel).sum()} против "
              f"{hp.reindex(sel).sum():.1f}) → во 2-й половине {a:.0f} против {b:.1f} (×{a / max(b, 1e-9):.2f})")
        out[lab] = list(sel)
    return out


if __name__ == "__main__":
    E = events()
    print(f"событий: {len(E)} — {E.kind.value_counts().to_dict()}; монет {E.s.nunique()}; счетов с позициями {len(FIRST)}")
    X = hits(E)
    g4a(E, X)
    print("\nГ4б: устойчивы ли «знающие» счета")
    S = g4b(E, X)
    pickle.dump(dict(E=E, X=X, S=S), open("s34/insiders.pkl", "wb"))
