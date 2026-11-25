"""s288 — масштабы после постов Whale Alert: |ход| BTC, |ход| индекса альтов (равновесная корзина 50 крупнейших),
медиана |хода| альтов, |ход| самой монеты (для альтов) за 15 / 60 / 240 мин; кратность оборота за 60 мин; |ход| и оборот
за 60 мин ДО поста (для сравнения). ТОЛЬКО абсолютные величины: направленные доходы здесь НЕ считаются.

Момент события T — время поста, округлённое вверх до границы 15-мин свечи (окно «после» целиком после поста).
Контроль — те же моменты недели за ±1, ±2, ±3 нед. (до 6 на событие), без событий той же семьи в ±3 ч.
Семьи — категории describe.py; события одной семьи (для альтов — одной монеты) ближе 60 мин склеиваются в первое.
Свечи и вселенная альтов — s286 volstudy (load_period, daily_aux): 2020–2022 — s117/k_2020.pkl, 2022–2024 — s117/k_oos.pkl,
2024–2026 — s2/k2y.pkl (по 19.10.2026).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/scale.py → s288/scale_summary.csv, scale_report.txt."""
import os
import sys
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "s286", "study"))
import common288 as C  # noqa: E402
import volstudy as V  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
BAR, DAY, WEEK = 900, 86400, 7 * 86400
HZ = (15, 60, 240)
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def families(P):
    tr = P.kind == "transfer"
    st = P.cc == "stable"
    F = {
        "чеканка USDT": (P.kind == "mint") & (P.tic == "USDT"),
        "чеканка USDT ≥ 500 млн $": (P.kind == "mint") & (P.tic == "USDT") & (P.usd >= 5e8),
        "чеканка USDC": (P.kind == "mint") & (P.tic == "USDC"),
        "сжигание USDT и USDC": (P.kind == "burn") & P.tic.isin(["USDT", "USDC"]),
        "казна → биржа": P.cat.str.startswith("казна → биржа"),
        "стейблкоин → Binance": tr & st & (P.cat == "стейблкоин → Binance"),
        "стейблкоин → другие биржи": tr & st & (P.cat == "стейблкоин → другие биржи"),
        "стейблкоин ← биржи": tr & st & P.cat.str.startswith("стейблкоин ←"),
        "BTC → биржи": tr & P.cat.isin(["BTC → Binance", "BTC → другие биржи"]),
        "BTC ← биржи": tr & P.cat.str.startswith("BTC ←"),
        "ETH → биржи": tr & P.cat.isin(["ETH → Binance", "ETH → другие биржи"]),
        "ETH ← биржи": tr & P.cat.str.startswith("ETH ←"),
        "альт → Binance": tr & (P.cat == "альт → Binance") & P.perp,
        "альт → другие биржи": tr & (P.cat == "альт → другие биржи") & P.perp,
    }
    return F


def thin(t, key=None, gap=3600):
    """Склейка событий ближе gap (по ключу — монете)."""
    t = np.asarray(t, np.int64)
    key = np.zeros(len(t), int) if key is None else np.asarray(key)
    o = np.lexsort((t, key))
    keep = np.zeros(len(t), bool)
    last = {}
    for i in o:
        k = key[i]
        if k not in last or t[i] - last[k] >= gap:
            keep[i] = True
            last[k] = t[i]
    return keep


def metrics(D, T, J=None):
    """|ход| и оборот в моменты T (границы свечей); J — индекс монеты (или −1) для «самой монеты»."""
    Cm, Q = D["C"], D["Q"]
    T = np.asarray(T, np.int64)
    i = (T - D["t0"]) // BAR
    ok = (i >= 8 + 7 * 96) & (i + 17 < D["n"]) & (T >= D["a"]) & (T < D["b"])
    J = np.full(len(T), -1) if J is None else np.asarray(J)
    i, T, J = i[ok], T[ok], J[ok]
    d = i // 96
    ib = D["ib"]
    out = {"T": T, "ok_idx": np.flatnonzero(ok)}
    p0 = Cm[:, i - 1]
    top = D["top"][d]
    for h in HZ:
        rh = Cm[:, i - 1 + h // 15] / p0 - 1
        out[f"btc_a{h}"] = np.abs(rh[ib]) * 100
        A = np.take_along_axis(rh.T, np.maximum(top, 0), 1)
        A[top < 0] = np.nan
        out[f"idx_a{h}"] = np.abs(np.nanmean(A, 1)) * 100
        out[f"alt_med_a{h}"] = np.nanmedian(np.abs(A), 1) * 100
        sg = D["sig"][:, d] * np.sqrt(h / 15)
        out[f"btc_z{h}"] = np.abs(rh[ib]) / sg[ib]
        jj = np.maximum(J, 0)
        cr = rh[jj, np.arange(len(T))]
        out[f"coin_a{h}"] = np.where(J >= 0, np.abs(cr) * 100, np.nan)
        out[f"coin_z{h}"] = np.where(J >= 0, np.abs(cr) / sg[jj, np.arange(len(T))], np.nan)
    pre = p0 / Cm[:, i - 5] - 1
    out["btc_pre60"] = np.abs(pre[ib]) * 100
    P_ = np.take_along_axis(pre.T, np.maximum(top, 0), 1)
    P_[top < 0] = np.nan
    out["idx_pre60"] = np.abs(np.nanmean(P_, 1)) * 100
    jj = np.maximum(J, 0)
    out["coin_pre60"] = np.where(J >= 0, np.abs(pre[jj, np.arange(len(T))]) * 100, np.nan)
    base = D["q7"][:, d] / (7 * 24)
    qp = Q[:, i] + Q[:, i + 1] + Q[:, i + 2] + Q[:, i + 3]
    qb = Q[:, i - 4] + Q[:, i - 3] + Q[:, i - 2] + Q[:, i - 1]
    for nm, q in (("q60", qp), ("qpre60", qb)):
        x = q / base
        out[f"btc_{nm}"] = x[ib]
        X = np.take_along_axis(x.T, np.maximum(top, 0), 1)
        X[top < 0] = np.nan
        out[f"alt_{nm}"] = np.nanmedian(X, 1)
        out[f"coin_{nm}"] = np.where(J >= 0, x[jj, np.arange(len(T))], np.nan)
    return pd.DataFrame(out)


COLS = ["btc_a15", "btc_a60", "btc_a240", "idx_a15", "idx_a60", "idx_a240", "alt_med_a60", "coin_a15", "coin_a60",
        "coin_a240", "btc_z60", "coin_z60", "btc_q60", "alt_q60", "coin_q60", "btc_pre60", "idx_pre60", "coin_pre60",
        "btc_qpre60", "coin_qpre60"]


def run_period(per, P):
    D = V.load_period(per)
    V.daily_aux(D)
    idx = {c: j for j, c in enumerate(D["coins"])}
    a, b = C.PER[per]
    F = families(P)
    rows = []
    for fam, mask in F.items():
        x = P[mask & (P.t >= a) & (P.t < b)].copy()
        if len(x) < 5:
            continue
        coinkey = None
        J = None
        if fam.startswith("альт"):
            x["j"] = [idx.get(s, idx.get("1000" + s, idx.get(C.ALIAS.get(s, ""), -1))) for s in x.tic]
            x = x[x.j >= 0]
            coinkey = x.j.values
        keep = thin(x.t.values, coinkey)
        x = x[keep]
        T = (np.ceil(x.t.values / BAR) * BAR).astype(np.int64)
        if coinkey is not None:
            J = x.j.values
        elif fam.startswith("ETH") or fam.startswith("BTC"):          # «сама монета» — ETH или BTC
            J = np.full(len(x), D["ie"] if fam.startswith("ETH") else D["ib"])
        ev = metrics(D, T, J)
        # контроль: те же моменты недели ±1..3 нед., без событий семьи (той же монеты) в ±3 ч
        allT = np.sort((np.ceil(P[mask].t.values / BAR) * BAR).astype(np.int64))
        cT, cJ = [], []
        for k, (t0, j) in enumerate(zip(ev["T"].values, (J[ev.ok_idx.values] if coinkey is not None else [None] * len(ev)))):
            for w in (-3, -2, -1, 1, 2, 3):
                tc = t0 + w * WEEK
                if coinkey is None:
                    s = np.searchsorted(allT, tc - 3 * 3600)
                    if s < len(allT) and allT[s] <= tc + 3 * 3600:
                        continue
                else:
                    tj = np.sort(T[J == j])
                    s = np.searchsorted(tj, tc - 3 * 3600)
                    if s < len(tj) and tj[s] <= tc + 3 * 3600:
                        continue
                cT.append(tc)
                cJ.append(j if j is not None else -1)
        if coinkey is not None:
            cJ = np.array(cJ)
        elif J is not None:
            cJ = np.full(len(cT), J[0])
        else:
            cJ = None
        ct = metrics(D, np.array(cT, np.int64), cJ)
        r = {"период": per, "семья": fam, "событий": len(ev), "в месяц": len(ev) / C.months(per), "контролей": len(ct)}
        for c in COLS:
            e_, c_ = np.nanmedian(ev[c]) if len(ev) else np.nan, np.nanmedian(ct[c]) if len(ct) else np.nan
            r[c + "_ev"] = e_
            r[c + "_x"] = e_ / c_ if c_ and np.isfinite(c_) and c_ > 0 else np.nan
        rows.append(r)
        say(f"{per} | {fam}: событий {len(ev)} ({len(ev) / C.months(per):.1f} в мес.), контролей {len(ct)}")
    del D
    return rows


def main():
    P = pd.read_pickle(f"{C.OUT}/posts.pkl.gz")
    rows = []
    pers = os.environ.get("S288_PER", "2020–2022,2022–2024,2024–2026").split(",")
    for per in pers:
        rows += run_period(per, P)
    S = pd.DataFrame(rows)
    S.to_csv(f"{C.OUT}/scale_summary.csv", index=False)
    say("\nКратность медианы к контролю (те же часы недели без событий семьи); 2020–2022 / 2022–2024 / 2024–2026")
    show = [("|ход| BTC 15 мин", "btc_a15"), ("|ход| BTC 60 мин", "btc_a60"), ("|ход| BTC 240 мин", "btc_a240"),
            ("|ход| индекса альтов 60 мин", "idx_a60"), ("|ход| индекса альтов 240 мин", "idx_a240"),
            ("|ход| монеты 15 мин", "coin_a15"), ("|ход| монеты 60 мин", "coin_a60"), ("|ход| монеты 240 мин", "coin_a240"),
            ("оборот BTC 60 мин", "btc_q60"), ("оборот альтов 60 мин", "alt_q60"), ("оборот монеты 60 мин", "coin_q60"),
            ("|ход| BTC 60 мин ДО", "btc_pre60"), ("|ход| монеты 60 мин ДО", "coin_pre60"), ("оборот монеты 60 мин ДО", "coin_qpre60")]
    for fam in S["семья"].unique():
        x = S[S["семья"] == fam].set_index("период")
        say(f"\n-- {fam}: в месяц " + " / ".join(f"{x.loc[p, 'в месяц']:.1f}" if p in x.index else "—"
                                                 for p in ("2020–2022", "2022–2024", "2024–2026")))
        for nm, c in show:
            if not x[c + "_x"].notna().any():
                continue
            v = " / ".join(f"{x.loc[p, c + '_x']:.2f}" if p in x.index and np.isfinite(x.loc[p, c + "_x"]) else "—"
                           for p in ("2020–2022", "2022–2024", "2024–2026"))
            say(f"   {nm}: ×{v}")
        say("   медиана |ход| BTC 60 мин после, %: " + " / ".join(
            f"{x.loc[p, 'btc_a60_ev']:.2f}" if p in x.index else "—" for p in ("2020–2022", "2022–2024", "2024–2026")))
    open(f"{C.OUT}/scale_report.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
