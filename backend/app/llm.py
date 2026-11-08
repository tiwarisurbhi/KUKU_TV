"""SiliconFlow client. Every call is built by qwen_prompts.build_request(step, lang=...)
and returns a validated Pydantic object.

Anti-leak layers (unchanged):
 1. response_format = json_schema from qwen_prompts (falls back to json_object + schema in prompt)
 2. enable_thinking = False (from build_request's extra_body)
 3. reasoning_content is dropped, streamed or not
 4. clean_json_text: strip <think>…</think>, code fences, text outside the JSON object
 5. Pydantic validation; one repair turn via qwen_prompts.build_repair_messages
 6. callers only forward whitelisted fields; `notes` never leaves the backend
"""
import asyncio
import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

from . import config, keys, qwen_prompts as qp
from .models import STEP_MODELS

log = logging.getLogger("llm")
_sem = asyncio.Semaphore(config.LLM_CONCURRENCY)
_mode = {"value": config.LLM_RESPONSE_MODE}


class LLMError(RuntimeError):
    pass


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def clean_json_text(text: str) -> str:
    text = text or ""
    text = _THINK.sub("", text)
    if "</think>" in text:                       # unclosed / leading reasoning block
        text = text.rsplit("</think>", 1)[1]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = text.find("{"), text.rfind("}")
    return text[a:b + 1] if a != -1 and b > a else text


def _payload(req: dict, messages: list, stream: bool) -> dict:
    """build_request() output -> raw HTTP body (extra_body keys go top-level over HTTP)."""
    body = {k: v for k, v in req.items() if k not in ("extra_body", "messages", "response_format")}
    body.update(req.get("extra_body") or {})
    body["model"] = config.LLM_MODEL or req["model"]
    body["stream"] = stream
    body["enable_thinking"] = False
    if _mode["value"] == "json_schema":
        body["messages"] = messages
        body["response_format"] = req["response_format"]
    else:
        schema = req["response_format"]["json_schema"]["schema"]
        body["messages"] = [{"role": "system", "content": messages[0]["content"] +
                             "\n\nReturn ONLY one JSON object that matches this JSON Schema exactly:\n" +
                             json.dumps(schema, ensure_ascii=False)}] + messages[1:]
        body["response_format"] = {"type": "json_object"}
    return body


async def _post(req: dict, messages: list, on_text=None) -> str:
    """One model call. If the key is out of credit / invalid, it is retired and the call moves to the next key."""
    busy = 0
    while True:
        try:
            key = keys.LLM.current()
        except keys.NoLiveKey as e:
            raise LLMError(str(e))
        status, body, finish = await _post_once(req, messages, on_text, key)
        if status >= 400 and keys.LLM.check(key, status, body):
            continue                                   # key retired for good; same request, next key
        if (status == 429 or status >= 500) and busy < 3:
            busy += 1                                  # rate limit / server hiccup: same key, short back-off
            await asyncio.sleep(2 * busy)
            continue
        break
    if status == 400 and _mode["value"] == "json_schema" and "response_format" in body.lower():
        log.warning("Provider rejected json_schema; switching to json_object mode")
        _mode["value"] = "json_object"
        return await _post(req, messages, on_text)
    if status >= 400:
        raise LLMError(f"LLM HTTP {status}: {body[:400]}")
    if finish == "length":
        raise LLMError("LLM output was cut off (max_tokens). Try a shorter source.")
    return body


async def _post_once(req: dict, messages: list, on_text, key: str) -> tuple:
    stream = bool(on_text and config.LLM_STREAM)
    url = f"{config.SILICONFLOW_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT_S) as client:
        if stream:
            status, body, finish = await _stream(client, url, _payload(req, messages, True), headers, on_text)
        else:
            r = await client.post(url, json=_payload(req, messages, False), headers=headers)
            status, body, finish = r.status_code, r.text, None
            if status < 400:
                data = r.json()
                msg = data["choices"][0]["message"]
                if msg.get("reasoning_content"):
                    log.info("dropped %d chars of reasoning_content", len(msg["reasoning_content"]))
                body, finish = msg.get("content") or "", data["choices"][0].get("finish_reason")
    return status, body, finish


async def _stream(client, url, payload, headers, on_text):
    """SSE: keep `content` deltas, drop `reasoning_content`. on_text(text_so_far) ~5x/second."""
    parts, finish, dropped, last_emit = [], None, 0, 0.0
    async with client.stream("POST", url, json=payload, headers=headers) as r:
        if r.status_code >= 400:
            return r.status_code, (await r.aread()).decode("utf-8", "replace"), None
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ch = (json.loads(data).get("choices") or [{}])[0]
            except json.JSONDecodeError:
                continue
            d = ch.get("delta") or {}
            dropped += len(d.get("reasoning_content") or "")
            if d.get("content"):
                parts.append(d["content"])
                now = time.monotonic()
                if now - last_emit > 0.2:
                    last_emit = now
                    _safe(on_text, "".join(parts))
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    text = "".join(parts)
    _safe(on_text, text)
    if dropped:
        log.info("dropped %d chars of streamed reasoning_content", dropped)
    return 200, text, finish


def _safe(fn, text):
    try:
        fn(text)
    except Exception:                                  # the live view must never break a model call
        log.exception("live view callback failed")


async def call(step: str, lang: str = "hi", *, on_text=None, **variables):
    """Run one qwen_prompts step and return its validated model."""
    return await call_request(step, qp.build_request(step, lang=lang, **variables), lang, on_text=on_text)


async def call_request(step: str, req: dict, lang: str = "hi", *, on_text=None):
    """Run a prebuilt request (qwen_prompts or voice_prompts shape) and validate it."""
    model = STEP_MODELS[step]
    if config.MOCK_LLM:
        from . import mock
        data = mock.respond(step, req["messages"][-1]["content"], lang)
        if on_text:                                    # replay slowly so the live view can be tested offline
            raw = json.dumps(data, ensure_ascii=False)
            for i in range(0, len(raw), 80):
                on_text(raw[:i + 80])
                await asyncio.sleep(0.04)
        else:
            await asyncio.sleep(0.3)
        return model.model_validate(data)
    if not keys.LLM:
        raise LLMError("No SiliconFlow key is set (SILICONFLOW_API_KEY_1 … _5 in backend/.env)")

    messages = req["messages"]
    async with _sem:
        content, err = await _post(req, messages, on_text), None
        for attempt in range(2):
            try:
                return model.model_validate(json.loads(clean_json_text(content)))
            except (json.JSONDecodeError, ValidationError) as e:
                err = e
                log.warning("%s attempt %d invalid: %s", step, attempt + 1, str(e)[:300])
                if attempt == 1:
                    break
                repair = dict(req, **{k: v for k, v in qp.SAMPLING["json_repair"].items() if k != "top_k"})
                repair["extra_body"] = dict(req.get("extra_body") or {}, top_k=qp.SAMPLING["json_repair"]["top_k"])
                messages = qp.build_repair_messages(req["messages"], content[:14000], str(e)[:1200])
                content = await _post(repair, messages)
        raise LLMError(f"{step}: model did not return valid structured output ({err})")
