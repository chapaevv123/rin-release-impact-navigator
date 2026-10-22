"""One bounded NVIDIA-hosted Prototype request; no retry or partner fallback."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

MODEL_ID = "nvidia/nemotron-3.5-lightning-30b-a3b"
ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
MAX_TOKENS = 384
REASONING_BUDGET = 32
TIMEOUT_SECONDS = 25


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def payload(prompt: str) -> dict:
    return {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "Return one strict JSON object only. Copy cited spans exactly. Do not claim verification."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_budget": REASONING_BUDGET,
    }


def send_once(credential: str, body: dict, opener=None) -> dict:
    if not isinstance(credential, str) or not credential:
        raise ValueError("NVIDIA credential missing")
    if body.get("model") != MODEL_ID or body.get("max_tokens") != MAX_TOKENS:
        raise ValueError("unbounded or wrong-model request")
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Authorization": "Bearer " + credential, "Content-Type": "application/json",
                 "Accept": "application/json"}, method="POST")
    connection = opener or urllib.request.build_opener(NoRedirect()).open
    with connection(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise urllib.error.HTTPError(ENDPOINT, response.status, "unexpected response", {}, None)
        raw = response.read(256_000)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("malformed NVIDIA response")
    return parsed


def extract(parsed: dict) -> dict:
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("response choices missing")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("response content missing")
    return {"model_id": parsed.get("model"), "response_id": parsed.get("id"),
            "content": message["content"], "finish_reason": choices[0].get("finish_reason"),
            "usage": parsed.get("usage")}


def verify_attempt_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict) or receipt.get("schema") != "rin.nemotron_inference.v1":
        return {"ok": False, "reason": "INVALID_SCHEMA"}
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()
    if receipt.get("receipt_sha256") != digest:
        return {"ok": False, "reason": "RECEIPT_HASH_MISMATCH"}
    if (receipt.get("endpoint") != ENDPOINT or receipt.get("model_requested") != MODEL_ID
            or receipt.get("key_value") != "REDACTED" or receipt.get("automatic_retries") != 0):
        return {"ok": False, "reason": "REQUEST_CONTRACT_INVALID"}
    if receipt.get("status") == "HTTP_ERROR" and receipt.get("http_status") == 401:
        if receipt.get("response_sha256") or receipt.get("usage") or receipt.get("rin_model_stage") != "UNKNOWN":
            return {"ok": False, "reason": "FAILED_REQUEST_HAS_MODEL_CLAIM"}
        return {"ok": True, "status": "HTTP_401_NO_INFERENCE"}
    if receipt.get("status") == "HTTP_200_INFERENCE":
        content = receipt.get("response_text")
        if (not isinstance(content, str) or receipt.get("response_model_id") != MODEL_ID
                or receipt.get("response_sha256") != hashlib.sha256(content.encode()).hexdigest()):
            return {"ok": False, "reason": "MODEL_RESPONSE_INVALID"}
        return {"ok": True, "status": "INFERENCE_CAPTURED"}
    return {"ok": False, "reason": "REQUEST_OUTCOME_UNVERIFIED"}
