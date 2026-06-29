from __future__ import annotations

import time
from typing import Any

import httpx

MAX_XERO_RETRIES = 6
MAX_XERO_RETRY_WAIT_SEC = 180.0


def _retry_wait_seconds(resp: httpx.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.5), 60.0)
        except ValueError:
            pass
    return min(2.0**attempt, 30.0)


def xero_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int = MAX_XERO_RETRIES,
    max_total_wait_sec: float = MAX_XERO_RETRY_WAIT_SEC,
    **kwargs: Any,
) -> httpx.Response:
    """Perform an HTTP request, retrying on Xero rate limit (429)."""
    total_wait = 0.0
    last_resp: httpx.Response | None = None
    for attempt in range(max_retries + 1):
        resp = client.request(method, url, **kwargs)
        last_resp = resp
        if resp.status_code != 429:
            return resp
        if attempt >= max_retries:
            return resp
        wait = _retry_wait_seconds(resp, attempt)
        if total_wait + wait > max_total_wait_sec:
            return resp
        time.sleep(wait)
        total_wait += wait
    assert last_resp is not None
    return last_resp
