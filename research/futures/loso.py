"""Проверка по фазам вслепую: для каждого квартала вариант выбирается по остальным шести, результат — на нём."""
import pickle, numpy as np, pandas as pd
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 80)
SEGN = ["S1 25.02–05.25", "S2 06–08.25", "S3 09–11.25", "S4 12.25–01.26", "T1 02–04.26", "T2 05–07.26", "T3 08–09.26"]
out = pickle.load(open("phase3.pkl", "rb"))
meta = pd.DataFrame([o[:11] for o in out], columns=["fam", "w", "lo", "hi", "run", "br", "fh4", "btc", "liq", "tp", "sl"])
S = np.array([o[11] for o in out]); Nn = np.array([o[12] for o in out]); SS = np.array([o[13] for o in out])
def desc(i):
    r = meta.iloc[i]
    band = f"{'+' if r.fam == 'pump' else '−'}{r.lo}…{'∞' if r.hi >= 1000 else r.hi}%"
    f = []
    if r.fh4: f.append(f"ниже макс. 4ч ≥{r.fh4}%")
    if r.btc != "любой": f.append(r.btc)
    if r.liq: f.append(f"объём 24ч ≥{r.liq}М$")
    if r.br: f.append(f"B/R≥{r.br}")
    return f"{'памп' if r.fam == 'pump' else 'слив'} {r.w} {band}, серия≥{r.run}ч" + (", " + ", ".join(f) if f else "") + f", выход {r.tp}/{r.sl}"
def pick(idx, k, crit, min_n):
    keep = [j for j in range(7) if j != k]
    s, n, ss = S[idx][:, keep], Nn[idx][:, keep], SS[idx][:, keep]
    ns, sm = n.sum(1), s.sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = sm / ns; var = ss.sum(1) / ns - mean ** 2; t = mean / np.sqrt(var / ns)
        segm = np.where(n > 0, s / np.maximum(n, 1), 0)
    pos = (s > 0).sum(1)
    if crit == "t":
        sc = np.where((ns >= min_n) & (pos >= 5), t, -np.inf)
    else:   # лучший худший квартал (на сделку), при достаточном числе сделок
        sc = np.where((ns >= min_n) & (n.min(1) >= 15), segm.min(1), -np.inf)
    return idx[np.argmax(sc)] if np.isfinite(sc.max()) else None
for fam, min_n in (("pump", 400), ("dump", 250)):
    idx = np.where(meta.fam == fam)[0]
    base = idx[(meta.iloc[idx].w == "4h").values & (meta.iloc[idx].lo == 8).values & (meta.iloc[idx].hi == 16).values & (meta.iloc[idx].run == 4).values &
               (meta.iloc[idx].br == (0 if fam == "pump" else 5)).values & (meta.iloc[idx].fh4 == 0).values & (meta.iloc[idx].btc == "любой").values &
               (meta.iloc[idx].liq == 0).values & (meta.iloc[idx].tp == 6).values]
    print(f"\n################ {('ПАМПЫ (правило 1)' if fam == 'pump' else 'СЛИВЫ (правило 2)')}: вариантов {len(idx)}")
    if len(base): b = base[0]; print(f"текущее правило ({desc(b)}): по кварталам [" + " ".join(f"{x:+6.1f}" for x in S[b]) + f"] итого {S[b].sum():+.1f}, сделок {Nn[b].sum()}")
    for crit, lab in (("t", "надёжность (t), ≥5 из 6 кварталов в плюсе"), ("min", "лучший худший квартал")):
        print(f"\n  критерий: {lab}")
        oos = []
        for k in range(7):
            j = pick(idx, k, crit, min_n)
            if j is None: print(f"   {SEGN[k]}: нет подходящих"); continue
            oos.append((S[j, k], Nn[j, k], S[base[0], k] if len(base) else np.nan))
            print(f"   {SEGN[k]}: вслепую {S[j, k]:+6.1f} ({Nn[j, k]:3d} сд.) | текущее {S[base[0], k] if len(base) else float('nan'):+6.1f} | выбран: {desc(j)}")
        o = np.array(oos)
        print(f"   ИТОГО вслепую {o[:, 0].sum():+.1f} на {int(o[:, 1].sum())} сделок, кварталов в плюсе {(o[:, 0] > 0).sum()}/7 | текущее правило {o[:, 2].sum():+.1f}, в плюсе {(o[:, 2] > 0).sum()}/7")
