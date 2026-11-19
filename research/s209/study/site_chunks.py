#!/usr/bin/env python3
"""s209: скачать JS-бандлы страницы сайта биржи и выписать из них адреса API.

Запуск: python3 site_chunks.py <имя> <папка-источник с html/js> <базовый URL чанков> <регэксп имени чанка>
  Читает все файлы папки-источника (и уже скачанные чанки), находит имена чанков по регэкспу,
  докачивает недостающие в /home/user/mc_data/s209/web/<имя>/ (пауза 0,3 с, UA research-script/1.0),
  повторяет, пока появляются новые имена (чанки ссылаются друг на друга), и пишет
  /home/user/mc_data/s209/web/<имя>/paths.txt — все строки вида /v1/..., /api/..., https://...
"""
import os, re, sys, time, urllib.request

UA = "research-script/1.0"


def main():
    name, src, base, rx = sys.argv[1:5]
    out = f"/home/user/mc_data/s209/web/{name}"
    os.makedirs(out, exist_ok=True)
    pat = re.compile(rx)
    done = set(os.listdir(out))
    seen = set()
    rounds = 0
    while True:
        rounds += 1
        texts = []
        for d in (src, out):
            for f in os.listdir(d):
                p = os.path.join(d, f)
                if os.path.isfile(p) and (f.endswith(".js") or f.endswith(".html") or f.endswith(".mjs")):
                    texts.append(open(p, encoding="utf-8", errors="replace").read())
        names = set()
        for t in texts:
            names.update(pat.findall(t))
        new = sorted(n for n in names if n not in done and n not in seen)
        print("круг", rounds, "имён", len(names), "новых", len(new), flush=True)
        if not new:
            break
        for n in new:
            seen.add(n)
            u = base.rstrip("/") + "/" + n
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    b = r.read()
                open(os.path.join(out, n), "wb").write(b)
                done.add(n)
            except Exception as e:
                print("ошибка", n, e, flush=True)
            time.sleep(0.3)
    # адреса API
    paths = set()
    rxp = re.compile(r"""[`"'](/(?:api|v\d|quote|public|priapi|bapi|fapi|sapi|x-api|v5|v3|v2|v1)[A-Za-z0-9_/${}.\-?=&]*)[`"']""")
    rxh = re.compile(r"https://[A-Za-z0-9.\-]+(?:/[A-Za-z0-9_/${}.\-]*)?")
    for d in (src, out):
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p) and (f.endswith(".js") or f.endswith(".html") or f.endswith(".mjs")):
                t = open(p, encoding="utf-8", errors="replace").read()
                paths.update(rxp.findall(t))
                paths.update(rxh.findall(t))
    with open(os.path.join(out, "paths.txt"), "w") as f:
        for x in sorted(paths):
            f.write(x + "\n")
    print("файлов", len(os.listdir(out)), "адресов", len(paths), flush=True)


if __name__ == "__main__":
    main()
