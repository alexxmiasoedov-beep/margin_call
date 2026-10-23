"""График двух стратегий s12: накопленный итог по сделкам (маржа 1 USDT × 1) по дате входа и распределение исходов."""
import datetime
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C1, C2 = "#2a78d6", "#eb6834"
J = pd.read_pickle("s12/final_journals.pkl"); UTC = datetime.timezone.utc
fig = plt.figure(figsize=(11.5, 8.6), dpi=150, facecolor=SURF)
gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1], hspace=0.38, wspace=0.22)
ax = fig.add_subplot(gs[0, :]); ax.set_facecolor(SURF)
for key, col, lab in (("A", C1, "🆕 первый займ свежего токена (вход через 24 ч, 21 сут, стоп +60%)"), ("B", C2, "📢 объявления Binance: делистинг и Monitoring Tag (7 сут, стоп +25%)")):
    j = J[key].sort_values("te"); x = [datetime.datetime.fromtimestamp(t, UTC) for t in j.te]; y = j.sp.cumsum().values
    ax.step(x, y, where="post", color=col, lw=2, label=lab.replace("🆕 ", "").replace("📢 ", ""))
    ax.annotate(f"{y[-1]:+.1f} USDT", (x[-1], y[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=10)
ax.axhline(0, color=INK2, lw=0.8)
cut = datetime.datetime(2025, 10, 1, tzinfo=UTC); ax.axvline(cut, color=INK2, lw=0.8, ls=(0, (3, 3)))
ax.text(cut + datetime.timedelta(days=5), ax.get_ylim()[1] * 0.55, "2-я половина", color=INK2, fontsize=9, va="top")
ax.set_title("Две стратегии из литературы, проверенные на данных Binance: накопленный итог, USDT (маржа 1 USDT × 1 на сделку)",
             color=INK, fontsize=11, loc="left", pad=18)
a, b = J["A"], J["B"]
ax.text(0, 1.01, f"первый займ свежего токена: {len(a)} сделок, {a.sp.mean()*100:+.1f}% на сделку, в плюсе {(a.sp > 0).mean():.0%} · "
        f"объявления: {len(b)} сделок, {b.sp.mean()*100:+.1f}% на сделку, в плюсе {(b.sp > 0).mean():.0%}", transform=ax.transAxes, color=INK2, fontsize=9, va="bottom")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9); ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%y"))
ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
for i, (key, col, nm) in enumerate((("A", C1, "Первый займ свежего токена: исход сделки, %"), ("B", C2, "Объявления Binance: исход сделки, %"))):
    c = fig.add_subplot(gs[1, i]); c.set_facecolor(SURF)
    v = J[key].sp.clip(-1, 1) * 100
    bins = np.arange(-100, 101, 10)
    c.hist(v, bins=bins, color=col, edgecolor=SURF, linewidth=1.5)
    c.axvline(0, color=INK2, lw=0.8)
    c.set_title(nm, color=INK, fontsize=11, loc="left")
    c.grid(axis="y", color=GRID, lw=0.8); c.set_axisbelow(True)
    for s in ("top", "right"): c.spines[s].set_visible(False)
    for s in ("left", "bottom"): c.spines[s].set_color(GRID)
    c.tick_params(colors=INK2, labelsize=8.5); c.set_ylabel("сделок", color=INK2, fontsize=9)
fig.text(0.01, 0.005, "Бэктест 10.2024–10.2026, фьючерсы Binance (делистингованные включены), фандинг и комиссия 0,1% за круг; одна открытая сделка на монету. "
         "Исходы ниже −100% (фандинг) показаны на краю.\nДанные: MarginData (CryptoCode), объявления Binance, data.binance.vision.", color=INK2, fontsize=8)
fig.savefig("s12/strategies.png", facecolor=SURF, bbox_inches="tight"); print("ok")
