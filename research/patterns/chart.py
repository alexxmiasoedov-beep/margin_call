import pickle, datetime, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
D = pickle.load(open("kaia/data.pkl", "rb")); K15, MT, P1 = D["K15"], D["MT"], D["P1"]
MSK = datetime.timezone(datetime.timedelta(hours=3))
dt = lambda t: datetime.datetime.fromtimestamp(t, MSK).replace(tzinfo=None)
T = lambda d, h, m: datetime.datetime(2026, 10, d, h, m)
a, b = datetime.datetime(2026, 10, 9, 9, 0, tzinfo=MSK).timestamp(), datetime.datetime(2026, 10, 10, 6, 0, tzinfo=MSK).timestamp()
K = K15[(K15[:, 0] >= a) & (K15[:, 0] < b)]
UP, DOWN, INK, INK2, GRID, SHADE, BG = "#2a78d6", "#e34948", "#0b0b0b", "#52514e", "#e6e5e0", "#f0efec", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG})
fig, ax = plt.subplots(4, 1, figsize=(16, 11.5), sharex=True, gridspec_kw={"height_ratios": [5, 1.4, 1.1, 1.1], "hspace": 0.08})
w = datetime.timedelta(minutes=15) * 0.62
phases = [(T(9, 9, 0), T(9, 11, 0), "база"), (T(9, 11, 0), T(9, 11, 15), "1"), (T(9, 11, 15), T(9, 11, 30), "2"),
          (T(9, 11, 30), T(9, 13, 30), "3 рост лесенкой\n+38% за 2 ч"), (T(9, 13, 30), T(9, 15, 30), "4а откат\n−18%"),
          (T(9, 15, 30), T(9, 21, 30), "4б боковик 6 ч\nс проколом 0,050"), (T(9, 21, 30), T(10, 3, 30), "5 второй рост\nк новому максимуму"),
          (T(10, 3, 30), T(10, 6, 0), "6 вершина 2,\nмаксимумы ниже")]
for i, (s, e, lab) in enumerate(phases):
    for x in ax: x.axvspan(s, e, color=SHADE if i % 2 == 0 else BG, zorder=0, lw=0)
    ax[0].text(s + (e - s) / 2, 0.0679, lab, ha="center", va="top", fontsize=8.5, color=INK2, linespacing=1.15)
ax[0].annotate("1 — импульс: одна свеча +21,5%,\n+12,4% за одну минуту (11:06)\n2 — пауза: одна свеча, откат −2,7%",
               (T(9, 11, 15), 0.0469), xytext=(T(9, 9, 10), 0.0560), fontsize=8.5, color=INK,
               arrowprops=dict(arrowstyle="-", color="#8a8984", lw=0.8))
for r in K:
    t, o, h, l, c = dt(r[0]) + datetime.timedelta(minutes=7.5), *r[1:5]
    col = UP if c >= o else DOWN
    ax[0].vlines(t, l, h, color=col, lw=1.0, zorder=3)
    ax[0].bar(t, max(abs(c - o), 0.00004), bottom=min(o, c), width=w, color=col, zorder=3, linewidth=0)
levels = [(0.03784, "0,0378 — база"), (0.04599, "0,0460 — закрытие импульсной свечи: в откате не тронута"),
          (0.04982, "0,0498 — середина всего роста (50%): дно отката 0,0497 в 19:00"), (0.06179, "0,0618 — вершина 1 (13:15)"),
          (0.06380, "0,0638 — вершина 2 (03:15), на 3% выше первой")]
for y, lab in levels:
    ax[0].axhline(y, color="#8a8984", lw=0.8, ls=(0, (4, 3)), zorder=1)
    left = y > 0.061                                   # вершины — подписи слева, где над базой пусто
    ax[0].text(T(9, 9, 5) if left else T(10, 5, 55), y + 0.00025, lab, fontsize=8, color=INK2, va="bottom", ha="left" if left else "right",
               zorder=4, bbox=dict(boxstyle="square,pad=0.1", fc=BG, ec="none", alpha=0.85))
for t, y, lab in ((T(9, 15, 16), 0.05179, "сигнал бота (правило 1)\n15:16, вход 0,0518"), (T(10, 1, 15), 0.05538, "сигнал D*\n01:15, вход 0,0554")):
    ax[0].plot([t], [y], marker="^", ms=8, color=INK, zorder=5)
    ax[0].annotate(lab, (t, y), xytext=(0, -30), textcoords="offset points", ha="center", fontsize=8, color=INK, zorder=5)
ax[0].set_ylim(0.0355, 0.0682); ax[0].set_ylabel("цена, USDT")
ax[0].set_title("KAIA, фьючерс Binance, 15 мин, время МСК — 09.10 09:00 – 10.10 06:00 (окно разбора 10:30–05:30)", loc="left", fontsize=11, pad=8)
ax[0].grid(axis="y", color=GRID, lw=0.6); ax[0].set_axisbelow(True)
ax[1].bar([dt(t) + datetime.timedelta(minutes=7.5) for t in K[:, 0]], K[:, 6] / 1e6, width=w, color="#86b6ef", linewidth=0, zorder=3)
ax[1].set_ylabel("объём,\nмлн $")
ax[1].text(0.995, 0.86, "объём за 15 мин: импульс 11,7 млн $ (в 350 раз выше базы), пик 33,6 на вершине 1, во второй волне — не больше 12,7",
           transform=ax[1].transAxes, fontsize=8, color=INK2, ha="right")
m = MT[(MT[:, 0] >= a) & (MT[:, 0] < b)]
ax[2].plot([dt(t) for t in m[:, 0]], m[:, 2] / 1e6, color=UP, lw=2, zorder=3); ax[2].set_ylabel("открытый\nинтерес, млн $")
ax[2].text(0.995, 0.12, "2,3 → 13 млн $ к вершине 1 (в монетах ×4), в откате не снижался, к вершине 2 — 14,8", transform=ax[2].transAxes,
           fontsize=8, color=INK2, ha="right")
p = P1[(P1[:, 0] >= a) & (P1[:, 0] < b)]; pp = p[:, 4].reshape(-1, 5).mean(axis=1) * 100
ax[3].plot([dt(t) for t in p[::5, 0]], pp, color=DOWN, lw=2, zorder=3); ax[3].axhline(0, color="#8a8984", lw=0.8)
ax[3].set_ylabel("премия\nфьючерса, %")
ax[3].text(0.995, 0.10, "фьючерс дешевле индекса до −12% (12:37) → фандинг в 15:00 упёрся в −2% и перешёл на ежечасный: −0,5…−0,15% в час (оценка)",
           transform=ax[3].transAxes, fontsize=8, color=INK2, ha="right")
for x in ax[1:]: x.grid(axis="y", color=GRID, lw=0.6); x.set_axisbelow(True)
ax[3].xaxis.set_major_locator(mdates.HourLocator(interval=1)); ax[3].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.setp(ax[3].get_xticklabels(), fontsize=7.5)
ax[3].set_xlim(T(9, 9, 0), T(10, 6, 0))
for x in ax:
    for s in ("top", "right"): x.spines[s].set_visible(False)
out = "/tmp/claude-0/-home-user-romanovdecor-site/55ef3fa1-b1d3-5bfb-a9b4-6937479954ec/scratchpad/kaia_09-10_architecture.png"
fig.savefig(out, dpi=150, bbox_inches="tight"); print(out)
