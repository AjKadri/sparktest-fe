// Tests for decode-revert: keccak vectors, selector derivation, and real captured failures.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { keccak256, selector } from './keccak.mjs';
import { decode, format, SIGNATURE } from './decode.mjs';

const fx = (n) => fs.readFileSync(new URL(`./fixtures/${n}`, import.meta.url), 'utf8');

// known keccak-256 vectors
assert.equal(keccak256(''), 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470');
console.log('keccak256("") = c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470  OK');
assert.equal(selector('transfer(address,uint256)'), 'a9059cbb');
console.log('selector(transfer(address,uint256)) = 0xa9059cbb  OK');
assert.equal(keccak256('abc'), '4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45');
console.log('keccak256("abc") = 4e03657a...6c45  OK');
// the PropertyFailed selector used by sparktest-evm (the compiler computed 0x4c350703 independently)
assert.equal(selector(SIGNATURE), '4c350703');
console.log(`selector(${SIGNATURE}) = 0x4c350703  OK`);

// real revert data captured from failing fe test runs
const u = decode(fx('u256_below_1000.hex'));
assert.equal(u.input.length, 1); assert.equal(u.input[0], 1000n); assert.equal(u.steps, 253n); assert.equal(u.case, 0n);
console.log('\n--- u256: x < 1000\n' + format(u));
assert.match(format(u), /case      1 \(index 0\)/); // user-facing case numbers are 1-based
const a = decode(fx('array6_ends_lt_10.hex'));
assert.equal(a.input.length, 6); assert.equal(a.input[5], 10n); assert.equal(a.input.slice(0, 5).every((x) => x === 0n), true);
console.log('\n--- [u64; 6]: a[0] + a[5] < 10\n' + format(a));

// error handling
assert.throws(() => decode('0xdeadbeef' + '00'.repeat(32)), /selector 0xdeadbeef/);
assert.throws(() => decode('0x4c350703'), /truncated/);
assert.throws(() => decode('0xzz'), /not hex/);
console.log('\nall decode-revert tests passed');
