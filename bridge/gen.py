"""Deterministic synthetic HL7 v2 traffic. No real patient data. Some messages carry planted defects."""
import random

FAMILY = ["Hansen", "Nielsen", "Jensen", "Larsen", "Pedersen", "Sorensen", "Rasmussen", "Madsen", "Kristensen", "Olsen"]
GIVEN = ["Anna", "Mads", "Sofie", "Jonas", "Emma", "Lars", "Maja", "Peter", "Ida", "Niels"]
TESTS = [
    ("2823-3", "Potassium", "mmol/L", 3.5, 5.1),
    ("2345-7", "Glucose", "mmol/L", 4.0, 7.8),
    ("718-7", "Hemoglobin", "g/dL", 12.0, 17.5),
]
DEFECTS = ["no_mrn", "bad_dob", "bad_sex", "text_value", "bad_type", "no_visit", "bad_class"]


def stamp(rng, base=20260101):
    return f"{base + rng.randint(0, 27)}{rng.randint(6, 20):02d}{rng.randint(0, 59):02d}{rng.randint(0, 59):02d}"


def make(seed=7, patients=40, bad=12):
    """Return (messages, planted) where planted maps control id to the defect."""
    rng = random.Random(seed)
    people = []
    for i in range(patients):
        people.append(dict(mrn=f"M{100000 + i}", family=rng.choice(FAMILY), given=rng.choice(GIVEN),
                           dob=f"{rng.randint(1940, 2015)}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}",
                           sex=rng.choice(["M", "F"]), visit=f"V{500000 + i}"))
    msgs, planted, n = [], {}, 0

    def header(kind, cid):
        return f"MSH|^~\\&|HIS|HOSPITAL|BRIDGE|HOSPITAL|{stamp(rng)}||{kind}|{cid}|P|2.5"

    def adt(p, kind, cid, defect=None):
        mrn, dob, sex, visit, cls = p["mrn"], p["dob"], p["sex"], p["visit"], rng.choice(["I", "O", "E"])
        if defect == "no_mrn": mrn = ""
        if defect == "bad_dob": dob = "1980-13-45"
        if defect == "bad_sex": sex = "X"
        if defect == "no_visit": visit = ""
        if defect == "bad_class": cls = "Z"
        return "\r".join([header(kind, cid), f"EVN|{kind.split('^')[1]}|{stamp(rng)}",
                          f"PID|1||{mrn}^^^HOSP^MR||{p['family']}^{p['given']}||{dob}|{sex}",
                          f"PV1|1|{cls}|WARD^{rng.randint(1, 40)}^A||||||||||||||||{visit}"])

    def oru(p, cid, defect=None):
        lines = [header("ORU^R01", cid), f"PID|1||{p['mrn']}^^^HOSP^MR||{p['family']}^{p['given']}||{p['dob']}|{p['sex']}",
                 f"OBR|1|||PANEL^Blood panel|||{stamp(rng)}"]
        for i, (code, name, unit, lo, hi) in enumerate(TESTS, 1):
            val = round(rng.uniform(lo - 0.6, hi + 0.8), 1)
            flag = "L" if val < lo else "H" if val > hi else "N"
            shown = "pending" if defect == "text_value" and i == 1 else val
            lines.append(f"OBX|{i}|NM|{code}^{name}^LN||{shown}|{unit}|{lo}-{hi}|{flag}|||F")
        return "\r".join(lines)

    for p in people:
        n += 1
        msgs.append(adt(p, "ADT^A01", f"C{n:05d}"))
        n += 1
        msgs.append(oru(p, f"C{n:05d}"))
    for k in range(bad):
        defect = DEFECTS[k % len(DEFECTS)]
        p = rng.choice(people)
        n += 1
        cid = f"C{n:05d}"
        if defect == "text_value": msgs.append(oru(p, cid, defect))
        elif defect == "bad_type": msgs.append(adt(p, "ADT^A99", cid))
        else: msgs.append(adt(p, "ADT^A08", cid, defect))
        planted[cid] = defect
    retries = rng.sample(msgs[:80], 6)
    msgs = msgs + retries
    rng.shuffle(msgs)
    return msgs, planted
