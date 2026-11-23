"""s259 — таблицы раздела 3 отчёта (markdown) из путей событий paths.py (/dev/shm/s259/paths.pkl). Цена перпа после события —
только для пампов по группам целиком (их продолжение известно из s256); для обвалов и разрезов — только механика.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/paths_md.py"""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import MID, TMP  # noqa: E402
from paths import EDGES, KS, SNAP0  # noqa: E402

HOURS = (-6, -1, 0, 1, 4, 24, 48)


def ix(k):
    return int(np.flatnonzero(KS == k)[0])


def rows_of(R, price):
    A = lambda key: np.array([r[key] for r in R], float)  # noqa: E731
    ib = ix(-2)
    c, p = A("c"), A("p")
    oi = A("oi") / A("oi")[:, [ib]] - 1
    out = []
    if price:
        out.append(("перп к −2 ч, медиана", np.expm1(np.log(c) - np.log(c[:, [ib]])), "pct1", np.nanmedian))
        out.append(("индекс к −2 ч, медиана", np.expm1((np.log(c) - np.log1p(p)) - (np.log(c[:, [ib]]) - np.log1p(p[:, [ib]]))), "pct1", np.nanmedian))
    out += [("премия p, среднее", p, "pct2", np.nanmean),
            ("фандинг r8 последнего начисления, среднее", A("f"), "pct3", np.nanmean),
            ("то же, медиана", A("f"), "pct3", np.nanmedian),
            ("оборот часа / обычный, медиана", A("q"), "x1", np.nanmedian),
            ("доля агрессивных покупок, медиана", A("tb"), "pct1u", np.nanmedian),
            ("OI в монетах к −2 ч, медиана", oi, "pct1", np.nanmedian),
            ("OI в монетах к −2 ч, среднее (±90%)", np.clip(oi, -0.9, 0.9), "pct1", np.nanmean),
            ("Δ лонг/шорт всех счетов", A("acc") - A("acc")[:, [ib]], "f2", np.nanmedian),
            ("Δ лонг/шорт топ-счетов", A("topa") - A("topa")[:, [ib]], "f2", np.nanmedian),
            ("Δ лонг/шорт топ-позиций", A("topp") - A("topp")[:, [ib]], "f2", np.nanmedian)]
    return out


def fmt(v, kind):
    if not np.isfinite(v):
        return "—"
    return {"pct1": f"{v:+.1%}", "pct1u": f"{v:.1%}", "pct2": f"{v:+.2%}", "pct3": f"{v:+.3%}", "x1": f"{v:.1f}",
            "f2": f"{v:+.2f}"}[kind].replace(".", ",").replace("-", "−")


def table(R, title, price):
    n_oi = sum(np.isfinite(r["oi"][ix(0)]) and np.isfinite(r["oi"][ix(-2)]) for r in R)
    print(f"\n**{title}** — событий {len(R)}, с метриками позиций {n_oi}\n")
    print("| час относительно свечи события | " + " | ".join(f"{h:+d}".replace("-", "−") for h in HOURS) + " |")
    print("|---|" + "---:|" * len(HOURS))
    for nm, X, kind, stat in rows_of(R, price):
        vals = [stat(X[:, ix(h)]) if np.isfinite(X[:, ix(h)]).sum() >= 5 else np.nan for h in HOURS]
        print(f"| {nm} | " + " | ".join(fmt(v, kind) for v in vals) + " |")
    oi = np.array([r["oi"][ix(0)] / r["oi"][ix(-2)] - 1 if r["oi"][ix(-2)] > 0 else np.nan for r in R])
    oi24 = np.array([r["oi"][ix(24)] / r["oi"][ix(0)] - 1 if r["oi"][ix(0)] > 0 else np.nan for r in R])
    acc = np.array([r["acc"][ix(0)] - r["acc"][ix(-2)] for r in R])
    m = np.isfinite(oi)
    if m.sum() >= 10:
        m2 = np.isfinite(oi24)
        print(f"\nЗа само событие (−2 ч → 0): OI вырос ≥ 10% у {(oi[m] >= 0.10).mean():.0%}, упал ≤ −5% у {(oi[m] <= -0.05).mean():.0%}; "
              f"лонг/шорт всех счетов снизился у {(acc[m] < 0).mean():.0%}. За сутки после (0 → +24 ч) OI вырос у {(oi24[m2] > 0).mean():.0%}, "
              f"на 20% и больше — у {(oi24[m2] >= 0.2).mean():.0%}.".replace(".", ",", 0))


def main():
    R = pickle.load(open(f"{TMP}/paths.pkl", "rb"))
    cut = lambda f: [r for r in R if f(r)]  # noqa: E731
    table(cut(lambda r: r["kind"] == "pump" and r["ns"]), "Пампы, без спота", True)
    table(cut(lambda r: r["kind"] == "pump" and not r["ns"]), "Пампы, со спотом", True)
    table(cut(lambda r: r["kind"] == "pump" and r["ns"] and np.searchsorted(EDGES, r["to7"]) == 4), "Пампы, без спота, оборот > 41,5 млн $/сут", False)
    table(cut(lambda r: r["kind"] == "pump" and not r["ns"] and np.searchsorted(EDGES, r["to7"]) == 4), "Пампы, со спотом, оборот > 41,5 млн $/сут", False)
    late = lambda r: r["kind"] == "pump" and r["ns"] and r["snap"] and r["t"] >= SNAP0  # noqa: E731
    table(cut(lambda r: late(r) and r["self"] > 0), "Пампы без спота 07–10.2026, сам перп в индексе", False)
    table(cut(lambda r: late(r) and r["self"] == 0), "Пампы без спота 07–10.2026, перпа в индексе нет", False)
    table(cut(lambda r: r["kind"] == "dump" and r["ns"]), "Обвалы, без спота", False)
    table(cut(lambda r: r["kind"] == "dump" and not r["ns"]), "Обвалы, со спотом", False)
    table(cut(lambda r: r["kind"] == "pump" and r["ns"] and r["t"] < MID), "Пампы, без спота, 1-я половина", False)
    table(cut(lambda r: r["kind"] == "pump" and r["ns"] and r["t"] >= MID), "Пампы, без спота, 2-я половина", False)


if __name__ == "__main__":
    main()
