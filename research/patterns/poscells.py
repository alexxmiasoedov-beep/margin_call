import pickle, itertools, numpy as np
exec(open("kaia/posmotifs.py").read().split("# ---------------- 1.")[0])
R = pickle.load(open("kaia/posmotifs_res.pkl", "rb")); ST = R["ST"]
K15 = pickle.load(open("kaia/k15_6m.pkl", "rb"))
for k, w in W.items():
    mv = []
    for s, te in zip(w["S"], w["TE"]):
        kk = K15[SYMS[s]]; e = int(np.searchsorted(kk[:, 0], te)); mv.append(kk[e - 1, 4] / kk[e - 96, 1] - 1)
    w["MV"] = np.array(mv)
def cells(k):
    w = W[k]; idx = dedupe(w, [i for i in range(len(w["S"])) if ST[k][i] is not None]); out = {}
    for i in idx:
        for mask in itertools.product((0, 1), repeat=5):
            if sum(mask): out.setdefault(tuple(v if m else "·" for v, m in zip(ST[k][i], mask)), []).append(i)
    return out
CA, CB, CC = cells("A"), cells("B"), cells("C")
def show(key, d):
    lab = ", ".join(v for v in key if v != "·"); row = []
    for k, CX in (("A", CA), ("B", CB), ("C", CC)):
        ix = CX.get(key, [])
        row.append(f"{k} {np.mean(W[k]['O'][ix] == d)*100:3.0f}% из {len(ix):4d} (фон {base[k][d]*100:.0f}%)" if ix else f"{k} —")
    ic = CC.get(key, [])
    pc = f" | итог в C {np.mean([pnl(C, i, d) for i in ic])*100:+.1f}%" if ic else ""
    print(f"  «{'вниз' if d < 0 else 'вверх'}» {lab}: " + " | ".join(row) + pc)
for d in (-1, 1):
    print(f"\nСамые сильные сочетания в A для «{'вниз' if d < 0 else 'вверх'}» (≥ 40 случаев):")
    top = sorted([(np.mean(A["O"][ix] == d) - base["A"][d], key) for key, ix in CA.items() if len(ix) >= 40], reverse=True)[:8]
    for dev, key in top: show(key, d)
print("\nСостояние как у KAIA (цена вверх, OI ×2+, премия < −4%, фандинг в упоре):")
for key in (("цена вверх", "OI ×2+", "премия < −4%", "фандинг в упоре", "·"), ("цена вверх", "OI ×2+", "премия < −4%", "·", "·"),
            ("·", "OI ×2+", "премия < −4%", "·", "·"), ("·", "·", "премия < −4%", "фандинг в упоре", "·"), ("цена вверх", "·", "·", "·", "·")):
    show(key, -1)
