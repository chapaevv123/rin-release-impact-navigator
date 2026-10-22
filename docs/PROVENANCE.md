# Development and source provenance

RIN application code was created in the recorded Open Agent Hackathon 2026 build window, beginning 2026-10-22 00:00 UTC. The first RIN code commit is `d8f58e6` at 2026-10-22 02:13 UTC. The concept, architecture research and frozen 12-case benchmark existed before the window; no RIN application code was found in that earlier package. The frozen benchmark remains 0/12 evaluated and is not used as a performance claim.

The `vendor/meterless-world-model` reference is pre-existing Apache-2.0 code from commit `1742dec56a66e58eef9dda2d2b865823758ca8cd`, with its license retained. Starlette/HTTPX source snapshots and the Flask changelog are upstream material with their included licenses. The local Starlette 0.36.3 / HTTPX 0.27.2 reproduction pin is explicitly not Starlette's upstream dependency declaration.

Cursor development evidence is [recorded separately](CURSOR_AGENT_EVIDENCE.md): owner-attested Agent use, independently reviewable code/test commit `e1cde63`, and a regression test for Skeptic coverage. Original Usage screenshots and a Cursor task/chat ID are unavailable locally. This record is not a claim about a Cursor runtime integration.

The saved Zetaris JOIN, Meterless graph and NVIDIA Nemotron receipt are linked from the [sponsor technology document](../SPONSOR_TECH.md). Their bounds are part of the claim: two registered local CSV sources, an in-memory graph, and one hosted model response retained as a hypothesis. No sponsor endorsement is implied.
