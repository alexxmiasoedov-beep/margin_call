"""s181 — адреса казначейств из DefiLlama-Adapters (registries/treasury.js и projects/treasury/*.js, снимок GitHub
19.11.2026, кэш /home/user/mc_data/s181/dla). Код адаптеров не исполняется: разбор текста. Берутся массивы owners,
ownTokenOwners (владельцы) и ownTokens (собственные токены) с привязкой к сети (ближайший внешний ключ «сеть: {»)
и к протоколу (ключ реестра «treasury/<имя>» или имя файла). Переменные (const X = [...]) и ADDRESSES.<сеть>.<токен>
разворачиваются. Итог — /home/user/mc_data/s181/dla_treasury.json."""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

ROOT = f"{C.OUT}/dla"
ADDR = re.compile(r"0x[0-9a-fA-F]{40}")
KEYS = ("ownTokenOwners", "ownTokens", "owners")
CORE = json.load(open(f"{ROOT}/projects/helper/coreAssets.json"))


def strip_comments(txt):
    out = []
    for line in txt.split("\n"):
        q, i, cut = None, 0, len(line)
        while i < len(line):
            ch = line[i]
            if q:
                if ch == "\\":
                    i += 2
                    continue
                if ch == q:
                    q = None
            elif ch in "'\"`":
                q = ch
            elif line.startswith("//", i):
                cut = i
                break
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


def grab(txt, i):
    """Значение с позиции i: массив [...] целиком или выражение до запятой/конца строки."""
    while i < len(txt) and txt[i] in " \t":
        i += 1
    if i < len(txt) and txt[i] == "[":
        depth, j = 0, i
        while j < len(txt):
            if txt[j] == "[":
                depth += 1
            elif txt[j] == "]":
                depth -= 1
                if depth == 0:
                    return txt[i:j + 1]
            j += 1
        return txt[i:]
    m = re.match(r"[^,\n}]+", txt[i:])
    return m.group(0) if m else ""


def consts(txt):
    """const ИМЯ = [...] | '0x…' на любом уровне."""
    out = {}
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*", txt):
        out[m.group(1)] = grab(txt, m.end())
    return out


def resolve(expr, cs, depth=0):
    addrs = set(a.lower() for a in ADDR.findall(expr))
    for m in re.finditer(r"ADDRESSES\.(\w+)\.(\w+)", expr):
        v = (CORE.get(m.group(1)) or {}).get(m.group(2))
        if isinstance(v, str) and ADDR.fullmatch(v):
            addrs.add(v.lower())
    if depth < 3:
        for name in re.findall(r"(?<![\w.$'\"])([A-Za-z_$][\w$]*)(?![\w$]*\s*:)", expr):
            if name in cs and name not in ("ADDRESSES", "nullAddress"):
                addrs |= resolve(cs[name], cs, depth + 1)
    return addrs


def chain_of(lines, k, indent):
    for j in range(k, -1, -1):
        m = re.match(r"^(\s*)['\"]?([A-Za-z0-9_\-]+)['\"]?\s*:\s*\{", lines[j])
        if m and len(m.group(1)) < indent:
            return m.group(2)
    return None


def parse(txt, proto_from_key):
    txt = strip_comments(txt)
    cs = consts(txt)
    lines = txt.split("\n")
    offs, o = [], 0
    for ln in lines:
        offs.append(o)
        o += len(ln) + 1
    res = {}
    proto = None
    for k, ln in enumerate(lines):
        if proto_from_key:
            m = re.match(r"^  ['\"]([^'\"]+)['\"]\s*:\s*\{", ln)
            if m:
                proto = m.group(1).replace("treasury/", "")
        else:
            proto = proto_from_key is False and None
        for key in KEYS:
            for m in re.finditer(r"(?<![\w$])" + key + r"\s*:", ln):
                val = grab(txt, offs[k] + m.end())
                addrs = resolve(val, cs)
                if not addrs:
                    continue
                indent = len(ln) - len(ln.lstrip())
                ch = chain_of(lines, k - 1, indent) or "?"
                rec = res.setdefault((proto, ch), {"owners": set(), "ownTokens": set()})
                rec["ownTokens" if key == "ownTokens" else "owners"] |= addrs
    return res


def main():
    out = []
    reg = open(f"{ROOT}/registries/treasury.js").read()
    reg = reg[reg.index("const configs"):]
    for (p, ch), v in parse(reg, True).items():
        out.append(dict(proto=p, chain=ch, src="registry", owners=sorted(v["owners"]), ownTokens=sorted(v["ownTokens"])))
    for f in sorted(glob.glob(f"{ROOT}/projects/treasury/*.js")):
        name = os.path.basename(f)[:-3]
        for (p, ch), v in parse(open(f).read(), False).items():
            out.append(dict(proto=name, chain=ch, src="file", owners=sorted(v["owners"]), ownTokens=sorted(v["ownTokens"])))
    json.dump(out, open(f"{C.OUT}/dla_treasury.json", "w"))
    own = {a for r in out for a in r["owners"]}
    eth = {a for r in out if r["chain"] == "ethereum" for a in r["owners"]}
    print(f"записей (протокол × сеть): {len(out)}; протоколов {len({r['proto'] for r in out})}; адресов-владельцев {len(own)}, "
          f"из них в сети ethereum {len(eth)}; записей с ownTokens {sum(1 for r in out if r['ownTokens'])}")
    chains = {}
    for r in out:
        chains[r["chain"]] = chains.get(r["chain"], 0) + len(r["owners"])
    print("адресов по сетям:", dict(sorted(chains.items(), key=lambda x: -x[1])[:15]))


if __name__ == "__main__":
    main()
