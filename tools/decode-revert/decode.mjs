#!/usr/bin/env node
// decode-revert: decodes Sparktest's PropertyFailed revert data.
//   node decode.mjs 0x4c350703...      (or: node decode.mjs < file.hex)
import fs from 'node:fs';
import { selector } from './keccak.mjs';

export const SIGNATURE = 'PropertyFailed(uint256,uint256,uint256,uint256[])';

export function decode(hex) {
  const h = hex.trim().replace(/^0x/, '');
  if (!/^[0-9a-fA-F]*$/.test(h) || h.length % 2) throw new Error('not hex data');
  const sel = h.slice(0, 8);
  const expected = selector(SIGNATURE);
  if (sel !== expected) throw new Error(`selector 0x${sel} is not ${SIGNATURE} (0x${expected})`);
  const body = h.slice(8);
  const word = (i) => {
    const w = body.slice(i * 64, i * 64 + 64);
    if (w.length !== 64) throw new Error(`truncated data at word ${i}`);
    return BigInt('0x' + w);
  };
  const seed = word(0), kase = word(1), steps = word(2);
  const offset = Number(word(3)) / 32; // byte offset of the dynamic array, relative to the start of the args
  const len = Number(word(offset));
  const input = [];
  for (let i = 0; i < len; i++) input.push(word(offset + 1 + i));
  return { selector: '0x' + sel, seed, case: kase, steps, input };
}

export function format(d) {
  return [
    `selector  ${d.selector}  (${SIGNATURE})`,
    `seed      ${d.seed}  (0x${d.seed.toString(16)})`,
    `case      ${d.case}`,
    `steps     ${d.steps}`,
    `input     ${d.input.length} word(s): [${d.input.join(', ')}]`,
  ].join('\n');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const json = args.includes('--json');
  const arg = args.find((a) => a !== '--json') ?? fs.readFileSync(0, 'utf8');
  try {
    const d = decode(arg);
    if (json) console.log(JSON.stringify(d, (k, v) => (typeof v === 'bigint' ? v.toString() : v)));
    else console.log(format(d));
  } catch (e) {
    console.error('decode-revert: ' + e.message);
    process.exit(1);
  }
}
