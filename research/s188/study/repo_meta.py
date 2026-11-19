"""s188 — метаданные склонированных репозиториев (звёзды, лицензия, последний push) из каталога repos.ecosyste.ms
и дата последнего коммита из клона. Клоны — /home/user/mc_data/s188/repos/<владелец>__<имя> (код не копируется
в репозиторий margin_call). Итог — /home/user/mc_data/s188/repo_meta.json и печать в лог."""
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

R = "/home/user/mc_data/s188/repos"
UA = {"User-Agent": "research-script/1.0"}
FULL = {  # имя клона → владелец/репозиторий на GitHub (клоны со своим коротким именем)
    "CyberPunkMetalHead__gateio-announcements":
        "CyberPunkMetalHead/gateio-crypto-trading-bot-binance-announcements-new-coins",
    "Bayi-Hu__Pump-and-Dump-Detection": "Bayi-Hu/Pump-and-Dump-Detection-on-Cryptocurrency",
}
out = []
for d in sorted(os.listdir(R)):
    full = FULL.get(d, d.replace("__", "/", 1))
    try:
        last = subprocess.run(["git", "-C", f"{R}/{d}", "log", "-1", "--format=%cI"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:
        last = ""
    meta = {}
    url = "https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/" + urllib.parse.quote(full, safe="")
    for i in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                meta = json.loads(r.read().decode())
            break
        except Exception as e:
            print("  ошибка", full, e)
            time.sleep(5)
    row = dict(repo=full, clone=d, last_commit=last[:10], stars=meta.get("stargazers_count"),
               license=meta.get("license"), pushed=(meta.get("pushed_at") or "")[:10],
               archived=meta.get("archived"), desc=(meta.get("description") or "")[:150])
    out.append(row)
    print(f"{row['repo']:<70} ★{row['stars']}  {row['license']}  последний коммит {row['last_commit']}"
          f"  {'(архив)' if row['archived'] else ''}")
    time.sleep(1.5)
json.dump(out, open("/home/user/mc_data/s188/repo_meta.json", "w"), ensure_ascii=False, indent=1)
