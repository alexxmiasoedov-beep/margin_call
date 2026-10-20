"""Паттерны с позициями: 1) по сходству рисунка цены+объёма+позиций; 2) по состояниям позиций. Отрезки A → B → C, как раньше."""
import pickle, math, datetime, itertools
import numpy as np
W = pickle.load(open("kaia/motif_windows.pkl", "rb")); F = pickle.load(open("kaia/posfeat.pkl", "rb"))
SYMS = sorted(pickle.load(open("kaia/k15_6m.pkl", "rb")).keys())
MSK = datetime.timezone(datetime.timedelta(hours=3)); fm = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%d.%m %H:%M")
def dedupe(w, idx, score=None):
    order = sorted(idx, key=(lambda i: -score[i]) if score is not None else (lambda i: w["TE"][i]))
    taken, out = {}, []
    for i in order:
        s, t = w["S"][i], w["TE"][i]
        if all(abs(t - x) >= 86400 for x in taken.get(s, [])): out.append(i); taken.setdefault(s, []).append(t)
    return out
def pnl(w, i, d): return 0.2 if w["O"][i] == d else -0.2 if w["O"][i] == -d else d * w["R48"][i]
def binom_p(k, n, p): return sum(math.comb(n, x) * p ** x * (1 - p) ** (n - x) for x in range(k, n + 1))
A, B, C = W["A"], W["B"], W["C"]; FA, FB, FC = F["A"], F["B"], F["C"]
base = {k: {d: np.mean(W[k]["O"][dedupe(W[k], range(len(W[k]["S"])))] == d) for d in (-1, 1)} for k in "ABC"}
allC = dedupe(C, range(len(C["S"])))
naive = {d: np.mean([pnl(C, i, d) for i in allC]) for d in (-1, 1)}
print(f"фон «первым −20% / +20%»: A {base['A'][-1]*100:.0f}/{base['A'][1]*100:.0f}%, B {base['B'][-1]*100:.0f}/{base['B'][1]*100:.0f}%, "
      f"C {base['C'][-1]*100:.0f}/{base['C'][1]*100:.0f}% | слепой шорт в C {naive[-1]*100:+.1f}%, лонг {naive[1]*100:+.1f}%")
# ---------------- 1. сходство рисунка цены + объёма + позиций
def posarr(FF):
    ok = np.array(["oi_shape" in x and "prem_min" in x and "fund_min" in x for x in FF])
    OS = np.array([x["oi_shape"] if "oi_shape" in x else np.zeros(96) for x in FF], np.float32)
    OX = np.array([np.log(x.get("oi_x", np.nan)) for x in FF]); PM = np.array([x.get("prem_min", np.nan) for x in FF])
    FL = np.array([bool(x.get("floor", False)) for x in FF]); TP = np.array([x.get("top_pos_ch", np.nan) for x in FF])
    return ok, OS, OX, PM, FL, TP
PA, PB, PC = posarr(FA), posarr(FB), posarr(FC)
def matches(w, pw, j):
    ok, OS, OX, PM, FL, TP = pw; okA, OSA, OXA, PMA, FLA, TPA = PA
    m = ((w["P"] @ A["P"][j]) >= 0.90) & ((w["V"] @ A["V"][j]) >= 0.60)
    ar = w["LR"] / A["LR"][j]; m &= (ar <= 1.6) & (ar >= 1 / 1.6) & ok
    m &= (OS @ OSA[j]) >= 0.70
    m &= np.abs(OX - OXA[j]) <= np.log(1.5)
    m &= np.abs(PM - PMA[j]) <= 3.0
    m &= FL == FLA[j]
    m &= (TP < 1) == (TPA[j] < 1)
    idx = np.flatnonzero(m)
    return dedupe(w, list(idx), w["P"] @ A["P"][j])
tmpl = dedupe(A, [i for i in range(len(A["S"])) if A["O"][i] != 0 and PA[0][i]])
print(f"\n1) Паттерны по сходству рисунка цены, объёма и позиций: кандидатов в A {len(tmpl)}", flush=True)
res = []
for j in tmpl:
    mB = matches(B, PB, j); o = A["O"][j]
    res.append(dict(j=j, o=o, nB=len(mB), same=sum(B["O"][i] == o for i in mB)))
crit = {"ваш: ≥2 повтора, все в ту же сторону": lambda r: r["same"] >= 2 and r["same"] == r["nB"],
        "мягче: ≥2 в ту же сторону, ≥ половины": lambda r: r["same"] >= 2 and r["same"] >= r["nB"] / 2,
        "строгий: ≥6 повторов, +25 п.п. к фону, p<0,05": lambda r: r["nB"] >= 6 and r["same"] / r["nB"] >= base["B"][r["o"]] + 0.25
                                                               and binom_p(r["same"], r["nB"], base["B"][r["o"]]) < 0.05}
for name, fn in crit.items():
    conf = [r for r in res if fn(r)]; pred = {}
    for r in conf:
        for i in matches(C, PC, r["j"]): pred.setdefault(i, []).append(r["o"])
    pi = {i: (1 if sum(v) > 0 else -1) for i, v in pred.items() if sum(v) != 0}
    idx = dedupe(C, list(pi))
    print(f"  [{name}] подтверждено {len(conf)} (вниз {sum(r['o'] == -1 for r in conf)}, вверх {sum(r['o'] == 1 for r in conf)}); проверка в C:")
    for dn, dv in (("вниз", -1), ("вверх", 1)):
        sel = [i for i in idx if pi[i] == dv]
        if not sel: print(f"     «{dn}»: прогнозов нет"); continue
        print(f"     «{dn}»: {len(sel)} прогнозов | сбылось {np.mean([C['O'][i] == dv for i in sel])*100:.0f}% (фон {base['C'][dv]*100:.0f}%), "
              f"наоборот {np.mean([C['O'][i] == -dv for i in sel])*100:.0f}% | итог {np.mean([pnl(C, i, dv) for i in sel])*100:+.1f}% "
              f"(слепой {'шорт' if dv < 0 else 'лонг'} {naive[dv]*100:+.1f}%)", flush=True)
# ---------------- 2. состояния позиций
def state(w, FF, i):
    x = FF[i]
    if "oi_x" not in x or "prem_min" not in x or "fund_min" not in x or not np.isfinite(x.get("top_pos_ch", np.nan)): return None
    oi = x["oi_x"]; pm = x["prem_min"]; fmn = x["fund_min"]; tp = x["top_pos_ch"]
    return (("цена вверх" if w["MV"][i] > 0.2 else "цена вниз" if w["MV"][i] < -0.2 else "туда-обратно"),
            ("OI упал" if oi < 0.9 else "OI ровно" if oi < 1.3 else "OI ×1,3–2" if oi < 2 else "OI ×2+"),
            ("премия ~0" if pm > -1 else "премия −1…−4%" if pm > -4 else "премия < −4%"),
            ("фандинг в упоре" if x.get("floor") or fmn <= -1 else "фандинг < −0,1%" if fmn <= -0.1 else "фандинг обычный"),
            ("топы в шорт" if tp < 0.85 else "топы в лонг" if tp > 1.15 else "топы ровно"))
K15 = pickle.load(open("kaia/k15_6m.pkl", "rb"))
for k, w in W.items():                                    # изменение цены за окно (конец/начало)
    mv = []
    for s, te in zip(w["S"], w["TE"]):
        kk = K15[SYMS[s]]; e = int(np.searchsorted(kk[:, 0], te)); mv.append(kk[e - 1, 4] / kk[e - 96, 1] - 1)
    w["MV"] = np.array(mv)
ST = {k: [state(W[k], F[k], i) for i in range(len(W[k]["S"]))] for k in "ABC"}
def cells(k):
    w = W[k]; idx = dedupe(w, [i for i in range(len(w["S"])) if ST[k][i] is not None]); out = {}
    for i in idx:
        st = ST[k][i]
        for mask in itertools.product((0, 1), repeat=5):          # все сочетания из 1–5 признаков
            if sum(mask) == 0: continue
            key = tuple(v if m else "·" for v, m in zip(st, mask))
            out.setdefault(key, []).append(i)
    return out
CA, CB, CC = cells("A"), cells("B"), cells("C")
print(f"\n2) Паттерны по состояниям (цена, OI, премия, фандинг, топ-трейдеры): событий с полными данными A {sum(1 for x in ST['A'] if x)}", flush=True)
cand = []
for key, idx in CA.items():
    if len(idx) < 40: continue
    for d in (-1, 1):
        ra = np.mean(A["O"][idx] == d)
        if ra >= base["A"][d] + 0.15 and binom_p(int(round(ra * len(idx))), len(idx), base["A"][d]) < 0.001:
            ib = CB.get(key, [])
            if len(ib) >= 15:
                rb = np.mean(B["O"][ib] == d)
                if rb >= base["B"][d] + 0.10:
                    cand.append((key, d, len(idx), ra, len(ib), rb))
print(f"   прошли A (≥40 случаев, +15 п.п. к фону) и B (≥15 случаев, +10 п.п.): {len(cand)} сочетаний", flush=True)
seen = set()
for key, d, na, ra, nb, rb in sorted(cand, key=lambda c: -(c[5] - base["B"][c[1]])):
    ic = CC.get(key, [])
    lab = ", ".join(v for v in key if v != "·")
    if not ic: print(f"   «{'вниз' if d < 0 else 'вверх'}» {lab}: в C случаев нет"); continue
    rc = np.mean(C["O"][ic] == d); oc = np.mean(C["O"][ic] == -d); pc = np.mean([pnl(C, i, d) for i in ic])
    print(f"   «{'вниз' if d < 0 else 'вверх'}» {lab}: A {ra*100:.0f}% из {na} | B {rb*100:.0f}% из {nb} | "
          f"C {rc*100:.0f}% из {len(ic)} (фон {base['C'][d]*100:.0f}%, наоборот {oc*100:.0f}%), итог {pc*100:+.1f}% (слепой {naive[d]*100:+.1f}%)", flush=True)
pickle.dump(dict(cand=cand, ST=ST), open("kaia/posmotifs_res.pkl", "wb"))
