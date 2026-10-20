"""Validation rules. Each rule returns a reason string or None."""
import re

SEX = {"M", "F", "O", "U"}
CLASSES = {"I", "O", "E"}
SUPPORTED = {"ADT^A01", "ADT^A08", "ORU^R01"}
DATE = re.compile(r"^\d{8}$")
STAMP = re.compile(r"^\d{14}$")
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def validate(msg):
    errors = []
    msh = msg.seg("MSH")
    if msh is None or not msg.control_id:
        return ["MSH-10 message control id is missing"]
    mtype = msg.message_type.split("&")[0]
    if mtype not in SUPPORTED:
        return [f"message type {mtype or 'empty'} is not supported"]
    if not STAMP.match(msh.get(7) or ""):
        errors.append("MSH-7 timestamp must be 14 digits")
    pid = msg.seg("PID")
    if pid is None:
        return errors + ["PID segment is missing"]
    if not pid.get(3, 1):
        errors.append("PID-3 patient identifier is missing")
    if not pid.get(5, 1):
        errors.append("PID-5 family name is missing")
    dob = pid.get(7)
    if not DATE.match(dob or ""):
        errors.append("PID-7 birth date must be YYYYMMDD")
    elif not (1 <= int(dob[4:6]) <= 12 and 1 <= int(dob[6:8]) <= 31):
        errors.append("PID-7 birth date is not a real date")
    if pid.get(8) not in SEX:
        errors.append(f"PID-8 sex code '{pid.get(8)}' is not in M, F, O, U")
    if mtype.startswith("ADT"):
        pv1 = msg.seg("PV1")
        if pv1 is None:
            errors.append("PV1 segment is missing")
        else:
            if pv1.get(2) not in CLASSES:
                errors.append(f"PV1-2 patient class '{pv1.get(2)}' is not in I, O, E")
            if not pv1.get(19):
                errors.append("PV1-19 visit number is missing")
    if mtype == "ORU^R01":
        obx = msg.all("OBX")
        if not obx:
            errors.append("ORU needs at least one OBX")
        for o in obx:
            if o.get(2) == "NM" and not NUMBER.match(o.get(5) or ""):
                errors.append(f"OBX-{o.get(1)} value '{o.get(5)}' is not a number")
            if not o.get(3, 1):
                errors.append(f"OBX-{o.get(1)} observation code is missing")
    return errors
