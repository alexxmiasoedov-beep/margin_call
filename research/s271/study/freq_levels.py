"""s271, дополнение владельца — частоты событий у зон поддержки и сопротивления и у «баз» (проторговок). Доходы не считаются.
Все признаки считаются только по свечам, закрытым к моменту события (без заглядывания вперёд). Правила — reports/уровни.md.

Таймфреймы: 15 мин (свечи архива) и 1 ч (четыре 15-мин свечи часа). ATR_pre — средний истинный диапазон за 96 свечей
перед окном базы (обычная волатильность до базы).

У1 «пробой базы» (平台突破, 박스권 돌파, пробой проторговки):
  база на свече t — окно из N = 24 свечей [t − 23, t]: диапазон R = max(high) − min(low) ≤ 2,5·ATR_pre; ход за окно
  |c_t − c_{t−23}| ≤ 0,5·R; у верхней и у нижней границы ≥ 2 касаний (свечи с high ≥ верх − 0,1·R / low ≤ низ + 0,1·R);
  событие — свеча t + 1 закрылась выше верха + 0,1·ATR_pre (вверх) или ниже низа − 0,1·ATR_pre (вниз);
  вариант «с объёмом» — оборот свечи пробоя ≥ 2× среднего оборота свечи базы.
У2 «ложный пробой базы» (假突破, Wyckoff spring/upthrust): тень свечи t + 1 вышла за границу на ≥ 0,1·ATR_pre, а закрытие
  осталось внутри (1 свеча); вариант «2 свечи» — пробой по У1 и закрытие следующей свечи снова внутри базы.
У3 «ретест пробитой границы» (回踩确认, 눌림목, зеркальный уровень): после пробоя по У1 цена ушла от границы на ≥ 0,5·ATR_pre,
  затем впервые вернулась к ней (low ≤ граница + 0,25·ATR_pre при пробое вверх) в 24 свечи и закрылась по ту же сторону.
У4 «пробой уровня прошлых суток / недели» (часовые свечи): первое за сутки UTC закрытие часа выше максимума или ниже
  минимума прошлых суток; то же для недели (с понедельника 00:00 UTC); вариант «узкий день» — прошлые сутки с самым
  узким диапазоном из 7 (NR7, Crabel).
У5 «касание сильной горизонтальной зоны» (часовые свечи): фракталы (максимум/минимум 3 свечи слева и справа, известны
  через 3 свечи) за прошлые 7 сут; зона — фракталы в пределах ±0,2·ATR(14) от ближайшего уровня; касания — фракталы зоны,
  разнесённые ≥ 6 ч, их ≥ 3; последний старше 12 ч; событие — свеча вошла в зону, а прошлое закрытие было дальше
  1·ATR от её края; «зеркальная» — в зоне есть и максимумы, и минимумы.
Вселенная — 100 перпов с наибольшим оборотом за прошлые 30 сут (возраст ≥ 30 сут); по монете одно событие вида за N свечей.

События (монета, вид, таймфрейм, время закрытия свечи события, уровень, ATR) — `/dev/shm/s271/levels_<период>.pkl`
(pandas); функция `collect(период)` возвращает ту же таблицу для проверки доходов.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s271/study/freq_levels.py [период …]"""
import os
import pickle
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import BAR, DAY, H, PER_ALL, TMP, crypto_perps, fmt, freq_line, liquid_rank, load_k  # noqa: E402

N, PRE = 24, 96
SWV = np.lib.stride_tricks.sliding_window_view


def to_hour(a):
    t = a["t"].astype(np.int64)
    i = np.flatnonzero(t % H == 0)
    i = i[i + 3 < len(t)]
    i = i[t[i + 3] == t[i] + 3 * BAR]
    hh = np.maximum.reduce([a["h"][i + k] for k in range(4)]).astype(float)
    ll = np.minimum.reduce([a["l"][i + k] for k in range(4)]).astype(float)
    qv = sum(a["qv"][i + k].astype(float) for k in range(4))
    return dict(t=t[i], h=hh, l=ll, c=a["c"][i + 3].astype(float), qv=qv, step=H)


def to_q(a):
    return dict(t=a["t"].astype(np.int64), h=a["h"].astype(float), l=a["l"].astype(float), c=a["c"].astype(float),
                qv=a["qv"].astype(float), step=BAR)


def roll_mean(x, w):
    cs = np.r_[0.0, np.cumsum(x)]
    out = np.full(len(x), np.nan)
    out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def base_events(b, add):
    """У1–У3 по одному ряду свечей; add(вид, время закрытия, уровень, ATR)."""
    t, h, l, c, qv, step = b["t"], b["h"], b["l"], b["c"], b["qv"], b["step"]
    n = len(t)
    if n < N + PRE + 30:
        return
    cont = np.r_[False, np.diff(t) == step]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    atr_pre = np.full(n, np.nan)
    atr_pre[N:] = roll_mean(tr, PRE)[:-N]                    # средний TR за 96 свечей до окна [t − N + 1, t]
    top = np.full(n, np.nan); bot = np.full(n, np.nan)
    Hw = SWV(h, N); Lw = SWV(l, N)
    top[N - 1:] = Hw.max(axis=1); bot[N - 1:] = Lw.min(axis=1)
    R = top - bot
    ok_live = np.zeros(n, bool); ok_live[N - 1:] = SWV((qv > 0).astype(float), N).min(axis=1) > 0
    ok_cont = np.zeros(n, bool); ok_cont[N - 1:] = SWV(cont.astype(float), N)[:, 1:].min(axis=1) > 0
    move = np.full(n, np.nan); move[N - 1:] = np.abs(c[N - 1:] - c[:n - N + 1])
    nt_top = np.zeros(n); nt_bot = np.zeros(n)
    nt_top[N - 1:] = (Hw >= (top[N - 1:] - 0.1 * R[N - 1:])[:, None]).sum(axis=1)
    nt_bot[N - 1:] = (Lw <= (bot[N - 1:] + 0.1 * R[N - 1:])[:, None]).sum(axis=1)
    mq = np.full(n, np.nan); mq[N - 1:] = SWV(qv, N).mean(axis=1)
    with np.errstate(invalid="ignore"):
        base = (ok_live & ok_cont & (atr_pre > 0) & (R <= 2.5 * atr_pre) & (move <= 0.5 * R)
                & (nt_top >= 2) & (nt_bot >= 2))
    last = {"up": -10 ** 9, "dn": -10 ** 9, "ft": -10 ** 9}
    for k in np.flatnonzero(base[:-2]):
        j = k + 1
        if t[j] != t[k] + step or qv[j] <= 0:
            continue
        A = atr_pre[k]; Tp, Bt = top[k], bot[k]
        te = int(t[j]) + step
        up = c[j] > Tp + 0.1 * A; dn = c[j] < Bt - 0.1 * A
        if up or dn:
            key = "up" if up else "dn"
            if j - last[key] < N:
                continue
            last[key] = j
            side = 1 if up else -1
            Lv = Tp if up else Bt
            nm = "вверх" if up else "вниз"
            add(f"У1 пробой {nm}", te, Lv, A)
            if qv[j] >= 2 * mq[k]:
                add(f"У1 пробой {nm} с объёмом ×2", te, Lv, A)
            if j + 1 < n and t[j + 1] == t[j] + step and Bt <= c[j + 1] <= Tp:
                add(f"У2 ложный пробой {nm} за 2 свечи", int(t[j + 1]) + step, Lv, A)
            far = False
            for r in range(j + 1, min(j + 1 + 24, n)):
                if t[r] != t[j] + (r - j) * step:
                    break
                back = (l[r] <= Lv + 0.25 * A) if up else (h[r] >= Lv - 0.25 * A)
                if back:
                    if far and side * (c[r] - Lv) >= 0:
                        add(f"У3 ретест с удержанием после пробоя {nm}", int(t[r]) + step, Lv, A)
                    break
                far |= (h[r] >= Lv + 0.5 * A) if up else (l[r] <= Lv - 0.5 * A)
            continue
        if j - last["ft"] < N:
            continue
        if h[j] > Tp + 0.1 * A and c[j] <= Tp:
            add("У2 ложный пробой вверх за 1 свечу", te, Tp, A); last["ft"] = j
        elif l[j] < Bt - 0.1 * A and c[j] >= Bt:
            add("У2 ложный пробой вниз за 1 свечу", te, Bt, A); last["ft"] = j


def day_week_events(b, add):
    """У4 на часовых свечах: первое за сутки (неделю) закрытие часа за максимумом/минимумом прошлых суток (недели)."""
    t, h, l, c = b["t"], b["h"], b["l"], b["c"]
    for per_len, name, off in ((DAY, "сутки", 0), (7 * DAY, "неделя", 3 * DAY)):   # неделя с понедельника (01.01.1970 — четверг)
        key = (t + off) // per_len
        u, first = np.unique(key, return_index=True)
        hi = np.maximum.reduceat(h, first); lo = np.minimum.reduceat(l, first)
        cnt = np.diff(np.r_[first, len(t)])
        full = cnt >= (24 if per_len == DAY else 150)
        rng = hi - lo
        for g in range(1, len(u)):
            if u[g] != u[g - 1] + 1 or not full[g - 1]:
                continue
            s0, s1 = first[g], first[g] + cnt[g]
            cc = c[s0:s1]
            iu = np.flatnonzero(cc > hi[g - 1]); idn = np.flatnonzero(cc < lo[g - 1])
            nr7 = per_len == DAY and g >= 7 and all(u[g - x] == u[g] - x and full[g - x] for x in range(1, 8)) \
                and rng[g - 1] < min(rng[g - 7:g - 1])
            for ii, nm, lv in ((iu, "максимума", hi[g - 1]), (idn, "минимума", lo[g - 1])):
                if len(ii):
                    te = int(t[s0 + ii[0]]) + H
                    add(f"У4 пробой {nm} ({name})", te, lv, rng[g - 1])
                    if nr7:
                        add(f"У4 пробой {nm} узкого дня (NR7)", te, lv, rng[g - 1])


def zone_events(b, days_ok, add):
    """У5 на часовых свечах: касание зоны из ≥ 3 разнесённых фракталов за 7 сут (±0,2·ATR)."""
    t, h, l, c = b["t"], b["h"], b["l"], b["c"]
    n = len(t)
    if n < 200:
        return
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    atr = np.r_[np.nan, roll_mean(tr, 14)[:-1]]                # ATR за 14 прошлых свечей
    W = SWV(h, 7); Wl = SWV(l, 7)
    ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    ph[3:n - 3] = (h[3:n - 3] >= W.max(axis=1)) & (h[3:n - 3] > W[:, 4:].max(axis=1))
    pl[3:n - 3] = (l[3:n - 3] <= Wl.min(axis=1)) & (l[3:n - 3] < Wl[:, 4:].min(axis=1))
    piv_i = np.flatnonzero(ph | pl)
    piv_p = np.where(ph[piv_i], h[piv_i], l[piv_i])
    piv_hi = ph[piv_i]
    conf = piv_i + 3                                           # фрактал известен на закрытии свечи i + 3
    last_ev = -10 ** 9
    for k in range(200, n):
        if k - last_ev < 6 or t[k] != t[k - 1] + H or not atr[k] > 0:
            continue
        if (int(t[k]) // DAY) * DAY not in days_ok:
            continue
        lo_i = np.searchsorted(conf, k - 168); hi_i = np.searchsorted(conf, k - 1, side="right")
        if hi_i - lo_i < 3:
            continue
        P = piv_p[lo_i:hi_i]; I = piv_i[lo_i:hi_i]; HI = piv_hi[lo_i:hi_i]
        A = atr[k]; tol = 0.2 * A
        for side in (1, -1):                                    # 1 — поддержка (цена пришла сверху), −1 — сопротивление
            cand = P[P < c[k - 1] - tol - A] if side == 1 else P[P > c[k - 1] + tol + A]
            if not len(cand):
                continue
            lv = cand.max() if side == 1 else cand.min()        # ближайший уровень
            if not ((l[k] <= lv + tol) if side == 1 else (h[k] >= lv - tol)):
                continue
            m = np.abs(P - lv) <= tol
            Im = np.sort(I[m])
            touches, last = 0, -10 ** 9
            for x in Im:
                if x - last >= 6:
                    touches += 1; last = x
            if touches < 3 or k - Im[-1] < 12:
                continue
            nm = "поддержка" if side == 1 else "сопротивление"
            add(f"У5 касание зоны ≥ 3 касаний ({nm})", int(t[k]) + H, lv, A)
            if HI[m].any() and (~HI[m]).any():
                add(f"У5 касание «зеркальной» зоны ({nm})", int(t[k]) + H, lv, A)
            if touches >= 4:
                add(f"У5 касание зоны ≥ 4 касаний ({nm})", int(t[k]) + H, lv, A)
            last_ev = k
            break


def collect(per):
    K = load_k(per)
    P = crypto_perps(K)
    cache = f"{TMP}/liq100_{per}.pkl"
    if os.path.exists(cache):
        LR = pickle.load(open(cache, "rb"))
    else:
        LR = liquid_rank(K, P, per, top=100, window=30)
        pickle.dump(LR, open(cache, "wb"))
    days_of = defaultdict(set)
    for d, ss in LR.items():
        for p in ss:
            days_of[p].add(d)
    rows = []
    for p in P:
        dd = days_of.get(p)
        if not dd:
            continue
        a = K[p]
        for tf, b in (("15 мин", to_q(a)), ("1 ч", to_hour(a))):
            def add(kind, te, lv, A, tf=tf, step=b["step"]):
                if ((te - step) // DAY) * DAY in dd:
                    rows.append((p, kind, tf, int(te), float(lv), float(A)))
            base_events(b, add)
            if tf == "1 ч":
                day_week_events(b, add)
                zone_events(b, dd, add)
    X = pd.DataFrame(rows, columns=["s", "kind", "tf", "t", "level", "atr"])
    for col in ("s", "kind", "tf"):
        X[col] = X[col].astype("category")
    return X


def run(per):
    cfg = PER_ALL[per]
    X = collect(per)
    X.to_pickle(f"{TMP}/levels_{per}.pkl")
    print(f"\n== {per} (вселенная — 100 ликвидных перпов в сутки; событий {len(X)})")
    for (tf, kind), g in X.groupby(["tf", "kind"], observed=True):
        print(f"{tf:6s} {kind:52s} {fmt(freq_line(g.t.values, cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")


if __name__ == "__main__":
    for per in (sys.argv[1:] or list(PER_ALL)):
        run(per)
