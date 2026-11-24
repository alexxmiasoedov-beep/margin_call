"""s275 — частоты сетапов Г1–Г3 на трёх периодах (2020–2022, 2022–2024, 2024–2026 + свежий отрезок). Доходы не считаются:
скрипт смотрит только данные до момента сетапа (цены после него не читает).

Общее:
- часовая панель (цена часа — закрытие последней 15-мин свечи часа со сделками), вселенная суток — топ-100 по обороту
  за прошлые 30 сут (`liquid_rank`), без BTC и индексных перпов;
- остаток e = r − a − b·BTC − c·альты; коэффициенты пересчитываются в 00:00 UTC каждых суток по 720 прошлым часам
  (МНК по часам без пропусков, ≥ 300 часов); индекс альтов — равный вес перпов с оборотом за прошлые 24 ч ≥ 5 млн $;
- σ24 — СО суточных сумм остатка s24 за прошлые 30 сут (на 00:00 UTC суток), только прошлое.

Г1 «остаточный провал продолжается»: срез каждые 4 ч (конец часа 00, 04, …, 20 UTC), s24 ≤ −2σ24 → (шорт монеты против
    рынка на 24 ч); не чаще раза в 24 ч на монету. Варианты: топ-30 / 31–100, порог 3σ, зеркало (s24 ≥ +2σ24).
Г2 «остаточный рост средних монет откатывается»: ранг 31–100, s24 ≥ +3σ24 → (шорт против рынка 24 ч); раз в 24 ч.
Г3 «перелёт вынужденной продажи в час падения рынка»: час, когда индекс альтов или BTC ≤ −1%; монета с остатком
    часа ≤ −2% и OI в монетах за час ≤ −3% (основной вариант; ещё ≤ −5%) → (лонг против рынка 4 ч); одна на монету
    за 4 ч. OI — s230/metrics (2022–2024), s228/met (2024–2026); за 2020–2022 OI нет — только вариант без OI. Ещё: число
    разных часов (события одного часа зависимы), зеркало «рынок вверх, монета выше беты, OI ≤ −5%».
События — /dev/shm/s275/freq_events_<период>.pkl (для overlap.py).
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/freq.py [период …] → OUT/freq_<периоды>.txt"""
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DAY, H, OUT, PER, TMP, cooldown, fmt, freq_line, load_k, panel, perps, universe  # noqa: E402

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def alt_factor(R, QV, iB):
    cs = np.cumsum(QV, axis=1)
    v = np.zeros_like(cs); v[:, 24:] = cs[:, 24:] - cs[:, :-24]
    ok = np.zeros(R.shape, bool); ok[:, 1:] = v[:, :-1] >= 5e6
    ok[iB] = False
    X = np.where(ok & np.isfinite(R), np.clip(R, -0.5, 0.5), np.nan)
    with np.errstate(all="ignore"):
        return np.nanmean(X, axis=0)


def rolling_resid(y, b, a, T, win=720, min_n=300):
    """Остаток с коэффициентами, пересчитанными в начале каждых суток по win прошлым часам."""
    v = np.isfinite(y) & np.isfinite(b) & np.isfinite(a)
    yy = np.where(v, y, 0.0); bb = np.where(v, b, 0.0); aa = np.where(v, a, 0.0); vv = v.astype(float)
    cs = {k: np.concatenate([[0.0], np.cumsum(x)]) for k, x in
          dict(n=vv, b=bb, a=aa, y=yy, bb=bb * bb, aa=aa * aa, ab=aa * bb, by=bb * yy, ay=aa * yy).items()}
    e = np.full(len(y), np.nan)
    day = ((T - 1) // DAY) * DAY
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(T)]
    for s0, s1 in zip(starts, ends):
        lo = max(0, s0 - win)
        S = {k: c[s0] - c[lo] for k, c in cs.items()}
        if S["n"] < min_n:
            continue
        M = np.array([[S["n"], S["b"], S["a"]], [S["b"], S["bb"], S["ab"]], [S["a"], S["ab"], S["aa"]]])
        rhs = np.array([S["y"], S["by"], S["ay"]])
        try:
            c = np.linalg.solve(M, rhs)
        except np.linalg.LinAlgError:
            continue
        e[s0:s1] = y[s0:s1] - c[0] - c[1] * b[s0:s1] - c[2] * a[s0:s1]
    return e


def rsum(x, k):
    c = np.concatenate([[0.0], np.cumsum(np.where(np.isfinite(x), x, 0.0))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(x))])
    out = np.full(len(x), np.nan)
    out[k - 1:] = c[k:] - c[:-k]
    nb = np.zeros(len(x), int); nb[k - 1:] = bad[k:] - bad[:-k]
    out[nb > 0] = np.nan
    return out


def sigma_daily(s24, T, win_days=30):
    """σ суточных сумм остатка за прошлые win_days сут, на начало суток (по срезам на концах часов 00:00 UTC)."""
    sig = np.full(len(T), np.nan)
    day = ((T - 1) // DAY) * DAY
    at0 = np.flatnonzero((T % DAY) == 0)                    # концы суток (00:00 UTC) — суммы ровно за прошлые сутки
    vals = s24[at0]; tt = T[at0]
    for d in np.unique(day):
        m = (tt <= d) & (tt > d - win_days * DAY) & np.isfinite(vals)
        if m.sum() >= 20:
            sig[day == d] = np.std(vals[m])
    return sig


def oi_series(per, p, T):
    if per == "2022–2024":
        f = f"s230/metrics/{p}.npy"
        if not os.path.exists(f):
            return None
        a = np.load(f, allow_pickle=True)
        if a.ndim != 2 or not len(a):
            return None
        t = a[:, 0].astype(np.int64); oi = a[:, 1].astype(float)
    elif per == "2024–2026":
        f = f"s228/met/{p}.npz"
        if not os.path.exists(f):
            return None
        z = np.load(f)
        t = z["t"].astype(np.int64); oi = z["v"][:, 0].astype(float)
    else:
        return None
    m = (t % H) == 0
    idx = np.searchsorted(T, t[m])
    ok = (idx < len(T)) & (T[np.minimum(idx, len(T) - 1)] == t[m])
    out = np.full(len(T), np.nan)
    out[idx[ok]] = oi[m][ok]
    return out


def run(per):
    t_s = time.time()
    cfg = PER[per]
    K = load_k(per)
    P = perps(K)
    LR = universe(K, P, per)
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    tend = cfg["tb"] or cfg["t1"]
    T, LC, QV = panel(K, P, cfg["t0"], tend, H)
    del K
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = alt_factor(R, QV, iB)
    btc = R[iB]
    day = ((T - 1) // DAY) * DAY
    say(f"\n==== {per}: перпов {len(P)}, часов {len(T)} ({time.time() - t_s:.0f} с)")
    # ранг в топ-100 на каждые сутки (по обороту за прошлые 30 сут — та же сортировка, что у liquid_rank)
    rank_day = {}
    for d, S in LR.items():
        rank_day[d] = S
    ev = {k: [] for k in ("g1", "g1_top30", "g1_31", "g1_3s", "g1_mirror", "g2", "g2_2s", "g2_top30",
                          "g3", "g3_noOI", "g3_mirror", "g3_hours", "g3_noOI_hours", "g1_daily",
                          "g3_oi3", "g3_oi3_hours")}
    # для ранга нужны обороты за 30 сут
    cs_q = np.cumsum(QV, axis=1)
    n_coins = 0
    for p in P:
        if p == "BTC":
            continue
        i = pidx[p]
        member = np.array([p in rank_day.get(int(d), ()) for d in day])
        if not member.any():
            continue
        n_coins += 1
        e = rolling_resid(R[i], btc, alt, T)
        s24 = rsum(e, 24)
        sig = sigma_daily(s24, T)
        # ранг монеты среди вселенной суток: по обороту за 30 сут до суток (cs_q по часам)
        z = s24 / sig
        slots = member & ((T % 14400) == 0) & np.isfinite(z)
        idx = np.flatnonzero(slots)
        # ранг (топ-30 или нет) — по обороту за 720 прошлых часов на начало суток
        for key, cond in (("g1", z[idx] <= -2), ("g1_3s", z[idx] <= -3), ("g1_mirror", z[idx] >= 2),
                          ("g2", z[idx] >= 3), ("g2_2s", z[idx] >= 2)):
            j = idx[cond]
            if len(j):
                keep = cooldown(T[j], DAY)
                for jj in j[keep]:
                    ev[key].append((int(T[jj]), p, int(jj)))
        jd = np.flatnonzero(member & ((T % DAY) == 0) & np.isfinite(z) & (z <= -2))
        if len(jd):
            for jj in jd[cooldown(T[jd], DAY)]:
                ev["g1_daily"].append((int(T[jj]), p, int(jj)))
        # Г3
        down = (alt <= -0.01) | (btc <= -0.01)
        up = (alt >= 0.01) | (btc >= 0.01)
        oi = oi_series(per, p, T)
        doi = np.full(len(T), np.nan)
        if oi is not None:
            doi[1:] = oi[1:] / oi[:-1] - 1
        c3n = member & down & (e <= -0.02)
        j = np.flatnonzero(c3n)
        if len(j):
            for jj in j[cooldown(T[j], 4 * H)]:
                ev["g3_noOI"].append((int(T[jj]), p, int(jj)))
        if oi is not None:
            j = np.flatnonzero(c3n & (doi <= -0.05))
            if len(j):
                for jj in j[cooldown(T[j], 4 * H)]:
                    ev["g3"].append((int(T[jj]), p, int(jj)))
            j = np.flatnonzero(c3n & (doi <= -0.03))
            if len(j):
                for jj in j[cooldown(T[j], 4 * H)]:
                    ev["g3_oi3"].append((int(T[jj]), p, int(jj)))
            j = np.flatnonzero(member & up & (e >= 0.02) & (doi <= -0.05))
            if len(j):
                for jj in j[cooldown(T[j], 4 * H)]:
                    ev["g3_mirror"].append((int(T[jj]), p, int(jj)))
    say(f"  монет во вселенной хотя бы сутки: {n_coins} ({time.time() - t_s:.0f} с)")
    # ранг для разделения топ-30 / 31–100: по обороту за 30 сут до начала суток
    def rank_of(p, t):
        d = int(((t - 1) // DAY) * DAY)
        S = rank_day.get(d)
        if not S:
            return 999
        j = int(np.searchsorted(T, d)) - 1
        lo = max(0, j - 720)
        vals = sorted(((cs_q[pidx[q], j] - cs_q[pidx[q], lo]) if j >= 0 else 0.0, q) for q in S if q in pidx)
        order = [q for _, q in sorted(vals, reverse=True)]
        return order.index(p) if p in order else 999
    for key_src, key_dst, lo, hi in (("g1", "g1_top30", 0, 30), ("g1", "g1_31", 30, 100), ("g2_2s", "g2_top30", 0, 30)):
        for t, p, jj in ev[key_src]:
            r = rank_of(p, t)
            if lo <= r < hi:
                ev[key_dst].append((t, p, jj))
    g2_31 = [(t, p, jj) for t, p, jj in ev["g2"] if 30 <= rank_of(p, t) < 100]
    ev["g2"] = g2_31
    ev["g3_hours"] = [(t, "", 0) for t in sorted({t for t, _, _ in ev["g3"]})]
    ev["g3_noOI_hours"] = [(t, "", 0) for t in sorted({t for t, _, _ in ev["g3_noOI"]})]
    ev["g3_oi3_hours"] = [(t, "", 0) for t in sorted({t for t, _, _ in ev["g3_oi3"]})]
    names = dict(g1="Г1 остаточный провал за 24 ч ≤ −2σ (топ-100, срез раз в 4 ч)",
                 g1_top30="   в т. ч. топ-30", g1_31="   в т. ч. 31–100", g1_3s="   порог −3σ",
                 g1_daily="   только срез 00:00 UTC", g1_mirror="   зеркало: рост ≥ +2σ (все)",
                 g2="Г2 остаточный рост ≥ +3σ у монет 31–100", g2_2s="   порог +2σ (топ-100)",
                 g2_top30="   рост ≥ +2σ у топ-30 (для сравнения)",
                 g3="Г3 перелёт с выносом OI в час падения рынка (монето-события)",
                 g3_hours="   разных часов", g3_oi3="   OI ≤ −3% (основной вариант после замысла)",
                 g3_oi3_hours="   OI ≤ −3% — разных часов", g3_noOI="   без условия OI (s271 Г8-подобный)",
                 g3_noOI_hours="   без OI — разных часов", g3_mirror="   зеркало: рынок вверх, выше беты, OI ≤ −5%")
    for key in ("g1", "g1_top30", "g1_31", "g1_3s", "g1_daily", "g1_mirror", "g2", "g2_2s", "g2_top30",
                "g3", "g3_hours", "g3_oi3", "g3_oi3_hours", "g3_noOI", "g3_noOI_hours", "g3_mirror"):
        Tev = [t for t, _, _ in ev[key]]
        if not Tev and key.startswith("g3") and per == "2020–2022" and "noOI" not in key:
            say(f"  {names[key]}: OI за этот период нет")
            continue
        say(f"  {names[key]}: {fmt(freq_line(Tev, per))}")
    pickle.dump({k: v for k, v in ev.items()}, open(f"{TMP}/freq_events_{per}.pkl", "wb"))
    say(f"  ({time.time() - t_s:.0f} с)")


if __name__ == "__main__":
    pers = sys.argv[1:] or list(PER)
    for per in pers:
        run(per)
    tag = "_".join(p[:4] for p in pers)
    open(f"{OUT}/freq_{tag}.txt", "w").write("\n".join(LINES) + "\n")
