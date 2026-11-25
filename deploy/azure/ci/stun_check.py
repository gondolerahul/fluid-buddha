"""Is the TURN relay answering? Sends a STUN Binding request over UDP and waits for the reply.

    python3 stun_check.py <host> [port]

Exit code 0 when the relay answers with a Binding success that matches the request.
"""
import os
import socket
import struct
import sys

MAGIC_COOKIE = 0x2112A442
BINDING_REQUEST = 0x0001
BINDING_SUCCESS = 0x0101


def binding_succeeds(host: str, port: int, timeout: float = 3.0) -> bool:
    transaction = os.urandom(12)
    request = struct.pack("!HHI", BINDING_REQUEST, 0, MAGIC_COOKIE) + transaction
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        try:
            s.sendto(request, (host, port))
            reply, _ = s.recvfrom(2048)
        except OSError:  # timeouts included
            return False
    if len(reply) < 20:
        return False
    kind, _, cookie = struct.unpack("!HHI", reply[:8])
    return kind == BINDING_SUCCESS and cookie == MAGIC_COOKIE and reply[8:20] == transaction


def main() -> int:
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3478
    for _ in range(3):
        if binding_succeeds(host, port):
            print(f"ok    STUN   {host}:{port}/udp")
            return 0
    print(f"no STUN answer from {host}:{port}/udp", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
