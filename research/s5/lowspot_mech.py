"""Механизм лонга «памп без спотовой розницы»: приходит ли спот позже (доля спота в следующие часы) и как это связано с ценой;
обычная доля спота у монеты (всегда «фьючерсная» или спот обычно есть, а в пампе — нет)."""
import pickle, os, re
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); H = pd.read_pickle("s5/lowspot_trades.pkl"); c = "p0.3_0.15_192"
SP = {}
for s in set(H.s):
    for n in (s, strip(s)):
        fn = f"s5/spot/{n}USDT.npy"
        if os.path.exists(fn): SP[s] = np.load(fn); break
def after(s, t, h0, h1):
    a = K[s]; j = np.searchsorted(a["t"], t - 900); b = SP[s]
    tt = a["t"][j + 1 + h0 * 4:j + 1 + h1 * 4]; ix = np.searchsorted(b[:, 0], tt); ok = ix < len(b); ok[ok] &= b[ix[ok], 0] == tt[ok]
    sv = b[ix[ok], 2].sum(); fv = a["qv"][j + 1 + h0 * 4:j + 1 + h1 * 4].astype(np.float64).sum()
    return sv / max(sv + fv, 1)
H["sh_next4"] = [after(s, t, 0, 4) for s, t in zip(H.s, H.t)]; H["sh_4_24"] = [after(s, t, 4, 24) for s, t in zip(H.s, H.t)]
H["grp"] = pd.cut(H.share, [0, 0.12, 0.2, 0.3, 1.01], labels=["<12%", "12–20%", "20–30%", "≥30%"])
print(H.groupby("grp", observed=True).agg(n=("s", "size"), share=("share", "median"), norm=("norm", "median"), next4=("sh_next4", "median"), h4_24=("sh_4_24", "median"),
                                           long=(c, "mean")).round(3).to_string())
L = H[H.share < 0.12].copy()
L["rise"] = L.sh_next4 - L.share
print("\nв группе < 12%: доля спота в следующие 4 ч выросла у", f"{(L.rise > 0).mean():.0%};", "лонг при росте доли / без роста:",
      f"{L[L.rise > 0.05][c].mean()*100:+.2f}% ({(L.rise > 0.05).sum()}) / {L[L.rise <= 0.05][c].mean()*100:+.2f}% ({(L.rise <= 0.05).sum()})  ← (это уже будущее, только для понимания)")
for lo, hi in ((0, 0.1), (0.1, 0.2), (0.2, 1.01)):
    g = L[(L.norm >= lo) & (L.norm < hi)]
    print(f"обычная доля спота {lo:.0%}–{hi:.0%}: {len(g)} сделок, лонг {g[c].mean()*100:+.2f}% ({g[g.y==1][c].mean()*100:+.2f}/{g[g.y==2][c].mean()*100:+.2f})")
