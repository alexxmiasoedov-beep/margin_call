"""s214 — 🔑⁺ᵛ: λ = токены разлока × цена перпа / средний суточный оборот перпа за 7 сут до входа для сделок 🔑⁺ (s142),
отчёт по дозе λ. Запись до расчёта — ВЫВОДЫ.md (коммит dacfd11).

Запуск из /home/user/mc_data:
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022
  python3 run.py report
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s182", "s139", "s213"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"


def tokens():
    """Токены разлока по (проект, T) — как в s142: сумма по суткам проекта, T — первое событие суток."""
    import unlock_test as U  # noqa: E402
    E = U.events()
    E["day"] = E["T"] // DAY
    g = E.groupby(["slug", "day"])
    return g.agg(T=("T", "min"), tokens=("tokens", "sum")).reset_index()[["slug", "T", "tokens"]]


def run(per):
    import fastbt as FB  # noqa: E402
    from run import mult  # noqa: E402  (s213: множитель в тикере перпа)
    K = FB.K
    S = pd.read_pickle(f"{OUT}/s142_{per}.pkl")
    S = S.merge(tokens(), on=["slug", "T"], how="left")
    lam = []
    for r in S.itertuples():
        s = r.s
        if s not in K or not np.isfinite(r.tokens):
            lam.append(np.nan)
            continue
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        qv = K[s]["qv"].astype(float)
        i = int(np.searchsorted(t, int(r.t) - 900))
        if i < 672 or i >= len(t):
            lam.append(np.nan)
            continue
        vbar = qv[i - 672:i].sum() / 7.0
        lam.append(r.tokens * c[i] / mult(s) / vbar if vbar > 0 else np.nan)
    S["lam"] = lam
    S["per"] = per
    S.to_pickle(f"{OUT}/s214_{per}.pkl")
    print(per, "сделок", int(S.net.notna().sum()), "с λ", int(S.lam.notna().sum()), "медиана λ",
          round(float(S.lam.median()), 3), "λ ≥ 0,5:", int((S.lam >= 0.5).sum()), flush=True)


def wk(t, days=7):
    return (np.asarray(t, np.int64) // (days * DAY)) * (days * DAY)


def line(C, x, per):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = C.ct(x.net, wk(x.t))
    _, tm, _ = C.ct(x.net, wk(x.t, 30))
    mh, th, _ = C.ct(x.hed, wk(x.t))
    md, td, _ = C.ct(x.net - x.pl, wk(x.t))
    cut = C.ts(C.PER[per][2])
    return (f"n={n:4d} ({n / C.months(per):4.1f}/мес) {m:+.2%} (t по неделям {t:+.1f}, по месяцам {tm:+.1f}) | половины "
            f"{x[x.t < cut].net.mean():+.2%} / {x[x.t >= cut].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | "
            f"сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")


def report():
    import common182 as C  # noqa: E402
    print("s214 — 🔑⁺ᵛ: доза λ = разлок / суточный оборот перпа внутри сделок 🔑⁺ (T − 7 → T + 1, стоп 50%)\n")
    pn, ph, pdl = [], [], []
    for per in C.PER:
        S = pd.read_pickle(f"{OUT}/s214_{per}.pkl")
        S = S[S.net.notna() & S.lam.notna()]
        print(f"== {per} ==   λ: медиана {S.lam.median():.2f}, p25 {S.lam.quantile(.25):.2f}, p75 {S.lam.quantile(.75):.2f}")
        print(f"  все 🔑⁺ с λ: {line(C, S, per)}")
        for th in (0.25, 0.5, 1.0):
            print(f"  λ ≥ {th}: {line(C, S[S.lam >= th], per)}")
        print(f"  λ < 0,5: {line(C, S[S.lam < 0.5], per)}")
        x = S[S.lam >= 0.5]
        d, se = C.diff(S.net, S.lam >= 0.5, wk(S.t))
        pdl.append((d, se, len(S)))
        print(f"  Δ λ ≥ 0,5 − λ < 0,5: {d:+.2%} (t по неделям {d / se:+.1f})")
        m, t, n = C.ct(x.net, wk(x.t))
        mh, th, _ = C.ct(x.hed, wk(x.t))
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3 по неделям", t >= 3),
                    ("обе половины > 0", h1 > 0 and h2 > 0), ("сверх плацебо > 0", (x.net - x.pl).mean() > 0),
                    ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Три периода, λ ≥ 0,5: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t по неделям {th:+.1f})")
    print("  по периодам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Доза Δ λ ≥ 0,5 − λ < 0,5 вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
