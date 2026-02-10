#!/usr/bin/env python3
"""Verify live API endpoints. Requires server running at localhost:8000."""
import requests

BASE = "http://localhost:8000/api"


def main():
    try:
        r = requests.get(f"{BASE}/health", timeout=2)
        if r.status_code != 200:
            print("API not healthy")
            return 1
    except Exception as e:
        print(f"API not reachable: {e}")
        return 1

    r = requests.get(f"{BASE}/anomalies?lookback_days=7&sigma=2.0")
    assert r.status_code == 200
    assert "llm_context" in r.json()

    r = requests.get(f"{BASE}/actor-network?min_weight=2")
    assert r.status_code == 200
    assert "llm_context" in r.json()

    r = requests.get(f"{BASE}/hotspots?clustering=dbscan")
    assert r.status_code == 200

    print("All live API checks passed")
    return 0


if __name__ == "__main__":
    exit(main())
