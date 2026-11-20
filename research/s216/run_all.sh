#!/bin/sh
# s216 — все прогоны перебора: 8 исходов × (основной + 3 перемешанных), по 4 процесса. Запуск из /home/user/mc_data.
R=$(dirname "$0")
for o in s4 s24 s48 s168 l4 l24 l48 l168; do
  echo "$o"; for k in 0 1 2; do echo "$o shuffle $k"; done
done | xargs -P 4 -I{} sh -c "python3 $R/bombe.py {} > s216_log_\$(echo {} | tr ' ' '_').txt 2>&1"
