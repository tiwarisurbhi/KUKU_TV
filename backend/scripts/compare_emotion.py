"""Narrate one project twice — Cartesia emotion tags ON and OFF — for a listening test.
Usage: python3 backend/scripts/compare_emotion.py <project_id> [persona]
Writes backend/data/audio/<id>-emotion-on.wav and <id>-emotion-off.wav (same cues, same voice)."""
import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config, db, tts  # noqa: E402


async def main(pid: str, persona: str):
    p = db.load(pid)
    if not p or p.get("status") != "ready" or "story" not in p:
        sys.exit(f"project {pid} not found or not ready")
    for mode, tag in (("all", "on"), ("off", "off")):
        a = await tts.narrate(p, persona, float(p.get("pace", 1.0)), mode)
        dst = config.AUDIO_DIR / f"{pid}-emotion-{tag}.wav"
        shutil.copy(config.AUDIO_DIR / Path(a["url"]).name, dst)
        print(f"emotion tags {tag:3}: {dst}  ({a['duration']:.1f}s, voice {a['voice']})")

asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "grandma"))
