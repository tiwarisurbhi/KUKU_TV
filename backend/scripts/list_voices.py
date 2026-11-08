"""List Cartesia voices for a language so you can pick persona voice ids.
Usage: python3 backend/scripts/list_voices.py hi
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402

from app import config  # noqa: E402

lang = sys.argv[1] if len(sys.argv) > 1 else "hi"
r = httpx.get(f"{config.CARTESIA_BASE_URL}/voices", params={"language": lang, "limit": 100},
              headers={"Authorization": f"Bearer {config.CARTESIA_API_KEY}", "X-API-Key": config.CARTESIA_API_KEY,
                       "Cartesia-Version": config.CARTESIA_VERSION}, timeout=30)
r.raise_for_status()
for v in r.json().get("data", []):
    print(f"{v['id']}  {v.get('gender') or '':<14} {v['name']:<28} {(v.get('description') or '')[:70]}")
