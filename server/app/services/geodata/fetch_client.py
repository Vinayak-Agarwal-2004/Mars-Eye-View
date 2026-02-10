import os
import urllib.request
from typing import Any


def fetch(
    url: str,
    headers: dict | None = None,
    timeout: int | None = None,
    retries: int | None = None,
) -> bytes:
    timeout = timeout if timeout is not None else int(os.environ.get("GEODATA_FETCH_TIMEOUT", "120"))
    retries = retries if retries is not None else int(os.environ.get("GEODATA_RETRIES", "2"))

    req_headers = {"User-Agent": "Mars-Eye-View/1.0"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
    raise last_err
