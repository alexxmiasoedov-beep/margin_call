"""Г4. Займ перед объявлениями Binance (Engelberg, Reed & Ringgenberg: шорт сильнее предсказывает в дни плохих новостей;
корейские шортисты занимали заранее перед уменьшением капитала). События — сделки журнала 📢 из бэктеста s12
(s12/final_journals.pkl «B»: метка мониторинга, делистинг спота, делистинг фьючерса; вход не позже часа после публикации).
Для каждой монеты по архиву MarginData (s7/margin.pkl):
  - доля постов канала за сутки, где монета была (присутствие), и средний BOR за сутки — в окне −20…+7 суток;
  - база монеты: все её сутки в архиве, кроме ±30 суток вокруг любого её события 📢;
  - плацебо: до 50 случайных дат той же монеты вне окон событий — та же статистика окна −10…−1 сутки.
Затем сделки 📢: с займом перед событием (монета была в канале в окне −10…−1) против без него.
Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, G, PREF

M = pickle.load(open("s7/margin.pkl", "rb")); PT = np.sort(M["PT"])
D0 = int(PT[0] // DAY + 1) * DAY; D1 = int(PT[-1] // DAY) * DAY
DAYS = np.arange(D0, D1, DAY)
NPOST = np.histogram(PT, bins=np.r_[DAYS, D1])[0]                    # постов канала за сутки


def daily(coin):
    """Присутствие (доля постов) и средний BOR по суткам архива; NaN — монеты в канале не было."""
    g = G.get(coin)
    pres, bor = np.zeros(len(DAYS)), np.full(len(DAYS), np.nan)
    if g is None:
        return pres, bor
    k = np.searchsorted(DAYS, g[:, 0], "right") - 1
    ok = (k >= 0) & (k < len(DAYS))
    cnt = np.bincount(k[ok], minlength=len(DAYS)); s = np.bincount(k[ok], weights=g[ok, 1], minlength=len(DAYS))
    pres = np.where(NPOST > 0, cnt / np.maximum(NPOST, 1), 0.0)
    bor = np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)
    return pres, bor


def window(pres, bor, d, a, b):
    """Статистика окна суток [d + a, d + b]: средняя доля присутствия, средний BOR по суткам присутствия."""
    i0, i1 = d + a, d + b + 1
    if i0 < 0 or i1 > len(DAYS):
        return np.nan, np.nan
    return pres[i0:i1].mean(), np.nanmean(bor[i0:i1]) if np.isfinite(bor[i0:i1]).any() else np.nan


if __name__ == "__main__":
    B = pd.read_pickle("s12/final_journals.pkl")["B"].copy()
    B["coin"] = [c if c in G else PREF.sub("", c) for c in B.s]
    B["d"] = ((B.te // DAY) * DAY - D0) // DAY
    B = B[(B.d >= 20) & (B.d + 7 < len(DAYS))].reset_index(drop=True)
    print(f"событий 📢 с полным окном архива (−20…+7 суток): {len(B)} из 156; по типам: "
          + ", ".join(f"{k} {v}" for k, v in B.kind.value_counts().items()))
    rng = np.random.default_rng(7)
    prof_p, prof_b, rows, plac = [], [], [], []
    for coin, g in B.groupby("coin"):
        pres, bor = daily(coin)
        excl = np.zeros(len(DAYS), bool)
        for d in g.d:
            excl[max(0, d - 30):d + 31] = True
        base_p = pres[~excl].mean() if (~excl).any() else np.nan
        base_b = np.nanmedian(bor[~excl]) if np.isfinite(bor[~excl]).any() else np.nan
        for e in g.itertuples():
            prof_p.append(pres[e.d - 20:e.d + 8] - base_p)
            prof_b.append(bor[e.d - 20:e.d + 8] / base_b if base_b and np.isfinite(base_b) else np.full(28, np.nan))
            p, b = window(pres, bor, e.d, -10, -1)
            rows.append(dict(i=e.Index, coin=coin, kind=e.kind, te=e.te, sp=e.sp, h=e.h, pre_p=p, pre_b=b,
                             base_p=base_p, base_b=base_b, any_pre=p > 0))
        cand = np.flatnonzero(~excl[:len(DAYS) - 8]); cand = cand[cand >= 20]
        for d in rng.choice(cand, min(50, len(cand)), replace=False) if len(cand) else []:
            p, b = window(pres, bor, d, -10, -1)
            plac.append(dict(coin=coin, pre_p=p, pre_b=b, base_p=base_p, base_b=base_b, any_pre=p > 0))
    R, P = pd.DataFrame(rows), pd.DataFrame(plac)
    print("\n1. Займ перед событием (окно −10…−1 сутки) против плацебо-дат тех же монет:")
    for nm, d in (("события 📢", R), ("плацебо", P)):
        rb = d.pre_b / d.base_b
        print(f"  {nm:11s} n={len(d):5d}: монета была в канале {d.any_pre.mean():.0%}; доля постов с монетой {d.pre_p.mean():.3f} "
              f"(база монеты {d.base_p.mean():.3f}); BOR к медиане монеты (где была) {np.nanmedian(rb):.2f}× (среднее "
              f"{np.nanmean(rb):.2f}×), доля ≥ 2× {np.nanmean(rb >= 2):.0%}")
    diff = R.pre_p.values - R.base_p.values; pdiff = P.pre_p.values - P.base_p.values
    perm = [rng.choice(pdiff, len(diff)).mean() for _ in range(5000)]
    print(f"  присутствие сверх базы: события {np.nanmean(diff):+.4f}, плацебо {np.nanmean(pdiff):+.4f}; "
          f"перестановочный p = {np.mean(np.array(perm) >= np.nanmean(diff)):.3f}")
    print("\n2. Профиль по суткам (−20…+7): присутствие сверх базы монеты и BOR к медиане монеты (медиана по событиям):")
    pp, pb = np.vstack(prof_p), np.vstack(prof_b)
    for k in range(0, 28, 3):
        print(f"  сутки {k - 20:+3d}: присутствие {np.nanmean(pp[:, k]):+.3f}, BOR {np.nanmedian(pb[:, k]):.2f}×, "
              f"событий с монетой в канале {np.mean(np.isfinite(pb[:, k])):.0%}")
    print("\n3. Сделки 📢 (шорт из s12, sp — цена+фандинг, h — с хеджем): с займом перед событием против без него:")
    for nm, m in (("монета была в канале за −10…−1", R.any_pre), ("не была", ~R.any_pre),
                  ("BOR ≥ 2× медианы монеты", R.pre_b / R.base_b >= 2), ("остальные", ~(R.pre_b / R.base_b >= 2))):
        g = R[m]
        if len(g) < 5:
            print(f"  {nm}: n={len(g)} — мало"); continue
        h1, h2 = g.sp[g.te < CUT], g.sp[g.te >= CUT]
        print(f"  {nm:32s} n={len(g):3d}: {g.sp.mean() * 100:+.2f}% (медиана {g.sp.median() * 100:+.2f}%, в плюсе "
              f"{(g.sp > 0).mean():.0%}), с хеджем {g.h.mean() * 100:+.2f}%; половины {h1.mean() * 100:+.2f}/{h2.mean() * 100:+.2f}%")
    print("  по типам, был в канале / не был: " + "; ".join(
        f"{k}: {g.sp[g.any_pre].mean() * 100:+.1f}% ({g.any_pre.sum()}) / {g.sp[~g.any_pre].mean() * 100:+.1f}% ({(~g.any_pre).sum()})"
        for k, g in R.groupby("kind")))
    R.to_pickle("s22/h4_events.pkl")
