"""Tiny SQLite store: one JSON document per project, plus a version log of kept edits."""
import json
import sqlite3
import threading
import time

from . import config

_lock = threading.Lock()
_conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
_conn.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL)")
_conn.execute("CREATE TABLE IF NOT EXISTS versions (project_id TEXT, n INTEGER, data TEXT, created REAL)")
_conn.commit()


def save(p: dict) -> None:
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)",
                      (p["id"], json.dumps(p, ensure_ascii=False), time.time()))
        _conn.commit()


def load(pid: str):
    with _lock:
        row = _conn.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
    return json.loads(row[0]) if row else None


def add_version(pid: str, n: int, snapshot: dict) -> None:
    with _lock:
        _conn.execute("INSERT INTO versions VALUES (?,?,?,?)",
                      (pid, n, json.dumps(snapshot, ensure_ascii=False), time.time()))
        _conn.commit()


# ---------- Cartesia voice catalog cache (one row per language) ----------
_conn.execute("CREATE TABLE IF NOT EXISTS voice_catalog (lang TEXT PRIMARY KEY, data TEXT NOT NULL, fetched REAL)")
_conn.commit()


def get_voices(lang: str):
    """-> (voices, fetched_at) or (None, 0)"""
    with _lock:
        row = _conn.execute("SELECT data, fetched FROM voice_catalog WHERE lang=?", (lang,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else (None, 0)


def put_voices(lang: str, voices: list) -> None:
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO voice_catalog VALUES (?,?,?)",
                      (lang, json.dumps(voices, ensure_ascii=False), time.time()))
        _conn.commit()
