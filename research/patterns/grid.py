import pickle, datetime, sys, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
MSK = datetime.timezone(datetime.timedelta(hours=3))
dt = lambda t: datetime.datetime.fromtimestamp(t, MSK).replace(tzinfo=None)
K = pickle.load(open("kaia/k15_all.pkl", "rb")); P = pickle.load(open(sys.argv[1], "rb")); out = sys.argv[2]
ORDER = {"образец": 0, "очень похож": 1, "похож": 2, "частично": 3}
P = sorted(P, key=lambda r: (ORDER.get(r.get("tier"), 9), r["ti"]))
UP, DOWN, INK, INK2, BG = "#2a78d6", "#e34948", "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": "#c3c2b7", "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": BG, "axes.facecolor": BG})
n = len(P); cols = 3; rows = (n + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(17, 3.6 * rows)); axs = np.array(axs).reshape(-1)
for ax, r in zip(axs, P):
    k = K[r["sym"]]; a, b = r.get("win0", r["ti"] - 6 * 3600), r.get("win1", max(r["t2"], r["tl"]) + 6 * 3600)
    x = k[(k[:, 0] >= a) & (k[:, 0] < b)]
    w = datetime.timedelta(minutes=15) * 0.65
    for t, o, h, l, c in x[:, :5]:
        col = UP if c >= o else DOWN; tt = dt(t) + datetime.timedelta(minutes=7.5)
        ax.vlines(tt, l, h, color=col, lw=0.7); ax.bar(tt, max(abs(c - o), (h - l) * 0.02 + 1e-12), bottom=min(o, c), width=w, color=col, lw=0)
    for t, y, lab, va in ((r["ti"], r["o"], "импульс", "top"), (r["t1"], r["H1"], "вершина 1", "bottom"), (r.get("tl2", r["tl"]), r.get("L2", r["L"]), "дно отката", "top"),
                          (r["t2"], r["H2"], "волна 2", "bottom")):
        ax.plot([dt(t) + datetime.timedelta(minutes=7.5)], [y], marker="o", ms=5, mfc="none", mec=INK, mew=1.2, zorder=5)
        ax.annotate(lab, (dt(t) + datetime.timedelta(minutes=7.5), y), xytext=(0, -11 if va == "top" else 6), textcoords="offset points",
                    ha="center", fontsize=7.5, color=INK, va=va)
    ax.axhline(r["H1"], color="#8a8984", lw=0.7, ls=(0, (4, 3)))
    span = (b - a) / 3600
    ax.set_xlim(dt(a), dt(b)); ax.xaxis.set_major_locator(mdates.HourLocator(interval=6 if span > 26 else 3 if span > 10 else 1)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m\n%H:%M"))
    res = "вторая волна дошла до вершины" if r["h2vs1"] >= -3 else "второй волны нет"
    ax.set_title(f"{r['sym']} — {r.get('tier', '')}: {dt(a):%d.%m %H:%M} – {dt(b):%d.%m %H:%M} МСК\nимпульс {dt(r['ti']):%d.%m %H:%M} МСК {r['imp']:+.0f}%, вершина 1 +{r['up1']:.0f}%, "
                 f"откат −{r.get('drop2', r['drop']):.0f}% ({r.get('R2', r['R']):.0f}% роста)\n{res}: {r['h2vs1']:+.1f}% к вершине 1", loc="left", fontsize=8, color=INK)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", lw=0.5)
for ax in axs[n:]: ax.axis("off")
fig.tight_layout(); fig.savefig(out, dpi=120); print(out)
