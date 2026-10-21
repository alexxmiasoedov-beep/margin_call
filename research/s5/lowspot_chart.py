"""График: накопленный итог лонга «памп без розницы» (правила A и B), маржа 1 USDT × 10, по дате входа (МСК)."""
import datetime
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150, facecolor=SURF); ax.set_facecolor(SURF)
for nm, col, lab in (("B", "#2a78d6", "B: спот < 12%, Корея < 20%, лира < 10% (404 сделки)"), ("A", "#eb6834", "A: спот < 10%, Корея < 10%, лира < 5% (169 сделок)")):
    g = pd.read_pickle(f"s5/lowspot_{nm}.pkl").sort_values("t")
    x = [datetime.datetime.fromtimestamp(t + 3 * 3600, datetime.timezone.utc) for t in g.t]; y = np.cumsum(g.p.values * 10)
    ax.step(x, y, where="post", color=col, lw=2, label=lab)
    ax.annotate(f"{y[-1]:+.0f} USDT", (x[-1], y[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=10)
ax.axhline(0, color=INK2, lw=0.8)
ax.axvline(datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc), color=INK2, lw=0.8, ls=(0, (3, 3)))
ax.text(datetime.datetime(2025, 10, 8, tzinfo=datetime.timezone.utc), ax.get_ylim()[1] * 0.95, "2-й год", color=INK2, fontsize=9, va="top")
ax.set_title("Лонг «памп без розницы»: накопленный итог, USDT (маржа 1 × 10, тейк 30% / стоп 15% / 48 ч, с комиссией и фандингом)",
             color=INK, fontsize=11, loc="left")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9); ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%Y"))
ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
fig.tight_layout(); fig.savefig("s5/lowspot_long_2y.png", facecolor=SURF)
