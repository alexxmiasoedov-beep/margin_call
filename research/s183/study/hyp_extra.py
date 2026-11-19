"""s183 — уточнения к гипотезам без доходов:
  Г1 — частота при порогах доли Кореи 15 / 20 / 25%; характеристики монет корзины против прочих ликвидных (возраст,
       оборот, капитализация, бета, фандинг, премия Кореи); доля корзины, где монета торгуется только на одной бирже;
  Г2 — состав корзины «OI ↓ ≥ 15% при |цена| ≤ 10%»: доля с фандингом за 7 сут ≥ 0 (закрывают лонги) и < 0 (закрывают
       шорты), падение OI в $ против падения в монетах; четыре квадранта «OI × цена» (增仓/减仓 × 上涨/下跌) — монет на срез;
  общая устойчивость: сколько сделок в месяц у Г1 и Г2 приходится на одну и ту же монету в одну неделю.
Запуск: python3 -I hyp_extra.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from coverage import load  # noqa: E402
from hyp_freq import KJ, recent_journal  # noqa: E402

N = 5


def top(X, score, cond, asc=False):
    out = []
    for d0, g in X.groupby("d0"):
        g = g[cond(g)]
        g = g.sort_values(score, ascending=asc).head(N)
        out.append(g)
    return pd.concat(out) if out else X.iloc[:0]


def main():
    for per in C.PERS:
        X = load(per)
        X = X[X.liq5.astype(bool)].replace([np.inf, -np.inf], np.nan).copy()
        J = C.journals(per)
        rj = recent_journal(J, KJ)
        X["kj7"] = [(d, s) in rj for d, s in zip(X.d0, X.s)]
        wk = X.d0.nunique()
        mpw = 30.4 / 7
        print(f"\n=== {per}: срезов {wk}")
        # Г1: пороги
        for thr in (0.15, 0.20, 0.25):
            for nj in (True, False):
                g = X[(X.kshare7 >= thr) & (~X.kj7 if nj else True)]
                cnt = g.groupby("d0").size().reindex(X.d0.unique(), fill_value=0)
                trades = np.minimum(cnt, N).sum() / wk * mpw
                print(f"  Г1 доля ≥ {thr:.0%}{' без журналов 7 сут' if nj else ''}: монет на срез медиана {cnt.median():.0f}, "
                      f"сделок в месяц (до 5) {trades:.1f}")
        B = top(X, "kshare7", lambda g: (g.kshare7 >= 0.20) & ~g.kj7)
        rest = X[~X.set_index(["d0", "s"]).index.isin(B.set_index(["d0", "s"]).index)]
        cols = ["age", "qv7", "lmcap", "beta28", "vol28", "f7", "kprem7", "r28", "max28", "sshare7"]
        print("  Г1 корзина против прочих ликвидных (медианы): " + "; ".join(
            f"{c} {B[c].median():.3g} / {rest[c].median():.3g}" for c in cols if c in X.columns))
        one = []
        P = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")[["s", "d", "krv_upbit", "krv_bithumb"]]
        P["wk"] = P.d - (P.d - 4 * C.DAY) % (7 * C.DAY)                 # понедельник недели
        P["up"] = P.krv_upbit.fillna(0) > 0
        P["bt"] = P.krv_bithumb.fillna(0) > 0
        W = P.groupby(["s", "wk"])[["up", "bt"]].any()
        for r in B.itertuples():
            k = (r.s, r.d0 - 7 * C.DAY)
            if k in W.index:
                u, b = W.loc[k]
                one.append("обе" if u and b else ("только Upbit" if u else ("только Bithumb" if b else "нет")))
        if one:
            vc = pd.Series(one).value_counts(normalize=True)
            print("  Г1 корзина — рынки к воне на прошлой неделе: " + ", ".join(f"{k} {v:.0%}" for k, v in vc.items()))
        # Г2: состав
        Y = X[X.oi_g7.notna()]
        if not len(Y):
            continue
        wko = Y.d0.nunique()
        B2 = top(Y, "oi_g7", lambda g: (g.oi_g7 <= np.log(0.85)) & (g.r7.abs() <= np.log(1.10)), asc=True)
        usd = np.log((B2.oi_usd) / (B2.oi_prev * np.exp(B2.r7)))         # приблизительно: OI $ к OI монет × цена неделю назад
        print(f"  Г2 корзина (срезов с OI {wko}): фандинг 7 сут ≥ 0 — {(B2.f7 >= 0).mean():.0%}, < 0 — {(B2.f7 < 0).mean():.0%}; "
              f"медиана падения OI в монетах {np.expm1(B2.oi_g7.median()):+.0%}, хода цены {np.expm1(B2.r7.median()):+.1%}")
        q = []
        for name, cond in (("增仓上涨 OI ↑ ≥ 5%, цена ↑ ≥ 10%", (Y.oi_g7 >= np.log(1.05)) & (Y.r7 >= np.log(1.10))),
                           ("减仓上涨 OI ↓ ≤ −5%, цена ↑ ≥ 10%", (Y.oi_g7 <= np.log(0.95)) & (Y.r7 >= np.log(1.10))),
                           ("增仓下跌 OI ↑ ≥ 5%, цена ↓ ≤ −10%", (Y.oi_g7 >= np.log(1.05)) & (Y.r7 <= np.log(0.90))),
                           ("减仓下跌 OI ↓ ≤ −5%, цена ↓ ≤ −10%", (Y.oi_g7 <= np.log(0.95)) & (Y.r7 <= np.log(0.90))),
                           ("OI ↓ ≤ −15%, |цена| ≤ 10%", (Y.oi_g7 <= np.log(0.85)) & (Y.r7.abs() <= np.log(1.10))),
                           ("OI ↑ ≥ +15%, |цена| ≤ 10%", (Y.oi_g7 >= np.log(1.15)) & (Y.r7.abs() <= np.log(1.10)))):
            c = Y[cond].groupby("d0").size().reindex(Y.d0.unique(), fill_value=0)
            q.append(f"{name}: {c.median():.0f} (p10 {c.quantile(0.1):.0f})")
        print("  квадранты «OI × цена» за 7 сут, монет на срез: " + "; ".join(q))
        # общие монеты Г1 и Г2
        k1 = set(zip(B.d0, B.s)); k2 = set(zip(B2.d0, B2.s))
        print(f"  общих монето-недель Г1 и Г2: {len(k1 & k2)} из {len(k1)} / {len(k2)}")


if __name__ == "__main__":
    main()
