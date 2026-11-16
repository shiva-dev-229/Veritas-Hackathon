// Node-compatible namespace: works as a classic script in the browser and under require().
var root = (typeof window !== 'undefined') ? window : globalThis;
root.PT = root.PT || {};

root.PT.features = (function () {
  // Hand assignment for touch-typing keys (Space is handled separately and is not in this map).
  var HAND = {};
  function assign(codes, hand) {
    codes.forEach(function (c) { HAND[c] = hand; });
  }

  assign(
    ['Backquote', 'Digit1', 'Digit2', 'Digit3', 'Digit4', 'Digit5',
     'KeyQ', 'KeyW', 'KeyE', 'KeyR', 'KeyT',
     'KeyA', 'KeyS', 'KeyD', 'KeyF', 'KeyG',
     'KeyZ', 'KeyX', 'KeyC', 'KeyV', 'KeyB'],
    'L'
  );
  assign(
    ['Digit6', 'Digit7', 'Digit8', 'Digit9', 'Digit0', 'Minus', 'Equal',
     'KeyY', 'KeyU', 'KeyI', 'KeyO', 'KeyP',
     'BracketLeft', 'BracketRight', 'Backslash',
     'KeyH', 'KeyJ', 'KeyK', 'KeyL', 'Semicolon', 'Quote',
     'KeyN', 'KeyM', 'Comma', 'Period', 'Slash'],
    'R'
  );

  // TODO: verify direction codes against a real Tappy sample
  var HEADER = ['timestamp', 'hand', 'hold_time', 'latency', 'flight', 'direction'];

  function isTypingKey(code) {
    return Object.prototype.hasOwnProperty.call(HAND, code) || code === 'Space';
  }

  function round2(x) {
    if (x === null || x === undefined || !isFinite(x)) return null;
    return Math.round(x * 100) / 100 + 0; // + 0 normalises -0
  }

  function toRows(raw, t0) {
    raw = raw || [];
    if (t0 === undefined || t0 === null) {
      t0 = raw.length
        ? raw.reduce(function (m, e) { return e.down < m ? e.down : m; }, Infinity)
        : 0;
    }

    var entries = raw
      .filter(function (e) {
        return isTypingKey(e.code) && e.repeat !== true && e.up != null;
      })
      .slice()
      .sort(function (a, b) { return a.down - b.down; });

    var rows = [];
    var prev = null; // previous exported row: { down, up, side }
    entries.forEach(function (e) {
      var isSpace = e.code === 'Space';
      var hand = isSpace ? null : HAND[e.code];
      var row = {
        timestamp: round2(e.down - t0),
        hand: hand,
        hold_time: round2(e.up - e.down),
        latency: null,
        flight: null,
        direction: null
      };
      if (prev) {
        row.latency = round2(e.down - prev.down);
        row.flight = round2(e.down - prev.up);
        row.direction = isSpace ? 'S' : prev.side + hand;
      }
      rows.push(row);
      prev = { down: e.down, up: e.up, side: isSpace ? 'S' : hand };
    });
    return rows;
  }

  function valuesOf(rows, key) {
    return rows
      .map(function (r) { return r[key]; })
      .filter(function (v) { return v !== null && v !== undefined && isFinite(v); });
  }

  function mean(vals) {
    if (!vals.length) return null;
    return vals.reduce(function (s, v) { return s + v; }, 0) / vals.length;
  }

  function median(vals) {
    if (!vals.length) return null;
    var s = vals.slice().sort(function (a, b) { return a - b; });
    var mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  function summary(rows) {
    rows = rows || [];
    return {
      count: rows.length,
      meanHold: round2(mean(valuesOf(rows, 'hold_time'))),
      meanLatency: round2(mean(valuesOf(rows, 'latency'))),
      meanFlight: round2(mean(valuesOf(rows, 'flight'))),
      medianHold: round2(median(valuesOf(rows, 'hold_time')))
    };
  }

  function cell(v) {
    return (v === null || v === undefined) ? '' : String(v);
  }

  function toCSV(rows) {
    var lines = [HEADER.join(',')];
    (rows || []).forEach(function (r) {
      lines.push(HEADER.map(function (k) { return cell(r[k]); }).join(','));
    });
    return lines.join('\n') + '\n';
  }

  function toJSON(session) {
    return JSON.stringify(session, null, 2);
  }

  return {
    HAND: HAND,
    isTypingKey: isTypingKey,
    toRows: toRows,
    summary: summary,
    toCSV: toCSV,
    toJSON: toJSON
  };
})();

if (typeof module !== 'undefined') module.exports = root.PT.features;
