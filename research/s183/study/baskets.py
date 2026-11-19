"""s183 — недельные корзины шорта (до 5 монет на понедельник 00:00 UTC) по кандидатным признакам: частота, оборот
корзины (доля замен неделя к неделе), число разных монет, концентрация, пересечение с входами журналов (вход в неделю
сделки [d0; d0 + 7 сут) и за неделю до среза) и пересечение корзин между собой. Доходы, цены после среза и плацебо
не считаются.

Запуск: python3 -I baskets.py   Итог: /home/user/mc_data/s183/baskets.pkl"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from coverage import load  # noqa: E402

N = 5
# (имя, признак, направление: +1 — шорт наибольших, −1 — шорт наименьших, условие отбора или None)
SIG = [
    ("Корея: доля", "kshare7", +1, None),
    ("Корея: доля сверх нормы", "kabn", +1, None),
    ("Корея: аном. оборот", "kabto", +1, None),
    ("Корея: аном. оборот (ст.)", "ksabto", +1, None),
    ("Binance: аном. оборот (ст.)", "sabto", +1, None),
    ("Binance: аном. оборот", "abto", +1, None),
    ("OI: рост 7 сут", "oi_g7", +1, None),
    ("OI: падение 7 сут", "oi_g7", -1, None),
    ("OI / капитализация", "oi_mc", +1, None),
    ("OI / оборот", "oi_qv", +1, None),
    ("оборот / капитализация", "turn7", +1, None),
    ("доля спота", "sshare7", +1, None),
    ("MAX 28 сут", "max28", +1, None),
    ("бета 28 сут", "beta28", +1, None),
    ("нижняя бета", "dbeta28", +1, None),
    ("IVOL 28 сут", "ivol28", +1, None),
    ("CGO: убыток держателей", "cgo60", -1, None),
    ("CGO: прибыль держателей", "cgo60", +1, None),
    ("базис-моментум", "bmom28", +1, None),
    ("премия перпа", "prem7", +1, None),
    ("фандинг растёт", "df", +1, None),
    ("лонги счетов", "lsr_acc", +1, None),
    ("аутсайдеры 2–4 нед.", "r28s", -1, None),
]
JN = ["🔝", "👀", "⏰", "🛒", "🇰🇷", "🇰🇷🆕", "🔑⁺", "🐋"]


def baskets(X, feat, sgn, cond):
    out = {}
    for d0, g in X.groupby("d0"):
        g = g[g[feat].notna() & np.isfinite(g[feat])]
        if not len(g):
            continue                                   # признака на срезе нет (OI до 12.2021) — неделя не в счёт
        if cond is not None:
            g = g[cond(g)]
        if not len(g):
            out[d0] = []
            continue
        g = g.sort_values(feat, ascending=(sgn < 0))
        out[d0] = list(g.s.head(N))
    return out


def stats(B, J, per, mons, X=None):
    weeks = sorted(B)
    # ex-ante характеристики корзины (по прошлым данным): бета к индексу альтов, остаточный риск за неделю, фандинг 7 сут
    be, sig, fu = [], [], []
    if X is not None:
        Xi = X.set_index(["d0", "s"])
        for w in weeks:
            if len(B[w]) < N:
                continue
            z = Xi.loc[[(w, s) for s in B[w]]]
            be.append(z.beta28.mean())
            iv = z.ivol28.dropna()
            if len(iv):
                sig.append(np.sqrt((iv ** 2).mean() / len(iv)) * np.sqrt(7))
            fu.append(z.f7.mean())
    names = [len(B[w]) for w in weeks]
    full = sum(1 for n in names if n >= N)
    turn = []
    for a, b in zip(weeks[:-1], weeks[1:]):
        if len(B[a]) >= N and len(B[b]) >= N:
            turn.append(1 - len(set(B[a]) & set(B[b])) / N)
    allc = [s for w in weeks for s in B[w]]
    vc = pd.Series(allc).value_counts()
    top3 = vc.head(3).sum() / max(len(allc), 1)
    ov_now, ov_prev = {j: 0 for j in JN}, {j: 0 for j in JN}
    any_now = any_prev = 0
    Jg = {s: g for s, g in J.groupby("s")}
    for w in weeks:
        for s in B[w]:
            g = Jg.get(s)
            hit_now = hit_prev = False
            if g is not None:
                for j in JN:
                    t = g.t[g.j == j].values
                    if ((t >= w) & (t < w + 7 * C.DAY)).any():
                        ov_now[j] += 1; hit_now = True
                    if ((t >= w - 7 * C.DAY) & (t < w)).any():
                        ov_prev[j] += 1; hit_prev = True
            any_now += hit_now; any_prev += hit_prev
    n = max(len(allc), 1)
    sw = np.nanmedian(sig) if sig else np.nan
    wk = len(weeks)                                   # все срезы, где признак есть (пустая корзина — ноль сделок)
    return dict(per=per, weeks=wk, full=full / max(wk, 1), per_month=len(allc) / max(wk * 7 / 30.4, 1e-9),
                beta=np.nanmedian(be) if be else np.nan, sig_w=sw, f7=np.nanmedian(fu) if fu else np.nan,
                mde=3 * sw / np.sqrt(max(full, 1)),
                turnover=np.mean(turn) if turn else np.nan, coins=len(vc), top3=top3,
                top_coins=", ".join(f"{k}:{v}" for k, v in vc.head(4).items()),
                any_now=any_now / n, any_prev=any_prev / n,
                **{f"now_{j}": ov_now[j] / n for j in JN}, **{f"prev_{j}": ov_prev[j] / n for j in JN})


def main():
    rows, allB = [], {}
    for per in C.PERS:
        X = load(per)
        X = X[X.liq5.astype(bool)].replace([np.inf, -np.inf], np.nan)
        J = C.journals(per)
        mons = C.months(per)
        print(f"\n=== {per}: срезов {X.d0.nunique()}, месяцев {mons:.1f}; входов журналов: "
              + ", ".join(f"{j} {int((J.j == j).sum())}" for j in JN if (J.j == j).any()), flush=True)
        print(f"  {'корзина':30s} {'сделок/мес':>10s} {'полных нед.':>11s} {'замен':>6s} {'монет':>6s} {'топ-3':>6s} "
              f"{'журнал в неделю':>15s} {'журнал до среза':>15s} {'бета':>5s} {'σ нед.':>6s} {'f7':>7s} {'MDE':>6s}  частые монеты")
        for name, f, sgn, cond in SIG:
            if f not in X.columns or X[f].notna().sum() == 0:
                continue
            B = baskets(X, f, sgn, cond)
            allB[(per, name)] = B
            st = stats(B, J, per, mons, X)
            st["name"] = name
            rows.append(st)
            print(f"  {name:30s} {st['per_month']:10.1f} {st['full']:11.0%} {st['turnover']:6.0%} {st['coins']:6d} "
                  f"{st['top3']:6.0%} {st['any_now']:15.0%} {st['any_prev']:15.0%} {st['beta']:5.2f} {st['sig_w']:6.1%} "
                  f"{st['f7']:+7.3%} {st['mde']:6.2%}  {st['top_coins']}")
        # пересечение корзин между собой: среднее число общих монет на срез (из 5)
        names = [n for n, *_ in SIG if (per, n) in allB]
        key = ["Корея: доля", "Корея: доля сверх нормы", "Корея: аном. оборот", "Binance: аном. оборот (ст.)",
               "OI: рост 7 сут", "OI: падение 7 сут", "OI / капитализация", "оборот / капитализация", "доля спота",
               "MAX 28 сут", "бета 28 сут", "IVOL 28 сут", "CGO: убыток держателей"]
        key = [k for k in key if k in names]
        print("  общих монет в корзинах (из 5, среднее по срезам, где обе полны):")
        for i, a in enumerate(key):
            line = []
            for b in key[i + 1:]:
                A, Bb = allB[(per, a)], allB[(per, b)]
                v = [len(set(A[w]) & set(Bb[w])) for w in A if len(A[w]) >= N and len(Bb.get(w, [])) >= N]
                if v and np.mean(v) >= 0.5:
                    line.append(f"{b} {np.mean(v):.1f}")
            if line:
                print(f"    {a}: " + "; ".join(line))
        # доля входов журналов, у которых монета на срезе перед входом была в корзине (обратное пересечение)
        print("  доля входов журнала, чья монета была в корзине на ближайшем прошлом срезе:")
        for name in ["Корея: доля", "Корея: доля сверх нормы", "Корея: аном. оборот", "OI: рост 7 сут", "OI: падение 7 сут",
                     "доля спота", "MAX 28 сут"]:
            if (per, name) not in allB:
                continue
            B = allB[(per, name)]
            ws = np.array(sorted(B))
            parts = []
            for j in JN:
                Jj = J[(J.j == j) & (J.t >= ws[0]) & (J.t < ws[-1] + 7 * C.DAY)]
                if not len(Jj):
                    continue
                k = np.searchsorted(ws, Jj.t.values, "right") - 1
                hit = [s in B[ws[i]] for s, i in zip(Jj.s, k)]
                parts.append(f"{j} {np.mean(hit):.0%}")
            print(f"    {name:28s} " + "; ".join(parts))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{C.OUT}/baskets.pkl")
    pd.to_pickle(allB, f"{C.OUT}/baskets_sets.pkl")


if __name__ == "__main__":
    main()
