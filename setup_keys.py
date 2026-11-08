#!/usr/bin/env python3
"""Interactive key setup for Screening Room.

    python3 setup_keys.py

Asks for up to 5 SiliconFlow keys and 5 Cartesia keys (typing is hidden), checks each one
against the live API, confirms the Hindi narrator voices exist on your account
(auto-picks replacements if not), and writes backend/.env.
Press Enter at any prompt to keep the current value; type "-" to clear a slot.
Keys are used in order; one that runs out of credit is retired and the next takes over (see backend/app/keys.py).
"""
import getpass
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("Missing dependency: run  python3 -m pip install -r backend/requirements.txt  first.")

ENV = Path(__file__).resolve().parent / "backend" / ".env"
CARTESIA = "https://api.cartesia.ai"
CARTESIA_VERSION = "2026-08-14"
SF_BASES = ["https://api.siliconflow.com/v1", "https://api.siliconflow.cn/v1"]
SF_SLOTS, CA_SLOTS = 5, 5

# Default Hindi voices (public Cartesia library). Verified against your account below.
PRESET = {
    "VOICE_GRANDMA": ("4459a9a5-69d6-4680-b970-e13dc51845b6", "Siya — warm storyteller (female)"),
    "VOICE_RADIO": ("0f14d8cb-f039-41fe-a813-a9b4bee7eed8", "Nisha — broadcast speaker (female)"),
    "VOICE_TRAILER": ("7e8cb11d-37af-476b-ab8f-25da99b18644", "Anuj — engaging narrator (male)"),
}

G, Y, R, B, X = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


def read_env() -> dict:
    vals = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def write_env(vals: dict) -> None:
    order = [
        ("# --- Writing model: SiliconFlow (used in order; a key out of credit is retired for good) ---", None),
        *[(f"SILICONFLOW_API_KEY_{i}", "") for i in range(1, SF_SLOTS + 1)], ("SILICONFLOW_BASE_URL", SF_BASES[0]),
        ("LLM_MODEL", "Qwen/Qwen3.8-27B"),
        ("\n# --- Narration: Cartesia (same failover) ---", None), *[(f"CARTESIA_API_KEY_{i}", "") for i in range(1, CA_SLOTS + 1)],
        ("TTS_MODEL", "sonic-3.6"),
        ("VOICE_DEFAULT", PRESET["VOICE_GRANDMA"][0]), ("VOICE_GRANDMA", PRESET["VOICE_GRANDMA"][0]),
        ("VOICE_RADIO", PRESET["VOICE_RADIO"][0]), ("VOICE_TRAILER", PRESET["VOICE_TRAILER"][0]),
        ("\n# --- Offline demo without keys (1 = on) ---", None), ("MOCK_LLM", "0"), ("MOCK_TTS", "0"),
    ]
    lines, known = [], set()
    for k, default in order:
        if default is None:
            lines.append(k)
            continue
        known.add(k)
        lines.append(f"{k}={vals.get(k, default)}")
    extra = [f"{k}={v}" for k, v in vals.items() if k not in known]
    if extra:
        lines += ["\n# --- Other settings ---"] + extra
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV.chmod(0o600)          # keys readable only by you
    except OSError:
        pass


def ask_secret(label: str, current: str) -> str:
    hint = f" [Enter keeps …{current[-4:]}, - clears]" if current else " [Enter skips]"
    v = getpass.getpass(f"{B}{label}{X}{hint}: ").strip()
    return "" if v == "-" else (v or current)


def migrate_single(vals: dict, name: str) -> None:
    """Old .env had one NAME=...; it becomes NAME_1."""
    old = vals.pop(name, "")
    if old and not vals.get(f"{name}_1"):
        vals[f"{name}_1"] = old


def check_siliconflow(key: str, model: str):
    """-> (base_url, model) or raises. Tries the global endpoint, then the China endpoint."""
    for base in SF_BASES:
        try:
            r = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, params={"type": "text"}, timeout=20)
        except httpx.HTTPError:
            continue
        if r.status_code == 200:
            ids = [m["id"] for m in r.json().get("data", [])]
            if model in ids or not ids:
                return base, model
            qwen = [i for i in ids if "Qwen" in i and "27B" in i] or [i for i in ids if "Qwen" in i][:8]
            print(f"{Y}  '{model}' isn't in this account's model list.{X}")
            for n, i in enumerate(qwen, 1):
                print(f"   {n}. {i}")
            pick = input("  Pick a number, or press Enter to keep your model id anyway: ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(qwen):
                return base, qwen[int(pick) - 1]
            return base, model
    raise RuntimeError("key rejected by both api.siliconflow.com and api.siliconflow.cn")


def cartesia_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "X-API-Key": key, "Cartesia-Version": CARTESIA_VERSION}


def check_cartesia(key: str) -> list:
    r = httpx.get(f"{CARTESIA}/voices", headers=cartesia_headers(key), params={"language": "hi", "limit": 100}, timeout=20)
    if r.status_code in (401, 403):
        raise RuntimeError("Cartesia rejected the key")
    r.raise_for_status()
    return r.json().get("data", [])


def voice_ok(key: str, vid: str) -> bool:
    try:
        return httpx.get(f"{CARTESIA}/voices/{vid}", headers=cartesia_headers(key), timeout=15).status_code == 200
    except httpx.HTTPError:
        return False


def pick_voice(voices: list, gender: str, taken: set):
    def score(v):
        d = f"{v.get('name', '')} {v.get('description', '')} {v.get('tagline', '')}".lower()
        return (v.get("gender") == gender) * 4 + any(w in d for w in ("narrat", "story")) * 3 + ("warm" in d) - (v["id"] in taken) * 10
    return max(voices, key=score) if voices else None


def main():
    print(f"\n{B}Screening Room — API key setup{X}\nWrites {ENV}\n")
    vals = read_env()

    migrate_single(vals, "SILICONFLOW_API_KEY")
    migrate_single(vals, "CARTESIA_API_KEY")

    # SiliconFlow — up to 5 keys, used in order
    print(f"{B}SiliconFlow keys{X} (key 1 is used first; when it runs out the app moves to key 2, and so on)")
    for i in range(1, SF_SLOTS + 1):
        name = f"SILICONFLOW_API_KEY_{i}"
        key = ask_secret(f"  SiliconFlow key {i}", vals.get(name, ""))
        vals[name] = key
        if not key:
            continue
        try:
            base, model = check_siliconflow(key, vals.get("LLM_MODEL", "Qwen/Qwen3.8-27B"))
            vals.update(SILICONFLOW_BASE_URL=base, LLM_MODEL=model)
            print(f"{G}    ✓ key {i} works ({base.split('//')[1].split('/')[0]}, model {model}){X}")
        except Exception as e:
            print(f"{R}    ✗ key {i}: couldn't verify ({e}). Saved anyway.{X}")
    if not any(vals.get(f"SILICONFLOW_API_KEY_{i}") for i in range(1, SF_SLOTS + 1)):
        print(f"{Y}  No SiliconFlow key — the writing model won't run until one is set.{X}")

    # Cartesia + voices — up to 2 keys, used in order
    print(f"\n{B}Cartesia keys{X} (key 1 is used first; when it runs out the app moves to key 2, and so on)")
    ckey = ""
    for i in range(1, CA_SLOTS + 1):
        name = f"CARTESIA_API_KEY_{i}"
        k = ask_secret(f"  Cartesia key {i}", vals.get(name, ""))
        vals[name] = k
        if k and i > 1:
            try:
                check_cartesia(k)
                print(f"{G}    ✓ key {i} works{X}")
            except Exception as e:
                print(f"{R}    ✗ key {i}: couldn't verify ({e}). Saved anyway.{X}")
        ckey = ckey or k
    if ckey:
        try:
            voices = check_cartesia(ckey)
            print(f"{G}  ✓ Cartesia key works · {len(voices)} Hindi voices available{X}")
            taken = set()
            for env_key, (vid, label) in PRESET.items():
                cur = vals.get(env_key) or vid
                if voice_ok(ckey, cur):
                    vals[env_key] = cur
                    print(f"{G}  ✓ {env_key:<14} {label if cur == vid else cur}{X}")
                else:
                    alt = pick_voice(voices, "masculine" if env_key == "VOICE_TRAILER" else "feminine", taken)
                    if alt:
                        vals[env_key] = alt["id"]
                        print(f"{Y}  ↺ {env_key:<14} preset not on your account; using {alt['name']} ({alt['id']}){X}")
                    else:
                        print(f"{R}  ✗ {env_key}: no Hindi voice found{X}")
                taken.add(vals.get(env_key, ""))
            vals["VOICE_DEFAULT"] = vals.get("VOICE_GRANDMA", PRESET["VOICE_GRANDMA"][0])
        except Exception as e:
            print(f"{R}  ✗ Couldn't verify: {e}. Saved anyway with the default Hindi voices.{X}")
    else:
        print(f"{Y}  Skipped — narration won't run until this is set.{X}")

    vals.setdefault("MOCK_LLM", "0")
    vals.setdefault("MOCK_TTS", "0")
    write_env(vals)
    print(f"\n{G}{B}Saved.{X} Start the app with  ./run.sh  (restart it if it's already running).\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled — nothing changed.")
