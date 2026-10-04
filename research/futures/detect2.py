"""Пары признаков, составной балл и цель для 15/25. Отбор признаков и порогов — ТОЛЬКО на train (первые 60%), проверка на test."""
import itertools
from detect import d, FEATS, auc, np, pd
from sim import SIG, trade
P = {(s["sym"], s["ep"]): s for s in SIG}
r = [trade(P[(a, b)], 15, 25) for a, b in zip(d.sym, d.ep)]
d["y_stop1525"] = [int(x["kind"] == "стоп") for x in r]; d["y_pnl1525"] = [x["pnl"] for x in r]

def study(sub, label, ycol, pcol):
    tr, te = sub[sub.part == "train"], sub[sub.part == "test"]
    au = []
    for f in FEATS:
        A, p = auc(tr[f], tr[ycol])
        if not np.isnan(A): au.append((f, A, p))
    au = sorted(au, key=lambda x: x[2])[:25]                       # топ по train
    print(f"\n######## {label} | цель {ycol}: стопов train {tr[ycol].sum()}/{len(tr)}, test {te[ycol].sum()}/{len(te)}; итог train {tr[pcol].sum():+.1f}, test {te[pcol].sum():+.1f}")
    # 1) пары
    res = []
    for (f1, A1, _), (f2, A2, _) in itertools.combinations(au, 2):
        for q1 in (0.33, 0.67):
            for q2 in (0.33, 0.67):
                t1, t2 = tr[f1].quantile(q1), tr[f2].quantile(q2)
                c1 = (lambda x, t=t1: x > t) if q1 > 0.5 else (lambda x, t=t1: x < t)
                c2 = (lambda x, t=t2: x > t) if q2 > 0.5 else (lambda x, t=t2: x < t)
                btr = c1(tr[f1]) & c2(tr[f2])
                if btr.sum() < 12: continue
                bte = c1(te[f1]) & c2(te[f2])
                res.append((f"{f1} {'>' if q1>0.5 else '<'} {t1:.3g} И {f2} {'>' if q2>0.5 else '<'} {t2:.3g}", -tr[btr][pcol].sum(), btr.sum(),
                            tr[btr][ycol].mean() * 100, -te[bte][pcol].sum(), bte.sum(), te[bte][ycol].mean() * 100 if bte.sum() else np.nan))
    x = pd.DataFrame(res, columns=["исключить, если", "выигр_train", "n_train", "стоп%_train", "выигр_test", "n_test", "стоп%_test"]).sort_values("выигр_train", ascending=False)
    top = x.head(15)
    print(f"пары: проверено {len(x)}; топ-15 по train → на test в плюсе {(top.выигр_test > 0).sum()}, сумма на test {top.выигр_test.sum():+.1f}")
    print(top.round(2).to_string(index=False))
    # 2) составной балл из топ-k признаков train (знак по train)
    for k in (3, 5, 10):
        fs = au[:k]; z_tr = 0; z_te = 0
        for f, A, _ in fs:
            m, s = tr[f].median(), (tr[f].quantile(.75) - tr[f].quantile(.25)) or 1
            sg = 1 if A > 0.5 else -1
            z_tr = z_tr + sg * ((tr[f] - m) / s).clip(-3, 3).fillna(0); z_te = z_te + sg * ((te[f] - m) / s).clip(-3, 3).fillna(0)
        for share in (0.1, 0.2):
            thr = z_tr.quantile(1 - share)
            print(f"балл из {k} признаков, отсечь {share*100:.0f}% (порог по train): train {tr[z_tr < thr][pcol].sum():+.1f} (было {tr[pcol].sum():+.1f}), "
                  f"test {te[z_te < thr][pcol].sum():+.1f} (было {te[pcol].sum():+.1f}); отсеяно на test {int((z_te >= thr).sum())}, стопов среди них {te[z_te >= thr][ycol].sum()}")
if __name__ == "__main__":
  for label, sub in (("ОБА ПРАВИЛА", d), ("ПРАВИЛО 1", d[d.rule == "1"]), ("ПРАВИЛО 2", d[d.rule == "2"])):
    study(sub, label, "y_stop", "y_pnl")
    study(sub, label, "y_stop1525", "y_pnl1525")
