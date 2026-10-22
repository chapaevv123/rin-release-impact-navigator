# Sponsor technology

## Zetaris — verified registered local source JOIN

The existing owner-machine Zetaris Compose stack is used without reinstall. `rin.zetaris_bridge` sends bounded read-only SQL through `docker exec -i` to the already running UI container. Credentials are supplied from the local approved configuration and passed to the transient process on stdin. The adapter does not log authentication data.

The older synthetic Flask fixture uses inline SQL values. The new real-case receipt records two owner-registered CSV tables, `RIN_RELEASE.release_changes` and `RIN_USAGE.project_usage`, independently listed by Zetaris, described and queried. SELECT/COUNT returned 2 release rows and 1 usage row. A bounded cross-source JOIN returned one `httpx.Client` / `testclient.py:392` row with the release and project receipt IDs. [Live SQL receipt](artifacts/zetaris_live_join_receipt.json) stores UTC query IDs, source identifiers, database IDs 805/806, rows and result hashes; [E2E receipt](artifacts/zetaris_live_e2e_receipt.json) shows that verified JOIN in the RIN/Meterless decision path. These are two local NDP File System CSV sources derived from one pinned evidence bundle. **Heterogeneous remote federation is not demonstrated.** The service does not cryptographically sign query responses; RIN retains a local hash-checked capture and replay.

The [source record](docs/ZETARIS_SOURCE_PLAN.md) distinguishes the earlier failed direct SQL registration from the owner's subsequent NDP File System registration and the verified live query. No table or database creation is needed to replay the saved evidence.

## Meterless — verified local graph write/read

`meterless_graph.ts` uses the World Model reference implementation from `Meterless/Meterless` commit `1742dec56a66e58eef9dda2d2b865823758ca8cd`. It upserts project, release and symbol entities, writes `changes` and `uses` relations, then reads the graph. In the captured Flask fixture it selects `VERIFY_DIFFERENTIAL_BEHAVIOR` after the read confirms the intersection. It is in-memory and does not claim persistence across runs.

The [real-case graph receipt](artifacts/meterless_real_case_receipt.json) records the starting hypothesis states (`SUPPORTED`, `REFUTED`, `UNRESOLVED`). In the [live-source E2E receipt](artifacts/zetaris_live_e2e_receipt.json), the registered JOIN query ID is added to the graph finding's evidence links before World Model readback; the next action is `REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI` because the local PASS→FAIL differential is already recorded. The verdict remains bounded `REVIEW`. Missing source evidence or inconsistent graph yields `UNKNOWN`. Storage is in-memory and does not persist across runs.

## NVIDIA and Cursor

A pre-window Nemotron direct inference receipt exists in Pulse artifacts outside this standalone repository. This RIN build first tried a credential that returned HTTP 401; that [failed attempt](artifacts/nemotron_v3_4_inference_receipt.json) is preserved. The owner then supplied a different existing NVIDIA Build key. One bounded POST to the NVIDIA-hosted free Prototype route returned a real `nvidia/nemotron-3.5-lightning-30b-a3b` response with 516 total tokens. RIN validates two exact source citations, then rechecks the saved Zetaris query, Skeptic coverage challenges and Meterless graph. The model output remains a **HYPOTHESIS** while the deterministic verdict remains **REVIEW**. The [successful sanitized receipt](artifacts/nemotron_owner_key_inference_receipt.json) records the actual output, usage and hashes. UI display is replay, with no fresh model call. This single success is not a reliability metric or proof of an account-wide no-overage setting. See [Nemotron status](docs/NEMOTRON_STATUS.md).

Cursor IDE CLI 3.19.7 is installed. The owner reports a real Cursor Agent coding workflow and included Usage changing from 2% to 22%; the code result and fifteen passing tests were independently checked. Original account screenshots and chat ID are not locally retained. See [Cursor evidence](docs/CURSOR_AGENT_EVIDENCE.md). This is development provenance, not a Cursor call in either captured RIN case.
