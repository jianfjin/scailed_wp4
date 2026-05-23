import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import ts from 'typescript';

async function importTypeScriptModule(path) {
  const source = await readFile(path, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const dir = mkdtempSync(join(tmpdir(), 'stakeholder-catalog-'));
  const compiled = join(dir, 'stakeholderCatalog.mjs');
  writeFileSync(compiled, output);
  return import(compiled);
}

const catalog = await importTypeScriptModule(new URL('../src/stakeholderCatalog.ts', import.meta.url));

test('buildStakeholderOptions groups generated WP2 stakeholder IDs and shows human labels', () => {
  const options = catalog.buildStakeholderOptions([
    'academic-spinout-001',
    'academic-spinout-002',
    'public-health-agency-111',
    'biotech-sme',
  ]);

  assert.deepEqual(options.map((option) => option.group), [
    'Academic spinout',
    'Academic spinout',
    'Public health agency',
    'Biotech SME',
  ]);
  assert.equal(options[0].label, 'Academic spinout #001');
  assert.equal(options[2].label, 'Public health agency #111');
  assert.equal(options[3].label, 'Biotech SME');
});

test('filterStakeholderOptions searches labels, groups, and raw IDs case-insensitively', () => {
  const options = catalog.buildStakeholderOptions([
    'academic-spinout-001',
    'clinical-cro-017',
    'public-health-agency-111',
  ]);

  assert.deepEqual(
    catalog.filterStakeholderOptions(options, 'CRO').map((option) => option.value),
    ['clinical-cro-017'],
  );
  assert.deepEqual(
    catalog.filterStakeholderOptions(options, 'health agency').map((option) => option.value),
    ['public-health-agency-111'],
  );
});

test('formatStakeholderLoadedCopy reports profile and category counts', () => {
  const options = catalog.buildStakeholderOptions([
    'academic-spinout-001',
    'academic-spinout-002',
    'clinical-cro-017',
    'public-health-agency-111',
  ]);

  assert.equal(
    catalog.formatStakeholderLoadedCopy(options),
    '4 WP2 mock stakeholder profiles loaded across 3 categories.',
  );
});
