import json

import pytest

from bridge.fhir import to_fhir
from bridge.gen import DEFECTS, make
from bridge.hl7 import build_ack, mllp_unwrap, mllp_wrap, parse
from bridge.mllp import send, serve
from bridge.pipeline import Bridge
from bridge.validate import validate

ADT = ("MSH|^~\\&|HIS|HOSPITAL|BRIDGE|HOSPITAL|20260105101500||ADT^A01|C1|P|2.5\r"
       "EVN|A01|20260105101500\r"
       "PID|1||M1^^^HOSP^MR||Hansen^Anna||19800214|F\r"
       "PV1|1|I|WARD^12^A||||||||||||||||V9")
ORU = ("MSH|^~\\&|LAB|HOSPITAL|BRIDGE|HOSPITAL|20260105101500||ORU^R01|C2|P|2.5\r"
       "PID|1||M1^^^HOSP^MR||Hansen^Anna||19800214|F\r"
       "OBR|1|||PANEL^Blood panel|||20260105090000\r"
       "OBX|1|NM|2823-3^Potassium^LN||5.6|mmol/L|3.5-5.1|H|||F")


def test_msh_field_numbering():
    msg = parse(ADT)
    assert msg.seg("MSH").get(1) == "|"
    assert msg.seg("MSH").get(9) == "ADT^A01"
    assert msg.control_id == "C1"


def test_components_and_missing_fields():
    pid = parse(ADT).seg("PID")
    assert pid.get(3, 1) == "M1"
    assert pid.get(5, 2) == "Anna"
    assert pid.get(30) == ""


def test_ack_carries_control_id_and_code():
    ack = build_ack(parse(ADT), "AA", "ok")
    assert ack.split("\r")[1] == "MSA|AA|C1|ok"
    assert "ACK^A01" in ack


def test_mllp_roundtrip():
    assert mllp_unwrap(mllp_wrap(ADT)) == ADT


def test_valid_messages_pass():
    assert validate(parse(ADT)) == []
    assert validate(parse(ORU)) == []


@pytest.mark.parametrize("old,new,word", [
    ("M1^^^HOSP^MR", "^^^HOSP^MR", "PID-3"),
    ("19800214", "1980-13-45", "PID-7"),
    ("|F\r", "|X\r", "PID-8"),
    ("|I|WARD", "|Z|WARD", "PV1-2"),
    ("ADT^A01|C1", "ADT^A99|C1", "not supported"),
])
def test_each_defect_is_named(old, new, word):
    errors = validate(parse(ADT.replace(old, new, 1)))
    assert errors and word in errors[0]


def test_text_in_numeric_result_is_rejected():
    errors = validate(parse(ORU.replace("|5.6|", "|pending|")))
    assert any("not a number" in e for e in errors)


def test_adt_maps_to_patient_and_encounter():
    patient, enc = to_fhir(parse(ADT))
    assert patient["gender"] == "female" and patient["birthDate"] == "1980-02-14"
    assert patient["id"] == "pat-m1"
    assert enc["class"]["code"] == "IMP" and enc["subject"]["reference"] == "Patient/pat-m1"


def test_oru_maps_observation_with_range_and_flag():
    obs = to_fhir(parse(ORU))[1]
    assert obs["code"]["coding"][0]["system"] == "http://loinc.org"
    assert obs["valueQuantity"] == {"value": 5.6, "unit": "mmol/L"}
    assert obs["referenceRange"][0]["high"]["value"] == 5.1
    assert obs["interpretation"][0]["coding"][0]["code"] == "H"
    assert obs["effectiveDateTime"] == "2026-01-05T09:00:00Z"


def test_retry_is_acknowledged_but_not_processed_twice(tmp_path):
    b = Bridge(tmp_path)
    assert "MSA|AA|C1|ok" in b.handle(ADT)
    assert "duplicate ignored" in b.handle(ADT)
    assert b.stats["mapped"] == 1 and b.stats["duplicates"] == 1


def test_rejected_message_is_quarantined_with_reason(tmp_path):
    b = Bridge(tmp_path)
    ack = b.handle(ADT.replace("|F\r", "|X\r", 1))
    assert "MSA|AE|C1" in ack
    row = json.loads((tmp_path / "quarantine.jsonl").read_text().splitlines()[0])
    assert row["control_id"] == "C1" and "PID-8" in row["reasons"][0]


def test_garbage_does_not_crash(tmp_path):
    b = Bridge(tmp_path)
    assert "MSA|AR" in b.handle("hello")


def test_generator_plants_every_defect_kind():
    _, planted = make()
    assert set(planted.values()) == set(DEFECTS)


def test_all_planted_defects_are_caught_over_tcp(tmp_path):
    msgs, planted = make()
    b = Bridge(tmp_path)
    port, thread, stop = serve(b, expected=len(msgs))
    acks = send(msgs, port)
    thread.join(timeout=5)
    caught = {json.loads(x)["control_id"] for x in (tmp_path / "quarantine.jsonl").read_text().splitlines()}
    assert caught == set(planted)
    assert len(acks) == len(msgs)
    assert b.stats["received"] == b.stats["mapped"] + b.stats["duplicates"] + b.stats["rejected"]
