"""Map HL7 v2 messages to FHIR R4 resources (plain dicts). Timestamps are read as UTC."""
from .hl7 import unescape

GENDER = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
CLASS = {"I": ("IMP", "inpatient encounter"), "O": ("AMB", "ambulatory"), "E": ("EMER", "emergency")}
FLAG = {"N": "N", "H": "H", "L": "L", "HH": "HH", "LL": "LL"}
SYSTEMS = {"LN": "http://loinc.org"}


def iso_date(v):
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"


def iso_time(v):
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}T{v[8:10]}:{v[10:12]}:{v[12:14]}Z"


def patient_id(pid):
    return "pat-" + pid.get(3, 1).lower()


def patient(msg):
    pid = msg.seg("PID")
    res = {
        "resourceType": "Patient",
        "id": patient_id(pid),
        "identifier": [{"system": "urn:hospital:mrn", "value": pid.get(3, 1)}],
        "name": [{"family": unescape(pid.get(5, 1)), "given": [g for g in [unescape(pid.get(5, 2))] if g]}],
        "gender": GENDER[pid.get(8)],
        "birthDate": iso_date(pid.get(7)),
    }
    return res


def encounter(msg):
    pv1 = msg.seg("PV1")
    code, display = CLASS[pv1.get(2)]
    res = {
        "resourceType": "Encounter",
        "id": "enc-" + pv1.get(19).lower(),
        "status": "in-progress",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": code, "display": display},
        "subject": {"reference": "Patient/" + patient_id(msg.seg("PID"))},
        "location": [{"location": {"display": " ".join(p for p in [pv1.get(3, 1), pv1.get(3, 2), pv1.get(3, 3)] if p)}}],
    }
    return res


def observations(msg):
    out = []
    pid = msg.seg("PID")
    for o in msg.all("OBX"):
        code, display, system = o.get(3, 1), o.get(3, 2), o.get(3, 3)
        coding = {"code": code, "display": display}
        if system in SYSTEMS:
            coding["system"] = SYSTEMS[system]
        res = {
            "resourceType": "Observation",
            "id": f"obs-{msg.control_id.lower()}-{o.get(1)}",
            "status": "final" if o.get(11) == "F" else "preliminary",
            "code": {"coding": [coding]},
            "subject": {"reference": "Patient/" + patient_id(pid)},
            "valueQuantity": {"value": float(o.get(5)), "unit": o.get(6)},
        }
        obr = msg.seg("OBR")
        if obr is not None and obr.get(7):
            res["effectiveDateTime"] = iso_time(obr.get(7))
        rng = o.get(7)
        if "-" in rng:
            low, high = rng.split("-", 1)
            res["referenceRange"] = [{"low": {"value": float(low), "unit": o.get(6)}, "high": {"value": float(high), "unit": o.get(6)}}]
        if o.get(8) in FLAG:
            res["interpretation"] = [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": FLAG[o.get(8)]}]}]
        out.append(res)
    return out


def to_fhir(msg):
    mtype = msg.message_type.split("&")[0]
    res = [patient(msg)]
    if mtype.startswith("ADT"):
        res.append(encounter(msg))
    else:
        res.extend(observations(msg))
    return res
