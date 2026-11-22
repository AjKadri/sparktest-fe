// Minimal keccak-256 (the Ethereum variant: 0x01 padding, not SHA3's 0x06). No dependencies.
const MASK = (1n << 64n) - 1n;
const RC = [
  0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
  0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
  0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
  0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
  0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
  0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n,
];
const ROT = [
  [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
];
const rotl = (x, n) => (n === 0 ? x : ((x << BigInt(n)) | (x >> BigInt(64 - n))) & MASK);

function keccakF(s) {
  for (let round = 0; round < 24; round++) {
    const c = [0, 1, 2, 3, 4].map((x) => s[x][0] ^ s[x][1] ^ s[x][2] ^ s[x][3] ^ s[x][4]);
    const d = [0, 1, 2, 3, 4].map((x) => c[(x + 4) % 5] ^ rotl(c[(x + 1) % 5], 1));
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) s[x][y] ^= d[x];
    const b = [0, 1, 2, 3, 4].map(() => [0n, 0n, 0n, 0n, 0n]);
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) b[y][(2 * x + 3 * y) % 5] = rotl(s[x][y], ROT[x][y]);
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) s[x][y] = b[x][y] ^ (~b[(x + 1) % 5][y] & MASK & b[(x + 2) % 5][y]);
    s[0][0] ^= RC[round];
  }
}

export function keccak256(input) {
  const data = typeof input === 'string' ? new TextEncoder().encode(input) : input;
  const rate = 136;
  const padded = new Uint8Array(Math.ceil((data.length + 1) / rate) * rate);
  padded.set(data);
  padded[data.length] ^= 0x01;
  padded[padded.length - 1] ^= 0x80;
  const s = [0, 1, 2, 3, 4].map(() => [0n, 0n, 0n, 0n, 0n]);
  for (let off = 0; off < padded.length; off += rate) {
    for (let i = 0; i < rate / 8; i++) {
      let lane = 0n;
      for (let j = 7; j >= 0; j--) lane = (lane << 8n) | BigInt(padded[off + i * 8 + j]);
      s[i % 5][Math.floor(i / 5)] ^= lane;
    }
    keccakF(s);
  }
  let out = '';
  for (let i = 0; i < 4; i++) {
    const lane = s[i % 5][Math.floor(i / 5)];
    for (let j = 0; j < 8; j++) out += ((lane >> BigInt(8 * j)) & 0xffn).toString(16).padStart(2, '0');
  }
  return out;
}

export const selector = (signature) => keccak256(signature).slice(0, 8);
