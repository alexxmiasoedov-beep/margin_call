"""s176 — Г3 «временная часть хода по потокам» (гипотеза и порог — ВЫВОДЫ.md, записаны до расчёта). Срез раз в сутки 00:00 UTC:
блоки лагов 0–1, 2–6, 7–24 ч дохода перпа, чистого агрессивного потока перпа и спота; доля спота; фандинг; взаимодействие
«рост на споте». Цель — доход за 48 ч сверх индекса альтов. Шаги:
  build <период> — панель, цель и сделки (шорт 48 ч, стоп 25%) монет с |R24| ≥ 3%; запуск как s175/venue.py (папка периода
                   со спотовым кэшем, MC_K/MC_F для старых периодов);
  fit            — Фама — Макбет на первой половине 2024–2026 гг. (из /home/user/mc_data);
  report         — корзины S и сравнения B1–B3 на трёх выборках вне оценки (из /home/user/mc_data)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s174", "s175"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from trapped import NONCRYPTO, ct, hourly  # noqa: E402
from venue import PER, spot_old, ts  # noqa: E402

OUT, DAY, H = "/home/user/mc_data", 86400, 3600
RAW = ["r1", "r6", "r24", "fp1", "fp6", "fp24", "fs1", "fs6", "fs24", "sh", "f"]
REG = RAW + ["Rxsh"]
FIT_END, OOS_START = ts("2025-11-29"), ts("2025-12-01")
MOVE, NB = 0.03, 5


def build(per):
    from common import K, funding, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, y0 = ts(PER[per][0]), ts(PER[per][1]), PER[per][3]
    kind = pd.read_pickle(f"{OUT}/s12/perp_kind.pkl")
    bad = set(kind.get("tradfi", set())) | NONCRYPTO | {"BTC", "ETH"}
    SP = pd.read_pickle(f"{OUT}/s23/spot1h.pkl") if y0 is None else None
    T_, I_ = alt_index(K)

    def ix(tt):
        j = int(np.searchsorted(T_, tt - 900, "right")) - 1
        return I_[j] if 0 <= j < len(I_) else np.nan

    rows = []
    for s in sorted(K):
        if s in bad or s.endswith("USDC") or "tb" not in K[s]:
            continue
        sp = SP.get(s) if SP is not None else spot_old(s, y0)
        if sp is None or not len(sp):
            continue
        T, x = hourly(K[s])
        if len(T) < 24 * 40:
            continue
        sp = np.asarray(sp, float); Hs = sp[:, 0].astype(np.int64) // H
        m_ = (Hs >= T[0]) & (Hs <= T[-1]); k_ = (Hs[m_] - T[0]).astype(int)
        sq = np.zeros(len(T)); stb = np.zeros(len(T)); sq[k_] = sp[m_, 1]; stb[k_] = sp[m_, 2]
        qv, tb, c = x["qv"], x["tb"], x["c"]
        nz = np.flatnonzero(qv > 0)
        if not len(nz):
            continue
        first = nz[0]
        with np.errstate(divide="ignore", invalid="ignore"):
            lc = np.log(np.where(c > 0, c, np.nan))
        C = {nm: np.r_[0.0, np.cumsum(a)] for nm, a in (("fp", 2 * tb - qv), ("fs", 2 * stb - sq), ("q", qv), ("sq", sq))}

        def rs(nm, a, b):                        # сумма по часам a…b включительно
            return C[nm][b + 1] - C[nm][a]
        fr = funding(s); a15 = K[s]; t15 = a15["t"].astype(np.int64); c15 = a15["c"].astype(float)
        lo_t, hi_t = live(s)
        for i in np.flatnonzero(T % 24 == 23):
            if i < first + 744 or i < 192:
                continue
            sig = (int(T[i]) + 1) * H; te = sig + 900
            if not (t0 <= te < t1):
                continue
            v24 = rs("q", i - 23, i)
            if v24 < 5e6:
                continue
            qp = rs("q", i - 191, i - 24) / 168; qs = rs("sq", i - 191, i - 24) / 168
            if qp <= 0 or qs <= 0:
                continue
            s24 = rs("sq", i - 23, i)
            r = dict(s=s, t=te, R24=lc[i] - lc[i - 24], r1=lc[i] - lc[i - 1], r6=lc[i - 1] - lc[i - 6], r24=lc[i - 6] - lc[i - 24],
                     fp1=rs("fp", i, i) / qp, fp6=rs("fp", i - 5, i - 1) / qp, fp24=rs("fp", i - 23, i - 6) / qp,
                     fs1=rs("fs", i, i) / qs, fs6=rs("fs", i - 5, i - 1) / qs, fs24=rs("fs", i - 23, i - 6) / qs,
                     sh=s24 / (s24 + v24))
            m = (fr[:, 0] > sig - DAY) & (fr[:, 0] <= sig) if len(fr) else np.zeros(0, bool)
            r["f"] = float(fr[m, 1].sum()) if m.any() else 0.0
            if not all(np.isfinite(r[k]) for k in RAW + ["R24"]):
                continue
            j = idx_at(s, te)
            r["y48"] = np.nan
            if j is not None and t15[j] + 900 == te and j + 192 < len(t15) and t15[j + 192] == t15[j] + 192 * 900 \
                    and lo_t <= t15[j] and t15[j + 192] <= hi_t:
                r["y48"] = c15[j + 192] / c15[j] - 1 - (ix(te + 48 * H) / ix(te) - 1)
            r["net"] = r["hed"] = np.nan; r["why"] = ""
            if abs(r["R24"]) >= MOVE and j is not None and t15[j] + 900 == te:
                z = trade(s, j, tp=None, sl=0.25, hold_h=48, side=-1)
                if z:
                    r["net"] = z["net"]; r["why"] = z["why"]
                    r["hed"] = z["net"] + ix(te + int(z["bars"]) * 900) / ix(te) - 1
            rows.append(r)
    P = pd.DataFrame(rows)
    P.to_pickle(f"{OUT}/s176_panel_{per}.pkl")
    print(per, "срезов", len(P), "монет", P.s.nunique() if len(P) else 0, "| с целью", int(P.y48.notna().sum()) if len(P) else 0,
          "| сделок (|R24| ≥ 3%)", int(P.net.notna().sum()) if len(P) else 0, flush=True)


def ranks(P):
    """Ранги признаков внутри дня в [−0,5; 0,5] и взаимодействие «рост на споте»."""
    P = P.copy()
    g = P.groupby("t")
    for k in RAW + ["R24"]:
        P["x_" + k] = g[k].rank(pct=True) - 0.5
    P["x_Rxsh"] = P["x_R24"] * P["x_sh"] * 4
    return P


def nw_t(x, lags=2):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 10:
        return np.nan
    u = x - x.mean(); v = (u @ u) / n
    for L in range(1, lags + 1):
        v += 2 * (1 - L / (lags + 1)) * (u[L:] @ u[:-L]) / n
    return x.mean() / np.sqrt(v / n) if v > 0 else np.nan


def fit():
    P = pd.read_pickle(f"{OUT}/s176_panel_2024–2026.pkl")
    P = ranks(P); P = P[(P.t < FIT_END) & P.y48.notna()]
    B = []
    for t, g in P.groupby("t"):
        if len(g) < 30:
            continue
        X = np.c_[np.ones(len(g)), g[["x_" + k for k in REG]].to_numpy()]
        b, *_ = np.linalg.lstsq(X, g.y48.to_numpy(), rcond=None)
        B.append(b)
    B = np.array(B); beta = B.mean(0)
    pd.to_pickle({"beta": beta, "reg": REG, "days": len(B)}, f"{OUT}/s176_beta.pkl")
    print(f"Фама — Макбет, первая половина 2024–2026 гг.: дней {len(B)}; коэффициент — доход за 48 ч сверх индекса на разницу "
          "рангов от середины до края (×0,5), t Ньюи — Уэста (2 лага):")
    for k, b, col in zip(["конст."] + REG, beta, B.T):
        print(f"  {k:6s} {b * 0.5:+.3%} (t {nw_t(col):+.1f})")


def score(P, beta):
    P = ranks(P)
    P["S"] = beta[0] + P[["x_" + k for k in REG]].to_numpy() @ beta[1:]
    P["ftot"] = P.fp1 + P.fp6 + P.fp24 + P.fs1 + P.fs6 + P.fs24
    P["B1"] = P.groupby("t").R24.rank(pct=True) - P.groupby("t").ftot.rank(pct=True)
    return P


def baskets(P):
    """Дневные корзины среди монет с |R24| ≥ 3%: S — 5 с наименьшим S; B1 — 5 с наибольшим ранг(R24) − ранг(поток);
    B2 — 5 с наибольшим R24; B3 — все. Возвращает сделки (с меткой корзины) и дневные средние."""
    Q = P[P.net.notna() & (P.R24.abs() >= MOVE)]
    out = []
    for t, g in Q.groupby("t"):
        if len(g) < NB * 2:
            continue
        for nm, sub in (("S", g.nsmallest(NB, "S")), ("B1", g.nlargest(NB, "B1")), ("B2", g.nlargest(NB, "R24")), ("B3", g)):
            out.append(sub.assign(b=nm))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def report():
    beta = pd.read_pickle(f"{OUT}/s176_beta.pkl")["beta"]
    S = {}
    for per in PER:
        P = score(pd.read_pickle(f"{OUT}/s176_panel_{per}.pkl"), beta); P["per"] = per
        if per == "2024–2026":
            S["2024–2026, 1-я половина (оценка)"] = P[P.t < OOS_START]; S["2024–2026, 2-я половина"] = P[P.t >= OOS_START]
        else:
            S[per] = P
    allb, oos = {}, []
    for nm, P in S.items():
        D = P[P.y48.notna()]
        ic = D.groupby("t").apply(lambda g: g.S.corr(g.y48, method="spearman") if len(g) >= 30 else np.nan).dropna()
        D = D.assign(dec=D.groupby("t").S.transform(lambda v: pd.qcut(v.rank(method="first"), 10, labels=False) if len(v) >= 30 else np.nan))
        dm = D.groupby("dec").y48.mean()
        Bk = baskets(P); allb[nm] = Bk
        months = (P.t.max() - P.t.min()) / (30.4 * DAY)
        print(f"\n{nm}: срезов {len(P)}, монет в день ~{P.groupby('t').size().median():.0f}; IC S → доход 48 ч {ic.mean():+.3f} "
              f"(t {nw_t(ic):+.1f}); децили S (доход 48 ч сверх индекса): " + " ".join(f"{v * 100:+.2f}" for v in dm.values))
        dd = {}
        for b in ("S", "B1", "B2", "B3"):
            x = Bk[Bk.b == b]
            m, t, n = ct(x.hed, x.t); mr, tr, _ = ct(x.net, x.t)
            dd[b] = x.groupby("t").hed.mean()
            print(f"  {b}: n {n:5d} ({n / months:5.1f}/мес) с хеджем {m:+.2%} (t {t:+.1f}) | без хеджа {mr:+.2%} (t {tr:+.1f}) | "
                  f"стопов {(x.why == 'стоп').mean():.0%}")
        print("  разница S − B (по дням, с хеджем): " + " | ".join(
            f"{b} {(dd['S'] - dd[b]).mean():+.2%} (t {nw_t((dd['S'] - dd[b]).dropna()):+.1f})" for b in ("B1", "B2", "B3")))
        if "оценка" not in nm:
            oos.append(Bk)
    O = pd.concat(oos, ignore_index=True)
    x = O[O.b == "S"]; m, t, n = ct(x.hed, x.t)
    d3 = (x.groupby("t").hed.mean() - O[O.b == "B3"].groupby("t").hed.mean()).dropna()
    print(f"\nТри выборки вне оценки вместе: корзина S с хеджем {m:+.2%} (t {t:+.1f}, n {n}); S − B3 {d3.mean():+.2%} "
          f"(t {nw_t(d3):+.1f})")
    Bk = pd.concat([allb["2024–2026, 1-я половина (оценка)"], allb["2024–2026, 2-я половина"]], ignore_index=True)
    x = Bk[Bk.b == "S"]; m, t, n = ct(x.net, x.t); months = (ts("2026-10-17") - ts("2024-10-01")) / (30.4 * DAY)
    print(f"Правило владельца, 2024–2026, корзина S без хеджа: n {n} ({n / months:.0f}/мес) {m:+.2%} (t {t:+.1f}) | половины "
          f"{x[x.t < OOS_START].net.mean():+.2%} / {x[x.t >= OOS_START].net.mean():+.2%} | B3 {Bk[Bk.b == 'B3'].net.mean():+.2%}")


if __name__ == "__main__":
    a = sys.argv[1]
    fit() if a == "fit" else (report() if a == "report" else build(a))
