'use strict';
const assert = require('assert');
const F = require('../js/features.js');

const e = (code, down, up, extra) => Object.assign({ code, down, up }, extra || {});

// 1. Hand map
assert.strictEqual(F.HAND.KeyA, 'L');
assert.strictEqual(F.HAND.KeyT, 'L');
assert.strictEqual(F.HAND.KeyY, 'R');
assert.strictEqual(F.HAND.Digit5, 'L');
assert.strictEqual(F.HAND.Digit6, 'R');
assert.strictEqual(F.HAND.Slash, 'R');
assert.strictEqual(F.HAND.Space, undefined, 'Space must not be in HAND');
assert.strictEqual(F.isTypingKey('Space'), true);
assert.strictEqual(F.isTypingKey('KeyA'), true);
assert.strictEqual(F.isTypingKey('ShiftLeft'), false);
assert.strictEqual(F.isTypingKey('Backspace'), false);
{
  const rows = F.toRows([e('Space', 0, 50)]);
  assert.strictEqual(rows[0].hand, null, 'Space row hand must be null');
}

// 2. First row has null latency/flight/direction
{
  const rows = F.toRows([e('KeyA', 0, 100), e('KeyJ', 200, 260)]);
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(rows[0].latency, null);
  assert.strictEqual(rows[0].flight, null);
  assert.strictEqual(rows[0].direction, null);
}

// 3. Overlapping keys -> negative flight
{
  const rows = F.toRows([e('KeyA', 0, 120), e('KeyJ', 80, 150)]);
  assert.strictEqual(rows[1].latency, 80);
  assert.strictEqual(rows[1].flight, -40);
  assert.strictEqual(rows[1].direction, 'LR');
  assert.strictEqual(rows[1].hand, 'R');
  assert.strictEqual(rows[1].hold_time, 70);
}

// 4. Repeat and unreleased entries are skipped
{
  const rows = F.toRows([
    e('KeyA', 0, 100),
    e('KeyA', 20, 100, { repeat: true }),
    e('KeyS', 150, null),
    e('KeyD', 200, 260)
  ]);
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(rows[1].latency, 200, 'skipped entries must not count as previous');
  assert.strictEqual(rows[1].flight, 100);
  assert.strictEqual(rows[1].direction, 'LL');
}

// 5. Non-typing keys excluded and never act as "previous"
{
  const rows = F.toRows([
    e('KeyA', 0, 100),
    e('ShiftLeft', 50, 60),
    e('Backspace', 70, 80),
    e('KeyJ', 200, 250)
  ]);
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(rows[1].latency, 200);
  assert.strictEqual(rows[1].flight, 100);
  assert.strictEqual(rows[1].direction, 'LR');
}

// 6. Space handling
{
  const rows = F.toRows([
    e('KeyA', 0, 100),
    e('Space', 150, 200),
    e('KeyJ', 250, 300),
    e('KeyF', 350, 400)
  ]);
  assert.strictEqual(rows[1].hand, null);
  assert.strictEqual(rows[1].direction, 'S');
  assert.strictEqual(rows[1].flight, 50);
  assert.strictEqual(rows[2].direction, 'SR');
  assert.strictEqual(rows[3].direction, 'RL');
}
{
  const rows = F.toRows([e('Space', 0, 50), e('KeyA', 100, 150)]);
  assert.strictEqual(rows[1].direction, 'SL');
}

// 7. Timestamp relative to t0 (default: min down across all raw entries)
{
  const raw = [e('ShiftLeft', 1000, 1010), e('KeyA', 1100, 1180)];
  const rows = F.toRows(raw);
  assert.strictEqual(rows.length, 1);
  assert.strictEqual(rows[0].timestamp, 100);
  assert.strictEqual(rows[0].hold_time, 80);
  assert.strictEqual(F.toRows(raw, 1000)[0].timestamp, 100);
  assert.strictEqual(F.toRows(raw, 0)[0].timestamp, 1100);
}

// 8. Rounding to 2 decimals
{
  // latency = 20.0051 - 0.001 = 20.0041 -> 20; flight = 20.0051 - 10.0049 = 10.0002 -> 10
  // hold = 10.0049 - 0.001 = 10.0039 -> 10; timestamp = 0.001 -> 0
  const rows = F.toRows([e('KeyA', 0.001, 10.0049), e('KeyS', 20.0051, 30)]);
  assert.strictEqual(rows[0].timestamp, 0);
  assert.strictEqual(rows[0].hold_time, 10);
  assert.strictEqual(rows[1].latency, 20);
  assert.strictEqual(rows[1].flight, 10);
  // half-way rounding case: 1.005 style values round up to 2 decimals
  const r2 = F.toRows([e('KeyA', 0, 1.23), e('KeyS', 1.236, 2)]);
  assert.strictEqual(r2[1].latency, 1.24);
  assert.strictEqual(r2[1].flight, 0.01);
}

// 9. Rows never contain key codes
{
  const rows = F.toRows([e('KeyA', 0, 100), e('Space', 150, 200), e('KeyJ', 250, 300)]);
  assert.ok(rows.length > 0);
  assert.ok(rows.every((r) => !Object.prototype.hasOwnProperty.call(r, 'code')));
  assert.ok(rows.every((r) => Object.keys(r).every((k) => !/code|text|key/i.test(k))));
}

// 10. Summary means / median, nulls ignored
{
  const rows = [
    { timestamp: 0, hand: 'L', hold_time: 100, latency: null, flight: null, direction: null },
    { timestamp: 1, hand: 'R', hold_time: 120, latency: 200, flight: 50, direction: 'LR' },
    { timestamp: 2, hand: 'L', hold_time: 80, latency: 300, flight: null, direction: 'RL' }
  ];
  const s = F.summary(rows);
  assert.strictEqual(s.count, 3);
  assert.strictEqual(s.meanHold, 100);
  assert.strictEqual(s.meanLatency, 250);
  assert.strictEqual(s.meanFlight, 50);
  assert.strictEqual(s.medianHold, 100);
}
{
  const s = F.summary([
    { hold_time: 100, latency: null, flight: null },
    { hold_time: 101, latency: null, flight: null }
  ]);
  assert.strictEqual(s.medianHold, 100.5);
  assert.strictEqual(s.meanLatency, null);
  assert.strictEqual(s.meanFlight, null);
}
{
  const s = F.summary([{ hold_time: 1, latency: 1, flight: 1 }, { hold_time: 2, latency: 2, flight: 2 }, { hold_time: 2, latency: 2, flight: 2 }]);
  assert.strictEqual(s.meanHold, 1.67, 'mean must be rounded to 2 decimals');
}
{
  const s = F.summary([]);
  assert.deepStrictEqual(s, { count: 0, meanHold: null, meanLatency: null, meanFlight: null, medianHold: null });
}

// 11. CSV header, empty cells for nulls, LF line endings
{
  const rows = F.toRows([e('KeyA', 0, 120), e('KeyJ', 80, 150)]);
  const csv = F.toCSV(rows);
  const lines = csv.split('\n');
  assert.strictEqual(lines[0], 'timestamp,hand,hold_time,latency,flight,direction');
  assert.strictEqual(lines[1], '0,L,120,,,');
  assert.strictEqual(lines[2], '80,R,70,80,-40,LR');
  assert.ok(!csv.includes('\r'));
  assert.strictEqual(F.toCSV([]), 'timestamp,hand,hold_time,latency,flight,direction\n');
}

// 12. JSON export
{
  const session = { meta: { age: null, gender: null, startedAt: 'x', userAgent: 'y' }, rows: [], summary: F.summary([]) };
  assert.strictEqual(F.toJSON(session), JSON.stringify(session, null, 2));
}

console.log('all features tests passed');
