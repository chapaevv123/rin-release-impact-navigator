# Registered RIN sources and live Zetaris join

**Current status: CROSS_SOURCE_JOIN_VERIFIED.** The owner registered the two prepared CSVs through the NDP File System UI. Zetaris `SHOW TABLES`, `DESCRIBE`, `SELECT` and `COUNT` independently confirmed both tables. The live bounded JOIN returned one row linking `httpx.Client` to `testclient.py:392` and the saved release/project receipt IDs. [Live SQL capture](../artifacts/zetaris_live_join_receipt.json) has query IDs, UTC timestamps, source identifiers, database IDs 805/806, rows and hashes; [RIN/Meterless E2E](../artifacts/zetaris_live_e2e_receipt.json) consumes that captured result. Neither two local CSVs nor their join prove federation of heterogeneous remote systems.

Earlier direct SQL registration failed with `Invalid file path to access`; the [historical gate receipt](../artifacts/zetaris_v3_1_gate.json) remains for audit. Do not repeat registration or namespace creation. The service responses are locally hash captured, not cryptographically signed by Zetaris.

`python bench/prepare_zetaris_sources.py` replays the pinned Starlette/HTTPX case, verifies its six receipts, and exports two small UTF-8 CSV files:

| Intended source | File | Rows | SHA-256 |
|---|---|---:|---|
| Release changes | `samples/zetaris_sources/release_changes.csv` | 2 | `b9169cb7727196506b688c87512377ee6db0c81143c852f9f140c4ec3681ea68` |
| Repository usage | `samples/zetaris_sources/project_usage.csv` | 1 | `def9a9e3f395d8dc1bf961fa508300a228e5c674cd18e488a08a2b1c5fdebfa7` |

The two release rows are `httpx.Client` and `httpx.Client.proxies`. The one usage row is the recorded `httpx.Client` reference in `testclient.py:392`. Each row carries its bundle receipt ID. The export does not claim these files are original upstream tables; they are derived, reproducible RIN evidence tables.

The actual service table identifiers are `RIN_RELEASE.release_changes` and `RIN_USAGE.project_usage`. `SHOW LIGHTNING DATABASES` returned database IDs 805 and 806; these are database IDs, not opaque per-table registration IDs. The owner used the documented [File System upload](https://kbase.zetaris.com/knowledge/file-system-overview) and [File Source connection](https://kbase.zetaris.com/knowledge/connect) workflow. No per-table numeric registration ID was exposed by the read-only SQL responses.

The captured bounded source query is:

```sql
SELECT r.symbol, u.path, r.release_receipt_id, u.project_receipt_id
FROM RIN_RELEASE.release_changes r
JOIN RIN_USAGE.project_usage u ON r.symbol = u.symbol
LIMIT 10
```

`rin.zetaris_live.verify_live_capture` rechecks the captured schema, source identifiers, CSV hashes and rows, counts, JOIN hash and cited RIN bundle before graph use. `rin.zetaris_sources.validate_join` requires the exact qualified source IDs and SQL. Empty, forged or inconsistent results return `UNKNOWN`. The captured rows are reproducible local evidence, not a service-signed receipt.

Observed intersection is one row for `httpx.Client` and `testclient.py:392`. It corroborates the real-case `REVIEW` explanation; the recorded local PASS→TypeError differential remains independent. The accurate sponsor claim is **registered cross-source join over two local CSVs**, with heterogeneous remote federation unverified.
