"""Фон для шорта после дампа: тот же шорт (тейк/стоп/48 ч, фандинг, комиссия) у тех же монет в случайные моменты
(каждые 12 ч в 00:00 и 12:00 UTC) и у тех же монет в моменты дампов других монет (тот же рынок)."""
import pickle, datetime
import numpy as np, pandas as pd
src = open("s6/feat.py").read()
exec(src.split("P = pd.read_pickle")[0])
exec("FX = {}" + src.split("FX = {}")[1].split("prev = {}")[0].split("def kr_arrays")[0])
D = pd.read_pickle("s7/feat_dump.pkl")
UTC = datetime.timezone.utc; A = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
grp = {"пара к лире, доля < 3%": D[(D.has_try == 1) & (D.fshare < 0.03)], "монета в Корее": D[D.korea == 1], "все дампы": D}
rng = np.random.default_rng(0)
for nm, g in grp.items():
    syms = g.s.unique(); res = []
    for s in syms:
        a = K[s]; t = a["t"]; idx = np.flatnonzero(((t + 900) % 43200 == 0) & (t + 900 >= A) & (t + 900 <= A + 727 * 86400))
        if len(idx) > 40: idx = rng.choice(idx, 40, replace=False)
        for j in idx:
            if j < 700 or j + 192 >= len(t): continue
            o = outcomes(s, int(j)); res.append((t[j] + 900 < CUT, o.get("S_10_10", np.nan), o.get("S_10_25", np.nan)))
    R = pd.DataFrame(res, columns=["y1", "S_10_10", "S_10_25"])
    for col in ("S_10_10", "S_10_25"):
        print(f"{nm}: дампы {col} {g[col].mean()*100:+.2f}% (1-й {g[g.y==1][col].mean()*100:+.2f}, 2-й {g[g.y==2][col].mean()*100:+.2f}) | "
              f"фон в случайные моменты {R[col].mean()*100:+.2f}% (1-й {R[R.y1][col].mean()*100:+.2f}, 2-й {R[~R.y1][col].mean()*100:+.2f}), выборка фона {len(R)}")
