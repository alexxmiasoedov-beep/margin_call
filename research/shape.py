"""Форма графика за сутки до сигнала (15м свечи) и ход после: структура vs исход при 6/20/48."""
import json, glob, os, bisect
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 240)

MARGIN, LEV, FEE = 1.0, 10, 0.0005
GAP, MIN_RUN, PMIN, PMAX, BR_MIN, TP, SL, HB = 1800, 4.0, 8, 17, 5, 6, 20, 48 * 4
SW = 3.0   # порог зигзага, %

df = pd.read_csv("dataset.csv", usecols=["sym", "epoch", "br"]).sort_values(["sym", "epoch"])
df["gap"] = df.groupby("sym").epoch.diff(); df["run_id"] = ((df.gap.isna()) | (df.gap > GAP)).groupby(df.sym).cumsum()
df["run_h"] = (df.epoch - df.groupby(["sym", "run_id"]).epoch.transform("min")) / 3600; df = df[df.run_h >= MIN_RUN]
K = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]; k = np.array(json.load(open(fn))["k"], dtype=float)
    if len(k) < 300 or k[:, 4].std() / k[:, 4].mean() < 0.002: continue
    K[s] = (k[:, 0].astype(int), k[:, 1], k[:, 2], k[:, 3], k[:, 4])
df = df[df.sym.isin(K)].sort_values("epoch")


def zigzag(c, th):
    """Число разворотов (свингов) на закрытиях с порогом th %."""
    n = 0; dir_ = 0; ext = c[0]
    for x in c[1:]:
        if dir_ == 0:
            if (x / ext - 1) * 100 >= th: dir_ = 1; ext = x
            elif (ext / x - 1) * 100 >= th: dir_ = -1; ext = x
        elif dir_ == 1:
            if x > ext: ext = x
            elif (ext / x - 1) * 100 >= th: n += 1; dir_ = -1; ext = x
        else:
            if x < ext: ext = x
            elif (x / ext - 1) * 100 >= th: n += 1; dir_ = 1; ext = x
    return n


rows = []; last = {}; open_until = {}; last_stop = {}
for r in df.itertuples():
    t, o, h, l, c = K[r.sym]; i = bisect.bisect_right(t, r.epoch) - 1
    if i < 200 or i + HB + 1 >= len(t): continue
    p = o[i]; b4h = (p / c[i - 16] - 1) * 100
    rule = "1" if PMIN <= b4h <= PMAX else ("2" if -PMAX <= b4h <= -PMIN and r.br >= BR_MIN else None)
    if not rule: continue
    if r.sym in last and r.epoch - last[r.sym] < 86400: continue
    if r.sym in open_until and open_until[r.sym] > r.epoch: continue
    last[r.sym] = r.epoch
    end = i + HB; res = None
    for j in range(i, end + 1):
        if h[j] >= p * (1 + SL / 100): res, kind, hrs = -SL / 10, "стоп", (j - i) / 4; break
        if l[j] <= p * (1 - TP / 100): res, kind, hrs = TP / 10, "тейк", (j - i) / 4; break
    if res is None: res, kind, hrs = -(c[end] / p - 1) * 10, "время", (end - i) / 4
    res -= MARGIN * LEV * FEE * 2
    if r.sym in last_stop and r.epoch - last_stop[r.sym] < 48 * 3600: continue
    open_until[r.sym] = r.epoch + hrs * 3600
    if kind == "стоп": last_stop[r.sym] = r.epoch + hrs * 3600
    # работаем с графиком "в направлении сигнала": для падений цена переворачивается (1/цена), тогда слив выглядит как памп
    if rule == "1":
        hh, ll, cc, pp = h, l, c, p
    else:
        hh, ll, cc, pp = 1 / l, 1 / h, 1 / c, 1 / p
    H = hh[i - 96:i]; L = ll[i - 96:i]; C = cc[i - 96:i]
    ext_idx = int(H.argmax()); hrs_since_ext = (96 - ext_idx) / 4
    prior = H[:-16]; prior_ext = prior.max(); prior_idx = int(prior.argmax())
    vs_prior = (pp / prior_ext - 1) * 100                                  # >0 — перехай прежнего экстремума
    pull = (L[prior_idx:-16].min() / prior_ext - 1) * 100 if prior_idx < 80 else 0.0
    move_prior = (prior_ext / C[0] - 1) * 100                              # рост от начала суток до прежнего экстремума
    swings = zigzag(C, SW)
    rng24 = (H.max() / L.min() - 1) * 100
    pos24 = (pp - L.min()) / max(H.max() - L.min(), 1e-12)
    A = ll[i:end + 1]; B = hh[i:end + 1]
    mfe = (1 - A.min() / pp) * 100                                         # макс. ход в нашу сторону, %
    mae = (B.max() / pp - 1) * 100                                         # макс. ход против, %
    newhigh_after = B.max() > H.max()                                      # после сигнала цена ушла выше суточного экстремума, бывшего ДО сигнала
    if move_prior < 3:
        shape = "прямой памп" if rule == "1" else "прямой слив"
    elif vs_prior > 0.5:
        shape = "рост→откат→ПЕРЕХАЙ" if rule == "1" else "слив→отскок→новое дно"
    elif vs_prior >= -3:
        shape = "рост→откат→двойная вершина" if rule == "1" else "слив→отскок→двойное дно"
    else:
        shape = "рост→откат→нижний хай" if rule == "1" else "слив→отскок→выше дна"
    rows.append(dict(sym=r.sym, epoch=r.epoch, rule=rule, исход=kind, pnl=res, часов=hrs, форма=shape, vs_prior=vs_prior, откат=pull, до_пампа=move_prior,
                     свингов=swings, диап24=rng24, поз24=pos24, часов_от_экстр=hrs_since_ext, mfe=mfe, mae=mae, перехай_после=newhigh_after))
D = pd.DataFrame(rows); D["тейк"] = (D.исход == "тейк").astype(int); D["стоп"] = (D.исход == "стоп").astype(int); mid = D.epoch.median()
D.to_csv("shape.csv", index=False)
print(f"сделок {len(D)}")


def table(d, col, title):
    g = d.groupby(col, observed=True).agg(n=("pnl", "size"), тейк=("тейк", "mean"), стоп=("стоп", "mean"), pnl=("pnl", "mean"), сумма=("pnl", "sum"),
                                          ход_за=("mfe", "median"), до8=("mfe", lambda x: (x >= 8).mean()), до10=("mfe", lambda x: (x >= 10).mean()),
                                          против=("mae", "median"), перехай=("перехай_после", "mean"))
    g = g.assign(тейк=lambda x: (x.тейк * 100).round(0), стоп=lambda x: (x.стоп * 100).round(0), pnl=lambda x: x.pnl.round(2), сумма=lambda x: x.сумма.round(1),
                 ход_за=lambda x: x.ход_за.round(1), до8=lambda x: (x.до8 * 100).round(0), до10=lambda x: (x.до10 * 100).round(0), против=lambda x: x.против.round(1), перехай=lambda x: (x.перехай * 100).round(0))
    print(f"\n-- {title} --\n  ход_за = медиана макс. хода в нашу сторону за 48ч, %; до8/до10 = доля сделок, где ход дошёл до 8/10%; против = медиана макс. хода против; перехай = доля, где после сигнала цена ушла выше суточного экстремума до сигнала")
    print("  " + g.to_string().replace("\n", "\n  "))


for rule, name in (("1", "ПРАВИЛО 1 — ПАМПЫ"), ("2", "ПРАВИЛО 2 — ПАДЕНИЯ")):
    d = D[D.rule == rule].copy()
    print(f"\n==================== {name}, n={len(d)} ====================")
    table(d, "форма", "форма суток до сигнала")
    d["b_откат"] = pd.cut(d.откат, [-99, -15, -8, -4, 0.01], labels=["откат >15%", "8–15%", "4–8%", "<4%"])
    table(d[d.до_пампа >= 3], "b_откат", "глубина отката между прежним экстремумом и последним заходом (только формы с прежним экстремумом)")
    d["b_св"] = pd.cut(d.свингов, [-1, 1, 3, 5, 99], labels=["0–1 (тренд)", "2–3", "4–5", "6+ (пила)"])
    table(d, "b_св", f"число разворотов ≥{SW:g}% за сутки")
    d["b_поз"] = pd.cut(d.поз24, [-0.01, 0.5, 0.8, 0.95, 1.01], labels=["ниже середины", "50–80%", "80–95%", "у экстремума"])
    table(d, "b_поз", "положение цены сигнала в суточном диапазоне (1 = на экстремуме суток в сторону сигнала)")
    d["b_экс"] = pd.cut(d.часов_от_экстр, [-0.1, 0.5, 2, 6, 12, 24], labels=["сейчас", "0,5–2 ч", "2–6 ч", "6–12 ч", "12–24 ч"])
    table(d, "b_экс", "сколько часов назад был экстремум суток")

print("\n==================== ЧТО ПРОИСХОДИТ ПОСЛЕ ТЕЙКА 6% ====================")
for rule in ("1", "2"):
    x = D[(D.rule == rule) & (D.тейк == 1)]
    print(f"правило {rule}: тейков {len(x)}; ход дошёл до 8% в {(x.mfe>=8).mean()*100:.0f}%, до 10% в {(x.mfe>=10).mean()*100:.0f}%, до 15% в {(x.mfe>=15).mean()*100:.0f}%; "
          f"потом перехай суточного экстремума в {(x.перехай_после).mean()*100:.0f}%, медиана хода против {x.mae.median():.1f}%")
print("\n== устойчивость форм по половинам (тейк%/стоп%) ==")
for rule in ("1", "2"):
    for shp, g in D[D.rule == rule].groupby("форма"):
        a = g[g.epoch < mid]; b = g[g.epoch >= mid]
        print(f"  правило {rule} {shp:32s} n={len(g):3d} тейк {g.тейк.mean()*100:3.0f}% ({a.тейк.mean()*100:.0f}/{b.тейк.mean()*100:.0f}) стоп {g.стоп.mean()*100:3.0f}% ({a.стоп.mean()*100:.0f}/{b.стоп.mean()*100:.0f}) PnL/сд {g.pnl.mean():+.2f} ({a.pnl.sum():+.1f}/{b.pnl.sum():+.1f})")
