"""s283 — движок лимитных входов по 15-мин свечам (заготовка; правила гипотез — в ВЫВОДЫ.md после изучения s282).

Лимитка на свечу i стоит на уровне L = ref · (1 − side · x), где ref — закрытие свечи i − 1 (уровень переставляется
каждые 15 мин). side = +1 — покупка ниже цены (лонг на прострел вниз), side = −1 — продажа выше цены (шорт на прострел
вверх). Исполнение — если цена прошла уровень с проколом pen: low ≤ L · (1 − pen) для покупки, high ≥ L · (1 + pen)
для продажи (касание без прокола не считается). Цена входа — L.

Выход:
- hold = 0 — закрытие свечи исполнения;
- hold = n > 0 — закрытие свечи i + n; стоп sl и тейк tp проверяются по свечам i + 1 … i + n (свеча исполнения не
  проверяется: порядок цен внутри неё неизвестен); если в одной свече и стоп, и тейк — считается стоп;
- стоп исполняется по худшей из цены стопа и открытия свечи с проскальзыванием slip; тейк — лимиткой по цене тейка.
Комиссии: вход — мейкер fee_in, выход по времени и стопу — тейкер fee_out, тейк — мейкер fee_in. Фандинг — фактический
за [вход, выход] по массиву начислений (t, ставка), шорт получает положительный фандинг.
Одна позиция на монету: следующая лимитка ставится со свечи после выхода (cool — ещё пауза в свечах)."""
import numpy as np

BAR = 900


def run(a, x, side, pen=0.002, hold=0, sl=None, tp=None, fee_in=0.0002, fee_out=0.0005, slip=0.002, cool=0,
        fund=None, mask=None):
    """a — dict массивов свечей монеты (t, o, h, l, c, qv); mask[i] — можно ли ставить лимитку на свечу i.
    Возвращает список сделок: (i входа, t входа, цена входа, i выхода, t выхода, цена выхода, причина, доход)."""
    t = a["t"].astype(np.int64)
    o, h, lo, c = (a[k].astype(float) for k in ("o", "h", "l", "c"))
    qv = a["qv"].astype(float)
    n = len(t)
    if fund is not None and len(fund):
        ft = fund[:, 0].astype(np.int64)
        cs = np.r_[0.0, np.cumsum(fund[:, 1])]
    else:
        ft, cs = np.zeros(0, np.int64), np.zeros(1)
    ref = np.r_[np.nan, c[:-1]]
    L = ref * (1 - side * x)
    cont = np.r_[False, (t[1:] - t[:-1]) == BAR] & (qv > 0) & np.r_[False, qv[:-1] > 0]
    if side > 0:
        hit = cont & (lo <= L * (1 - pen))
    else:
        hit = cont & (h >= L * (1 + pen))
    if mask is not None:
        hit &= mask
    out = []
    i, free = 1, 1
    cand = np.flatnonzero(hit)
    k = 0
    while k < len(cand):
        i = cand[k]
        if i < free:
            k += 1
            continue
        p0 = L[i]
        j, px, why = i, c[i], "время"
        if hold > 0:
            end = min(i + hold, n - 1)
            if t[end] != t[i] + (end - i) * BAR:          # дыра в свечах — выход на последней непрерывной
                good = np.flatnonzero(t[i:end + 1] == t[i] + np.arange(end - i + 1) * BAR)
                end = i + good[-1]
            j, px = end, c[end]
            for m in range(i + 1, end + 1):
                adv = (lo[m] <= p0 * (1 - sl)) if (sl and side > 0) else (h[m] >= p0 * (1 + sl)) if sl else False
                fav = (h[m] >= p0 * (1 + tp)) if (tp and side > 0) else (lo[m] <= p0 * (1 - tp)) if tp else False
                if adv:
                    lvl = p0 * (1 - side * sl)
                    px = (min(lvl, o[m]) * (1 - slip)) if side > 0 else (max(lvl, o[m]) * (1 + slip))
                    j, why = m, "стоп"
                    break
                if fav:
                    px = p0 * (1 + side * tp)
                    j, why = m, "тейк"
                    break
        fee = fee_in + (fee_in if why == "тейк" else fee_out)
        t_in, t_out = int(t[i]) + BAR // 2, int(t[j]) + BAR          # время входа внутри свечи неизвестно — середина
        f = cs[np.searchsorted(ft, t_out, "right")] - cs[np.searchsorted(ft, t_in, "right")] if len(ft) else 0.0
        net = side * (px / p0 - 1) - side * f - fee
        out.append((int(i), int(t[i]), float(p0), int(j), int(t[j]), float(px), why, float(net)))
        free = j + 1 + cool
        k += 1
    return out


if __name__ == "__main__":                                       # проверка на искусственных свечах
    T = np.arange(10) * BAR
    a = dict(t=T, o=np.full(10, 100.0), h=np.full(10, 101.0), l=np.full(10, 99.0), c=np.full(10, 100.0), qv=np.ones(10))
    a["l"][3] = 90.0; a["c"][3] = 97.0                          # прострел вниз на свече 3, закрытие 97
    r = run(a, 0.05, +1)
    assert len(r) == 1 and r[0][0] == 3 and abs(r[0][2] - 95.0) < 1e-9 and abs(r[0][5] - 97.0) < 1e-9, r
    assert abs(r[0][7] - (97 / 95 - 1 - 0.0007)) < 1e-12, r
    for m in (4, 5, 6, 7):                                       # после прострела цена 96…98
        a["o"][m], a["h"][m], a["l"][m], a["c"][m] = 97.0, 98.0, 96.0, 97.0
    r = run(a, 0.05, +1, hold=4)                                 # выход по времени — закрытие свечи 7
    assert r[0][6] == "время" and r[0][3] == 7 and abs(r[0][5] - 97.0) < 1e-9, r
    a["h"][5] = 104.0                                            # тейк 5% на свече 5 (от 95 → 99,75)
    r = run(a, 0.05, +1, hold=4, tp=0.05)
    assert r[0][6] == "тейк" and r[0][3] == 5 and abs(r[0][5] - 99.75) < 1e-9, r
    a["l"][4] = 80.0; a["o"][4] = 85.0                           # стоп 10% на свече 4: уровень 85,5, открытие 85 → 85·0,998
    r = run(a, 0.05, +1, hold=4, sl=0.10, tp=0.05)
    assert r[0][6] == "стоп" and r[0][3] == 4 and abs(r[0][5] - 85.0 * 0.998) < 1e-9, r
    a2 = dict(t=T, o=np.full(10, 100.0), h=np.full(10, 101.0), l=np.full(10, 99.0), c=np.full(10, 100.0), qv=np.ones(10))
    a2["h"][6] = 110.0; a2["c"][6] = 103.0
    r = run(a2, 0.05, -1)                                        # прострел вверх: продажа на 105, закрытие 103
    assert len(r) == 1 and abs(r[0][7] - (-(103 / 105 - 1) - 0.0007)) < 1e-12, r
    print("проверки движка пройдены")
