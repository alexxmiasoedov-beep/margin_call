"""Карта ликвидаций (топ-100 монет, часовой открытый интерес s22/metrics_full). Каждый прирост OI (контракты × типичная
цена часа) — новые позиции; ликвидируемая (агрессивная) сторона: лонги — доля агрессивных покупок часа (панель s23),
шорты — остальное. Плечи ×5/×10/×25/×50 с весами 0,25/0,35/0,25/0,15 → уровни ликвидации P·(1 ∓ 1/L) в корзинах по 0,5%.
Снижение OI — пропорциональное закрытие; уровень, до которого дошла цена (low/high часа), — снят. Признаки на конце часа:
топливо лонгов в 5% и 10% ниже цены (LF), шортов выше (SF) в часах нормального оборота, перекос IMB = (SF − LF)/(SF + LF).
Проверка — Фама — Макбет по срезам раз в 4 ч (доход к медиане этих монет через 4 и 24 ч), первая половина — поиск.
Кэш признаков — s24/liq.pkl. Запуск из папки с данными: python3 g4_liqmap.py [--confirm]"""
import os
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from common23 import CUT, G, P, ROW, TRADFI                      # noqa: E402

CONF = "--confirm" in sys.argv
B = 0.005
MIX = ((5, 0.25), (10, 0.35), (25, 0.25), (50, 0.15))
PATH = "s24/liq.pkl"
coins = [s.strip() for s in open("s22/top100.txt") if s.strip() and s.strip() not in TRADFI and s.strip() in ROW]


def load_oi(s):
    d = f"s22/metrics_full/{s}"
    arr = [np.load(f"{d}/{f}") for f in sorted(os.listdir(d))]
    a = np.concatenate([x for x in arr if len(x)]) if arr else np.zeros((0, 7))
    out = np.full(len(G), np.nan)
    k = np.searchsorted(G, a[:, 0].astype(np.int64))
    ok = (k < len(G)) & (G[np.minimum(k, len(G) - 1)] == a[:, 0].astype(np.int64))
    out[k[ok]] = a[ok, 1]
    return out


def build():
    feats = {}
    for s in coins:
        j = ROW[s]
        C, HI, LO, Q, TB = (P[k][j].astype(np.float64) for k in ("C", "HI", "LO", "Q", "TB"))
        oi = load_oi(s)
        Vb = pd.Series(Q).rolling(720, min_periods=240).median().shift(1).values
        ok = np.isfinite(C) & np.isfinite(oi) & np.isfinite(HI) & np.isfinite(LO) & (Q > 0)
        if ok.sum() < 2000:
            continue
        lp = np.log(C[ok]); b0 = int(np.floor(lp.min() / B)) - 300; nb = int(np.ceil(lp.max() / B)) + 300 - b0
        L = np.zeros(nb); S = np.zeros(nb)
        F = np.full((len(G), 4), np.nan)                              # LF5, SF5, LF10, SF10 (в часах оборота)
        bi = lambda x: int(np.floor(np.log(x) / B)) - b0
        prev = None
        for k in range(len(G)):
            if not ok[k]:
                prev = None; L[:] = 0; S[:] = 0                       # разрыв данных — карта заново
                continue
            if prev is not None:
                lo_b, hi_b = bi(LO[k]), bi(HI[k])
                L[max(lo_b, 0):] = 0                                   # уровни лонгов не ниже low часа — ликвидированы
                S[:min(hi_b + 1, nb)] = 0                              # уровни шортов не выше high часа
                d = oi[k] - oi[prev]
                if d > 0:
                    vw = (HI[k] + LO[k] + C[k]) / 3; add = d * vw; bs = TB[k] / Q[k]
                    for lev, w in MIX:
                        L[bi(vw * (1 - 1 / lev))] += add * bs * w
                        S[min(bi(vw * (1 + 1 / lev)), nb - 1)] += add * (1 - bs) * w
                elif oi[prev] > 0:
                    f = max(0.0, 1 + d / oi[prev]); L *= f; S *= f
            prev = k
            if np.isfinite(Vb[k]) and Vb[k] > 0:
                pb = bi(C[k])
                F[k] = [L[bi(C[k] * 0.95):pb].sum() / Vb[k], S[pb + 1:bi(C[k] * 1.05) + 1].sum() / Vb[k],
                        L[bi(C[k] * 0.90):pb].sum() / Vb[k], S[pb + 1:bi(C[k] * 1.10) + 1].sum() / Vb[k]]
        feats[s] = F
        print(f"  {s}: часов с картой {np.isfinite(F[:, 0]).sum()}", flush=True)
    pickle.dump(feats, open(PATH, "wb"))
    return feats


feats = pickle.load(open(PATH, "rb")) if os.path.exists(PATH) else build()
cs = list(feats)
C = np.array([P["C"][ROW[s]] for s in cs], np.float64)
X = {nm: np.array([feats[s][:, i] for s in cs]) for i, nm in enumerate(("LF5", "SF5", "LF10", "SF10"))}
for k in ("5", "10"):
    X["IMB" + k] = (X["SF" + k] - X["LF" + k]) / (X["SF" + k] + X["LF" + k] + 1e-9)
    X["TOT" + k] = np.log1p(X["SF" + k] + X["LF" + k])
R24 = np.log(C / np.roll(C, 24, axis=1)); R24[:, :24] = np.nan
X["R24"] = R24 - np.nanmedian(R24, axis=0)
idx = np.flatnonzero((G % 14400 == 0) & ((G >= CUT) if CONF else (G < CUT)))
idx = idx[idx >= 24 * 40]


def fwd(h):
    y = np.roll(C, -h, axis=1) / C - 1; y[:, -h:] = np.nan
    return y - np.nanmedian(y, axis=0)


def nw(b, lag):
    b = np.asarray(b, float); b = b[np.isfinite(b)]; n = len(b)
    d = b - b.mean(); v = d @ d / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (d[l:] @ d[:-l]) / n
    return b.mean() / np.sqrt(v / n)


print(f"{'ВТОРАЯ' if CONF else 'первая'} половина: монет {len(cs)}, срезов {len(idx)}")
for h in (4, 24):
    Y = fwd(h)
    for names in (["IMB5"], ["IMB10"], ["IMB5", "R24"], ["IMB10", "TOT10", "R24"]):
        B_ = []
        for k in idx:
            y = Y[:, k]; Z = np.column_stack([X[n][:, k] for n in names])
            ok = np.isfinite(y) & np.isfinite(Z).all(axis=1)
            if ok.sum() < 30:
                continue
            Zr = (pd.DataFrame(Z[ok]).rank(pct=True).values - 0.5)
            yy = np.clip(y[ok], *np.quantile(y[ok], [0.01, 0.99]))
            B_.append(np.linalg.lstsq(np.column_stack([np.ones(ok.sum()), Zr]), yy, rcond=None)[0][1:])
        B_ = np.array(B_); lag = max(1, h // 4)
        print(f"  {h:2d} ч, {'+'.join(names):>16}: " + " | ".join(f"{n} {B_[:, i].mean() * 100:+.3f} п. п. (t {nw(B_[:, i], lag):+.1f})"
                                                              for i, n in enumerate(names)) + f"  [срезов {len(B_)}]")
