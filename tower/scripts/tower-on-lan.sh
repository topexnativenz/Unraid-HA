#!/bin/bash
# Exit 0 when tower is reachable on LAN (for OpenSSH Match exec).
python3 - "${TOWER_LAN_HOST:-192.168.1.7}" "${TOWER_SSH_PORT:-22}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

s = socket.socket()
s.settimeout(2.0)
try:
    s.connect((host, port))
except Exception:
    sys.exit(1)
else:
    sys.exit(0)
finally:
    s.close()
PY
