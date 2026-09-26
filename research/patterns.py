"""Паттерны движения цены ПЕРЕД сигналом (честно, по свечам до открытия свечи сигнала) против исхода при 6/20/48."""
import json, glob, os, bisect
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 230)

MARGIN, LEV, FEE = 1.0, 10, 0.0005
GAP, MIN_RUN, PMIN, PMAX, BR_MIN, TP, SL, HB = 1800, 4.0, 8, 17, 5, 6, 20, 48 * 4

df = pd.read_csv("dataset.csv", usecols=["sym", "epoch", "br"]).sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff(); df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600; df = df[df.run_h >= MIN_RUN]
K = {}; V = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]; k = np.array(json.load(open(fn))["k"], dtype=float)
    if len(k) < 300 or k[:, 4].std() / k[:, 4].mean() < 0.002: continue
    K[s] = (k[:, 0].astype(int), k[:, 1], k[:, 2], k[:, 3], k[:, 4]); V[s] = k[:, 5]
df = df[df.sym.isin(K)].sort_values("epoch")

rows = []; last = {}; open_until = {}; last_stop = {}
for r in df.itertuples():
    t, o, h, l, c = K[r.sym]; i = bisect.bisect_right(t, r.epoch) - 1
    if i < 200 or i + 1 >= len(t): continue
    p = o[i]                                  # цена в момент сигнала
    b4h = (p / c[i - 16] - 1) * 100
    rule = "1" if PMIN <= b4h <= PMAX else ("2" if -PMAX <= b4h <= -PMIN and r.br >= BR_MIN else None)
    if not rule: continue
    if r.sym in last and r.epoch - last[r.sym] < 86400: continue
    if r.sym in open_until and open_until[r.sym] > r.epoch: continue
    last[r.sym] = r.epoch
    end = min(i + HB, len(t) - 1); res = None
    for j in range(i, end + 1):
        if h[j] >= p * (1 + SL / 100): res, kind, hrs = -SL / 10, "стоп", (j - i) / 4; break
        if l[j] <= p * (1 - TP / 100): res, kind, hrs = TP / 10, "тейк", (j - i) / 4; break
    if res is None: res, kind, hrs = -(c[end] / p - 1) * 10, "время", (end - i) / 4
    res -= MARGIN * LEV * FEE * 2
    if r.sym in last_stop and r.epoch - last_stop[r.sym] < 48 * 3600: continue
    open_until[r.sym] = r.epoch + hrs * 3600
    if kind == "стоп": last_stop[r.sym] = r.epoch + hrs * 3600
    sgn = 1 if rule == "1" else -1            # для падений считаем движение "по модулю" в сторону сигнала
    mv = lambda n: sgn * (p / c[i - n] - 1) * 100
    b15, b30, b1, b2, b24 = mv(1), mv(2), mv(4), mv(8), mv(96)
    # за сколько минут набралось 8% в сторону сигнала (идём назад от цены сигнала)
    n8 = next((n for n in range(1, 97) if sgn * (p / c[i - n] - 1) * 100 >= 8), 97)
    peak = h[i - 16:i].max() if sgn > 0 else l[i - 16:i].min()
    from_peak = sgn * (p / peak - 1) * 100    # <0: цена уже отошла от экстремума 4ч
    rng1h = (h[i - 4:i].max() / l[i - 4:i].min() - 1) * 100
    vol1 = V[r.sym][i - 4:i].sum() / max(V[r.sym][i - 100:i - 4].sum() / 24, 1e-9)
    green = 0
    for j in range(i - 1, i - 17, -1):
        if sgn * (c[j] - o[j]) > 0: green += 1
        else: break
    rows.append(dict(sym=r.sym, epoch=r.epoch, rule=rule, исход=kind, pnl=res, часов=hrs, b4h=abs(b4h), b24=b24, b2h=b2, b1h=b1, b30=b30, b15=b15,
                     мин_на_8=n8 * 15, доля_1ч=b1 / abs(b4h) * 100, от_пика=from_peak, диап1ч=rng1h, объём1ч=vol1, свечей_подряд=green,
                     сутки_до_4ч=b24 - abs(b4h)))
D = pd.DataFrame(rows); D["стоп"] = (D.исход == "стоп").astype(int); D["тейк"] = (D.исход == "тейк").astype(int); D["быстрый"] = ((D.исход == "тейк") & (D.часов <= 1)).astype(int)
mid = D.epoch.median(); D.to_csv("patterns.csv", index=False)
print(f"сделок {len(D)}: правило 1 {int((D.rule=='1').sum())}, правило 2 {int((D.rule=='2').sum())}; тейк {D.тейк.mean()*100:.0f}%, стоп {D.стоп.mean()*100:.0f}%, быстрый тейк (<=1ч) {D.быстрый.mean()*100:.0f}%")


def show(d, f, bins, labels, title):
    d = d.dropna(subset=[f]).copy(); d["b"] = pd.cut(d[f], bins, labels=labels)
    g = d.groupby("b", observed=True).agg(n=("pnl", "size"), тейк=("тейк", "mean"), стоп=("стоп", "mean"), быстрый=("быстрый", "mean"), pnl=("pnl", "mean"), сумма=("pnl", "sum"))
    p = stats.mannwhitneyu(d[d.стоп == 1][f], d[d.стоп == 0][f]).pvalue if d.стоп.sum() > 3 else np.nan
    rho, pr = stats.spearmanr(d[f], d.pnl)
    print(f"\n-- {title} (стоп vs не-стоп p={p:.3f}; Spearman с PnL {rho:+.3f} p={pr:.3f}) --")
    print("  " + g.assign(тейк=lambda x: (x.тейк * 100).round(0), стоп=lambda x: (x.стоп * 100).round(0), быстрый=lambda x: (x.быстрый * 100).round(0), pnl=lambda x: x.pnl.round(2), сумма=lambda x: x.сумма.round(1)).to_string().replace("\n", "\n  "))


for rule, name in (("1", "ПРАВИЛО 1 — ПАМПЫ"), ("2", "ПРАВИЛО 2 — ПАДЕНИЯ")):
    d = D[D.rule == rule]
    print(f"\n==================== {name}, n={len(d)} ====================")
    show(d, "мин_на_8", [0, 30, 60, 120, 180, 240, 999], ["≤30 мин", "31–60", "61–120", "121–180", "181–240", "дольше 4ч"], "за сколько минут набралось 8% в сторону сигнала")
    show(d, "доля_1ч", [-999, 0, 25, 50, 75, 999], ["откат (<0)", "0–25%", "25–50%", "50–75%", ">75%"], "какая доля 4-часового движения пришлась на последний час")
    show(d, "b15", [-99, -2, -0.5, 0.5, 2, 5, 99], ["< −2%", "−2…−0,5", "−0,5…0,5", "0,5…2", "2…5", "> 5%"], "движение за последние 15 минут (в сторону сигнала)")
    show(d, "от_пика", [-99, -5, -3, -1.5, -0.5, 0.01], ["дальше 5% от пика", "3–5%", "1,5–3%", "0,5–1,5%", "на пике"], "насколько цена уже отошла от экстремума за 4ч")
    show(d, "b24", [-99, 0, 10, 20, 35, 60, 999], ["< 0", "0–10", "10–20", "20–35", "35–60", "> 60%"], "движение за сутки")
    show(d, "сутки_до_4ч", [-99, -5, 0, 5, 15, 30, 999], ["< −5", "−5…0", "0–5", "5–15", "15–30", "> 30%"], "сутки без последних 4ч (был ли тренд ДО пампа)")
    show(d, "диап1ч", [0, 3, 5, 8, 12, 99], ["<3%", "3–5", "5–8", "8–12", ">12%"], "размах (макс/мин) последнего часа")
    show(d, "объём1ч", [0, 2, 4, 8, 16, 999], ["<2×", "2–4×", "4–8×", "8–16×", ">16×"], "объём последнего часа к среднему часовому за сутки")
    show(d, "свечей_подряд", [-1, 0, 1, 2, 3, 99], ["0", "1", "2", "3", "4+"], "15-мин свечей подряд в сторону сигнала перед ним")

print("\n==================== КОМБИНАЦИИ (обе половины периода, ищем углы с тейк ≥ 85% или стоп ≥ 25%) ====================")
def combo(mask, label, d=D):
    x = D.loc[mask[mask].index]
    if len(x) < 25: return
    a = x[x.epoch < mid]; b = x[x.epoch >= mid]
    flag = "★" if x.тейк.mean() >= 0.85 and a.тейк.mean() >= 0.8 and b.тейк.mean() >= 0.8 else ("✗" if x.стоп.mean() >= 0.25 and a.стоп.mean() >= 0.2 and b.стоп.mean() >= 0.2 else " ")
    print(f" {flag} {label:58s} n={len(x):3d} тейк {x.тейк.mean()*100:3.0f}% ({a.тейк.mean()*100:.0f}/{b.тейк.mean()*100:.0f}) стоп {x.стоп.mean()*100:3.0f}% ({a.стоп.mean()*100:.0f}/{b.стоп.mean()*100:.0f}) PnL/сд {x.pnl.mean():+.2f} сумма {x.pnl.sum():+.1f}")
P = D[D.rule == "1"]
combo(P.мин_на_8 <= 60, "памп: 8% набрано за ≤60 мин (резкий)")
combo(P.мин_на_8 > 180, "памп: 8% набирались >3ч (плавный)")
combo((P.мин_на_8 <= 60) & (P.сутки_до_4ч > 5), "памп резкий + рост >5% за сутки до него (как MOVR)")
combo((P.мин_на_8 <= 60) & (P.сутки_до_4ч <= 0), "памп резкий без роста до него")
combo(P.от_пика < -3, "памп: цена уже отошла от пика >3% (откат начался)")
combo(P.от_пика >= -0.5, "памп: цена на пике (откат не начался)")
combo((P.от_пика >= -0.5) & (P.b15 > 2), "памп: на пике и последние 15 мин +2% и больше (ещё летит)")
combo((P.от_пика < -1.5) & (P.мин_на_8 <= 60), "памп: резкий и уже откатил >1,5%")
combo(P.доля_1ч > 75, "памп: >75% движения за последний час")
combo(P.доля_1ч < 25, "памп: <25% движения за последний час")
combo(P.объём1ч > 8, "памп: объём часа >8× среднего")
combo((P.объём1ч > 8) & (P.от_пика < -1.5), "памп: объём >8× и откат от пика начался")
combo(P.b24 > 35, "памп: сутки > +35%")
combo((P.b24 > 35) & (P.мин_на_8 <= 60), "памп: сутки >35% и резкий")
combo(P.свечей_подряд >= 3, "памп: 3+ зелёных свечи подряд перед сигналом")
combo(P.свечей_подряд == 0, "памп: последняя свеча красная")
Q = D[D.rule == "2"]
combo(Q.сутки_до_4ч < -10, "падение: сутки до него > +10% (памп, потом слив — как XAI)", D)
combo(Q.сутки_до_4ч > 5, "падение: и до него уже падала", D)
combo(Q.мин_на_8 <= 60, "падение: резкое (8% за ≤60 мин)", D)
combo(Q.от_пика >= -0.5, "падение: цена на минимуме", D)
combo(Q.от_пика < -3, "падение: цена уже отскочила >3% от минимума", D)
combo(Q.объём1ч > 8, "падение: объём часа >8×", D)
print("\n★ = тейк ≥85% устойчиво в обеих половинах; ✗ = стоп ≥25% устойчиво")
