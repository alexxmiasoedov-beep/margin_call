"""s201: когда Santiment пересчитывал значения — computedAt у каждого дневного значения (includeComputedAt: true).
Задержка computedAt − день и даты массовых пересчётов: что в истории «как было», а что переписано позже.
Без вызовов API: читает кэш /home/user/mc_data/s201/daily/."""
import glob
import os

import pandas as pd

for f in sorted(glob.glob("/home/user/mc_data/s201/daily/*.pkl")):
    name = os.path.basename(f)[:-4]
    d = pd.read_pickle(f)
    if "computedAt" not in d or d.computedAt.isna().all():
        continue
    ca = pd.to_datetime(d.computedAt, utc=True, errors="coerce")
    lag = (ca - d.datetime).dt.total_seconds() / 86400
    rec = d.datetime >= pd.Timestamp("2026-09-01", tz="UTC")
    top = ca.dt.floor("D").value_counts().head(4)
    print(f"{name}: задержка, сут — медиана {lag.median():.1f} (с 09.2026: {lag[rec].median():.1f}); "
          f"пересчитано позже D+2: {(lag > 2).mean()*100:.0f}%, позже D+40: {(lag > 40).mean()*100:.0f}%; "
          f"крупнейшие даты пересчёта: " + ", ".join(f"{k.date()}:{v}" for k, v in top.items()))
