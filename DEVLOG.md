# Devlog

## 2026-10-22 — competition window, local unpublished build

- Read the full expanded current event rules 01–10; saved the captured rule text under Pulse artifacts.
- Verified local Meterless World Model write/read separately.
- Started existing Docker Desktop. Zetaris containers became healthy; Windows host port forwarding returned empty replies. Internal Compose networking successfully ran `SELECT 1` and a one-row `JOIN`. No volume or service configuration was changed.
- Built deterministic snapshot receipts, AST usage matching, hypothesis states, fail-closed verdicts and independent bundle verifier.
- Captured Flask 3.1.0 official changelog and labeled the Python application fixture synthetic.
- Completed one local sponsor chain (Zetaris inline SQL + Meterless graph) with `REVIEW`, five verifiable receipts and a recorded UI bundle. Added `requirements.txt` pin validation: conflicting old version now yields `UNKNOWN`.
- Ran ten unit/failure tests and replay checks. In the dynamic-usage failure case, the bounded skeptic reopened a statically refuted hypothesis to `UNRESOLVED`; no verdict was upgraded. Captured desktop/mobile UI screenshots with headless Edge.
- A fresh Git archive first failed replay because Windows CRLF conversion changed source-byte hashes. Added `.gitattributes` to pin LF; a second archive passed tests and replay. Sponsor setup on a clean machine remains untested.

## 2026-10-22 — Cursor Agent contribution, owner-attested

- The owner reports that Cursor Agent reviewed this repository, fixed the Skeptic coverage-challenge ordering in `src/rin/core.py`, and added a regression test in `tests/test_core.py`. Included Usage reportedly moved from 2% to 22%; screenshots and a chat ID are not locally available. See [Cursor evidence](docs/CURSOR_AGENT_EVIDENCE.md).
- Independent review confirmed the narrow fix. The static-absence case now yields `UNKNOWN` and shows `INSUFFICIENT_TEST_COVERAGE` in Skeptic challenges. `NO_ACTION` remains unsupported. Fifteen tests passed, zero failed; Starlette verify and replay still pass. The reviewed code was committed locally as `e1cde63f4f24140d043ea1dcb43701d6f0c7b01e`.

Open: connector-backed RIN Zetaris sources, structured Nemotron call under confirmed free quota, frozen benchmark evaluation, final keyboard/interaction QA, timed demo and owner review. Cursor Usage screenshots and task ID can strengthen the submission audit if retained.

## 2026-10-22 — V3 local release preparation

- Rechecked the first-party captured rules, clean Git state and resources before work. Docker daemon was unavailable; no local service or source metadata was changed. The prior inline SQL and registered public CSV receipts remain the only live Zetaris evidence.
- Replayed the real Starlette case, exported two hash-pinned RIN evidence CSVs and implemented a bounded source-join validator. Unit tests confirm missing/forged results downgrade to `UNKNOWN`; these are prepared sources, **not** a federation receipt.
- Ran Meterless World Model write/read on the real case. Because the old/new differential is already recorded, the graph-selected action is now `REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI`. The graph remains in-memory and does not change the bounded `REVIEW` verdict.
- Added a separate development evaluation: two `REVIEW`, one typed `UNKNOWN`, tampered receipt and forged `NO_ACTION` rejected. Frozen 12-case benchmark remains 0/12.
- Improved the first-screen explanation and hypothesis state cues. Chrome QA now passes real Enter/Escape receipt interaction, case switch, error clearing and 390px no-overflow; real V3 screenshots retained.
- Prepared seven-slide local PDF, five-action judge script, voiceover/capture checklist and updated README/compliance documents. The video is not recorded, public GitHub is not published, and Nemotron current account-level free access remains unverified.

## 2026-10-22 — registered Zetaris sources and real-case E2E

- The owner registered the two RIN CSVs through the local NDP File System UI. Read-only `SHOW TABLES`, `DESCRIBE`, `SELECT` and `COUNT` verified `RIN_RELEASE.release_changes` (2 rows) and `RIN_USAGE.project_usage` (1 row) under distinct Lightning databases. A bounded SQL JOIN returned one `httpx.Client` / `testclient.py:392` match with the saved release/project receipt IDs. Query IDs, timestamps, rows, source identifiers and SHA-256 hashes are in `artifacts/zetaris_live_join_receipt.json`.
- Added a verifier that rechecks the captured source rows against both hash-pinned CSVs and the six-receipt real-case bundle. The live JOIN query ID is linked to the hypothesis ledger and an in-memory Meterless graph finding. Graph readback selects `REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI`; the bounded decision is `REVIEW`. Missing/tampered source or inconsistent graph yields `UNKNOWN`, never `NO_ACTION`.
- Twenty unit tests pass, zero fail; original six-receipt verify/replay and live-source E2E replay match. Two local CSV sources do not prove federation of heterogeneous remote systems. Frozen benchmark remains 0/12; Nemotron current free inference, human video and publication are still pending.

## 2026-10-22 — V3.3/V3.4 NVIDIA access attempt and release hardening

- V3.3 added a replay panel for the captured live RIN-source Zetaris JOIN and query-linked Meterless graph. Chrome QA passed desktop/mobile, receipt buttons, keyboard controls and 390px width. A clean Git archive passed 24 tests, receipt verification and both replays. Seven-slide PDF and local release package were refreshed. No video was recorded.
- The owner confirmed the NVIDIA-hosted Lightning Prototype Free Endpoint. An existing owner-controlled key authenticated model listing. A single V3.4 `POST /v1/chat/completions` used the official NVIDIA host, 384 output tokens, reasoning budget 32, 25-second timeout and no retry. It returned HTTP 401. A read-only model-list diagnostic with the same key still returned HTTP 200 and 83 models. The sanitized attempt receipt has no model output or usage; the model-assisted result is `UNKNOWN`. The existing deterministic Zetaris/Meterless `REVIEW` remains independent.
- Later on 2026-10-22, the owner supplied a different existing NVIDIA Build key reference. Its read-only model list returned HTTP 200 and included Lightning. One bounded NVIDIA-hosted free Prototype POST returned actual Nemotron output (285 prompt, 231 completion tokens); source spans, Zetaris query link, Skeptic challenges and Meterless replay passed the RIN gate. The output stayed `HYPOTHESIS` and deterministic `REVIEW` stayed independent. The old HTTP 401 receipt remains preserved. No paid route, retry, public upload or video capture occurred.
- Added a guarded one-request client, exact-span proposal validator tied to Skeptic challenges and the verified sponsor chain, plus failure and receipt-tamper tests. Twenty-nine tests passed at this point; source receipts and both replays matched. The later successful owner-key response above is the actual Nemotron hypothesis; it is not verdict authority. Frozen benchmark remains 0/12. No further inference call is needed for the saved replay.

## 2026-10-22 — V4 public showcase preparation

- Retained the owner-approved V3.8/V3.9 UI, six functional routes and real Starlette/HTTPX `REVIEW` case. Three compact GIFs were captured from genuine local Chrome interactions with saved replay evidence; no owner video was available in the checked workspace.
- Reworked the English README around the real investigation, sponsor receipts, architecture, formal evidence conditions, limitations and reproducible commands. Added an allowlisted static demo builder and local-only publication package preparation. No GitHub push, public deployment, video upload or contest submission occurred.
