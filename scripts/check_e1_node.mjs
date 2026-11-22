// Node: same wasm, same stub imports as the page
import fs from 'node:fs';
const m = await WebAssembly.compile(fs.readFileSync(new URL('../web/qc_wasm.wasm', import.meta.url)));
let fails = [], mem;
const { exports } = await WebAssembly.instantiate(m, { env: { qc_fail: (i, c) => fails.push([i, c]), __fe_revert: (a, l) => { throw new Error('revert ' + Buffer.from(mem.buffer, a, l).toString('hex')); } } });
mem = exports.memory;
for (const [seed, cases, limit] of [[12345n, 1000, 99000n], [12345n, 1000, 100000n], [7n, 1000000, 99999n], [7n, 100000000, 100000n]]) {
  fails = []; const t = performance.now();
  const n = exports.run_below(seed, cases, limit);
  console.log(`seed=${seed} cases=${cases} limit=${limit} -> failures=${n} first=${JSON.stringify(fails[0]?.map(String))} ${(performance.now() - t).toFixed(1)}ms`);
}
