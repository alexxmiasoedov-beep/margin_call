"""s39 — проверка Г1–Г4 (ВЫВОДЫ.md, записаны до данных) на показателях других бирж.
Г1/Г2: каскад ликвидаций Gate (≥ 99-го перцентиля «ликвидации за час / OI в $», цена за час ≤ −3% или ≥ +3%) → лонг или шорт
на 24 ч с открытия следующего часа по марк-цене Gate, к рынку (медиана монет), комиссия 0,1%; одна сделка на монету за
24 ч; плацебо — та же монета на 7/14/21 сут раньше. Г3: доля счетов в лонге Gate в 00:00 UTC (≥ 200 счетов) → шорт верхней
десятой части, лонг нижней, 24 ч. Г4: займы маржи OKX R = отношение / цена, изменение log R за 3 сут → лонг верхней
десятой части, шорт нижней, 3 сут по суточным закрытиям Binance; t Ньюи — Уэста. Половины — по 90 сут.
Данные — s39/gate.pkl (gate_fetch.py), s39/okx.pkl (okx_fetch.py). Итог — s39/res.pkl. Запуск из папки с данными."""
import pickle
import numpy as np, pandas as pd

FEE, H, DAY = 0.001, 3600, 86400
PL = (7, 14, 21)


def nw_t(x, lag):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 10:
        return np.nan
    e = x - x.mean(); v = e @ e / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(v / n)


def panel(G):
    """Общая почасовая сетка: марк-цена, OI $, ликвидации, счета; рынок — медиана часовых доходов."""
    T = np.unique(np.concatenate([d["t"] for d in G.values()]))
    syms = sorted(G)
    M = {f: np.full((len(syms), len(T)), np.nan) for f in ("mark_price", "open_interest_usd", "long_liq_usd", "short_liq_usd",
                                                         "long_users", "short_users")}
    for i, s in enumerate(syms):
        k = np.searchsorted(T, G[s]["t"])
        for f in M:
            M[f][i, k] = G[s][f]
    P = M["mark_price"]; P[P <= 0] = np.nan
    with np.errstate(all="ignore"):
        r1 = P[:, 1:] / P[:, :-1] - 1
        mk = np.r_[np.nan, np.nanmedian(r1, axis=0)]
    return syms, T, M, np.c_[np.full(len(syms), np.nan), r1], mk


def cascades(syms, T, M, R1, mk, side):
    liq = M["long_liq_usd" if side > 0 else "short_liq_usd"]; oi = M["open_interest_usd"]
    with np.errstate(all="ignore"):
        q = liq / np.where(oi > 1e5, oi, np.nan)
    thr = np.nanpercentile(q[q > 0], 99) if np.isfinite(q).any() else np.nan
    P = M["mark_price"]; cmk = np.r_[0.0, np.nancumsum(np.nan_to_num(mk[1:]))]
    rows, mid = [], T[0] + (T[-1] - T[0]) / 2

    def deal(i, k):                                         # вход в T[k + 1], выход через 24 ч
        a, b = k + 1, k + 25
        if b >= len(T) or not (np.isfinite(P[i, a]) and np.isfinite(P[i, b])):
            return None
        r = P[i, b] / P[i, a] - 1
        m = cmk[b] - cmk[a]
        return side * r - FEE, side * (r - m) - FEE

    for i in range(len(syms)):
        last = -np.inf
        for k in np.flatnonzero((q[i] >= thr) & (side * R1[i] <= -0.03)):
            if T[k] - last < DAY:
                continue
            a = deal(i, k)
            if a is None:
                continue
            last = T[k]
            pl = [deal(i, k - d * 24) for d in PL if k - d * 24 >= 1]
            pl = [x[1] for x in pl if x]
            rows.append(dict(s=syms[i], t=T[k], net=a[0], rel=a[1], plac=np.mean(pl) if pl else np.nan, half=1 + (T[k] >= mid)))
    return pd.DataFrame(rows), thr


def show_events(D, label):
    if D.empty:
        print(f"  {label}: событий нет"); return
    q = D.groupby(pd.to_datetime(D.t, unit="s").dt.date)
    dm = q.rel.mean(); t = dm.mean() / dm.std() * np.sqrt(len(dm)) if len(dm) > 2 and dm.std() > 0 else np.nan
    h1, h2 = D[D.half == 1].rel.mean(), D[D.half == 2].rel.mean()
    print(f"  {label}: событий {len(D)} (монет {D.s.nunique()}), к рынку {D.rel.mean():+.2%} (t {t:+.1f}), абсолютно "
          f"{D.net.mean():+.2%}, в плюсе {(D.rel > 0).mean():.0%} | половины {h1:+.2%} / {h2:+.2%} | плацебо {D.plac.mean():+.2%}")


def crowd(syms, T, M):
    P = M["mark_price"]; LU, SU = M["long_users"], M["short_users"]
    rows = []
    for k in np.flatnonzero(T % DAY == 0):
        e = k + 24
        if e >= len(T):
            break
        n = LU[:, k] + SU[:, k]
        ok = (n >= 200) & np.isfinite(P[:, k]) & np.isfinite(P[:, e])
        if ok.sum() < 30:
            continue
        sh = LU[ok, k] / n[ok]; r = P[ok, e] / P[ok, k] - 1
        o = np.argsort(sh); m = max(int(round(len(o) * 0.1)), 3)
        lo, hi = o[:m], o[-m:]
        rows.append(dict(t=T[k], LS=(r[lo].mean() - r[hi].mean()) / 2 - FEE, n=int(ok.sum())))
    return pd.DataFrame(rows)


def okx_test(O):
    """Точки OKX стоят в 16:00 UTC (полночь по Пекину); показатель считается известным через сутки после отметки.
    Формирование — граница суток d (00:00 UTC): последняя точка с отметкой ≤ d − 1 сут и точка на 3 сут раньше.
    R = отношение / ближайшее предыдущее суточное закрытие Binance. Доход — закрытие в d → закрытие в d + 3 сут."""
    loan, px = O["loan"], O["px"]
    close = {}                                                 # символ → (время закрытия, мс; закрытие)
    for s, v in px.items():
        v = sorted(v)
        close[s] = (np.array([t + DAY * 1000 for t, _ in v]), np.array([c for _, c in v]))
    def c_at(s, t, before=True):
        tt, cc = close[s]
        i = int(np.searchsorted(tt, t, "right")) - 1
        return (cc[i] if i >= 0 and t - tt[i] < 2 * DAY * 1000 else None) if before else None
    def c_exact(s, t):
        tt, cc = close[s]
        i = int(np.searchsorted(tt, t))
        return cc[i] if i < len(tt) and tt[i] == t else None
    LR = {}
    for s, v in loan.items():
        if s not in close:
            continue
        v = sorted(v)
        ts = np.array([t for t, _ in v]); r = []
        for t, x in v:
            c = c_at(s, t)
            r.append(np.log(x / c) if c and x > 0 else np.nan)
        LR[s] = (ts, np.array(r))
    days = sorted({int(t // (DAY * 1000) + 1) * DAY * 1000 for v in loan.values() for t, _ in v})
    rows = []
    for d in days:
        sig, ret = {}, {}
        for s, (ts, r) in LR.items():
            i = int(np.searchsorted(ts, d - DAY * 1000, "right")) - 1
            if i < 0:
                continue
            j = int(np.searchsorted(ts, ts[i] - 3 * DAY * 1000, "right")) - 1
            if j < 0 or ts[i] - ts[j] != 3 * DAY * 1000 or not (np.isfinite(r[i]) and np.isfinite(r[j])):
                continue
            c0, c1 = c_exact(s, d), c_exact(s, d + 3 * DAY * 1000)
            if not c0 or not c1:
                continue
            sig[s] = r[i] - r[j]; ret[s] = c1 / c0 - 1
        if len(sig) < 30:
            continue
        S = pd.Series(sig).sort_values(); m = max(int(round(len(S) * 0.1)), 3)
        lo, hi = S.index[:m], S.index[-m:]
        avg = np.mean(list(ret.values()))
        rows.append(dict(t=d / 1000, LS=(np.mean([ret[s] for s in hi]) - np.mean([ret[s] for s in lo])) / 2 - FEE,
                         lo_rel=np.mean([ret[s] for s in lo]) - avg, hi_rel=np.mean([ret[s] for s in hi]) - avg, n=len(S)))
    return pd.DataFrame(rows)


def show_port(D, label, lag):
    if D.empty:
        print(f"  {label}: мало данных"); return
    mid = D.t.min() + (D.t.max() - D.t.min()) / 2
    h1, h2 = D[D.t < mid].LS, D[D.t >= mid].LS
    print(f"  {label}: дат {len(D)}, монет в срезе {D.n.median():.0f}, лонг-шорт {D.LS.mean():+.3%} (t {nw_t(D.LS, lag):+.1f}) | "
          f"половины {h1.mean():+.3%} (t {nw_t(h1, lag):+.1f}) / {h2.mean():+.3%} (t {nw_t(h2, lag):+.1f}) | в плюсе {(D.LS > 0).mean():.0%}")


if __name__ == "__main__":
    res = {}
    try:
        G = pickle.load(open("s39/gate.pkl", "rb"))
        syms, T, M, R1, mk = panel(G)
        print(f"Gate: монет {len(syms)}, часов {len(T)} ({pd.to_datetime(T[0], unit='s'):%d.%m.%Y} – {pd.to_datetime(T[-1], unit='s'):%d.%m.%Y})")
        for side, lab in ((+1, "Г1: каскад ликвидаций лонгов → лонг 24 ч"), (-1, "Г2: каскад ликвидаций шортов → шорт 24 ч")):
            D, thr = cascades(syms, T, M, R1, mk, side); res[lab] = D
            print(f"  порог 99-го перцентиля: ликвидации {thr:.2%} OI за час")
            show_events(D, lab)
        D = crowd(syms, T, M); res["Г3"] = D
        show_port(D, "Г3: против толпы счетов Gate (24 ч)", 0)
    except FileNotFoundError:
        print("Gate: данных нет")
    try:
        O = pickle.load(open("s39/okx.pkl", "rb"))
        D = okx_test(O); res["Г4"] = D
        show_port(D, "Г4: займы маржи OKX (лонг растущих займов под лонг, шорт растущих под шорт, 3 сут)", 2)
        if not D.empty:
            print(f"      рост займов под шорт (нижняя десятая часть) к срезу {D.lo_rel.mean():+.2%}, под лонг (верхняя) {D.hi_rel.mean():+.2%}")
    except FileNotFoundError:
        print("OKX: данных нет")
    pickle.dump(res, open("s39/res.pkl", "wb"))
