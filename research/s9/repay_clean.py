"""Правило ↩️ ровно как в боте (scanner.repay_rule + trader.virt_open) по всему архиву MarginData с 20.02.2025:
каждый пост свечи проверяется отдельно (первый подходящий), вход на закрытии 15-мин свечи поста, новая сделка по монете —
только когда прежняя закрыта и с её входа прошло ≥ 24 ч. В repay.py кандидаты (×1,5 и +10 тыс. $) прореживались по часу
до окончательного фильтра — это скрытое условие «резкий всплеск». Здесь оба варианта: чистый (как в боте) и «резкий»
(цепочка как в repay.py и без памяти: за прошлый час у монеты не было кандидата ×1,5). Отбор порогов — по 1-й половине,
проверка на 2-й, контроль на перемешанных внутри месяца исходах."""
import itertools
import numpy as np, pandas as pd
exec(open("s9/md_events.py").read().split("# 15-мин сетка постов канала")[0])
GRIDS = ((10, 25), (7, 20), (10, 10))
rows = []
for c0, arr in G.items():
    s = sym_of.get(c0) or sym_of.get(strip(c0))
    if s is None or s not in K: continue
    a = K[s]; t = a["t"]; c = a["c"].astype(np.float64)
    tt, bor, rep = arr[:, 0], arr[:, 1], arr[:, 2]
    st_idx = np.r_[0, np.flatnonzero(np.diff(tt) > 30 * 60) + 1]; ends = np.r_[st_idx[1:] - 1, len(tt) - 1]
    for st, en in zip(st_idx, ends):
        T0 = tt[st]; last_chain = -1e18; loose_t = []
        for i in range(st, en + 1):
            run = (tt[i] - T0) / 3600
            k = np.searchsorted(tt, tt[i] - 3600, "right") - 1
            if k < st or tt[i] - tt[k] > 75 * 60: continue
            x = rep[i] / max(rep[k], 1.0); dr = rep[i] - rep[k]
            loose = x >= 1.5 and dr >= 10e3
            if not loose: continue
            calm = not any(tt[i] - 3600 <= q < tt[i] for q in loose_t[-20:])     # за прошлый час кандидата ×1,5 не было
            loose_t.append(tt[i])
            chain = run >= 2 and tt[i] - last_chain >= 3600                      # как dedup(SEL, 1) в repay.py
            if chain: last_chain = tt[i]
            if run < 2: continue
            j = int(np.searchsorted(t, tt[i], "right") - 1)
            if j < 300 or j >= len(t) - 2: continue
            rows.append((s, j, tt[i], run, x, dr, bor[i], c[j] / c[j - 96] - 1, calm, chain))
C = pd.DataFrame(rows, columns=["s", "j", "t", "run", "x", "dr", "bor", "mv", "calm", "chain"])
C = C[C.mv.abs() >= 0.05].sort_values("t").reset_index(drop=True)
print("постов-кандидатов (×1,5, +10 тыс. $, серия ≥ 2 ч, |сутки| ≥ 5%):", len(C))
def trade(s, j, tp, sl):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + HOLD, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64) / e - 1; lo = a["l"][j + 1:end + 1].astype(np.float64) / e - 1
    gq = np.flatnonzero(lo <= -tp / 100); bq = np.flatnonzero(hi >= sl / 100)
    g = gq[0] if len(gq) else 10**9; b = bq[0] if len(bq) else 10**9
    if b <= g and b < 10**9: q = b; px = -sl / 100
    elif g < 10**9: q = g; px = tp / 100
    else: q = end - j - 1; px = 1 - float(a["c"][end]) / e
    fs = fund_sum(s, t[j] + 900, t[j + 1 + q] + 900)
    return px - 0.001 + fs, float(t[j + 1 + q] + 900 - (t[j] + 900))           # итог и длительность
U = C[["s", "j"]].drop_duplicates().reset_index(drop=True)
for tp, sl in GRIDS:
    r = [trade(s, j, tp, sl) for s, j in zip(U.s, U.j)]
    U[f"p{tp}_{sl}"] = [x[0] for x in r]; U[f"d{tp}_{sl}"] = [x[1] for x in r]
C = C.merge(U, on=["s", "j"], how="left")
C["T"] = [float(K[s]["t"][j] + 900) for s, j in zip(C.s, C.j)]                 # закрытие свечи = вход
C["half"] = np.where(C.t < CUT, 1, 2); C["m"] = pd.to_datetime(C.t, unit="s").dt.strftime("%y%m")
C.to_pickle("s9/repay_clean.pkl")
def journal(D, g):
    """Сделки журнала: первый подходящий пост свечи, монета свободна (прежняя закрыта) и ≥ 24 ч с прежнего входа."""
    D = D.drop_duplicates(["s", "j"]).sort_values("t"); keep = []; last = {}
    p, d = f"p{g[0]}_{g[1]}", f"d{g[0]}_{g[1]}"
    for i, s, T, dd in zip(D.index, D.s, D["T"], D[d]):
        lo, lc = last.get(s, (-1e18, -1e18))
        if T - lo >= 86400 and T >= lc: keep.append(i); last[s] = (T, T + dd)
    return D.loc[keep]
def stats(g, col):
    h1, h2 = g[g.half == 1], g[g.half == 2]; mm = g.groupby("m")[col].sum()
    eq = (g.sort_values("T")[col] * 10).cumsum(); dd = (eq - eq.cummax()).min()
    return (f"n={len(g):4d} WR {(g[col] > 0).mean():.0%} {g[col].mean()*100:+.2f}% итог {g[col].sum()*10:+.1f} USDT просадка {dd:.1f} | "
            f"1-я {len(h1)} {h1[col].mean()*100:+.2f}% / 2-я {len(h2)} {h2[col].mean()*100:+.2f}% | месяцев в плюсе {(mm > 0).sum()}/{len(mm)}")
BASE = (C.x >= 2) & (C.run >= 6) & (C.dr >= 20e3) & (C.mv.abs() >= 0.10)
for nm, m in (("чистое (как в боте)", BASE), ("резкое — цепочка, как в repay.py", BASE & C.chain), ("резкое — за час не было ×1,5", BASE & C.calm)):
    for g in GRIDS:
        print(f"{nm:34s} {g[0]}/{g[1]}: " + stats(journal(C[m], g), f"p{g[0]}_{g[1]}"))
sel = journal(C[BASE], (10, 25)); s9 = sel[sel.t >= 1756771200]
print(f"чистое с 02.09.2025 (сверка с эмуляцией бота: 119 сделок, +1,60%): n={len(s9)} {s9.p10_25.mean()*100:+.2f}%")
def variants(D, flag):
    res = []
    for xr, run, bmin, mv, g in itertools.product((1.5, 2, 3), (2, 6, 12), (0, 1e6), (0.05, 0.10, 0.15), GRIDS):
        m = (D.x >= xr) & (D.run >= run) & (D.bor >= bmin) & (D.dr >= 20e3) & (D.mv.abs() >= mv)
        if flag: m &= D[flag]
        j = journal(D[m], g); col = f"p{g[0]}_{g[1]}"; h1, h2 = j[j.half == 1], j[j.half == 2]
        if len(h1) < 30: continue
        res.append(dict(xr=xr, run=run, bmin=bmin, mv=mv, g=f"{g[0]}/{g[1]}", n=len(j), m=j[col].mean(), n1=len(h1), m1=h1[col].mean(),
                        n2=len(h2), m2=h2[col].mean()))
    return pd.DataFrame(res).sort_values("m1", ascending=False)
rng = np.random.default_rng(3)
for flag in (None, "chain", "calm"):
    V = variants(C, flag)
    sh = []
    for k in range(10):
        D = C.copy()
        for mm, idx in D.groupby("m").groups.items():
            idx = np.array(list(idx)); perm = rng.permutation(idx)
            for g in GRIDS:
                cols = [f"p{g[0]}_{g[1]}", f"d{g[0]}_{g[1]}"]; D.loc[idx, cols] = C.loc[perm, cols].values
        sh.append(variants(D, flag).head(20).m2.mean())
    print(f"[{flag or 'чистое'}] вариантов {len(V)}; 20 лучших по 1-й: 1-я {V.head(20).m1.mean()*100:+.2f}% → 2-я {V.head(20).m2.mean()*100:+.2f}% "
          f"(в плюсе {(V.head(20).m2 > 0).mean():.0%}); все варианты на 2-й {V.m2.mean()*100:+.2f}% | перемешанные: 2-я {np.mean(sh)*100:+.2f}% (макс {np.max(sh)*100:+.2f}%)")
    print(V.head(5).round(4).to_string(index=False))
