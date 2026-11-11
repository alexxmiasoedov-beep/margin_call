"""Г2, уточнение для 🏦: даёт ли доля часов в канале (мера 🏦) что-то сверх волатильности. На той же корзине, что
h2_dtc.py (s22/h2_basket.pkl: каждый день в 01:00 UTC монеты, бывшие в канале за 7 суток, оборот ≥ 10 млн $):
сортировки по волатильности, двойная сортировка «волатильность × доля в канале», Фама–Макбет без мер займа.
Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT
from h2_dtc import nw_t

if __name__ == "__main__":
    U = pd.read_pickle("s22/h2_basket.pkl").dropna(subset=["x", "share", "vol"])
    print("Сортировки (верхний квинтиль к среднему корзины, шорт к рынку за 7 суток):")
    for col, nm in (("share", "доля в канале"), ("vol", "волатильность 7 сут")):
        top = []
        for d, g in U.groupby("d"):
            if len(g) >= 10:
                q = g[col].rank(pct=True); top.append((d, g.x[q > 0.8].mean() - g.x.mean(), g.n[q > 0.8].mean()))
        t = pd.DataFrame(top, columns=["d", "top", "net"])
        print(f"  {nm:20s}: {t.top.mean() * 100:+.2f}% (t НУ {nw_t(t.top):+.1f}; половины {t.top[t.d < CUT].mean() * 100:+.2f}/"
              f"{t.top[t.d >= CUT].mean() * 100:+.2f}), шорт с фандингом {t.net.mean() * 100:+.2f}% (t НУ {nw_t(t.net):+.1f})")
    print("\nДвойная сортировка: внутри терцилей волатильности — доля в канале, верхняя треть минус нижняя:")
    rows = []
    for d, g in U.groupby("d"):
        if len(g) < 15:
            continue
        vt = pd.qcut(g.vol.rank(method="first"), 3, labels=False)
        for k in range(3):
            h = g[vt == k]; q = h.share.rank(pct=True)
            rows.append((d, k, h.x[q > 2 / 3].mean() - h.x[q <= 1 / 3].mean()))
    W = pd.DataFrame(rows, columns=["d", "vt", "spread"])
    for k, nm in enumerate(("низкая", "средняя", "высокая")):
        s = W[W.vt == k].set_index("d").spread
        print(f"  волатильность {nm:8s}: {s.mean() * 100:+.2f}% (t НУ {nw_t(s):+.1f})")
    s = W.groupby("d").spread.mean()
    print(f"  в среднем по терцилям: {s.mean() * 100:+.2f}% (t НУ {nw_t(s):+.1f}; половины {s[s.index < CUT].mean() * 100:+.2f}/"
          f"{s[s.index >= CUT].mean() * 100:+.2f})")
    print("\nФама–Макбет (непересекающиеся недели, ранги 0…1):")
    for cols in (["share"], ["vol"], ["share", "vol"], ["share", "vol", "r7", "f7"]):
        coefs = []
        for d in sorted(U.d.unique())[::7]:
            g = U[U.d == d].dropna(subset=cols + ["x"])
            if len(g) < 15:
                continue
            X = np.column_stack([np.ones(len(g))] + [g[c].rank(pct=True).values for c in cols])
            coefs.append(np.linalg.lstsq(X, g.x.values, rcond=None)[0][1:])
        C = np.array(coefs)
        print(f"  {' + '.join(cols):22s}: " + "; ".join(f"{c} {C[:, i].mean() * 100:+.2f}% (t {C[:, i].mean() / C[:, i].std() * np.sqrt(len(C)):+.1f})"
                                                     for i, c in enumerate(cols)))
