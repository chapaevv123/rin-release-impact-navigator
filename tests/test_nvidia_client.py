import json
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rin.nvidia_client import ENDPOINT, MODEL_ID, MAX_TOKENS, extract, payload, send_once, verify_attempt_receipt  # noqa: E402


class Response:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return json.dumps(self.value).encode()


class NvidiaClientTests(unittest.TestCase):
    def test_one_bounded_request_uses_exact_nvidia_endpoint(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response({"model": MODEL_ID, "choices": [{"message": {"content": "{}"},
                                                               "finish_reason": "stop"}],
                             "usage": {"total_tokens": 42}})

        body = payload("pinned public release excerpt")
        result = extract(send_once("test-credential", body, opener))
        self.assertEqual(result["model_id"], MODEL_ID)
        self.assertEqual(result["usage"]["total_tokens"], 42)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0].full_url, ENDPOINT)
        self.assertEqual(json.loads(requests[0][0].data)["max_tokens"], MAX_TOKENS)
        self.assertFalse(body["chat_template_kwargs"]["enable_thinking"])

    def test_api_failure_is_not_retried(self):
        calls = []

        def fail(request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(ENDPOINT, 402, "insufficient credits", {}, None)

        with self.assertRaises(urllib.error.HTTPError):
            send_once("test-credential", payload("excerpt"), fail)
        self.assertEqual(calls, [ENDPOINT])

    def test_malformed_api_content_and_unbounded_payload_rejected(self):
        with self.assertRaises(ValueError):
            extract({"choices": [{"message": {"content": None}}]})
        with self.assertRaises(ValueError):
            send_once("test-credential", {**payload("excerpt"), "max_tokens": 99999},
                      lambda *_: Response({}))

    def test_actual_401_receipt_verifies_and_tamper_fails(self):
        receipt = json.loads((ROOT / "artifacts/nemotron_v3_4_inference_receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(verify_attempt_receipt(receipt), {"ok": True, "status": "HTTP_401_NO_INFERENCE"})
        receipt["http_status"] = 200
        self.assertEqual(verify_attempt_receipt(receipt)["reason"], "RECEIPT_HASH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
