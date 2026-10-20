import json
import sys
import tempfile
from pathlib import Path

from .gen import make
from .mllp import send, serve
from .pipeline import Bridge


def demo(outdir):
    msgs, planted = make()
    bridge = Bridge(outdir)
    port, thread, stop = serve(bridge, expected=len(msgs))
    acks = send(msgs, port)
    thread.join(timeout=5)
    codes = {}
    for a in acks:
        code = a.split("\r")[1].split("|")[1]
        codes[code] = codes.get(code, 0) + 1
    quarantined = [json.loads(line) for line in Path(outdir, "quarantine.jsonl").read_text().splitlines()]
    found = {q["control_id"] for q in quarantined}
    print(f"messages sent over MLLP: {len(msgs)}")
    print(f"ACK codes: {codes}")
    print(f"stats: {bridge.stats}")
    print(f"planted defects: {len(planted)}, caught: {len(found & set(planted))}, missed: {len(set(planted) - found)}")
    return bridge.stats


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    out = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()
    if cmd == "demo":
        demo(out)
    else:
        print("usage: python -m bridge demo [outdir]")
