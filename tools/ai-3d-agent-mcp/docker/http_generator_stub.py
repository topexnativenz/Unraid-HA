#!/usr/bin/env python3
"""Minimal HTTP generator matching the MCP http backend contract (CPU stub)."""

from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import trimesh


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        w = float(body.get("width_mm", 40))
        d = float(body.get("depth_mm", 40))
        h = float(body.get("height_mm", 60))
        mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        extents = np.asarray(mesh.extents, dtype=float)
        mesh.apply_scale(np.array([w, d, h]) / extents)
        data = mesh.export(file_type="stl")
        payload = json.dumps({"stl_b64": base64.b64encode(data).decode("ascii")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 7860), Handler).serve_forever()
