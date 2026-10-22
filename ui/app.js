const $ = id => document.getElementById(id);
let bundle = null;
let loadToken = 0;
let inspectorToken = 0;
let stageRecords = [];
let capturedSponsor = null;
let capturedModel = null;
let selectedHypothesis = null;
let selectedReleaseChange = null;
const text = (id, value) => { $(id).textContent = value ?? '—'; };
function node(tag, cls, value) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (value !== undefined) el.textContent = String(value);
  return el;
}
function renderSourceSnippet(receipt, span, stageId) {
  const container = $('inspector-span');
  container.replaceChildren();
  const snapshot = receipt.snapshot;
  const position = snapshot.indexOf(span);
  const lines = snapshot.split('\n');
  const selected = snapshot.slice(0, position).split('\n').length - 1;
  const appCall = stageId === 'use' ? lines.findIndex(line => line.includes('app=self.app,')) : -1;
  const indices = appCall > selected
    ? [selected, appCall - 1, appCall]
    : Array.from({length: Math.min(3, lines.length)}, (_, offset) => Math.max(0, Math.min(selected - 1, lines.length - 3)) + offset);
  let previous = -1;
  for (const index of indices) {
    if (index < 0 || index >= lines.length) continue;
    if (previous >= 0 && index > previous + 1) container.append(node('span', 'code-gap', '⋮  omitted source lines'));
    const row = node('span', 'code-line');
    if (index === selected) row.classList.add('selected');
    if (index === appCall) row.classList.add('related');
    row.append(node('span', 'line-no', `${index + 1}  `));
    const parts = lines[index].split(/(\bclass\b|\bdef\b|\breturn\b|\bself\b|\bhttpx\b|\bClient\b|\bTestClient\b|\bapp\b|\bTypeError\b)/g);
    for (const part of parts) {
      if (!part) continue;
      const cls = /^(class|def|return)$/.test(part) ? 'syntax-keyword'
        : /^(httpx|Client|TestClient|TypeError)$/.test(part) ? 'syntax-symbol'
        : /^(self|app)$/.test(part) ? 'syntax-variable' : '';
      row.append(node('span', cls, part));
    }
    container.append(row);
    previous = index;
  }
  return selected + 1;
}
function labelMode(b) {
  if (b.differential?.status === 'RECORDED_LOCAL_DIFFERENTIAL') return 'REPLAY · REAL PROJECT + RECORDED LOCAL RUN';
  const z = b.sponsors?.zetaris || '';
  const m = b.sponsors?.meterless || '';
  if (z.startsWith('PASS') && m.startsWith('PASS')) return 'REPLAY · CAPTURED LOCAL SPONSOR CALLS';
  return 'REPLAY · OFFLINE ANALYSIS';
}
function displayReceipt(r) {
  const span = r.exact_span_or_line;
  const pos = span ? r.snapshot.indexOf(span) : -1;
  const excerpt = pos >= 0 ? r.snapshot.slice(Math.max(0, pos - 230), pos + Math.max(span.length, 80) + 230) : r.snapshot.slice(0, 900);
  $('receipt-detail').textContent = JSON.stringify({
    receipt_id: r.receipt_id, source_type: r.source_type,
    source: r.source_url_or_local_reference, version: r.source_commit_or_version,
    sha256: r.content_hash_sha256, captured_utc: r.capture_timestamp_utc,
    tool: r.tool, verification: r.verification_status,
    excerpt: excerpt + (r.snapshot.length > excerpt.length ? '\n[…see downloaded JSON for full snapshot]' : '')
  }, null, 2);
  $('receipt-dialog').showModal();
}
function displayCaptured(title, record) {
  $('receipt-detail').textContent = JSON.stringify({label: title, ...record}, null, 2);
  $('receipt-dialog').showModal();
}
async function loadCapturedSponsor(token) {
  const panel = $('captured-sponsor');
  panel.hidden = false;
  $('open-join-receipt').disabled = true;
  $('open-graph-receipt').disabled = true;
  text('captured-sponsor-summary', 'Loading captured query evidence.');
  try {
    const [joinResponse, graphResponse] = await Promise.all([
      fetch('../artifacts/zetaris_live_join_receipt.json', {cache:'no-store'}),
      fetch('../artifacts/zetaris_live_e2e_receipt.json', {cache:'no-store'})
    ]);
    if (!joinResponse.ok || !graphResponse.ok) throw new Error('receipt missing');
    const [join, e2e] = await Promise.all([joinResponse.json(), graphResponse.json()]);
    if (token !== loadToken) return;
    const row = join.join?.rows?.[0];
    const linked = join.status === 'CROSS_SOURCE_JOIN_VERIFIED'
      && join.join?.http_status === 200 && join.join.rows.length === 1
      && row?.[0] === 'httpx.Client' && row?.[1] === 'testclient.py:392'
      && e2e.source_query_id === join.join.query_id
      && e2e.decision?.graph_used === true && e2e.decision?.verdict === 'REVIEW';
    if (!linked) throw new Error('captured receipts disagree');
    capturedSponsor = {join, e2e};
    renderReplays();
    text('captured-sponsor-summary', `SQL query ${join.join.query_id} returned 1 cited httpx.Client usage at testclient.py:392. Meterless graph next action: ${e2e.decision.next_action.replaceAll('_', ' ')}.`);
    $('open-join-receipt').disabled = false;
    $('open-graph-receipt').disabled = false;
    $('trace-zetaris').disabled = false;
    $('trace-meterless').disabled = false;
    $('trace-zetaris').querySelector('em').textContent = 'LIVE-CAPTURED / REPLAY';
    $('trace-meterless').querySelector('em').textContent = 'GRAPH VERIFIED / REPLAY';
    $('trace-zetaris').querySelector('.sponsor-description').textContent = 'One cited use-site row · local CSV JOIN';
    $('trace-meterless').querySelector('.sponsor-description').textContent =
      `Next: ${e2e.decision.next_action.replaceAll('_', ' ').toLowerCase()}`;
    $('trace-zetaris').onclick = () => $('open-join-receipt').click();
    $('trace-meterless').onclick = () => $('open-graph-receipt').click();
    $('open-join-receipt').onclick = () => displayCaptured('CAPTURED LIVE ZETARIS QUERY / REPLAY', {
      source_ids: join.join.source_ids, sql: join.join.sql, captured_at_utc: join.captured_at_utc,
      query_id: join.join.query_id, rows: join.join.rows, result_sha256: join.join.result_sha256,
      capture_sha256: join.capture_sha256
    });
    $('open-graph-receipt').onclick = () => displayCaptured('CAPTURED METERLESS GRAPH / REPLAY', {
      source_query_id: e2e.source_query_id, decision: e2e.decision,
      graph: e2e.meterless_graph, graph_output_sha256: e2e.graph_output_sha256
    });
  } catch (_) {
    if (token === loadToken) {
      capturedSponsor = null;
      renderReplays();
      text('captured-sponsor-summary', 'Captured sponsor evidence unavailable or inconsistent. No sponsor conclusion is shown.');
      for (const id of ['trace-zetaris','trace-meterless']) $(id).querySelector('.sponsor-description').textContent = 'Evidence unavailable';
    }
  }
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}
async function sha256(value) {
  const data = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}
async function loadCapturedModel(token, b) {
  const panel = $('captured-model');
  panel.hidden = false;
  $('open-model-receipt').disabled = true;
  text('captured-model-summary', 'Checking captured model receipt.');
  try {
    const [modelResponse, graphResponse] = await Promise.all([
      fetch('../artifacts/nemotron_owner_key_inference_receipt.json', {cache:'no-store'}),
      fetch('../artifacts/zetaris_live_e2e_receipt.json', {cache:'no-store'})
    ]);
    if (!modelResponse.ok || !graphResponse.ok) throw new Error('receipt missing');
    const [record, e2e] = await Promise.all([modelResponse.json(), graphResponse.json()]);
    if (token !== loadToken) return;
    const {receipt_sha256, ...body} = record;
    const proposal = record.citation_validation?.proposal;
    const cited = proposal?.source_receipt_ids?.length === 2
      && proposal.source_receipt_ids.every((id, index) => {
        const source = b.receipts?.find(item => item.receipt_id === id);
        return source?.snapshot?.includes(proposal.exact_source_spans?.[index]);
      });
    const verified = record.status === 'HTTP_200_INFERENCE' && record.http_status === 200
      && record.response_model_id === 'nvidia/nemotron-3.5-lightning-30b-a3b'
      && record.citation_validation?.state === 'HYPOTHESIS'
      && record.deterministic_verdict === 'REVIEW' && e2e.decision?.verdict === 'REVIEW'
      && record.citation_validation?.source_query_id === e2e.source_query_id
      && proposal?.changed_symbol === 'httpx.Client' && cited
      && receipt_sha256 === await sha256(JSON.stringify(canonical(body)))
      && record.response_sha256 === await sha256(record.response_text);
    if (!verified) throw new Error('model receipt failed local checks');
    capturedModel = record;
    renderReplays();
    text('captured-model-summary', `${record.response_model_id} proposed: ${proposal.proposed_impact} RIN retained it as HYPOTHESIS; the separately checked verdict is REVIEW.`);
    $('open-model-receipt').disabled = false;
    $('trace-model').disabled = false;
    $('trace-model').querySelector('em').textContent = `HYPOTHESIS / REPLAY · ${record.usage.total_tokens} TOKENS`;
    $('trace-model').querySelector('.sponsor-description').textContent =
      `Saved HTTP ${record.http_status} · cited model proposal`;
    $('trace-model').onclick = () => $('open-model-receipt').click();
    $('open-model-receipt').onclick = () => displayCaptured('CAPTURED NVIDIA MODEL OUTPUT / REPLAY', {
      http_status: record.http_status, model_id: record.response_model_id, captured_at_utc: record.at_utc,
      response_text: record.response_text,
      hypothesis: proposal, citation_gate: record.citation_validation.state,
      skeptic_challenges: record.citation_validation.skeptic_challenges,
      source_query_id: record.citation_validation.source_query_id,
      deterministic_verdict: record.deterministic_verdict, usage: record.usage,
      response_sha256: record.response_sha256, receipt_sha256: record.receipt_sha256
    });
  } catch (_) {
    if (token === loadToken) {
      capturedModel = null;
      renderReplays();
      text('captured-model-summary', 'Model receipt unavailable or inconsistent. No model contribution is claimed.');
      $('trace-model').querySelector('.sponsor-description').textContent = 'Evidence unavailable';
    }
  }
}
function buildStageRecords(b) {
  const get = type => b.receipts?.find(item => item.source_type === type);
  const release = get('PUBLIC_RELEASE_SNAPSHOT');
  const source = get('PROJECT_CODE');
  const runtime = b.receipts?.find(item => item.receipt_id === b.differential?.new?.receipt_id);
  const change = b.hypotheses?.[0]?.release_change || '';
  const use = b.findings?.[0]?.usage?.[0];
  const sourceLine = use && source?.snapshot?.split('\n')[use.line - 1]?.trim();
  const error = b.differential?.new?.exception_message || '';
  return [
    {id:'release', title:'Release change', value:`${b.dependency || 'Unknown'} ${b.new_version || '—'}`,
      context:'Pinned dependency release note', span:change, receipt:release,
      limit:'The release note alone does not prove project impact.'},
    {id:'api', title:'Changed API surface', value:b.findings?.[0]?.symbol || 'Unconfirmed symbol',
      context:'Changed symbol inferred from the cited release span', span:change, receipt:release,
      limit:'A symbol match still needs a verified project use site.'},
    {id:'use', title:'Project use site', value:use ? `${use.file}:${use.line}` : 'Usage unverified',
      context:'Project source at the recorded use site', span:sourceLine || '', receipt:source,
      limit:b.manifest_provenance === 'LOCAL_REPRODUCTION_PIN_NOT_UPSTREAM_MANIFEST'
        ? 'The 0.27.2 pin is a local reproduction input, not Starlette’s upstream manifest.'
        : 'Fixture or incomplete project coverage cannot establish universal impact.'},
    {id:'runtime', title:'Differential check', value:b.differential?.status === 'RECORDED_LOCAL_DIFFERENTIAL'
      ? `${b.differential.old.outcome} → ${b.differential.new.exception_type}` : 'Not demonstrated',
      context:'Recorded local old/new constructor run', span:error, receipt:runtime,
      limit:'The selected constructor behavior does not cover every application path.'},
    {id:'decision', title:'Bounded decision', value:b.verdict || 'UNKNOWN',
      context:b.reason || 'No supported verdict', span:error, receipt:runtime,
      limit:`Scope: ${b.scope || 'unverified'}. Target CI review remains necessary.`},
  ];
}
async function inspectStage(id) {
  const token = ++inspectorToken;
  const stage = stageRecords.find(item => item.id === id);
  document.querySelectorAll('.canvas-stage').forEach(button =>
    button.setAttribute('aria-pressed', String(button.dataset.stage === id)));
  if (!stage) {
    text('inspector-status', 'UNKNOWN');
    text('inspector-heading', 'Evidence unavailable');
    text('inspector-context', 'Select a case with checkable receipts.');
    for (const key of ['span','source','receipt','sha','file','line']) text(`inspector-${key}`, '—');
    text('inspector-provenance', 'Provenance unavailable.');
    text('inspector-limit', 'No project impact claim can be inspected.');
    $('inspector-open').disabled = true;
    return;
  }
  text('inspector-status', 'CHECKING HASH');
  text('inspector-heading', stage.title);
  text('inspector-context', stage.context);
  text('inspector-limit', stage.limit);
  text('inspector-file', stage.receipt?.source_url_or_local_reference?.split('/').pop() || 'SOURCE UNAVAILABLE');
  text('inspector-line', 'Checking line');
  $('inspector-open').disabled = true;
  const receipt = stage.receipt;
  const valid = !!(bundle?.verification?.ok && receipt?.snapshot && stage.span
    && receipt.snapshot.includes(stage.span)
    && receipt.content_hash_sha256 === await sha256(receipt.snapshot));
  if (token !== inspectorToken) return;
  text('inspector-status', valid ? (id === 'decision' ? `${bundle.verdict} · BOUNDED` : 'VERIFIED RECEIPT') : 'UNKNOWN');
  if (valid) {
    const line = renderSourceSnippet(receipt, stage.span, id);
    text('inspector-line', `Line ${line}`);
  } else {
    text('inspector-span', 'No checkable source span for this stage.');
    text('inspector-line', 'UNAVAILABLE');
  }
  text('inspector-source', valid ? receipt.source_url_or_local_reference : 'UNAVAILABLE');
  text('inspector-receipt', valid ? receipt.receipt_id : '—');
  text('inspector-sha', valid ? receipt.content_hash_sha256 : '—');
  text('inspector-provenance', valid
    ? `Version: ${receipt.source_commit_or_version || 'unavailable'} · Captured: ${receipt.capture_timestamp_utc || 'unavailable'}`
    : 'Provenance unavailable.');
  text('canvas-caption', valid ? `${stage.title}: ${stage.limit}` : `${stage.title}: evidence unavailable`);
  if (valid) {
    $('inspector-open').disabled = false;
    $('inspector-open').onclick = () => displayReceipt(receipt);
  }
}
function renderCanvas(b) {
  stageRecords = buildStageRecords(b);
  for (const stage of stageRecords) {
    text(`canvas-${stage.id}`, stage.value);
    const button = document.querySelector(`.canvas-stage[data-stage="${stage.id}"]`);
    button.querySelector('.stage-state').textContent = stage.receipt && stage.span
      ? (stage.id === 'decision' ? `VERDICT / ${b.verdict}` : 'SOURCE RECEIPT') : 'UNKNOWN';
  }
  text('note-release', b.hypotheses?.[0]?.release_change || 'Change unavailable');
  text('note-api', b.findings?.[0]?.symbol || 'Symbol unverified');
  text('note-use', b.findings?.[0]?.usage?.[0] ? `${b.findings[0].usage[0].file}:${b.findings[0].usage[0].line}` : 'Use site unavailable');
  text('note-runtime', b.differential?.status === 'RECORDED_LOCAL_DIFFERENTIAL' ? `${b.differential.old.outcome} → ${b.differential.new.exception_type}` : 'No recorded differential');
  text('note-decision', b.reason || 'Reason unavailable');
  inspectStage('use');
}
function render(b) {
  bundle = b;
  $('download').disabled = false;
  $('evidence-download').disabled = false;
  text('mode-label', labelMode(b));
  text('verdict', b.verdict);
  text('verdict-reason', b.reason);
  text('scope', b.scope);
  text('project', b.project?.split(' (')[0] || 'UNAVAILABLE');
  text('case-number', $('case-select').value === 'real' ? '002' : '001');
  const real = b.manifest_provenance === 'LOCAL_REPRODUCTION_PIN_NOT_UPSTREAM_MANIFEST';
  text('case-summary', real && b.differential?.status === 'RECORDED_LOCAL_DIFFERENTIAL'
    ? `HTTPX ${b.new_version} removed app=. Starlette TestClient still passes it. Isolated check: ${b.differential.old.outcome} → ${b.differential.new.exception_type}.`
    : `A recorded release change intersects the listed project code. RIN recommends ${b.verdict} within the captured evidence scope.`);
  text('footer-provenance', real ? 'Real public code · Local reproduction pin · No universal safety claim'
    : 'Synthetic project fixture · Captured local sponsor calls · No universal safety claim');
  const hypotheses = $('hypotheses'); hypotheses.replaceChildren();
  for (const h of b.hypotheses || []) {
    const wrap = node('button', 'hypothesis');
    wrap.type = 'button';
    wrap.addEventListener('click', () => { selectedHypothesis = h.hypothesis_id; location.hash = '#/hypotheses'; renderHypotheses(); });
    wrap.classList.add(`state-${h.state.toLowerCase()}`);
    wrap.append(node('span', 'item-label', h.hypothesis_id), node('strong', '', h.testable_claim),
      node('span', 'state', h.state), node('p', '', h.next_action));
    hypotheses.append(wrap);
  }
  const blinds = $('blind-spots'); blinds.replaceChildren();
  for (const reason of b.unknown_reasons || []) blinds.append(node('li', '', reason.replaceAll('_', ' ')));
  if (!b.unknown_reasons?.length) blinds.append(node('li', '', 'None recorded in stated scope'));
  const list = $('receipts'); list.replaceChildren();
  for (const [index, r] of (b.receipts || []).entries()) {
    const button = node('button', 'receipt');
    button.type = 'button';
    button.append(node('span', 'num', String(index + 1).padStart(2, '0') + ' / SNAPSHOT'),
      node('strong', '', r.source_type.replaceAll('_', ' ')),
      node('code', '', r.content_hash_sha256.slice(0, 24) + '…'));
    button.addEventListener('click', () => displayReceipt(r));
    button.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        button.click();
      }
    });
    list.append(button);
  }
  text('receipt-count', `${b.receipts?.length || 0} checkable receipts · SHA-256 · verify with RIN CLI`);
  const timeline = $('timeline'); timeline.replaceChildren();
  for (const event of b.timeline || []) timeline.append(node('li', '', event.event.replaceAll('_', ' ')));
  renderCanvas(b);
  renderRoutes(b);
}
function route() {
  const name = location.hash.match(/^#\/(home|investigation|releases|evidence|hypotheses|replays)$/)?.[1] || 'investigation';
  document.querySelectorAll('[data-view]').forEach(view => { view.hidden = view.dataset.view !== name; });
  document.querySelectorAll('[data-route]').forEach(link => {
    const active = link.dataset.route === name;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  document.title = `RIN — ${name[0].toUpperCase()}${name.slice(1)}`;
  window.scrollTo(0, 0);
}
function addDetail(parent, label, value) {
  const row = node('div', 'detail-row');
  row.append(node('span', 'route-kicker', label), node('p', '', value ?? 'Unavailable'));
  parent.append(row);
}
function receiptButton(r, label = r.source_type.replaceAll('_', ' ')) {
  const button = node('button', 'route-item');
  button.type = 'button';
  button.append(node('span', 'route-kicker', r.verification_status || 'UNKNOWN'), node('strong', '', label),
    node('code', '', r.receipt_id || 'Receipt ID unavailable'),
    node('span', 'route-item-foot', r.source_url_or_local_reference || 'Source unavailable'));
  button.addEventListener('click', () => displayReceipt(r));
  return button;
}
function renderHome(b) {
  text('home-case', `${b.project || 'Unknown project'} / ${b.dependency || 'Unknown dependency'}`);
  text('home-summary', `${b.old_version || 'Unknown'} → ${b.new_version || 'Unknown'}. ${b.reason || 'No evidence-backed reason available.'}`);
  text('home-verdict', b.verification?.ok ? b.verdict : 'UNKNOWN');
  text('home-reason', b.verification?.ok ? b.reason : 'Evidence verification unavailable.');
  text('home-scope', b.scope || 'Scope unavailable');
  text('home-receipts', String(b.receipts?.length ?? '—'));
  text('home-hypotheses', String(b.hypotheses?.length ?? '—'));
  text('home-mode', labelMode(b));
}
function renderReleases(b) {
  const release = b.receipts?.find(r => r.source_type === 'PUBLIC_RELEASE_SNAPSHOT');
  text('release-versions', `${b.dependency || 'Unknown'} ${b.old_version || '?'} → ${b.new_version || '?'}`);
  text('release-provenance', `Selected project: ${b.project || 'Unknown'}. ${b.manifest_provenance?.replaceAll('_', ' ') || 'Manifest provenance unavailable'}.`);
  const changes = [...new Map((b.hypotheses || []).filter(h => h.release_change)
    .map(h => [h.release_change, h])).values()];
  const list = $('release-list'); list.replaceChildren();
  if (!changes.some(h => h.release_change === selectedReleaseChange)) selectedReleaseChange = changes[0]?.release_change || null;
  for (const h of changes) {
    const button = node('button', 'release-change'); button.type = 'button';
    button.setAttribute('aria-pressed', String(h.release_change === selectedReleaseChange));
    button.append(node('span', 'route-kicker', h.state), node('strong', '', h.potentially_affected_symbol || 'Symbol unavailable'), node('span', '', h.release_change));
    button.onclick = () => { selectedReleaseChange = h.release_change; renderReleases(b); };
    list.append(button);
  }
  const selected = changes.find(h => h.release_change === selectedReleaseChange);
  text('release-symbol', selected?.potentially_affected_symbol || 'Unverified');
  text('release-change', selected?.release_change || 'No cited release change available.');
  const use = selected?.project_usage?.[0];
  text('release-use', use ? `${use.symbol} at ${use.file}:${use.line} · receipt ${use.receipt_id}` : 'No verified direct use site for this change in the selected source scope.');
  text('release-limit', selected?.next_action || b.scope || 'Impact scope unavailable.');
  $('release-receipt').disabled = !release;
  $('release-receipt').onclick = release ? () => displayReceipt(release) : null;
}
async function renderEvidence(b) {
  const token = loadToken;
  const list = $('evidence-list'); list.replaceChildren();
  text('evidence-count', `${b.receipts?.length || 0} recorded source receipts`);
  text('evidence-verification', b.verification?.ok
    ? `Bundle verification: ${b.verification.receipt_count} receipts, ${b.verification.problems?.length || 0} reported problems. Local SHA-256 checks are running below.`
    : 'Bundle verification did not pass. Treat the conclusion as UNKNOWN.');
  for (const r of b.receipts || []) {
    const card = receiptButton(r);
    const hash = node('code', 'route-hash', r.content_hash_sha256 || 'SHA-256 unavailable');
    const check = node('span', 'route-check', 'CHECKING SHA-256');
    card.append(hash, check); list.append(card);
    sha256(r.snapshot || '').then(digest => {
      if (token !== loadToken) return;
      check.textContent = digest === r.content_hash_sha256 && b.verification?.ok ? 'LOCAL HASH MATCH' : 'UNVERIFIED / UNKNOWN';
    }).catch(() => { if (token === loadToken) check.textContent = 'HASH CHECK UNAVAILABLE'; });
  }
}
function renderHypotheses() {
  const b = bundle;
  const list = $('hypothesis-list'), detail = $('hypothesis-detail');
  list.replaceChildren(); detail.replaceChildren();
  if (!b?.hypotheses?.length) { detail.append(node('p', '', 'No recorded hypotheses available.')); return; }
  const selected = b.hypotheses.find(h => h.hypothesis_id === selectedHypothesis) || b.hypotheses[0];
  selectedHypothesis = selected.hypothesis_id;
  for (const h of b.hypotheses) {
    const button = node('button', 'route-item hypothesis-choice'); button.type = 'button';
    button.setAttribute('aria-pressed', String(h.hypothesis_id === selectedHypothesis));
    button.append(node('span', 'route-kicker', `${h.hypothesis_id} / ${h.state}`), node('strong', '', h.testable_claim));
    button.onclick = () => { selectedHypothesis = h.hypothesis_id; renderHypotheses(); };
    list.append(button);
  }
  detail.append(node('span', 'route-kicker', `${selected.hypothesis_id} / ${selected.state}`), node('h2', '', selected.testable_claim));
  addDetail(detail, 'PROPOSED CHECK', selected.proposed_check);
  addDetail(detail, 'SUPPORTING RECEIPTS', selected.supporting_receipt_ids?.join(', ') || 'None recorded');
  addDetail(detail, 'CONTRADICTING RECEIPTS', selected.contradicting_receipt_ids?.join(', ') || 'None recorded');
  addDetail(detail, 'CASE-LEVEL SKEPTIC CHALLENGES', b.skeptic?.challenges?.join(' · ') || 'Unavailable');
  addDetail(detail, 'NEXT ACTION', selected.next_action);
  const links = node('div', 'detail-links');
  for (const id of new Set([...(selected.supporting_receipt_ids || []), ...(selected.contradicting_receipt_ids || [])])) {
    const r = b.receipts?.find(item => item.receipt_id === id);
    if (r) { const button = node('button', 'route-link', `Open ${id} →`); button.type = 'button'; button.onclick = () => displayReceipt(r); links.append(button); }
  }
  detail.append(links);
}
function replayButton(title, status, summary, click) {
  const button = node('button', 'route-item replay-item'); button.type = 'button'; button.disabled = !click;
  button.append(node('span', 'route-kicker', status), node('strong', '', title), node('p', '', summary));
  if (click) button.onclick = click;
  return button;
}
function renderReplays() {
  const list = $('replay-list'); list.replaceChildren();
  const real = $('case-select').value === 'real';
  list.append(
    replayButton('Zetaris / registered-source SQL JOIN', real && capturedSponsor ? 'LIVE-CAPTURED / DISPLAYED IN REPLAY' : 'UNAVAILABLE IN SELECTED CASE',
      real && capturedSponsor ? `Query ${capturedSponsor.join.join.query_id} · ${capturedSponsor.join.join.rows.length} cited row` : 'No verified captured JOIN for this case.',
      real && capturedSponsor ? () => $('open-join-receipt').click() : null),
    replayButton('Meterless / impact graph', real && capturedSponsor ? 'GRAPH VERIFIED / REPLAY' : 'UNAVAILABLE IN SELECTED CASE',
      real && capturedSponsor ? `Next action: ${capturedSponsor.e2e.decision.next_action.replaceAll('_', ' ')}` : 'No verified saved graph for this case.',
      real && capturedSponsor ? () => $('open-graph-receipt').click() : null),
    replayButton('NVIDIA Nemotron / model hypothesis', real && capturedModel ? 'HYPOTHESIS / REPLAY' : 'UNAVAILABLE IN SELECTED CASE',
      real && capturedModel ? `Saved HTTP ${capturedModel.http_status} · ${capturedModel.usage.total_tokens} usage tokens · deterministic verdict ${capturedModel.deterministic_verdict}` : 'No verified saved model output for this case.',
      real && capturedModel ? () => $('open-model-receipt').click() : null)
  );
}
function renderRoutes(b) { renderHome(b); renderReleases(b); renderEvidence(b); renderHypotheses(); renderReplays(); }
window.addEventListener('hashchange', route);
route();
$('canvas-track').addEventListener('click', event => {
  const stage = event.target.closest('.canvas-stage');
  if (stage) inspectStage(stage.dataset.stage);
});
$('canvas-track').addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') {
    const active = event.target.closest('.canvas-stage');
    if (active) {
      event.preventDefault();
      inspectStage(active.dataset.stage);
    }
    return;
  }
  if (!['ArrowLeft','ArrowRight'].includes(event.key)) return;
  const active = event.target.closest('.canvas-stage');
  if (!active) return;
  event.preventDefault();
  const buttons = [...document.querySelectorAll('.canvas-stage')];
  const index = buttons.indexOf(active);
  const next = buttons[(index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length];
  next.focus();
  inspectStage(next.dataset.stage);
});
$('download').addEventListener('click', () => {
  if (!bundle) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], {type:'application/json'}));
  const link = document.createElement('a');
  link.href = url; link.download = 'rin-evidence-bundle.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.querySelector('[data-focus-canvas]').addEventListener('click', event => {
  event.preventDefault();
  $('impact-canvas').scrollIntoView({behavior:'smooth', block:'start'});
  document.querySelector('.canvas-stage')?.focus({preventScroll:true});
});
$('evidence-download').addEventListener('click', () => $('download').click());
$('close-dialog').addEventListener('click', () => $('receipt-dialog').close());
let canvasZoom = 1;
function setCanvasZoom(value) {
  canvasZoom = Math.max(.8, Math.min(1.4, value));
  $('canvas-track').style.zoom = canvasZoom;
  document.querySelector('.stage-notes').style.zoom = canvasZoom;
}
$('zoom-in').addEventListener('click', () => setCanvasZoom(canvasZoom + .1));
$('zoom-out').addEventListener('click', () => setCanvasZoom(canvasZoom - .1));
$('fit').addEventListener('click', () => { setCanvasZoom(1); $('canvas-viewport').scrollLeft = 0; });
function setCanvasMode(mode) {
  $('canvas-viewport').classList.toggle('timeline-mode', mode === 'timeline');
  $('graph-mode').setAttribute('aria-pressed', String(mode === 'graph'));
  $('timeline-mode').setAttribute('aria-pressed', String(mode === 'timeline'));
  setCanvasZoom(1);
}
$('graph-mode').addEventListener('click', () => setCanvasMode('graph'));
$('timeline-mode').addEventListener('click', () => setCanvasMode('timeline'));
const cases = {real: '../artifacts/starlette_httpx_028_bundle.json', sponsor: '../artifacts/flask_3_1_e2e_bundle.json'};
function loadCase(name) {
  const token = ++loadToken;
  inspectorToken++;
  stageRecords = [];
  capturedSponsor = null;
  capturedModel = null;
  selectedHypothesis = null;
  selectedReleaseChange = null;
  $('download').disabled = true;
  $('evidence-download').disabled = true;
  renderReplays();
  $('captured-sponsor').hidden = true;
  $('captured-model').hidden = true;
  for (const id of ['trace-model','trace-zetaris','trace-meterless']) {
    $(id).disabled = true;
    $(id).querySelector('em').textContent = name === 'real' ? 'CHECKING RECEIPT' : 'NOT IN THIS CASE';
    $(id).querySelector('.sponsor-description').textContent = name === 'real'
      ? 'Checking saved evidence…' : 'No captured receipt for this case';
  }
  text('mode-label', 'LOADING EVIDENCE');
  fetch(cases[name], {cache:'no-store'})
  .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
  .then(value => { if (token === loadToken) render(value); })
  .then(() => { if (token === loadToken && name === 'real') {
    loadCapturedSponsor(token);
    loadCapturedModel(token, bundle);
  } })
  .catch(error => {
    if (token !== loadToken) return;
    bundle = null;
    capturedSponsor = null;
    capturedModel = null;
    stageRecords = [];
    inspectStage('none');
    $('captured-sponsor').hidden = true;
    $('captured-model').hidden = true;
    text('mode-label', 'EVIDENCE UNAVAILABLE');
    text('verdict', 'UNKNOWN');
    text('verdict-reason', `Evidence bundle could not be loaded (${error.message}). Run the local investigation and refresh.`);
    text('scope', 'No claim can be verified without a bundle.');
    text('case-summary', 'The selected evidence bundle is unavailable. No project impact claim is shown.');
    for (const id of ['project', 'receipt-count', 'note-release', 'note-api', 'note-use', 'note-runtime', 'note-decision']) text(id, '—');
    for (const id of ['hypotheses', 'blind-spots', 'receipts', 'timeline']) $(id).replaceChildren();
    for (const id of ['evidence-list', 'hypothesis-list', 'hypothesis-detail', 'release-list']) $(id).replaceChildren();
    for (const id of ['home-verdict', 'release-symbol', 'evidence-count']) text(id, 'UNKNOWN');
    for (const id of ['home-case', 'home-summary', 'home-reason', 'home-scope', 'home-receipts',
      'home-hypotheses', 'home-mode', 'release-versions', 'release-provenance', 'release-change',
      'release-use', 'release-limit']) text(id, 'Evidence unavailable for selected case.');
    text('evidence-verification', 'Bundle unavailable. No receipt can be verified.');
    $('release-receipt').disabled = true;
    renderReplays();
  });
}
$('case-select').addEventListener('change', event => loadCase(event.target.value));
loadCase($('case-select').value);
