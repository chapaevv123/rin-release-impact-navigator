import { readFileSync } from "node:fs";
import { WorldModel } from "./vendor/meterless-world-model/src/index.ts";

// Reference implementation from Meterless/Meterless commit
// 1742dec56a66e58eef9dda2d2b865823758ca8cd (Apache-2.0; see vendor LICENSE).
const bundlePath = process.argv[2];
if (!bundlePath) throw new Error("usage: node meterless_graph.ts BUNDLE_JSON");
const bundle = JSON.parse(readFileSync(bundlePath, "utf8"));
const joinPath = process.argv[3];
const joinReceipt = joinPath ? JSON.parse(readFileSync(joinPath, "utf8")) : null;
if (joinReceipt && (joinReceipt.status !== "CROSS_SOURCE_JOIN_VERIFIED"
  || joinReceipt.source_validation?.verdict !== "REVIEW"
  || !joinReceipt.join?.query_id || !Array.isArray(joinReceipt.join?.rows))) {
  throw new Error("registered source join receipt is not verified");
}
const at = new Date();
const source = { kind: joinReceipt ? "rin-bundle-and-zetaris-join" : "rin-verified-receipt-bundle", at };
const world = new WorldModel({ storage: "memory", namespace: "rin-investigation-v1" });
const project = await world.upsertEntity({
  type: "project", externalKey: { system: "rin", id: bundle.project },
  attrs: { name: bundle.project, inputHash: bundle.input_hash_sha256 }, source,
});
const release = await world.upsertEntity({
  type: "release", externalKey: { system: "pypi", id: `${bundle.dependency}-${bundle.new_version}` },
  attrs: { dependency: bundle.dependency, version: bundle.new_version,
    receiptId: bundle.receipts[0].receipt_id }, source,
});
const graphFindings: Array<{symbol: string; usageCount: number; evidenceIds: string[]}> = [];
for (const finding of bundle.findings) {
  const verifiedSourceRows = joinReceipt ? joinReceipt.join.rows.filter((row: unknown) =>
    Array.isArray(row) && row.length === 4 && row[0] === finding.symbol
      && finding.usage.some((usage: {file: string; line: number; receipt_id: string}) =>
        row[1] === `${usage.file}:${usage.line}` && row[3] === usage.receipt_id)
      && finding.receipt_ids.includes(row[2]) && finding.receipt_ids.includes(row[3])) : [];
  if (joinReceipt && !verifiedSourceRows.length) continue;
  const symbol = await world.upsertEntity({
    type: "symbol", externalKey: { system: "python", id: finding.symbol },
    attrs: { name: finding.symbol }, source,
  });
  await world.relate({ from: release.id, to: symbol.id, type: "changes", source });
  await world.relate({ from: project.id, to: symbol.id, type: "uses", source });
  const changed = await world.view("graph").neighborsOf(release.id, { via: "changes" });
  const used = await world.view("graph").neighborsOf(project.id, { via: "uses" });
  if (!changed.some(x => x.id === symbol.id) || !used.some(x => x.id === symbol.id)) {
    throw new Error("World Model graph failed to return evidence intersection");
  }
  graphFindings.push({ symbol: finding.symbol, usageCount: finding.usage.length,
    evidenceIds: joinReceipt ? [...finding.receipt_ids, `zetaris:query:${joinReceipt.join.query_id}`]
      : finding.receipt_ids });
}
const differentialRecorded = bundle.differential?.status === "RECORDED_LOCAL_DIFFERENTIAL";
const nextAction = !graphFindings.length ? "INVESTIGATE_MISSING_USAGE"
  : differentialRecorded ? "REVIEW_FAILED_DIFFERENTIAL_IN_TARGET_CI" : "VERIFY_DIFFERENTIAL_BEHAVIOR";
console.log(JSON.stringify({ model: "Meterless World Model reference 0.1.0", releaseId: release.id,
  projectId: project.id, graphFindings, nextAction, readAfterWrite: true,
  sourceJoinQueryId: joinReceipt?.join.query_id ?? null,
  sourceJoinResultSha256: joinReceipt?.join.result_sha256 ?? null,
  sourceMode: joinReceipt ? "REGISTERED_LOCAL_CSV_JOIN" : "BUNDLE_ONLY",
  hypothesisBefore: bundle.hypotheses.map((h: {hypothesis_id: string; state: string}) =>
    ({id: h.hypothesis_id, state: h.state})),
  verdictConstraint: graphFindings.length ? "REVIEW_OR_UNKNOWN" : "UNKNOWN",
  at: at.toISOString() }));
