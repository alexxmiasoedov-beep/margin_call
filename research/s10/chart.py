"""График фактора займа: накопленный доход лесенкой (шорт топ-10 канала + лонг рынка; только шорт), по кварталам,
и проверка сетки из 324 вариантов: доход на 1-й половине против 2-й."""
import datetime
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
W = pd.read_pickle("s10/factor11_weekly.pkl").dropna(subset=["pair", "short"])
R = pd.read_pickle("s10/factor8b_grid.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC)
x = [datetime.datetime.fromtimestamp(t, UTC) for t in W.index]
fig = plt.figure(figsize=(11.5, 9.2), dpi=150, facecolor=SURF)
gs = fig.add_gridspec(2, 2, height_ratios=[1.25, 1], width_ratios=[1.35, 1], hspace=0.34, wspace=0.22)
ax = fig.add_subplot(gs[0, :]); ax.set_facecolor(SURF)
for col, lab, y in ((C1, "шорт 10 монет + лонг рынка на ту же сумму", W.pair.cumsum() * 100), (C2, "только шорт 10 монет", W.short.cumsum() * 100)):
    ax.plot(x, y, color=col, lw=2, label=lab)
    ax.annotate(f"{y.iloc[-1]:+.0f}%", (x[-1], y.iloc[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontsize=10)
ax.axhline(0, color=INK2, lw=0.8)
ax.axvline(CUT, color=INK2, lw=0.8, ls=(0, (3, 3)))
ax.text(CUT + datetime.timedelta(days=5), ax.get_ylim()[1] * 0.97, "2-я половина (проверка)", color=INK2, fontsize=9, va="top")
ax.set_title("Фактор займа: шорт 10 монет, чаще всех бывших в канале MarginData за 7 дней — накопленный доход, %",
             color=INK, fontsize=11, loc="left", pad=20)
m, mm = W.pair.mean() * 100, W.short.mean() * 100
ax.text(0, 1.01, f"шорт+рынок {m:+.2f}%/нед, недель в плюсе {(W.pair > 0).mean():.0%}, просадка {((W.pair.cumsum() - W.pair.cumsum().cummax()).min()*100):.1f}% · "
        f"только шорт {mm:+.2f}%/нед, просадка {((W.short.cumsum() - W.short.cumsum().cummax()).min()*100):.1f}%",
        transform=ax.transAxes, color=INK2, fontsize=9, va="bottom")
ax.title.set_position((0, 1.0))
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9); ax.xaxis.set_major_formatter(mdates.DateFormatter("%m.%y"))
ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
# по кварталам
b = fig.add_subplot(gs[1, 0]); b.set_facecolor(SURF)
q = W.groupby(pd.to_datetime(W.index, unit="s").to_period("Q"))[["pair", "short"]].sum() * 100
xx = np.arange(len(q)); wdt = 0.38
b.bar(xx - wdt / 2 - 0.01, q.pair, wdt, color=C1, label="шорт + рынок")
b.bar(xx + wdt / 2 + 0.01, q.short, wdt, color=C2, label="только шорт")
b.axhline(0, color=INK2, lw=0.8)
b.set_xticks(xx, [f"{p.quarter} кв.\n{p.year}" for p in q.index])
b.set_title("По кварталам, % (2025 — с 10 марта)", color=INK, fontsize=11, loc="left")
b.grid(axis="y", color=GRID, lw=0.8); b.set_axisbelow(True)
for s in ("top", "right"): b.spines[s].set_visible(False)
for s in ("left", "bottom"): b.spines[s].set_color(GRID)
b.tick_params(colors=INK2, labelsize=8.5); b.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK)
# сетка вариантов
c = fig.add_subplot(gs[1, 1]); c.set_facecolor(SURF)
for hd, col, lab in (("market", C1, "хедж рынком"), ("margin", C3, "хедж маржинальными монетами"), ("нет", C2, "без хеджа")):
    g = R[R.hedge == hd]
    c.scatter(g.m1 * 100, g.m2 * 100, s=18, color=col, edgecolor=SURF, linewidth=0.6, label=f"{lab} ({len(g)})", zorder=3)
c.axhline(0, color=INK2, lw=0.8); c.axvline(0, color=INK2, lw=0.8)
c.set_xlabel("1-я половина (до 01.12.2025), %/нед", color=INK2, fontsize=9); c.set_ylabel("2-я половина, %/нед", color=INK2, fontsize=9)
c.set_title(f"324 варианта настроек: все в плюсе на 2-й половине", color=INK, fontsize=11, loc="left")
c.grid(color=GRID, lw=0.8); c.set_axisbelow(True)
for s in ("top", "right"): c.spines[s].set_visible(False)
for s in ("left", "bottom"): c.spines[s].set_color(GRID)
c.tick_params(colors=INK2, labelsize=8.5); c.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=INK)
fig.text(0.01, 0.005, "Бэктест 10.03.2025–04.10.2026: вход каждый день в 01:00 UTC на 7 дней (1/7 капитала), объём ≥ 10 млн $/сут, без шортов с фандингом < −0,1%/8 ч; "
         "комиссия 0,1% за круг и фандинг учтены.\nДанные: MarginData (CryptoCode), фьючерсы Binance (data.binance.vision).", color=INK2, fontsize=8)
fig.savefig("s10/borrow_factor.png", facecolor=SURF, bbox_inches="tight")
print("ok")
