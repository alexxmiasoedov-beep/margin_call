#!/bin/sh
# s288 — пересборка из сырья. Запуск из /home/user/mc_data: sh <repo>/research/s288/study/run_all.sh
# 1) выгрузка канала (≈ 90 мин, продолжает с места остановки) и архива Whale Alert (40 МБ):
#    python3 -I <study>/fetch_tg.py whale_alert_io /dev/shm/s288/raw_io 1.05
#    curl -s -A research-script/1.0 -o /dev/shm/s288/archive/whale-alerts-archive.json.gz https://whale-alert.io/whale-alerts-archive.json.gzip
# 2) разбор и опись (всё — только счёт и абсолютные величины):
S=$(dirname "$0")
set -e
python3 -I $S/perps.py
python3 -I $S/parse_archive.py /dev/shm/s288/archive/whale-alerts-archive.json.gz /dev/shm/s288/wa_archive
python3 -I -c "import pandas as pd; pd.read_pickle('/dev/shm/s288/wa_archive.pkl').to_pickle('s288/wa_archive.pkl.gz', compression='gzip')"
python3 -I $S/parse_tg.py /dev/shm/s288/raw_io whale_alert_io s288/wa_io
python3 -I $S/describe.py s288/wa_io > /dev/null
python3 -I $S/whale_match.py > /dev/null
python3 -I $S/altchains.py > /dev/null
python3 -I $S/labels_check.py > /dev/null
python3 -I $S/scale.py > /dev/null
python3 -I $S/hyp_freq.py > /dev/null
python3 -I $S/rpc_check.py > /dev/null
