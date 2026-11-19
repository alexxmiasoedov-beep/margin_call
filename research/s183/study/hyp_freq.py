"""s183 — частоты и состав кандидатных правил (Г1–Г4 отчёта) по трём периодам без доходов: сколько монет проходит
условие на срез, сделок в месяц при потолке 5 монет, замены, концентрация, ex-ante бета / риск / фандинг корзины,
минимальный различимый эффект (t = 3), пересечение с журналами; то же для контроля той же формы.

Запуск: python3 -I hyp_freq.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from baskets import JN, stats  # noqa: E402
from coverage import load  # noqa: E402

N = 5
KJ = ["🔝", "👀", "⏰", "🇰🇷", "🇰🇷🆕", "🛒"]


def recent_journal(J, js, days=7):
    """{(понедельник, монета)} — у монеты был вход журналов js за прошлые days суток до среза."""
    out = set()
    Jj = J[J.j.isin(js)]
    for s, t in zip(Jj.s, Jj.t):
        d0 = (int(t) // (7 * C.DAY)) * 7 * C.DAY + 4 * C.DAY     # ближайший следующий понедельник (эпоха — четверг)
        if d0 <= t:
            d0 += 7 * C.DAY
        for k in range(0, days // 7 + 1):
            w = d0 + 7 * C.DAY * k
            if w - t <= days * C.DAY:
                out.add((w, s))
    return out


def pick(X, score, cond, asc=False, need=None):
    """Корзина на срез; срезы, где нет нужного признака (need, например OI до 12.2021), пропускаются."""
    B = {}
    for d0, g in X.groupby("d0"):
        if need is not None and g[need].notna().sum() == 0:
            continue
        g = g[cond(g)] if cond is not None else g
        g = g[np.isfinite(g[score])] if score in g.columns else g
        g = g.sort_values(score, ascending=asc)
        B[d0] = list(g.s.head(N))
    return B


def eligible(X, cond):
    c = X[cond(X)].groupby("d0").size().reindex(X.d0.unique(), fill_value=0)
    return c.median(), c.quantile(0.1)


def main():
    rows = []
    for per in C.PERS:
        X = load(per)
        X = X[X.liq5.astype(bool)].replace([np.inf, -np.inf], np.nan).copy()
        J = C.journals(per)
        mons = C.months(per)
        rj = recent_journal(J, KJ)
        X["kj7"] = [(d, s) in rj for d, s in zip(X.d0, X.s)]
        X["r7_rk"] = X.groupby("d0").r7.rank(pct=True)
        X["oi_rk"] = X.groupby("d0").oi_g7.rank(pct=True)
        X["sc_cover"] = X.r7_rk - X.oi_rk                      # рост цены при падении OI
        X["sc_build"] = X.r7_rk + X.oi_rk                      # рост цены при росте OI
        hasoi = X.oi_g7.notna()
        RULES = [
            # Г1 — доля корейской розницы (уровень)
            ("Г1 Корея: доля ≥ 20%, без журналов 7 сут", "kshare7", lambda g: (g.kshare7 >= 0.20) & ~g.kj7, False),
            ("Г1 Корея: доля ≥ 20% (все)", "kshare7", lambda g: g.kshare7 >= 0.20, False),
            ("Г1 контроль: рынок к воне, доля ≤ 3%", "kshare7", lambda g: (g.kshare7 <= 0.03) & g.kshare7.notna(), True),
            ("Г1 контроль: доля спота Binance (верх)", "sshare7", lambda g: g.sshare7.notna(), False),
            # Г2 — рост без новых денег (цена ↑, OI ↓: закрытие шортов)
            ("Г2 цена ↑ ≥ 10%, OI ↓ ≤ −5%", "sc_cover", lambda g: (g.r7 >= np.log(1.10)) & (g.oi_g7 <= np.log(0.95)), False),
            ("Г2 контроль: цена ↑ ≥ 10%, OI ↑ ≥ +5%", "sc_build", lambda g: (g.r7 >= np.log(1.10)) & (g.oi_g7 >= np.log(1.05)), False),
            ("Г2 контроль: цена ↑ ≥ 10% (любой OI)", "r7", lambda g: (g.r7 >= np.log(1.10)) & g.oi_g7.notna(), False),
            # Г3 — уход интереса при спокойной цене (OI ↓, |r7| ≤ 10%)
            ("Г3 OI ↓ ≤ −15%, |цена| ≤ 10%", "oi_g7", lambda g: (g.oi_g7 <= np.log(0.85)) & (g.r7.abs() <= np.log(1.10)), True),
            ("Г3 контроль: OI ↑ ≥ +15%, |цена| ≤ 10%", "oi_g7", lambda g: (g.oi_g7 >= np.log(1.15)) & (g.r7.abs() <= np.log(1.10)), False),
        ]
        print(f"\n=== {per}: срезов {X.d0.nunique()}, месяцев {mons:.1f}; срезов с ростом OI {X[hasoi].d0.nunique()}", flush=True)
        print(f"  {'правило':44s} {'прошло/срез':>11s} {'p10':>4s} {'сделок/мес':>10s} {'полных':>7s} {'замен':>6s} {'монет':>6s} "
              f"{'топ-3':>6s} {'жур.нед':>7s} {'жур.до':>6s} {'бета':>5s} {'σ нед.':>6s} {'f7':>7s} {'MDE':>6s}")
        for name, score, cond, asc in RULES:
            need = "oi_g7" if ("OI" in name or score.startswith("sc_")) else None
            Xe = X[X.d0.isin(X[X[need].notna()].d0.unique())] if need else X
            med, p10 = eligible(Xe, cond)
            B = pick(X, score, cond, asc, need)
            st = stats(B, J, per, mons, X)
            st["name"] = name; st["elig"] = med
            rows.append(st)
            print(f"  {name:44s} {med:11.1f} {p10:4.0f} {st['per_month']:10.1f} {st['full']:7.0%} {st['turnover']:6.0%} "
                  f"{st['coins']:6d} {st['top3']:6.0%} {st['any_now']:7.0%} {st['any_prev']:6.0%} {st['beta']:5.2f} "
                  f"{st['sig_w']:6.1%} {st['f7']:+7.3%} {st['mde']:6.2%}   {st['top_coins']}")
        # Г4 — стоимость по сети (кап. / активные адреса Coin Metrics)
        p = f"{C.OUT}/cm_value_{per}.pkl"
        if os.path.exists(p):
            V = pd.read_pickle(p)
            Y = X.merge(V, on=["d0", "s"], how="left")
            med, p10 = eligible(Y, lambda g: g.lp_aa.notna())
            B = pick(Y, "lp_aa", lambda g: g.lp_aa.notna(), False)
            st = stats(B, J, per, mons, Y)
            st["name"] = "Г4 кап./активные адреса (верх)"; st["elig"] = med
            rows.append(st)
            print(f"  {st['name']:44s} {med:11.1f} {p10:4.0f} {st['per_month']:10.1f} {st['full']:7.0%} {st['turnover']:6.0%} "
                  f"{st['coins']:6d} {st['top3']:6.0%} {st['any_now']:7.0%} {st['any_prev']:6.0%} {st['beta']:5.2f} "
                  f"{st['sig_w']:6.1%} {st['f7']:+7.3%} {st['mde']:6.2%}   {st['top_coins']}")
        # двойник: входы журналов по корейской доле монеты на прошлом срезе
        ws = np.array(sorted(X.d0.unique()))
        Xi = X.set_index(["d0", "s"]).kshare7
        print("  входы журналов по доле Кореи монеты на прошлом срезе (≥ 20% / < 20% / нет рынка к воне или вне ликвидных):")
        for j in JN:
            Jj = J[(J.j == j) & (J.t >= ws[0]) & (J.t < ws[-1] + 7 * C.DAY)]
            if not len(Jj):
                continue
            k = np.searchsorted(ws, Jj.t.values, "right") - 1
            v = [Xi.get((ws[i], s), np.nan) for s, i in zip(Jj.s, k)]
            v = np.array(v, float)
            hi, lo = np.nansum(v >= 0.2), np.nansum(v < 0.2)
            na = np.isnan(v).sum()
            print(f"    {j}: {hi / mons:5.1f} / {lo / mons:5.1f} / {na / mons:5.1f} в месяц (доля ≥ 20% среди известных: "
                  f"{hi / max(hi + lo, 1):.0%})")
    pd.DataFrame(rows).to_pickle(f"{C.OUT}/hyp_freq.pkl")


if __name__ == "__main__":
    main()
