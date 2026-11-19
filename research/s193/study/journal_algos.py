"""s193 — алгоритмы в ленте в момент входа журналов (выборка до 150 входов на журнал и период, `jobs_journal.py`).

Флаги (только данные до входа t): эпизод E1 той же монеты обнаружен до t и ещё идёт в t (конец в реальном времени
t₁ + max(3·шаг, 5 мин) ≥ t) — отдельно покупки и продажи; эпизод E1, шедший в последние 2 ч до t. База — те же флаги
в случайные моменты SRS-суток (то же время суток, что у входов). Частота двойника = входов журнала в месяц × доля.
Доходы не считаются."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s193"
DAY = 86400
PERS = ["2020–2022", "2022–2024", "2024–2026"]


def flags(Eix, s, t):
    """Флаги для монеты s и момента t (сек) по эпизодам E1 (словарь монета → DataFrame)."""
    e = Eix.get(s)
    out = dict(buy_run=False, sell_run=False, buy_2h=False, sell_2h=False)
    if e is None:
        return out
    tm = t * 1000
    det = e.det_t.values <= tm
    run = det & (e.end_rt.values >= tm)
    rec = det & (e.t1.values >= tm - 7_200_000)
    sd = e.side.values
    out.update(buy_run=bool((run & (sd > 0)).any()), sell_run=bool((run & (sd < 0)).any()),
               buy_2h=bool((rec & (sd > 0)).any()), sell_2h=bool((rec & (sd < 0)).any()))
    return out


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days = T["days"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    E = E[(E.mkt == "um") & E.E1].copy()
    E["end_rt"] = E.t1 + np.maximum(3 * E.med * 1000, 300_000)
    loaded = set(zip(days[days.mkt == "um"].s, days[days.mkt == "um"].d))
    Eix = {s: g for s, g in E.groupby("s")}
    EN = pd.read_pickle(f"{D}/entries_journal.pkl")
    rng = np.random.default_rng(7)
    rows = []
    for r in EN.itertuples():
        need = [r.d] + ([r.d - DAY] if r.t - r.d < 7200 else [])
        if not all((r.s, d) in loaded for d in need):
            continue
        rows.append(dict(per=r.per, j=r.j, s=r.s, t=r.t, **flags(Eix, r.s, r.t)))
    X = pd.DataFrame(rows)
    # база: SRS-сутки, момент — то же время суток, что у случайного входа периода
    base = []
    srs = days[days.tags.str.contains("srs") & (days.mkt == "um")]
    for per in PERS:
        tod = (EN[EN.per == per].t % DAY).values
        sd = srs[srs.per == per]
        if not len(sd) or not len(tod):
            continue
        pick = sd.sample(n=min(3000, len(sd)), replace=True, random_state=1)
        for s, d in zip(pick.s, pick.d):
            t = int(d + rng.choice(tod))
            if t - d < 7200 and (s, d - DAY) not in loaded:
                t = int(d + 7200 + (t - d))
            base.append(dict(per=per, **flags(Eix, s, t)))
    B = pd.DataFrame(base)
    print(f"входов с лентой: {len(X)} из {len(EN)}")
    for per in PERS:
        Jr = C.journals(per)
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        mon = C.months(per)
        cnt = Jr[(Jr.t >= t0) & (Jr.t < t1)].groupby("j").size() / mon
        b = B[B.per == per].mean(numeric_only=True)
        print(f"\n== {per}: доля входов с алгоритмом (E1, обнаружен до входа); база SRS: покупка идёт {b.buy_run:.1%}, "
              f"продажа идёт {b.sell_run:.1%}, покупка за 2 ч {b.buy_2h:.1%}, продажа за 2 ч {b.sell_2h:.1%} ==")
        x = X[X.per == per]
        for j, g in x.groupby("j"):
            m = g.mean(numeric_only=True)
            print(f"  {j}: n={len(g)}; покупка идёт {m.buy_run:.1%}, продажа идёт {m.sell_run:.1%}, покупка за 2 ч "
                  f"{m.buy_2h:.1%}, продажа за 2 ч {m.sell_2h:.1%}; входов журнала в месяц {cnt.get(j, np.nan):.1f} → "
                  f"«покупка за 2 ч» {cnt.get(j, np.nan) * m.buy_2h:.1f} в мес, «продажа за 2 ч» {cnt.get(j, np.nan) * m.sell_2h:.1f} в мес")
    pd.to_pickle(dict(X=X, B=B), f"{D}/journal_algos.pkl")


if __name__ == "__main__":
    main()
