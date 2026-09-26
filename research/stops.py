"""Можно ли было избежать стопов: признаки в момент сигнала (без будущего) против исхода при тейке 6 / стопе 20 / 48ч."""
import json, glob, os, bisect
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 220)

MARGIN, LEV, FEE = 1.0, 10, 0.0005
GAP, MIN_RUN, PMIN, PMAX, BR_MIN = 1800, 4.0, 8, 17, 5
TP, SL, HB = 6, 20, 48 * 4

df = pd.read_csv("dataset.csv", usecols=["sym", "epoch", "post", "bor", "rep", "br", "rank", "chng"]).sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff(); df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600
df["post_n"] = df.groupby("post").sym.transform("size")
df["bor_med_past"] = df.groupby("sym").bor.transform(lambda s: s.expanding().median().shift(1))   # норма займа монеты по прошлому
allposts = df[["sym", "epoch"]].copy()
df = df[df.run_h >= MIN_RUN]

K = {}; V = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]; k = np.array(json.load(open(fn))["k"], dtype=float)
    if len(k) < 200 or k[:, 4].std() / k[:, 4].mean() < 0.002: continue
    K[s] = (k[:, 0].astype(int), k[:, 1], k[:, 2], k[:, 3], k[:, 4]); V[s] = k[:, 5]
df = df[df.sym.isin(K)].sort_values("epoch")
# рынок: медиана 4ч/24ч изменения по всем монетам на сетке 15м (по закрытиям ПРЕДЫДУЩИХ баров)
grid = np.arange((df.epoch.min() // 900 - 200) * 900, (df.epoch.max() // 900 + 10) * 900, 900)
C = pd.DataFrame({s: pd.Series(v[4], index=v[0]).reindex(grid).ffill() for s, v in K.items()}, index=grid)
M4 = ((C / C.shift(16) - 1) * 100).median(axis=1); M24 = ((C / C.shift(96) - 1) * 100).median(axis=1)
fund = json.load(open("features6m.json"))["fund"]
fund = {s: sorted(v) for s, v in fund.items()}

rows = []; last = {}; open_until = {}; sig_hist = {}
posts_by_sym = {s: g.epoch.values for s, g in allposts.groupby("sym")}
for r in df.itertuples():
    t, o, h, l, c = K[r.sym]; i = bisect.bisect_right(t, r.epoch) - 1
    if i < 120 or i + 1 >= len(t): continue
    b4h = (o[i] / c[i - 16] - 1) * 100
    rule = "1" if PMIN <= b4h <= PMAX else ("2" if -PMAX <= b4h <= -PMIN and r.br >= BR_MIN else None)
    if not rule: continue
    if r.sym in last and r.epoch - last[r.sym] < 86400: continue
    if r.sym in open_until and open_until[r.sym] > r.epoch: continue
    e = o[i]; end = min(i + HB, len(t) - 1); res = None
    for j in range(i, end + 1):
        if h[j] >= e * (1 + SL / 100): res, kind, hrs = -SL / 10, "стоп", (j - i) / 4; break
        if l[j] <= e * (1 - TP / 100): res, kind, hrs = TP / 10, "тейк", (j - i) / 4; break
    if res is None: res, kind, hrs = -(c[end] / e - 1) * 10, "время", (end - i) / 4
    res -= MARGIN * LEV * FEE * 2; last[r.sym] = r.epoch; open_until[r.sym] = r.epoch + hrs * 3600
    prev_sigs = sig_hist.get(r.sym, []); n7 = sum(1 for x in prev_sigs if r.epoch - x < 7 * 86400); sig_hist.setdefault(r.sym, []).append(r.epoch)
    bar = t[i]; rets = np.diff(np.log(c[i - 96:i]))
    pp = posts_by_sym[r.sym]; n4h_posts = int(((pp >= r.epoch - 4 * 3600) & (pp < r.epoch)).sum()); n7d_posts = int(((pp >= r.epoch - 7 * 86400) & (pp < r.epoch)).sum())
    fr = fund.get(r.sym); fk = bisect.bisect_right(fr, [r.epoch, 9]) - 1 if fr else -1
    rows.append(dict(sym=r.sym, epoch=r.epoch, rule=rule, исход=kind, pnl=res, часов=hrs,
                     памп=abs(b4h), серия_ч=r.run_h, br=r.br, bor=r.bor, bor_rel=r.bor / r.bor_med_past if r.bor_med_past else np.nan,
                     место=r.rank, монет_в_посте=r.post_n, chng=r.chng,
                     b1h=(o[i] / c[i - 4] - 1) * 100, b24h=(o[i] / c[i - 96] - 1) * 100, b7d=(o[i] / c[max(i - 672, 0)] - 1) * 100,
                     от_макс24=(o[i] / h[i - 96:i].max() - 1) * 100, от_мин24=(o[i] / l[i - 96:i].min() - 1) * 100,
                     объём4ч_к_сут=V[r.sym][i - 16:i].sum() / max(V[r.sym][i - 112:i - 16].sum() / 6, 1e-9),
                     волат24=rets.std() * 100, рынок4ч=M4.get(bar - 900, np.nan), рынок24ч=M24.get(bar - 900, np.nan),
                     час=int((r.epoch % 86400) // 3600), день_нед=int(((r.epoch // 86400) + 3) % 7),
                     сигн7д=n7, постов4ч=n4h_posts, постов7д=n7d_posts, фандинг=fr[fk][1] * 100 if fk >= 0 else np.nan))
D = pd.DataFrame(rows); D["стоп"] = (D.исход == "стоп").astype(int); mid = D.epoch.median()
D.to_csv("stops_features.csv", index=False)
print(f"сделок {len(D)}, стопов {D.стоп.sum()} ({D.стоп.mean()*100:.0f}%), итого {D.pnl.sum():+.1f}")

feats = ["памп", "серия_ч", "br", "bor", "bor_rel", "место", "монет_в_посте", "b1h", "b24h", "b7d", "от_макс24", "от_мин24", "объём4ч_к_сут", "волат24", "рынок4ч", "рынок24ч", "час", "день_нед", "сигн7д", "постов4ч", "постов7д", "фандинг"]
print("\n== признак: доля стопов по квинтилям (низ → верх), PnL/сделку по квинтилям; p стоп-vs-нестоп; Spearman с PnL ==")
for f in feats:
    d = D.dropna(subset=[f])
    if d[f].nunique() < 4: continue
    try:
        q = pd.qcut(d[f], 5, duplicates="drop")
    except ValueError:
        continue
    g = d.groupby(q, observed=True).agg(стоп=("стоп", "mean"), pnl=("pnl", "mean"), n=("pnl", "size"))
    p = stats.mannwhitneyu(d[d.стоп == 1][f], d[d.стоп == 0][f]).pvalue
    rho, pr = stats.spearmanr(d[f], d.pnl)
    flag = " <--" if p < 0.01 or pr < 0.01 else ""
    print(f"  {f:14s} стоп% " + " ".join(f"{v*100:3.0f}" for v in g.стоп) + " | PnL " + " ".join(f"{v:+.2f}" for v in g.pnl) + f" | p={p:.3f} rho={rho:+.3f} p={pr:.3f}{flag}")

print("\n== по правилам и по часу суток ==")
print(D.groupby("rule").agg(n=("pnl", "size"), стоп=("стоп", "mean"), pnl=("pnl", "mean")).round(2).to_string())
hc = D.groupby(pd.cut(D.час, [-1, 3, 7, 11, 15, 19, 23], labels=["0–3", "4–7", "8–11", "12–15", "16–19", "20–23"]), observed=True).agg(n=("pnl", "size"), стоп=("стоп", "mean"), pnl=("pnl", "mean"), сумма=("pnl", "sum")).round(2)
print(hc.to_string())
dc = D.groupby("день_нед").agg(n=("pnl", "size"), стоп=("стоп", "mean"), pnl=("pnl", "mean"), сумма=("pnl", "sum")).round(2); dc.index = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]; print(dc.to_string())

print("\n== кандидаты-фильтры: что отсекаем, сколько денег теряем/спасаем, устойчивость по половинам ==")
def test(mask, label):
    cut = D[mask]; keep = D[~mask]
    if len(cut) < 10: return
    a = keep[keep.epoch < mid].pnl.sum(); b = keep[keep.epoch >= mid].pnl.sum()
    c1 = cut[cut.epoch < mid].pnl.sum(); c2 = cut[cut.epoch >= mid].pnl.sum()
    ok = "✓" if c1 < 0 and c2 < 0 else " "
    print(f" {ok} {label:44s} отсечено n={len(cut):3d} стоп {cut.стоп.mean()*100:3.0f}% сумма {cut.pnl.sum():+6.1f} ({c1:+5.1f}/{c2:+5.1f}) | остаток n={len(keep):3d} стоп {keep.стоп.mean()*100:3.0f}% итого {keep.pnl.sum():+6.1f} ({a:+5.1f}/{b:+5.1f})")
test(D.памп > 14, "памп/падение > 14%")
test(D.памп < 9, "памп/падение < 9%")
test(D.серия_ч > 24, "серия > 24 ч")
test(D.серия_ч < 5, "серия 4–5 ч")
test(D.место > 10, "место в посте > 10")
test(D.b24h > 25, "рост за сутки > 25%")
test(D.b24h > 40, "рост за сутки > 40%")
test(D.b7d > 50, "рост за неделю > 50%")
test(D.от_макс24 > -1, "цена у суточного максимума (< 1% от него)")
test(D.от_макс24 < -15, "цена ниже суточного максимума на 15%+")
test(D.объём4ч_к_сут > 3, "объём за 4ч > 3× среднего")
test(D.волат24 > D.волат24.quantile(.8), "волатильность в верхних 20%")
test(D.рынок4ч > 1, "рынок за 4ч вырос > 1%")
test(D.рынок24ч > 3, "рынок за сутки вырос > 3%")
test(D.рынок24ч < -3, "рынок за сутки упал > 3%")
test(D.сигн7д >= 1, "уже был сигнал по монете за 7 дней")
test(D.сигн7д >= 2, "2+ сигнала по монете за 7 дней")
test(D.постов7д < 20, "монета редко бывала в канале (< 20 постов/7д)")
test(D.фандинг < -0.1, "фандинг < −0,1%")
test(D.фандинг > 0.03, "фандинг > +0,03%")
test((D.час >= 0) & (D.час <= 3), "час 0–3 UTC")
test(D.bor_rel > 5, "займ > 5× нормы монеты")
test(D.bor_rel < 0.5, "займ < 0,5× нормы монеты")
test(D.монет_в_посте < 15, "мало монет в посте (< 15)")
