CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
def polymod(values):
    GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk
def hrp_expand(hrp): return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]
def decode(addr):
    hrp, data = addr.rsplit("1", 1)
    d = [CHARSET.find(c) for c in data]
    assert polymod(hrp_expand(hrp) + d) == 1, "bad checksum"
    return hrp, d[:-6]
def encode(hrp, data):
    values = hrp_expand(hrp) + data
    pm = polymod(values + [0] * 6) ^ 1
    chk = [(pm >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[d] for d in data + chk)
def convert(addr, hrp):
    return encode(hrp, decode(addr)[1])
if __name__ == "__main__":
    import sys
    for a in ["cosmos15v50ymp6n5dn73erkqtmq0u8adpl8d3ujv2e74", "cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9", "cosmos1l0znsvddllw9knha3yx2svnlxny676d8ns7uys", "cosmos1p3ucd3ptpw902fluyjzhq3ffgq4ntddac9sa3s"]:
        print(a, [convert(a, h) for h in ("celestia", "dydx", "osmo", "saga", "bbn", "terra", "band", "fetch", "allo", "axelar")])
