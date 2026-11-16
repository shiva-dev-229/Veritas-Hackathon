window.PT = window.PT || {};

PT.capture = (function () {
  var log = [];
  var pending = new Map(); // code -> down time

  function onKeyDown(e) {
    if (e.repeat === true) return;
    pending.set(e.code, performance.now()); // a re-press replaces the pending down
  }

  function onKeyUp(e) {
    if (!pending.has(e.code)) return; // keyup with no pending keydown is ignored
    var down = pending.get(e.code);
    pending.delete(e.code);
    log.push({ code: e.code, down: down, up: performance.now() });
  }

  function onBlur(e) {
    // capture-phase listener also sees element blurs; only window focus loss counts
    if (e && e.target !== window) return;
    pending.clear();
  }

  function detach() {
    window.removeEventListener('keydown', onKeyDown, true);
    window.removeEventListener('keyup', onKeyUp, true);
    window.removeEventListener('blur', onBlur, true);
  }

  function start() {
    detach(); // safe to call twice
    log = [];
    pending.clear();
    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('keyup', onKeyUp, true);
    window.addEventListener('blur', onBlur, true);
  }

  function stop() {
    detach();
    pending.clear();
  }

  function getRawLog() {
    return log
      .map(function (x) { return { code: x.code, down: x.down, up: x.up }; })
      .sort(function (a, b) { return a.down - b.down; });
  }

  function pendingCount() { return pending.size; }

  return { start: start, stop: stop, getRawLog: getRawLog, pendingCount: pendingCount };
})();
