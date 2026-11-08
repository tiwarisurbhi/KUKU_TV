"""API key pools with one-way failover.

Each service has an ordered list of keys (backend/.env):
    SILICONFLOW_API_KEY_1 … SILICONFLOW_API_KEY_5     (writing model)
    CARTESIA_API_KEY_1    … CARTESIA_API_KEY_5        (narration)
(The old single SILICONFLOW_API_KEY / CARTESIA_API_KEY still work and count as slot 1.)

Every call uses the first key that is still live. When a key comes back with an error that means
the KEY itself is finished (no balance / credits, invalid, revoked, suspended), that key is retired
and the same call is retried at once with the next key. A retired key is never picked again: the
retirement is stored in SQLite by fingerprint (sha256, never the key itself), so it survives
restarts. Rate limits (429 "too many requests / concurrency") and server errors (5xx) do NOT retire
a key; they are temporary and keep their existing back-off retries.

To bring a retired key back (say you topped it up), run:
    python -m app.keys            # show every slot and its state
    python -m app.keys reset llm  # or: reset tts / reset all
Replacing the key in .env with a new one also works: a new key has a new fingerprint.
"""
import hashlib
import logging
import re
import sys
import time

from . import config, db

log = logging.getLogger("keys")

db._conn.execute("CREATE TABLE IF NOT EXISTS retired_keys (service TEXT, fp TEXT, reason TEXT, at REAL, "
                 "PRIMARY KEY (service, fp))")
db._conn.commit()

# Phrases providers use when the account/key is out of money or no longer valid.
_DEAD_WORDS = re.compile(
    r"insufficient|balance|credit|quota|out of (?:characters|credits)|billing|payment|subscription|"
    r"invalid (?:api[ _-]?)?(?:key|token)|token is invalid|unauthori[sz]ed|revoked|suspended|disabled|expired|"
    r"not (?:a )?valid (?:api )?key|account (?:is )?(?:locked|banned|inactive)", re.I)
# Messages that only mean "slow down" — never retire on these.
_RATE_WORDS = re.compile(r"concurrency|rate[ _-]?limit|too many requests|requests per|try again", re.I)
# SiliconFlow error codes seen so far: 30001 balance insufficient, 30014 token invalid, 30011 key disabled
_SF_DEAD_CODES = re.compile(r'"code"\s*:\s*(30001|30011|30014)\b')


class NoLiveKey(RuntimeError):
    pass


def fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 8 else "…"


class KeyPool:
    def __init__(self, service: str, label: str, keys: list):
        self.service, self.label = service, label
        self.keys = list(dict.fromkeys(k for k in keys if k))      # ordered, de-duplicated
        self._retired = {fp: (reason, at) for fp, reason, at in db._conn.execute(
            "SELECT fp, reason, at FROM retired_keys WHERE service=?", (service,))}

    def __bool__(self):
        return bool(self.keys)

    def live(self) -> list:
        return [k for k in self.keys if fingerprint(k) not in self._retired]

    def current(self) -> str:
        live = self.live()
        if not live:
            n = len(self.keys)
            if not n:
                raise NoLiveKey(f"No {self.label} key is set in backend/.env")
            raise NoLiveKey(f"All {n} {self.label} key{'s' if n != 1 else ''} are retired (out of credit or "
                            f"invalid). Add a fresh key to backend/.env, or run  python -m app.keys reset "
                            f"{self.service}  if you topped one up.")
        return live[0]

    def slot(self, key: str) -> int:
        return self.keys.index(key) + 1 if key in self.keys else 0

    def is_dead(self, status: int, body: str) -> bool:
        """True when the error says this key/account is finished, not just busy."""
        body = body or ""
        if status in (401, 402):
            return True
        if self.service == "llm" and _SF_DEAD_CODES.search(body):
            return True
        if status >= 500:
            return False
        if status == 429 and _RATE_WORDS.search(body) and not re.search(r"insufficient|balance|credit|quota", body, re.I):
            return False
        if status == 403:
            return not re.search(r"\bvoice\b", body, re.I)        # a private voice is not a dead key
        return status in (400, 429) and bool(_DEAD_WORDS.search(body))

    def retire(self, key: str, reason: str) -> None:
        fp = fingerprint(key)
        if fp in self._retired:
            return                                               # another call already retired it
        self._retired[fp] = (reason[:300], time.time())
        with db._lock:
            db._conn.execute("INSERT OR REPLACE INTO retired_keys VALUES (?,?,?,?)",
                             (self.service, fp, reason[:300], time.time()))
            db._conn.commit()
        nxt = self.live()
        log.warning("%s key %d (%s) retired: %s — %s", self.label, self.slot(key), mask(key), reason[:160],
                    f"switching to key {self.slot(nxt[0])} ({mask(nxt[0])})" if nxt else "NO KEYS LEFT")

    def check(self, key: str, status: int, body: str) -> bool:
        """Call after a failed request. Retires the key if it is dead; True means 'retry with the next key'."""
        if status >= 400 and self.is_dead(status, body):
            self.retire(key, f"HTTP {status}: {(body or '').strip()[:240]}")
            return True
        return False

    def reset(self) -> int:
        with db._lock:
            n = db._conn.execute("DELETE FROM retired_keys WHERE service=?", (self.service,)).rowcount
            db._conn.commit()
        self._retired.clear()
        return n

    def summary(self) -> dict:
        return {"total": len(self.keys), "live": len(self.live()),
                "current": self.slot(self.live()[0]) if self.live() else 0}

    def report(self) -> list:
        out = []
        for i, k in enumerate(self.keys, 1):
            r = self._retired.get(fingerprint(k))
            out.append({"slot": i, "key": mask(k), "state": "retired" if r else "live",
                        "reason": r[0] if r else "", "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(r[1])) if r else ""})
        return out


def cartesia_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "X-API-Key": key, "Cartesia-Version": config.CARTESIA_VERSION}


LLM = KeyPool("llm", "SiliconFlow", config.SILICONFLOW_API_KEYS)
TTS = KeyPool("tts", "Cartesia", config.CARTESIA_API_KEYS)


def _cli(argv: list) -> None:
    pools = {"llm": LLM, "tts": TTS}
    if len(argv) >= 2 and argv[0] == "reset":
        for name in (pools if argv[1] == "all" else [argv[1]]):
            print(f"{pools[name].label}: {pools[name].reset()} key(s) brought back")
        return
    for name, pool in pools.items():
        print(f"\n{pool.label} ({name}) — {pool.summary()['live']} of {pool.summary()['total']} live")
        cur = pool.summary()["current"]
        for r in pool.report():
            mark = "  ← in use" if r["slot"] == cur else ""
            print(f"  {r['slot']}. {r['key']:<7} {r['state']:<8} {r['at']}  {r['reason'][:90]}{mark}")
    print()


if __name__ == "__main__":
    _cli(sys.argv[1:])
