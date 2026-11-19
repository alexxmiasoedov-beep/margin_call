"""s201: следующий ключ из меток Santiment — треть рывков баланса Binance (O4) складывается из наших же заводов поменьше
(каждый < 0,5% обращения). Проверяем на своём сборе s195 (переводы ≥ 0,05% обращения на адреса Binance от не-бирж,
10.2020–11.2026), сколько таких «дроблёных заводов» в месяц по трём периодам. Только частоты и описание, без доходов.

Событие «дробь за час»: сумма заводов монеты на Binance за скользящий час ≥ 0,5% обращения, ни один перевод не ≥ 0,5%,
у монеты не было ни 🐋-завода (≥ 0,5% одним переводом), ни такого события за 48 ч. Вариант «дробь за 24 ч» — то же
за скользящие сутки. Число разных отправителей в окне — один (режет сам) или несколько (толпа)."""
import numpy as np
import pandas as pd

X = pd.read_pickle("/home/user/mc_data/s195_deposits.pkl")
X = X[X.exch == "Binance"].sort_values("t").reset_index(drop=True)
PER = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17")}
print("заводов на Binance:", len(X), "монет:", X.perp.nunique())


def events(win_s):
    out = []
    for perp, g in X.groupby("perp"):
        t = g.t.values
        f = g.frac.values
        frm = g.frm.values
        last_ev = -1e18
        j0 = 0
        for i in range(len(t)):
            if f[i] >= 0.005:                         # 🐋-завод: блокирует 48 ч
                if t[i] - last_ev >= 48 * 3600:
                    out.append((perp, t[i], "single", f[i], 1))
                last_ev = t[i] if t[i] - last_ev >= 48 * 3600 else last_ev
                continue
            while t[j0] < t[i] - win_s:
                j0 += 1
            sl = slice(j0, i + 1)
            s = f[sl].sum()
            if s >= 0.005 and f[sl].max() < 0.005 and t[i] - last_ev >= 48 * 3600:
                out.append((perp, t[i], "split", s, len(set(frm[sl]))))
                last_ev = t[i]
    return pd.DataFrame(out, columns=["perp", "t", "kind", "frac", "senders"])


for label, win in (("за час", 3600), ("за 24 ч", 86400)):
    E = events(win)
    print(f"\nДробь {label}: всего событий {len(E)} (🐋-одиночных {int((E.kind == 'single').sum())}, "
          f"дроблёных {int((E.kind == 'split').sum())})")
    for per, (a, b) in PER.items():
        ta, tb = pd.Timestamp(a, tz="UTC").timestamp(), pd.Timestamp(b, tz="UTC").timestamp()
        e = E[(E.t >= ta) & (E.t < tb)]
        m = (tb - ta) / 86400 / 30.44
        sp = e[e.kind == "split"]
        print(f"  {per}: одиночных 🐋 {int((e.kind == 'single').sum())/m:.1f}/мес, дроблёных {len(sp)/m:.1f}/мес "
              f"(один отправитель {int((sp.senders == 1).sum())/m:.1f}, несколько {int((sp.senders > 1).sum())/m:.1f}); "
              f"медиана суммы дроби {sp.frac.median()*100:.2f}%")
    E.to_pickle(f"/home/user/mc_data/s201/split_{'1h' if win == 3600 else '24h'}.pkl")
