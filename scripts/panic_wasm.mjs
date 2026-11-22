// Prints the wasm result of the panic property as one JSON line (used by scripts/proof.py): node scripts/panic_wasm.mjs overflow-seed
import fs from 'node:fs';
import { loadSparktest } from '../web/sparktest-runner.mjs';
const st = await loadSparktest(fs.readFileSync(new URL('../web/demo_wasm.wasm', import.meta.url)));
const f = st.findPanic('panic_overflow', Number(process.argv[2] ?? 8101), 256);
console.log(JSON.stringify({ caseIndex: f.caseIndex, steps: f.steps, original: String(f.original), shrunk: String(f.shrunk), reason: f.reason, runs: f.runs, bisect: f.bisect.length }));
