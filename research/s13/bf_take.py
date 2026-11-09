"""Журнал 🏦 с тейком по сумме с хеджем: те же входы, что у 🏦 (каждый день в 01:00 UTC топ-10 по займу → 5 самых
волатильных, одна открытая сделка на монету), но выход, как только шорт + лонг BTC на ту же сумму (с фандингом обеих ног
и комиссией 0,1% за круг на каждую) дают ≥ +X%; иначе через 168 ч, как у 🏦. Итог считается каждые 15 мин по закрытиям
свечей. Стоп +100% у шорта — как в боте.

Что делать после досрочного выхода:
  A — монета свободна: снова шорт на ближайшем ежедневном наборе в 01:00 UTC, если она в топ-5 (как в боте сейчас);
  B — ждать: монета занята до конца исходных 168 ч, потом — как обычно;
  C — сразу снова шорт той же монеты по цене выхода, если она в последнем ежедневном наборе.

Запуск из папки с данными ветки data (s2/k2y.pkl, s2/fund2y.pkl, s10/daily_panel.pkl — research/s10/daily_panel.py):
  python3 s13/bf_take.py"""
import datetime
import pickle
import numpy as np, pandas as pd

UTC = datetime.timezone.utc
CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()      # граница половин, как в research/s10
D = pd.read_pickle("s10/daily_panel.pkl")
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
BAR, HOLD = 900, 672                                                # 15 мин; 168 ч = 672 свечи
FEE = 0.001                                                         # комиссия за круг на одну ногу

# Набор дня — ровно как в research/s10/journal_sim2.py (5 из топ-10) и в боте (scanner.borrow_factor_rule)
d = D[(D.v >= 10e6) & D.ret7.notna()]
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
top = top.assign(vr=top.groupby("T").vol.rank(ascending=False, method="first")).query("vr <= 5").sort_values("T")
DAYS = {T: list(g.s) for T, g in top.groupby("T")}


def fcum(s):
    """Накопленный фандинг монеты: F(a, b) — сумма ставок за начисления в (a, b] (>0 — платят лонги, шорт получает)."""
    f = FU.get(s)
    if f is None:
        return lambda a, b: np.zeros(np.shape(b))
    ft, cs = f[:, 0], np.r_[0, np.cumsum(f[:, 2])]
    return lambda a, b: cs[np.searchsorted(ft, b, "right")] - cs[np.searchsorted(ft, a, "right")]


FC = {}
B = K["BTC"]; FB = fcum("BTC")


def trade(s, t0, tp, stop_on=True):
    """Шорт s с t0 (начало 15-мин свечи) + лонг BTC на ту же сумму. Возвращает (время выхода, итог с хеджем, итог шорта,
    причина, максимум итога с хеджем за срок) или None, если свечей нет. tp=None — без тейка (как 🏦)."""
    a = K[s]; j0 = np.searchsorted(a["t"], t0); b0 = np.searchsorted(B["t"], t0)
    if j0 + HOLD >= len(a["t"]) or b0 + HOLD >= len(B["t"]) or a["t"][j0] != t0 or B["t"][b0] != t0 \
            or a["t"][j0 + HOLD] != t0 + HOLD * BAR or B["t"][b0 + HOLD] != t0 + HOLD * BAR:
        return None
    F = FC.setdefault(s, fcum(s))
    p0, q0 = float(a["o"][j0]), float(B["o"][b0])
    te = t0 + BAR * np.arange(1, HOLD + 1)                          # конец каждой свечи
    c = a["c"][j0:j0 + HOLD].astype(float); cb = B["c"][b0:b0 + HOLD].astype(float)
    short = -(c / p0 - 1) + F(t0, te) - FEE
    comb = short + (cb / q0 - 1) - FB(t0, te) - FEE
    stop = (a["h"][j0:j0 + HOLD].astype(float) >= 2 * p0) & stop_on
    hit = np.flatnonzero((comb >= tp) | stop) if tp is not None else np.flatnonzero(stop)
    if len(hit):
        k = hit[0]
        if stop[k] and not (tp is not None and comb[k] >= tp):
            sh = -1.0 + F(t0, te[k]) - FEE                          # стоп +100%: шорт при ×1 теряет всю маржу
            return te[k], sh + (cb[k] / q0 - 1) - FB(t0, te[k]) - FEE, sh, "стоп", comb[:k + 1].max()
        return te[k], comb[k], short[k], "тейк", comb[:k + 1].max()
    t1 = t0 + HOLD * BAR                                            # 168 ч — по открытию свечи, как в research/s10
    sh = -(float(a["o"][j0 + HOLD]) / p0 - 1) + F(t0, t1) - FEE
    return t1, sh + (float(B["o"][b0 + HOLD]) / q0 - 1) - FB(t0, t1) - FEE, sh, "168 ч", comb.max()


def journal(tp=None, policy="A", stop_on=True):
    busy, tr = {}, []                                               # монета → до какого времени занята
    for T in sorted(DAYS):
        for s in DAYS[T]:
            if busy.get(s, 0) > T:
                continue
            t0, n = T, 0
            while True:
                r = trade(s, t0, tp, stop_on)
                if r is None:
                    break
                t1, h, sh, why, mx = r
                tr.append(dict(T=t0, s=s, t1=t1, h=h, p=sh, why=why, re=n > 0, mx=mx))
                busy[s] = t1 if policy in ("A", "C") else max(t1, T + HOLD * BAR)
                day = (t1 - 3600) // 86400 * 86400 + 3600           # последний набор в 01:00 UTC до выхода
                if not (policy == "C" and why == "тейк" and s in DAYS.get(day, ()) and t1 % BAR == 0):
                    break
                t0, n = t1, n + 1                                   # C: сразу снова шорт по цене выхода
    return pd.DataFrame(tr)


def report(name, tr):
    tr = tr.assign(half=np.where(tr["T"] < CUT, 1, 2), days=(tr.t1 - tr["T"]) / 86400)
    span = (tr.t1.max() - tr["T"].min()) / 86400
    ex = tr.sort_values("t1"); eq = ex.h.cumsum()                   # просадка — по закрытым сделкам, в порядке выхода
    wk = pd.to_datetime(tr.t1, unit="s").dt.to_period("W"); W = tr.groupby(wk).h.sum()
    h1, h2 = tr[tr.half == 1], tr[tr.half == 2]
    print(f"\n{name}")
    print(f"  сделок {len(tr)} ({len(tr) / span * 7:.1f} в неделю), открыто одновременно в среднем {tr.days.sum() / span:.1f}, "
          f"держали в среднем {tr.days.mean() * 24:.0f} ч; выход: " + ", ".join(f"{k} {v:.0%}" for k, v in tr.why.value_counts(normalize=True).items()))
    print(f"  на сделку с хеджем {tr.h.mean() * 100:+.2f}% (медиана {tr.h.median() * 100:+.2f}%, в плюсе {(tr.h > 0).mean():.0%}; "
          f"1-я/2-я половина {h1.h.mean() * 100:+.2f}/{h2.h.mean() * 100:+.2f}); только шорт {tr.p.mean() * 100:+.2f}%")
    print(f"  маржа 1 USDT ×1 на сделку: с хеджем {tr.h.sum():+.1f} USDT (1-я/2-я {h1.h.sum():+.1f}/{h2.h.sum():+.1f}), просадка "
          f"{(eq - eq.cummax()).min():.1f}, недель в плюсе {(W > 0).mean():.0%}; только шорт {tr.p.sum():+.1f} USDT; "
          f"на сделко-день {tr.h.sum() / tr.days.sum() * 100:+.3f}%; хуже −50%: {(tr.h < -0.5).sum()}")
    return tr


if __name__ == "__main__":
    print(f"Наборы: {len(DAYS)} дней, {datetime.datetime.fromtimestamp(min(DAYS), UTC):%d.%m.%Y} – "
          f"{datetime.datetime.fromtimestamp(max(DAYS), UTC):%d.%m.%Y}")
    report("сверка с research/s10/journal_sim2.py — 168 ч без стопа (там 884 сделки, +3,26% с хеджем)", journal(None, stop_on=False))
    base = report("🏦 как в боте: 168 ч, стоп +100%", journal(None))
    for tp in (0.05, 0.10):                                         # что отрезает тейк: сделки 🏦, которые хоть раз дошли до +X%
        hit = base[base.mx >= tp]
        print(f"  дошли до +{tp * 100:.0f}% с хеджем хоть раз за 168 ч: {len(hit)} из {len(base)} ({len(hit) / len(base):.0%}); у них итог "
              f"через 168 ч {hit.h.mean() * 100:+.2f}% на сделку (медиана {hit.h.median() * 100:+.2f}%), хуже 0 — {(hit.h < 0).mean():.0%}; "
              f"остальные {base[base.mx < tp].h.mean() * 100:+.2f}%")
    for tp in (0.03, 0.05, 0.07, 0.10):
        for pol, txt in (("A", "снова шорт на ближайшем наборе, если монета в топ-5"), ("B", "ждать конца 168 ч"),
                         ("C", "сразу снова шорт, если монета в последнем наборе")):
            if tp != 0.05 and pol == "C":
                continue
            report(f"тейк +{tp * 100:.0f}% с хеджем, после тейка — {txt} ({pol})", journal(tp, pol))
    for pol in ("A", "B"):                                          # стоп по последней цене строже, чем по марк-цене в боте
        report(f"без стопа: тейк +5% с хеджем ({pol})", journal(0.05, pol, stop_on=False))
