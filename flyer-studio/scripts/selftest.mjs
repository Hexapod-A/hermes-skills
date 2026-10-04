#!/usr/bin/env node
// Proves the self-check works: a clean flyer passes, deliberately broken ones are caught.
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { renderSpec } from './render.mjs';

const out = fs.mkdtempSync(path.join(os.tmpdir(), 'flyer-selftest-'));
const cases = [
  { name: 'clean', expect: [], spec: { brand: '3xagentic', layout: 'announcement', content: { headline: 'Missed Calls Are\nMissed *Money*', body: 'We build systems that reply in seconds, 24/7.', cta: '3xagentic.xyz' } } },
  { name: 'too-much-copy', expect: ['too-many-lines'], spec: { brand: '3xagentic', layout: 'announcement', content: { headline: 'This headline is far too long to ever fit on a flyer because it just keeps going and going and going without stopping', body: 'Short body.', cta: '3xagentic.xyz' } } },
  { name: 'low-contrast', expect: ['low-contrast'], spec: { brand: '3xagentic', layout: 'announcement', css: '.body{color:#1a1a1a !important;opacity:1 !important}', content: { headline: 'Grey On Black', body: 'This body text is nearly invisible on black.', cta: '3xagentic.xyz' } } },
  { name: 'stat-no-source', expect: ['claim-without-source'], spec: { brand: '3xagentic', layout: 'stat', content: { stat: '87%', stat_label: 'An unsourced number' } } },
];
let failed = 0;
for (const c of cases) {
  const [res] = await renderSpec(c.spec, { out, name: c.name, sizes: ['square'] });
  const types = res.errors.map((e) => e.type);
  const ok = c.expect.length === 0 ? types.length === 0 : c.expect.every((t) => types.includes(t));
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${c.name}: expected [${c.expect.join(', ') || 'no errors'}], got [${types.join(', ') || 'no errors'}]`);
}
console.log(`outputs in ${out}`);
process.exit(failed ? 1 : 0);
