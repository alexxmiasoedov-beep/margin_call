"""Скрытая сеть пампов: пары монет (A → B), у которых после пампа A памп B в следующие W часов случается гораздо чаще, чем после
пампов любых других монет (это убирает общий фон «альтсезона»). Связи ищутся только на 1-м году, торговля — на 2-м:
после пампа A — лонг B в закрытии ближайшей 15-мин свечи. Комиссия 0,1%, фандинг по факту."""
import pickle, datetime, sys
import numpy as np, pandas as pd
from collections import defaultdict
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
P = sorted((e["t_in"], e["s"]) for e in EV)
t_all = np.array([t for t, _ in P]); s_all = np.array([s for _, s in P])
by = defaultdict(list)
for t, s in P: by[s].append(t)
by = {s: np.array(v) for s, v in by.items()}
def links(W, t0, t1, min_k=3, min_lift=5.0):
    """Связи A→B на отрезке [t0, t1): k — пампы A, после которых в течение W был памп B; фон q_B — то же после пампов других монет."""
    m = (t_all >= t0) & (t_all < t1); ts, ss = t_all[m], s_all[m]
    nxt = {}                                                          # для каждого пампа: какие монеты пампились в следующие W часов
    j = 0
    for i in range(len(ts)):
        hi = np.searchsorted(ts, ts[i] + W * 3600, "right"); lo = i + 1
        nxt[i] = set(ss[lo:hi]) - {ss[i]}
    cnt_after = defaultdict(int)                                      # (A, B) → k
    tot_after_B = defaultdict(int)                                    # B → после скольких чужих пампов был памп B
    nA = defaultdict(int)
    for i in range(len(ts)):
        nA[ss[i]] += 1
        for b in nxt[i]:
            cnt_after[(ss[i], b)] += 1; tot_after_B[b] += 1
    N = len(ts); out = []
    for (a, b), k in cnt_after.items():
        if k < min_k: continue
        qb = (tot_after_B[b] - k) / max(N - nA[a], 1)                 # фон: доля чужих пампов (не A), после которых пампилась B
        lift = (k / nA[a]) / max(qb, 1e-9)
        if lift >= min_lift: out.append((a, b, nA[a], k, k / nA[a], qb, lift))
    return pd.DataFrame(out, columns=["A", "B", "nA", "k", "pAB", "qB", "lift"])
def trade_long(s, T, tp, sl, hold_h):
    a = K[s]; t = a["t"]; j = int(np.searchsorted(t, (T // 900) * 900))      # свеча, начавшаяся в момент сигнала: вход в её закрытие
    if j >= len(t) - 2: return None
    e = float(a["c"][j]); end = min(j + hold_h * 4, len(t) - 1)
    lo = a["l"][j + 1:end + 1].astype(np.float64); hi = a["h"][j + 1:end + 1].astype(np.float64)
    bad, good = np.flatnonzero(lo <= e * (1 - sl)), np.flatnonzero(hi >= e * (1 + tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl
    elif q2 < 10**9: q = j + 1 + q2; px = tp
    else: q = end; px = float(a["c"][end]) / e - 1
    pre = e / float(a["c"][max(0, j - 16)]) - 1                         # рост B за 4 ч до входа
    fr = F.get(s); t_in = t[j] + 900; t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        mm = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = -float(fr[mm, 2].sum())
    return px + fund - 0.001, pre
if __name__ == "__main__":
    T0 = t_all.min(); T1 = t_all.max() + 1
    for W in (6, 12, 24):
        L = links(W, T0, CUT)
        for min_lift in (5, 10):
            sel = L[L.lift >= min_lift]; pairs = defaultdict(list)
            for a, b in zip(sel.A, sel.B): pairs[a].append(b)
            res = []
            for t, a in P:
                if t < CUT: continue
                for b in pairs.get(a, []):
                    recent = by.get(b, np.array([]))
                    if ((recent > t - 86400) & (recent <= t)).any(): continue          # B уже пампилась — не догоняем
                    r = trade_long(b, t, 0.15, 0.10, W)
                    if r and r[1] < 0.10: res.append((t, a, b, r[0]))
            d = pd.DataFrame(res, columns=["t", "A", "B", "p"])
            hit = 0
            for t, a, b in zip(d.t, d.A, d.B):
                rb = by.get(b, np.array([])); hit += ((rb > t) & (rb <= t + W * 3600)).any()
            print(f"W={W:2d} ч, лифт ≥ {min_lift:2d}: связей на 1-м году {len(sel):5d} | сделок на 2-м {len(d):5d} | лонг 15/10: {d.p.mean() * 100:+.2f}% "
                  f"| в плюсе {(d.p > 0).mean():.0%} | B пампилась за W: {hit / max(len(d), 1):.1%}", flush=True)
