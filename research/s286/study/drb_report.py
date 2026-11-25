"""s286 — сводка по экспирациям Deribit (изучение): размер OI на экспирации по типам и периодам (s157/expiries.json)
и насколько OI на экспирации «заглядывает вперёд» (deribit_late.py → /home/user/mc_data/s286/drb_late.csv).
Доходы, сходимость цены к страйкам и расстояние цены расчёта до max pain НЕ считаются (это проверка пиннинга, s287+). Запуск: python3 -I drb_report.py → drb_report.txt."""
import json

import numpy as np
import pandas as pd

OUT = "/home/user/mc_data/s286"
PER = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
       ("2024–2026", "2024-10-01", "2026-10-19")]


def per_of(t):
    for p, a, b in PER:
        if a <= t[:10] < b:
            return p
    return None


def main():
    lines = []
    ex = pd.DataFrame(json.load(open("/home/user/mc_data/s157/expiries.json")))
    ex["per"] = ex.t.map(per_of)
    ex = ex[ex.per.notna()]
    g = ex.groupby(["cur", "type", "per"]).agg(n=("exp", "size"), oi_med_bn=("notional", lambda x: np.median(x) / 1e9),
                                               oi_sum_bn=("notional", lambda x: x.sum() / 1e9),
                                               pc_oi=("put_call_oi", "median"))
    lines.append("OI на экспирации (млрд $, по записям расчёта Deribit; экспирации по 18.11.2026):")
    lines.append(g.round(3).to_string())
    try:
        d = pd.read_csv(f"{OUT}/drb_late.csv")
    except FileNotFoundError:
        d = None
    if d is not None and len(d):
        d["per"] = d.t.map(per_of)
        d = d[d.per.notna()]
        for c in ("mp", "mp_minus24", "mp_plus24", "mp_minus8", "mp_plus8"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d["same24"] = (d.mp == d.mp_minus24) & (d.mp == d.mp_plus24)
        d["same8"] = (d.mp == d.mp_minus8) & (d.mp == d.mp_plus8)
        d["dmp24"] = np.maximum((d.mp_minus24 - d.mp).abs(), (d.mp_plus24 - d.mp).abs()) / d.S
        d["dmp8"] = np.maximum((d.mp_minus8 - d.mp).abs(), (d.mp_plus8 - d.mp).abs()) / d.S
        d["share_near"] = d.v24_near5 / d.oi_near5
        h = d.groupby(["cur", "type", "per"]).agg(n=("exp", "size"), v24_oi=("share24", "median"),
                                                  v8_oi=("share8", "median"), v24_oi_near5=("share_near", "median"),
                                                  mp_same24=("same24", "mean"), mp_same8=("same8", "mean"),
                                                  dmp24_med=("dmp24", "median"), dmp24_p90=("dmp24", lambda x: x.quantile(.9)),
                                                  dmp8_med=("dmp8", "median"))
        lines.append("\nОбъём сделок по истекающим опционам за 24 / 8 ч до 08:00 UTC к OI на экспирации; max pain при OI ∓ объём:")
        lines.append(h.round(3).to_string())
    txt = "\n".join(lines)
    open(f"{OUT}/drb_report.txt", "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
