"""Поиск признаков стоповых сигналов. Цель — стоп при 6/20 (48 ч), каждая сделка отдельно.
Честность: поиск порогов только на первых 60% по времени (train), проверка на последних 40% (test)."""
import sys, itertools, warnings
import numpy as np, pandas as pd
from scipy.stats import mannwhitneyu
warnings.filterwarnings("ignore")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
import os
a = pd.read_csv("features.csv")
b = pd.read_csv("features_ext.csv") if os.path.exists("features_ext.csv") else pd.DataFrame({"sym": a.sym, "ep": a.ep})
d = a.merge(b, on=["sym", "ep"], how="left").sort_values("ep").reset_index(drop=True)
for c in ("spot_qv24_musd", "upbit_qv24_musd", "spot_ch_4h", "g_oi_musd"):
    if c not in d: d[c] = np.nan
d["spot_to_perp_qv"] = d.spot_qv24_musd / d.qv24_musd; d["upbit_to_perp_qv"] = d.upbit_qv24_musd / d.qv24_musd
d["spot_vs_perp_4h"] = d.spot_ch_4h - d.ch_4h if "spot_ch_4h" in d else np.nan
d["oi_to_qv24_g"] = d.g_oi_musd / d.qv24_musd
d["ch_1h_share"] = d.ch_1h / d.ch_4h; d["ch_15m_share"] = d.ch_15m / d.ch_4h
EXCL = {"sym", "ep", "rule", "y_kind", "y_stop", "y_pnl", "y_hours", "y_up20_48h", "y_maxup48", "y_pnl_notp25", "price_usd"}
FEATS = [c for c in d.columns if c not in EXCL and d[c].dtype != object and d[c].notna().mean() > 0.3 and d[c].nunique() > 2]
cut = d.ep.quantile(0.6); d["part"] = np.where(d.ep < cut, "train", "test")
print(f"сигналов {len(d)}; стопов {d.y_stop.sum()} ({d.y_stop.mean()*100:.0f}%); train до {pd.to_datetime(cut, unit='s'):%d.%m}; признаков {len(FEATS)}")
for r in "12": x = d[d.rule == int(r)] if d.rule.dtype != object else d[d.rule == r]; print(f"  правило {r}: {len(x)} сигналов, стопов {x.y_stop.mean()*100:.0f}%, итог {x.y_pnl.sum():+.1f}, на сделку {x.y_pnl.mean():+.3f}")
d["rule"] = d.rule.astype(str)

def auc(x, y):
    m = x.notna(); x, y = x[m], y[m]
    if y.sum() < 5 or (1 - y).sum() < 5: return np.nan, np.nan
    u, p = mannwhitneyu(x[y == 1], x[y == 0]); return u / (y.sum() * (1 - y).sum()), p

def univariate(sub, label):
    rows = []
    for f in FEATS:
        A, p = auc(sub[f], sub.y_stop)
        if np.isnan(A): continue
        A1, _ = auc(sub[sub.part == "train"][f], sub[sub.part == "train"].y_stop); A2, _ = auc(sub[sub.part == "test"][f], sub[sub.part == "test"].y_stop)
        rows.append((f, A, p, A1, A2, sub[f].notna().sum()))
    u = pd.DataFrame(rows, columns=["признак", "AUC", "p", "AUC_train", "AUC_test", "n"])
    u = u.sort_values("p"); m = len(u); u["q_FDR"] = (u.p * m / (np.arange(m) + 1))[::-1].cummin()[::-1].clip(upper=1)
    u["стабилен"] = np.sign(u.AUC_train - 0.5) == np.sign(u.AUC_test - 0.5)
    print(f"\n==== {label}: связь признаков со стопом (AUC 0,5 = нет связи; >0,5 — больше значение → чаще стоп) ====")
    print(u.head(30).round(3).to_string(index=False))
    return u

def quint(sub, f, k=5):
    x = sub[[f, "y_stop", "y_pnl"]].dropna()
    x["q"] = pd.qcut(x[f], k, duplicates="drop")
    return x.groupby("q", observed=True).agg(n=("y_stop", "size"), стоп=("y_stop", lambda v: v.mean() * 100), на_сделку=("y_pnl", "mean")).round(2)

def filters(sub, label, feats, pairs=True):
    tr, te = sub[sub.part == "train"], sub[sub.part == "test"]
    base_tr, base_te = tr.y_pnl.sum(), te.y_pnl.sum(); res = []
    for f in feats:
        qs = tr[f].quantile([.1, .2, .3, .7, .8, .9]).values
        for q in qs:
            for side in (">", "<"):
                bad_tr = (tr[f] > q) if side == ">" else (tr[f] < q)
                if bad_tr.sum() < 8: continue
                gain = -tr[bad_tr].y_pnl.sum()
                bad_te = (te[f] > q) if side == ">" else (te[f] < q)
                res.append((f"{f} {side} {q:.4g}", gain, bad_tr.sum(), tr[bad_tr].y_stop.mean() * 100, -te[bad_te].y_pnl.sum(), bad_te.sum(), te[bad_te].y_stop.mean() * 100 if bad_te.sum() else np.nan))
    r = pd.DataFrame(res, columns=["исключить, если", "выигрыш_train", "отсеяно_train", "стопов_среди_отсеянных_train%", "выигрыш_test", "отсеяно_test", "стопов_test%"])
    best = r.sort_values("выигрыш_train", ascending=False).drop_duplicates(subset=["исключить, если"]).groupby(r["исключить, если"].str.split().str[0]).head(1).head(25)
    print(f"\n==== {label}: лучшие одиночные фильтры (подобраны на train, проверены на test). База train {base_tr:+.1f}, test {base_te:+.1f} ====")
    print(best.round(2).to_string(index=False))
    print(f"Из топ-25 фильтров на test в плюсе: {(best.выигрыш_test > 0).sum()}; сумма выигрыша на test {best.выигрыш_test.sum():+.1f}")
    return best

def models(sub, label):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import roc_auc_score
    sub = sub.copy(); sub["m"] = pd.to_datetime(sub.ep, unit="s").dt.to_period("M")
    months = sorted(sub.m.unique()); preds = {}
    for name, mk in (("бустинг", lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=20, l2_regularization=1.0)),
                     ("логрегрессия", lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.05, max_iter=2000)))):
        p = pd.Series(np.nan, index=sub.index)
        for i in range(2, len(months)):                    # walk-forward: учимся на всех прошлых месяцах, предсказываем следующий
            trm = sub.m < months[i]; tsm = sub.m == months[i]
            if sub[trm].y_stop.sum() < 10 or not tsm.any(): continue
            mdl = mk(); mdl.fit(sub.loc[trm, FEATS], sub.loc[trm, "y_stop"]); p[tsm] = mdl.predict_proba(sub.loc[tsm, FEATS])[:, 1]
        preds[name] = p
        ok = p.notna(); y = sub.loc[ok, "y_stop"]; pn = sub.loc[ok, "y_pnl"]
        out = [f"{name}: вне выборки {ok.sum()} сигналов, AUC {roc_auc_score(y, p[ok]):.3f}; итог без фильтра {pn.sum():+.1f}"]
        for share in (0.1, 0.2, 0.3):
            thr = p[ok].quantile(1 - share); keep = p[ok] < thr
            out.append(f"отсеять {share*100:.0f}% самых рискованных → итог {pn[keep].sum():+.1f} (отсеяно стопов {y[~keep].sum()} из {y.sum()}, тейков среди отсеянных {(sub.loc[ok & (p >= thr), 'y_kind'] == 'тейк').sum()})")
        print(f"\n==== {label}: " + "\n     ".join(out))
    return preds

if __name__ == "__main__":
    for label, sub in (("ОБА ПРАВИЛА", d), ("ПРАВИЛО 1 (памп)", d[d.rule == "1"]), ("ПРАВИЛО 2 (слив)", d[d.rule == "2"])):
        u = univariate(sub, label)
        top = u[(u.стабилен)].head(6).признак.tolist()
        for f in top[:4]: print(f"\n{label} — {f} по квинтилям:\n{quint(sub, f).to_string()}")
        filters(sub, label, u.head(40).признак.tolist())
        models(sub, label)
