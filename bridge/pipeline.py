"""Receive HL7, validate, map to FHIR, write files. Idempotent on MSH-10; bad messages are quarantined with a reason."""
import json
import sqlite3
from pathlib import Path

from .fhir import to_fhir
from .hl7 import Hl7Error, build_ack, parse
from .validate import validate


class Bridge:
    def __init__(self, outdir, db=":memory:"):
        self.out = Path(outdir)
        (self.out / "fhir").mkdir(parents=True, exist_ok=True)
        self.q = self.out / "quarantine.jsonl"
        self.db = sqlite3.connect(db, check_same_thread=False)
        self.db.execute("create table if not exists seen (control_id text primary key, outcome text)")
        self.stats = dict(received=0, mapped=0, duplicates=0, rejected=0, resources=0)

    def handle(self, raw):
        """Process one message and return the ACK text."""
        self.stats["received"] += 1
        try:
            msg = parse(raw)
        except Hl7Error as exc:
            self.stats["rejected"] += 1
            self._quarantine("", raw, [str(exc)])
            return "MSH|^~\\&|BRIDGE|HOSPITAL|||20260101000000||ACK|ACKNONE|P|2.5\rMSA|AR||" + str(exc)
        cid = msg.control_id
        if cid and self.db.execute("select 1 from seen where control_id=?", (cid,)).fetchone():
            self.stats["duplicates"] += 1
            return build_ack(msg, "AA", "duplicate ignored")
        errors = validate(msg)
        if errors:
            self.stats["rejected"] += 1
            if cid:
                self.db.execute("insert or ignore into seen values (?, 'rejected')", (cid,))
                self.db.commit()
            self._quarantine(cid, raw, errors)
            return build_ack(msg, "AE", "; ".join(errors)[:200])
        resources = to_fhir(msg)
        for r in resources:
            path = self.out / "fhir" / f"{r['resourceType']}-{r['id']}.json"
            path.write_text(json.dumps(r, indent=2, sort_keys=True))
        self.db.execute("insert into seen values (?, 'mapped')", (cid,))
        self.db.commit()
        self.stats["mapped"] += 1
        self.stats["resources"] += len(resources)
        return build_ack(msg, "AA", "ok")

    def _quarantine(self, cid, raw, reasons):
        with self.q.open("a") as fh:
            fh.write(json.dumps(dict(control_id=cid, reasons=reasons, raw=raw.replace("\r", "\n"))) + "\n")
