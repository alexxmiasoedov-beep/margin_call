#!/bin/bash
# s227: перебор s216/bombe.py по CYBER — весь период (A до 2025, B 2025, C 2026) и эпоха канала (A' до 10.2025, B' до 04.2026)
cd /home/user/mc_data
B=/home/user/margin_call/research/s216/bombe.py
for era in main chan; do
  if [ $era = main ]; then export PFX=s227 TA=2025-01-01 TB=2026-01-01; else export PFX=s227c TA=2025-10-01 TB=2026-04-01; fi
  export MINN=150 ZB=2 SPARSE=1
  for c in y_l1 y_s1 y_l4 y_s4 y_l24 y_s24 y_l72 y_s72; do
    python3 $B $c 2>&1 | grep -v Warning
    for sd in 0 1 2; do python3 $B $c shuffle $sd > /dev/null 2>&1; done
  done
done
echo ГОТОВО
