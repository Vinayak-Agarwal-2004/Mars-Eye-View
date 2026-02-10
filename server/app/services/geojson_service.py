import json
import os
from pathlib import Path

from server.app.services.geodata.registry import get_provider


def _data_dir() -> Path:
    return Path(os.environ.get("GEODATA_DATA_DIR", "data"))


def _auth_headers_from_request(headers: dict | None) -> dict:
    if not headers:
        return {}
    out = {}
    for k in ("authorization", "cookie"):
        v = headers.get(k) or headers.get(k.replace("-", "_"))
        if v:
            out[k] = v
    return out


def _read_local(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        if len(data) < 10:
            return None
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def _write_local(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def get_world(params: dict | None = None, auth_headers: dict | None = None) -> dict:
    base = _data_dir()
    path = base / "countries.geojson"
    local = _read_local(path)
    if local is not None:
        return local
    provider = get_provider("natural_earth")
    raw = provider.fetch("world", params=params, headers=auth_headers or {})
    data = json.loads(raw.decode("utf-8"))
    _write_local(path, data)
    return data


def get_adm1(iso: str, params: dict | None = None, auth_headers: dict | None = None) -> dict:
    iso = iso.upper()
    base = _data_dir()
    path = base / "adm1" / f"{iso}.geojson"
    local = _read_local(path)
    if local is not None:
        return local
    provider = get_provider("geoboundaries")
    p = dict(params or {})
    p["iso"] = iso
    raw = provider.fetch("ADM1", params=p, headers=auth_headers or {})
    data = json.loads(raw.decode("utf-8"))
    _write_local(path, data)
    return data


def get_adm2(iso: str, params: dict | None = None, auth_headers: dict | None = None) -> dict:
    iso = iso.upper()
    base = _data_dir()
    path = base / "adm2" / f"{iso}.geojson"
    local = _read_local(path)
    if local is not None:
        return local
    provider = get_provider("geoboundaries")
    p = dict(params or {})
    p["iso"] = iso
    raw = provider.fetch("ADM2", params=p, headers=auth_headers or {})
    data = json.loads(raw.decode("utf-8"))
    _write_local(path, data)
    return data


def health() -> dict:
    out = {}
    for name in ("geoboundaries", "natural_earth"):
        try:
            p = get_provider(name)
            out[name] = "ok" if p.health() else "fail"
        except Exception:
            out[name] = "error"
    return out
