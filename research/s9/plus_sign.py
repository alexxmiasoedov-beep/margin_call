"""Как часто в постах MarginData колонка CHNG записана со знаком «+» — такие строки шаблон ROW бота (правила 1 и 2) не разбирает;
ROW_ALL (журнал ↩️) исправлен 22.10.2026."""
import sys, json, datetime, re, os
from collections import defaultdict
sys.path.insert(0, os.environ.get("BOT_DIR", "bot"))   # папка bot репозитория: BOT_DIR=…/margin_call/bot
os.environ.setdefault("STATE_FILE", "/tmp/rp_fid_state.json")
import scanner
FIX = re.compile(r"^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)\s+([+-]?[\d.]+)\s*$")
raw = {}
for fn in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl"):
    for ln in open(fn):
        x = json.loads(ln)
        if len(x) >= 3 and isinstance(x[2], str) and "B/R" in x[2][:80]: raw[x[0]] = (x[1], x[2])
M = defaultdict(lambda: [0, 0, 0, 0])       # строк с 5 колонками, из них с «+», разбирает ROW, разбирает ROW с «+»
for pid, (ts, txt) in raw.items():
    m = ts[:7]
    for l in txt.splitlines()[1:]:
        p = l.split()
        if len(p) != 5 or not re.match(r"^[A-Z0-9]+$", p[0]): continue
        M[m][0] += 1; M[m][1] += p[4].startswith("+")
        M[m][2] += bool(scanner.ROW.match(l.strip())); M[m][3] += bool(FIX.match(l.strip()))
print("месяц   строк  с «+»  ROW читает  ROW с «+» читал бы")
for m in sorted(M):
    a = M[m]
    if a[0]: print(f"{m} {a[0]:7d} {a[1] / a[0]:6.1%} {a[2] / a[0]:9.1%} {a[3] / a[0]:9.1%}")
last = max(raw.values())[0]; print("последний пост в архиве:", last)
