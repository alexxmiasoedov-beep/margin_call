"""s297 — изучение: минутная структура корейских скачков вокруг входов ⏰ и 🇰🇷 (данные — collect.py, s297/min.pkl).

Только признаки до входа и общий путь цены после входа без разбиения по признакам — доходы сделок по признакам
здесь не считаются (их считает следующая проверка после записи гипотез).
Окно до входа W: ⏰ — 60 мин (00:00–01:00 UTC), 🇰🇷 — 120 мин (памп ≤ 2 ч). Минутная сетка [te − 160, te + 240);
цены Upbit и Bithumb без сделок в минуте — последняя известная.
Признаки события (по площадкам up — Upbit, bt — Bithumb, bn — перп Binance):
  ret — ход за окно; t50 — минута, когда пройдена половина хода (от начала окна); lead = t50(Корея) − t50(перп);
  xc±1 — корреляция минутных доходов Кореи и перпа со сдвигом на минуту; pk — минута максимума до входа (от te);
  fade — насколько цена в te ниже максимума окна; vb10 — доля оборота окна Upbit в первые 10 мин; vl15 — в последние
  15 мин; prem — изменение отношения цены Upbit к перпу за окно (курс за 6 ч почти не меняется).
Общий путь после входа (среднее по всем событиям, без разбиения): ход за 15, 30, 60, 120, 240 мин и оборот Кореи
в первый час после входа к часу до входа. Запуск: python3 -I research/s297/study.py → s297/feat.pkl, s297/study.txt"""
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s297"
LO, HI = 160, 240
W = {"⏰": 60, "🇰🇷": 120}


def grid(a, te, col):
    """Значения столбца col (1 o, 2 h, 3 l, 4 c, 5 оборот) на минутной сетке [te − LO, te + HI); NaN — нет свечи."""
    out = np.full(LO + HI, np.nan)
    if a is None or not len(a):
        return out
    k = ((a[:, 0] - (te - LO * 60)) // 60).astype(int)
    ok = (k >= 0) & (k < LO + HI)
    out[k[ok]] = a[ok, col]
    return out


def ffill(x):
    x = x.copy()
    last = np.nan
    for i in range(len(x)):
        if np.isfinite(x[i]):
            last = x[i]
        else:
            x[i] = last
    return x


def feats(j, o, te):
    w = W[j]
    i0, i1 = LO - w, LO                       # окно до входа: минуты [te − w, te)
    r = {}
    C = {}
    for v in ("up", "bt", "bn"):
        a = o.get(v)
        c = ffill(grid(a, te, 4)); h = grid(a, te, 2); q = grid(a, te, 5)
        C[v] = c
        if not np.isfinite(c[i0 - 1]) or not np.isfinite(c[i1 - 1]):
            continue
        base, end = c[i0 - 1], c[i1 - 1]
        r[f"{v}_ret"] = end / base - 1
        path = c[i0:i1] / base - 1
        if r[f"{v}_ret"] > 0:
            r[f"{v}_t50"] = float(np.argmax(path >= r[f"{v}_ret"] / 2))
        hh = np.nanmax(np.where(np.isfinite(h[i0:i1]), h[i0:i1], c[i0:i1]))
        r[f"{v}_pk"] = float(np.nanargmax(np.where(np.isfinite(h[i0:i1]), h[i0:i1], c[i0:i1])) - w)
        r[f"{v}_fade"] = end / hh - 1
        for k in (15, 30, 60, 120, 240):
            if np.isfinite(c[i1 - 1 + k]):
                r[f"{v}_p{k}"] = np.log(c[i1 - 1 + k] / end)
        if v != "bn":
            qq = np.nan_to_num(q[i0:i1])
            if qq.sum() > 0:
                r[f"{v}_vb10"] = qq[:10].sum() / qq.sum()
                r[f"{v}_vl15"] = qq[-15:].sum() / qq.sum()
                post = np.nan_to_num(q[i1:i1 + 60]).sum()
                r[f"{v}_vpost"] = post / np.nan_to_num(q[i1 - 60:i1]).sum() if np.nan_to_num(q[i1 - 60:i1]).sum() > 0 else np.nan
    # Корея — Upbit, иначе Bithumb
    kr = "up" if "up_ret" in r else ("bt" if "bt_ret" in r else None)
    r["kr"] = kr
    if kr and "bn_ret" in r:
        if f"{kr}_t50" in r and "bn_t50" in r:
            r["lead"] = r[f"{kr}_t50"] - r["bn_t50"]
        ck, cb = C[kr], C["bn"]
        lk, lb = np.diff(np.log(ck[i0 - 1:i1])), np.diff(np.log(cb[i0 - 1:i1]))
        ok = np.isfinite(lk) & np.isfinite(lb)
        if ok.sum() >= 20:
            lk, lb = lk[ok], lb[ok]
            r["xc0"] = np.corrcoef(lk, lb)[0, 1]
            r["xc_kr_first"] = np.corrcoef(lk[:-1], lb[1:])[0, 1]     # Корея сейчас ↔ перп через минуту
            r["xc_bn_first"] = np.corrcoef(lb[:-1], lk[1:])[0, 1]     # перп сейчас ↔ Корея через минуту
        pr = ck / cb
        if np.isfinite(pr[i0 - 1]) and np.isfinite(pr[i1 - 1]):
            r["prem"] = pr[i1 - 1] / pr[i0 - 1] - 1
    return r


def q(x, ps=(0.1, 0.5, 0.9)):
    x = pd.Series(x).dropna()
    return "n/a" if not len(x) else " / ".join(f"{v:+.3g}" for v in x.quantile(ps))


def main():
    R = pickle.load(open(f"{OUT}/min.pkl", "rb"))
    rows = []
    for (j, per, s, te), o in R.items():
        if "err" in o:
            continue
        d = feats(j, o, te)
        d.update(j=j, per=per, s=s, te=te)
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/feat.pkl")
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    P("s297 — минутная структура корейских скачков (10-й / 50-й / 90-й перцентили)")
    for j in ("⏰", "🇰🇷"):
        for per in ("2020–2022", "2022–2024", "2024–2026"):
            Y = X[(X.j == j) & (X.per == per)]
            kr = Y.kr.notna()
            P(); P(f"== {j} {per}: событий {len(Y)}, с Кореей {kr.sum()} (Upbit {Y.up_ret.notna().sum()}, Bithumb {Y.bt_ret.notna().sum()}) ==")
            P(f"  ход за окно: перп {q(Y.bn_ret)}; Upbit {q(Y.up_ret)}; Bithumb {q(Y.bt_ret)}")
            P(f"  половина хода, мин от начала окна: перп {q(Y.bn_t50)}; Upbit {q(Y.up_t50)}")
            ld = Y.lead.dropna()
            P(f"  lead = t50 Кореи − t50 перпа, мин: {q(ld)}; Корея раньше ≥ 2 мин {(ld <= -2).mean():.0%}, перп раньше ≥ 2 мин "
              f"{(ld >= 2).mean():.0%}, одновременно {((ld > -2) & (ld < 2)).mean():.0%}")
            P(f"  корреляция минутных доходов: одновременно {Y.xc0.median():+.2f}; Корея → перп через минуту "
              f"{Y.xc_kr_first.median():+.2f}; перп → Корея через минуту {Y.xc_bn_first.median():+.2f}")
            P(f"  максимум до входа, мин от te: перп {q(Y.bn_pk)}; Upbit {q(Y.up_pk)}; доля событий с максимумом перпа "
              f"в последние 5 мин {(Y.bn_pk >= -5).mean():.0%}")
            P(f"  цена в te ниже максимума окна: перп {q(Y.bn_fade)}; Upbit {q(Y.up_fade)}")
            P(f"  доля оборота Upbit: первые 10 мин {q(Y.up_vb10)}; последние 15 мин {q(Y.up_vl15)}")
            P(f"  отношение Upbit к перпу за окно: {q(Y.prem)}")
            P(f"  путь после входа (среднее ln, все события): " + "; ".join(
                f"{k} мин перп {Y[f'bn_p{k}'].mean():+.2%} / Upbit {Y[f'up_p{k}'].mean():+.2%}" for k in (15, 60, 240)))
            P(f"  оборот Upbit в час после входа к часу до входа: {q(Y.up_vpost)}")
    open(f"{OUT}/study.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
