# Architecture

RIN is one bounded investigation loop. `rin.core` owns source and requirements snapshots, direct pin validation, AST usage, hypothesis states, receipt hashing, independent bundle verification and fail-closed verdicts. `rin.e2e` invokes the local Zetaris SQL adapter, then the Meterless graph. The UI reads the resulting immutable JSON bundle; it does not possess sponsor credentials.

## State transitions

`PROPOSED → TESTING → SUPPORTED | REFUTED | UNRESOLVED`. For the Flask fixture, the release claim proposes a usage check; line 6 of the synthetic project confirms usage, changes the hypothesis to `SUPPORTED`, and changes the next step to differential behavior verification. The Meterless graph read returns the same next step. Missing dynamic-path evidence leaves typed blind spots visible.

For the real Starlette case, the direct `httpx.Client` hypothesis is `SUPPORTED`, the direct `proxies` usage claim is `REFUTED` in the inspected source, and a separate dynamic-path hypothesis remains `UNRESOLVED`. The recorded old/new constructor run supports a bounded `REVIEW`. A local Meterless graph read on this same case selects a CI review of the already failed differential instead of requesting the differential again. Its output is an in-memory next-action receipt, not a new behavioral test.

## Receipt contract

Each receipt stores type, source reference, SHA-256 of the raw snapshot, source version or commit, exact span, UTC capture time, tool, result and verification status. `rin verify` recomputes hashes and checks citation IDs. Local snapshot integrity does not prove upstream content remained unchanged; pinned upstream URLs and commits are also recorded.

## Verdict limits

`REVIEW` means a reported change intersects static usage and merits human review. `UNKNOWN` means required evidence is missing or a sponsor check failed. `NO_ACTION` is rejected by the current verifier because static absence cannot establish full application safety. No automatic update is performed.

## Boundaries

- Zetaris auth remains server-side and is sent to the existing local container only via stdin to a transient process. No token is included in UI or bundle.
- Meterless reference code runs in memory for one investigation. A durable graph and provenance replay remain future work.
- Recorded release and project snapshots are plainly labeled; the UI replay makes no fresh external call.
- The synthetic project does not represent a real customer repository.
- Two CSVs exported from verified real-case receipts were registered as distinct Zetaris file sources. A bounded read-only JOIN returned one cited use-site row; the saved query and source IDs are in [the JOIN receipt](artifacts/zetaris_live_join_receipt.json). The sources are local CSVs derived from one pinned bundle, so heterogeneous remote federation is unproven. The source-join validator remains fail-closed; see [source plan](docs/ZETARIS_SOURCE_PLAN.md).
