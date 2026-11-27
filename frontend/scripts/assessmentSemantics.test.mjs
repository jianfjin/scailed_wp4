import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/assessmentSemantics.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { projectAssessmentSemantics } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

const finding = { capability_id: 'secure-processing', judgment: 'unknown', source: 'self_reported', verification_status: 'unverified', answer_ids: ['q1'], evidence_refs: [] };
const base = {
  session: { result_id: 'result-1', answer_revision: 3 },
  readiness_snapshot: { capability_findings: { 'secure-processing': finding } },
  recommended_path: { profile_id: 'evidence-v2', status: 'degraded', recommendation_kind: 'conditional_direction', missing_information: ['capability:secure-processing'], result_id: 'result-1', answer_revision: 3, current_validity: { valid: true, status: 'valid', lifecycle_revision: 4, affected_inputs: [] } },
};

test('unknown self-report is conditional and completeness never means verification', () => {
  const view = projectAssessmentSemantics(base);
  assert.equal(view.heading, 'Conditional direction');
  assert.equal(view.pathHeading, 'Candidate direction — more information required');
  assert.equal(view.confidenceLabel, 'Answer completeness');
  assert.equal(view.findings[0].judgmentLabel, 'Unknown');
  assert.equal(view.findings[0].sourceLabel, 'Self-reported');
  assert.equal(view.findings[0].verificationLabel, 'Unverified');
  assert.equal(view.resultId, 'result-1');
  assert.equal(view.answerRevision, 3);
  assert.equal(view.lifecycleRevision, 4);
});

test('known blocker is distinct from missing information', () => {
  const view = projectAssessmentSemantics({ ...base, recommended_path: { ...base.recommended_path, status: 'blocked', recommendation_kind: 'blocked', missing_information: [] } });
  assert.equal(view.heading, 'Blocked');
  assert.equal(view.pathHeading, 'Blocked candidate path');
});

test('withdrawal overrides executable presentation and preserves original result', () => {
  const view = projectAssessmentSemantics({ ...base, recommended_path: { ...base.recommended_path, status: 'ready', recommendation_kind: 'executable_path', current_validity: { valid: false, status: 'withdrawn', lifecycle_revision: 5, affected_inputs: [{ snapshot_id: 't1', contract: 'pf.taxonomy.v1', producer_wp: 'WP2', notice_id: 'n1', reason: 'source withdrawn', dependency_path: ['t1'] }] } } });
  assert.equal(view.heading, 'Historical result — inputs withdrawn');
  assert.equal(view.originalStatus, 'ready');
  assert.equal(view.pathHeading, 'Historical candidate path — unavailable for new guidance');
  assert.equal(view.affectedInputs[0].snapshot_id, 't1');
});

test('present self-report remains unverified even when guidance is available', () => {
  const view = projectAssessmentSemantics({ ...base, readiness_snapshot: { capability_findings: { 'secure-processing': { ...finding, judgment: 'present' } } }, recommended_path: { ...base.recommended_path, status: 'ready', recommendation_kind: 'executable_path' } });
  assert.equal(view.heading, 'Guidance available');
  assert.equal(view.findings[0].judgmentLabel, 'Present');
  assert.equal(view.findings[0].verificationLabel, 'Unverified');
});
