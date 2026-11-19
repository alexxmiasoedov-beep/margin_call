"""s201: дневные ряды метрик Santiment для вселенной перпов (основной slug + варианты сетей), окно без ключа
2025-11-20 … 2026-10-19 (последний полный день перед restrictedTo 2026-10-20 19:01 UTC), с computedAt.

Запуск: python3 fetch_daily.py metric1,metric2 [кусок] [extra_selector]
Итог: /home/user/mc_data/s201/daily/<метрика>[__<метка>].pkl — длинная таблица datetime, slug, value, computedAt."""
import json
import os
import sys

import pandas as pd

import san

D = san.D
FROM, TO = "2025-11-20T00:00:00Z", "2026-10-19T23:59:59Z"
os.makedirs(f"{D}/daily", exist_ok=True)
G = pd.read_csv(f"{D}/map.csv")
V = pd.read_csv(f"{D}/map_variants.csv")
UNI = sorted(set(G.slug) | set(V.slug))
META = json.load(open(f"{D}/meta.json"))
SAME = {  # метрики с тем же набором монет, что у уже известной (по документации Santiment)
    "social_volume": "social_volume_total", "social_dominance": "social_volume_total", "sentiment": "social_volume_total",
    "unique_social": "social_volume_total", "dormant_circulation": "dormant_circulation_365d", "mvrv": "mvrv_usd",
    "whale_transaction": "whale_transaction_count_100k_usd_to_inf", "deposit_transactions": "active_deposits",
    "active_withdrawals": "active_deposits", "exchange_": "exchange_inflow", "age_": "age_consumed",
    "labelled_historical_balance": "labelled_historical_balance", "marketcap_usd": None, "price_usd": None,
    "transaction_volume": "age_consumed", "network_growth": "network_growth", "daily_active": "daily_active_addresses",
    "trending_words_rank": "social_volume_total", "mean_dollar_invested_age": "mvrv_usd", "mean_age": "mvrv_usd",
}


def slugs_for(metric):
    if metric in META:
        av = set(META[metric]["availableSlugs"] or [])
        return [s for s in UNI if s in av]
    for pre, ref in SAME.items():
        if metric.startswith(pre):
            if ref is None:
                return list(UNI)
            av = set(META[ref]["availableSlugs"] or [])
            return [s for s in UNI if s in av]
    raise SystemExit(f"неизвестен набор монет для {metric}: сначала metadata (coverage.py {metric})")


def fetch(metric, chunk=260, extra="", label="", computed_at=True, interval="1d", frm=FROM, to=TO):
    sl = slugs_for(metric)
    parts = []
    for i in range(0, len(sl), chunk):
        js, q = san.per_slug(metric, sl[i:i + chunk], frm, to, interval, tag="daily" if interval == "1d" else interval,
                             extra_selector=extra, computed_at=computed_at)
        if js.get("errors"):
            print(f"{metric}: ошибка {js['errors'][0].get('message')}")
            continue
        parts.append(san.per_slug_frame(js))
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    name = metric + (f"__{label}" if label else "") + ("" if interval == "1d" else f"__{interval}")
    df.to_pickle(f"{D}/daily/{name}.pkl")
    nn = df.dropna(subset=["value"]) if len(df) else df
    print(f"{name}: slug запрошено {len(sl)}, строк {len(df)}, непустых {len(nn)}, slug с данными "
          f"{nn.slug.nunique() if len(nn) else 0}, дни {df.datetime.min() if len(df) else ''} … {df.datetime.max() if len(df) else ''}")
    return df


if __name__ == "__main__":
    mets = sys.argv[1].split(",")
    chunk = int(sys.argv[2]) if len(sys.argv) > 2 else 260
    extra = sys.argv[3] if len(sys.argv) > 3 else ""
    label = sys.argv[4] if len(sys.argv) > 4 else ""
    for m in mets:
        fetch(m, chunk, extra, label)
