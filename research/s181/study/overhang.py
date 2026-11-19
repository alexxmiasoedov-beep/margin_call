"""s181 — «навес» казначейств: запас собственного токена у казначейств DefiLlama (treasury_events.series) к монетам
в обращении CMC и к суточному обороту (дней продажи при 10% оборота) на последнюю дату и в среднем за период;
снижение запаса за 90 сут (скорость продажи). Только запасы и размеры; доходы и цены после дат не считаются."""
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_events as TE  # noqa: E402

warnings.filterwarnings("ignore")


def main():
    S, _ = TE.series()
    rows = []
    for s in S:
        df = TE.daily(s)
        cf = TE.circ_frame(s["cmc"]) if s["cmc"] else None
        if cf is None or not len(cf):
            continue
        df = df.join(cf[["circ", "vol", "px"]], how="left")
        df["circ"] = df["circ"].where(df["circ"] > 0).ffill(limit=7)
        df["px"] = df["px"].ffill(limit=3)
        df["adv"] = df.vol.where(df.vol > 0).rolling(30, 5).median().ffill(limit=3)
        last = df.dropna(subset=["h", "circ"]).tail(1)
        if not len(last):
            continue
        r = last.iloc[0]
        h90 = df.h.shift(90).loc[last.index[0]] if len(df) > 90 else np.nan
        rows.append(dict(slug=s["slug"], sym=s["sym"], date=pd.Timestamp(int(last.index[0]) * 86400, unit="s").date(),
                         hc=r.h / r.circ, usd=r.h * r.px, days10=r.h * r.px / (0.1 * r.adv) if r.adv > 0 else np.nan,
                         d90=(r.h - h90) / r.circ if h90 == h90 else np.nan))
    X = pd.DataFrame(rows).sort_values("hc", ascending=False)
    X.to_pickle(f"{C.OUT}/overhang.pkl")
    pd.set_option("display.width", 200)
    print(f"казначейств с запасом и обращением: {len(X)}")
    print(f"  запас ≥ 10% обращения: {(X.hc >= 0.1).sum()}; ≥ 25%: {(X.hc >= 0.25).sum()}; медиана {X.hc.median():.1%}")
    print(f"  дней продажи всего запаса при 10% суточного оборота: медиана {X.days10.median():.0f}; ≥ 100 сут — "
          f"{(X.days10 >= 100).sum()}")
    print(f"  изменение запаса за 90 сут к обращению: медиана {X.d90.median():+.2%}; снизился ≥ 1% обращения — "
          f"{(X.d90 <= -0.01).sum()}")
    print(X.head(25).to_string(index=False, formatters={"hc": "{:.1%}".format, "usd": lambda v: f"{v / 1e6:,.1f} млн $",
                                                         "days10": "{:.0f}".format, "d90": "{:+.2%}".format}))


if __name__ == "__main__":
    main()
