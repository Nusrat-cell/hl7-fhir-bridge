"""Tiny MLLP server and client so the bridge can be exercised over a real TCP socket."""
import socket
import threading

from .hl7 import EB_CR, SB, mllp_unwrap, mllp_wrap


def read_frame(conn):
    data = b""
    while not data.endswith(EB_CR):
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def serve(bridge, host="127.0.0.1", port=0, expected=None):
    """Start a listener in a thread. Returns (port, thread, stop_event)."""
    srv = socket.socket()
    srv.bind((host, port))
    srv.listen(5)
    srv.settimeout(0.2)
    stop = threading.Event()

    def loop():
        count = 0
        while not stop.is_set() and (expected is None or count < expected):
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            with conn:
                while True:
                    frame = read_frame(conn)
                    if not frame:
                        break
                    count += 1
                    conn.sendall(mllp_wrap(bridge.handle(mllp_unwrap(frame))))
                    if expected is not None and count >= expected:
                        break
        srv.close()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return srv.getsockname()[1], t, stop


def send(messages, port, host="127.0.0.1"):
    acks = []
    with socket.create_connection((host, port), timeout=5) as conn:
        for m in messages:
            conn.sendall(mllp_wrap(m))
            acks.append(mllp_unwrap(read_frame(conn)))
    return acks
