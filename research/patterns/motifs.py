"""Ваш метод поиска паттернов с честной проверкой.
Окно — сутки (96 свечей по 15 мин), шаг 1 ч, только «бурные» сутки (размах ≥ 25%). Исход — что случится первым за 48 ч
после конца окна: −20% («вниз»), +20% («вверх») или ни то ни другое. Похожесть: форма цены r ≥ 0,90, форма объёма r ≥ 0,60,
размах отличается не больше чем в 1,6 раза.
A — поиск паттернов (апрель–август), B — подтверждение повторами (19.08–16.09), C — проверка на новых данных (19.09–16.10)."""
import sys, pickle, datetime, math
import numpy as np
sys.path.insert(0, "kaia"); from shape import windows, N
MSK = datetime.timezone(datetime.timedelta(hours=3))
d = lambda y, m, dd: datetime.datetime(y, m, dd, tzinfo=MSK).timestamp()
PER = {"A": (d(2026, 4, 18), d(2026, 8, 17)), "B": (d(2026, 8, 19), d(2026, 9, 17)), "C": (d(2026, 9, 19), d(2026, 10, 17))}
RP, RV, AMP = 0.90, 0.60, 1.6
K = pickle.load(open("kaia/k15_6m.pkl", "rb")); SYMS = sorted(K)
def outcome(k, e):
    p = k[e - 1, 4]; seg = k[e:e + 192]
    if len(seg) < 192 or np.any(np.diff(seg[:, 0]) != 900): return None
    dn = np.flatnonzero(seg[:, 3] <= p * 0.8); up = np.flatnonzero(seg[:, 2] >= p * 1.2)
    fd = dn[0] if len(dn) else 999; fu = up[0] if len(up) else 999
    return (-1 if fd < fu else 1 if fu < fd else 0), seg[-1, 4] / p - 1
def build(per):
    t0, t1 = PER[per]; S, TE, LR, P, V, O, R48 = [], [], [], [], [], [], []
    for si, s in enumerate(SYMS):
        k = K[s]
        for te, e, rng, lr, p, v in windows(k, 4, 0.25, t0, t1):
            o = outcome(k, e)
            if o is None: continue
            S.append(si); TE.append(te); LR.append(lr); P.append(p); V.append(v); O.append(o[0]); R48.append(o[1])
    return dict(S=np.array(S), TE=np.array(TE), LR=np.array(LR), P=np.array(P, np.float32), V=np.array(V, np.float32), O=np.array(O), R48=np.array(R48))
W = {p: build(p) for p in PER}
for p, w in W.items():
    print(f"{p}: бурных окон {len(w['S'])}, монет {len(set(w['S']))} | исход вниз {np.mean(w['O'] == -1)*100:.0f}%, вверх {np.mean(w['O'] == 1)*100:.0f}%", flush=True)
def dedupe_idx(w, idx, score=None):
    """По монете не чаще одного события в сутки (оставляем лучшее по score или первое по времени)."""
    order = sorted(idx, key=(lambda i: -score[i]) if score is not None else (lambda i: w["TE"][i]))
    taken, out = {}, []
    for i in order:
        s, t = w["S"][i], w["TE"][i]
        if all(abs(t - x) >= 86400 for x in taken.get(s, [])): out.append(i); taken.setdefault(s, []).append(t)
    return out
A = W["A"]; tmpl = dedupe_idx(A, [i for i in range(len(A["S"])) if A["O"][i] != 0])
print("паттернов-кандидатов в A (сутки, после которых было движение ±20%):", len(tmpl), flush=True)
def matches(w, j):
    rp = w["P"] @ A["P"][j]; rv = w["V"] @ A["V"][j]; ar = w["LR"] / A["LR"][j]
    idx = np.flatnonzero((rp >= RP) & (rv >= RV) & (ar <= AMP) & (ar >= 1 / AMP))
    return dedupe_idx(w, list(idx), rp)
def base_rate(w, direction):
    idx = dedupe_idx(w, list(range(len(w["S"]))))
    return np.mean(w["O"][idx] == direction)
B, C = W["B"], W["C"]
bB = {o: base_rate(B, o) for o in (-1, 1)}; bC = {o: base_rate(C, o) for o in (-1, 1)}
print(f"фон B: вниз {bB[-1]*100:.0f}%, вверх {bB[1]*100:.0f}% | фон C: вниз {bC[-1]*100:.0f}%, вверх {bC[1]*100:.0f}%", flush=True)
def binom_p(k, n, p):
    return sum(math.comb(n, x) * p ** x * (1 - p) ** (n - x) for x in range(k, n + 1))
res = []
for j in tmpl:
    mB = matches(B, j); o = A["O"][j]
    same = sum(B["O"][i] == o for i in mB); opp = sum(B["O"][i] == -o for i in mB)
    res.append(dict(j=j, o=o, nB=len(mB), same=same, opp=opp, mB=mB))
pickle.dump(dict(res=res, tmpl=tmpl), open("kaia/motifs_B.pkl", "wb"))
crit = {
    "ваш: ≥2 повтора, все в ту же сторону": lambda r: r["same"] >= 2 and r["same"] == r["nB"],
    "мягче: ≥2 повтора в ту же сторону, ≥ половины": lambda r: r["same"] >= 2 and r["same"] >= r["nB"] / 2,
    "строгий: ≥6 повторов, чаще фона на 25 п.п., p<0,05": lambda r: r["nB"] >= 6 and r["same"] / r["nB"] >= bB[r["o"]] + 0.25
                                                             and binom_p(r["same"], r["nB"], bB[r["o"]]) < 0.05,
}
for name, fn in crit.items():
    conf = [r for r in res if fn(r)]
    pred = {}
    for r in conf:
        for i in matches(C, r["j"]):
            pred.setdefault(i, []).append(r["o"])
    pi = {i: (1 if sum(v) > 0 else -1) for i, v in pred.items() if sum(v) != 0}
    idx = dedupe_idx(C, list(pi))
    hit = np.mean([C["O"][i] == pi[i] for i in idx]) if idx else float("nan")
    opp = np.mean([C["O"][i] == -pi[i] for i in idx]) if idx else float("nan")
    base = np.mean([bC[pi[i]] for i in idx]) if idx else float("nan")
    pnl = np.mean([(0.2 if C["O"][i] == pi[i] else -0.2 if C["O"][i] == -pi[i] else pi[i] * C["R48"][i]) for i in idx]) if idx else float("nan")
    nd = sum(1 for i in idx if pi[i] == -1)
    print(f"\n[{name}] подтверждено паттернов: {len(conf)} (вниз {sum(r['o'] == -1 for r in conf)}, вверх {sum(r['o'] == 1 for r in conf)})")
    print(f"   проверка на новом месяце C: прогнозов {len(idx)} (вниз {nd}, вверх {len(idx) - nd}) | сбылось {hit*100:.0f}% против фона {base*100:.0f}% | "
          f"наоборот {opp*100:.0f}% | средний итог сделки по прогнозу {pnl*100:+.1f}% цены", flush=True)
