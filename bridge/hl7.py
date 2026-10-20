"""Minimal HL7 v2 parser, ACK builder and MLLP framing. Standard library only."""
from dataclasses import dataclass

SB = b"\x0b"
EB_CR = b"\x1c\x0d"


class Hl7Error(ValueError):
    pass


@dataclass
class Segment:
    name: str
    parts: list

    def get(self, n, comp=None):
        """Field n (HL7 numbering). MSH-1 is the field separator itself."""
        if self.name == "MSH":
            if n == 1:
                return "|"
            idx = n - 1
        else:
            idx = n
        if idx >= len(self.parts):
            return ""
        value = self.parts[idx].split("~")[0]
        if comp is None:
            return value
        pieces = value.split("^")
        return pieces[comp - 1] if comp - 1 < len(pieces) else ""


class Message:
    def __init__(self, segments):
        self.segments = segments

    def seg(self, name):
        for s in self.segments:
            if s.name == name:
                return s
        return None

    def all(self, name):
        return [s for s in self.segments if s.name == name]

    @property
    def control_id(self):
        msh = self.seg("MSH")
        return msh.get(10) if msh else ""

    @property
    def message_type(self):
        msh = self.seg("MSH")
        return msh.get(9) if msh else ""


def parse(raw):
    text = raw.replace("\r\n", "\r").replace("\n", "\r").strip("\r")
    if not text.startswith("MSH|"):
        raise Hl7Error("message does not start with MSH")
    segments = []
    for line in text.split("\r"):
        if not line:
            continue
        parts = line.split("|")
        segments.append(Segment(parts[0], parts))
    return Message(segments)


def unescape(value):
    return (value.replace("\\F\\", "|").replace("\\S\\", "^").replace("\\T\\", "&")
            .replace("\\R\\", "~").replace("\\E\\", "\\"))


def build_ack(msg, code, text, timestamp="20260101000000"):
    msh = msg.seg("MSH")
    trig = msg.message_type.split("^")[1] if "^" in msg.message_type else ""
    sending_app = msh.get(3) if msh else ""
    sending_fac = msh.get(4) if msh else ""
    header = f"MSH|^~\\&|BRIDGE|HOSPITAL|{sending_app}|{sending_fac}|{timestamp}||ACK^{trig}|ACK{msg.control_id}|P|2.5"
    return header + "\r" + f"MSA|{code}|{msg.control_id}|{text}"


def mllp_wrap(text):
    return SB + text.encode("utf-8") + EB_CR


def mllp_unwrap(data):
    if not data.startswith(SB) or not data.endswith(EB_CR):
        raise Hl7Error("bad MLLP framing")
    return data[1:-2].decode("utf-8")
