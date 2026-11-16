window.PT = window.PT || {};

PT.test = (function () {
  var WORD_COUNT = 60;
  var MIN_KEYS = 300;
  var EXTRA_WORDS = 10;
  var MAX_EXTRA_CHARS = 10;

  var WORDS = (
    "the be to of and a in that have it for not on with he as you do at this but his by from they we say her she or " +
    "an will my one all would there their what so up out if about who get which go me when make can like time no just him " +
    "know take people into year your good some could them see other than then now look only come its over think also back " +
    "after use two how our work first well way even new want because any these give day most us is was are been has had " +
    "were said did made find where much too very still being going why before never here off always those both under might " +
    "while last right since place small found such home read hand turn large spell air away animal house point page letter " +
    "mother answer study learn should world high every near add food between own below country plant school father keep " +
    "tree never start city earth eye light thought head story saw left few along close something seem next hard open " +
    "example begin life often together group run important until children side feet car mile night walk white sea began " +
    "grow took river four carry state once book hear stop without second later miss idea enough eat face watch far real " +
    "almost let above girl sometimes mountain cut young talk soon list song leave family"
  ).split(" ");

  var $ = function (id) { return document.getElementById(id); };

  var s = null;          // per-test state
  var meta = { age: null, gender: null };
  var tabArmed = false;
  var tickTimer = null;
  var idleTimer = null;

  function pick(n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(WORDS[Math.floor(Math.random() * WORDS.length)]);
    return out;
  }

  function newState() {
    return {
      words: pick(WORD_COUNT), typed: [""], wi: 0,
      started: false, ended: false, t0: 0, startedAt: null,
      keyCount: 0, correctKeys: 0, totalKeys: 0
    };
  }

  // ---------- rendering ----------
  function wordEl(i) { return $("words").children[i]; }

  function renderWord(i) {
    var el = wordEl(i);
    if (!el) return;
    var w = s.words[i], t = s.typed[i] || "";
    var html = "";
    var n = Math.max(w.length, t.length);
    for (var j = 0; j < n; j++) {
      var cls = "letter";
      var ch = j < w.length ? w[j] : t[j];
      if (j < t.length) {
        if (j >= w.length) cls += " extra incorrect";
        else cls += t[j] === w[j] ? " correct" : " incorrect";
      }
      html += '<span class="' + cls + '">' + ch + "</span>";
    }
    el.innerHTML = html;
    el.classList.toggle("active", i === s.wi);
    el.classList.toggle("error", i < s.wi && t !== w);
  }

  function renderAll() {
    var box = $("words");
    box.innerHTML = "";
    box.style.marginTop = "0px";
    for (var i = 0; i < s.words.length; i++) {
      var d = document.createElement("div");
      d.className = "word";
      box.appendChild(d);
      renderWord(i);
    }
    placeCaret();
  }

  function appendWords(n) {
    var extra = pick(n), box = $("words");
    for (var i = 0; i < extra.length; i++) {
      s.words.push(extra[i]);
      var d = document.createElement("div");
      d.className = "word";
      box.appendChild(d);
      renderWord(s.words.length - 1);
    }
  }

  function placeCaret() {
    var box = $("words"), el = wordEl(s.wi), caret = $("caret");
    if (!el) return;
    // keep the active word on the first or second visible line
    var first = box.children[0];
    // use fractional rects (offsetHeight rounds, which leaks slivers of hidden lines)
    var fr = first.getBoundingClientRect();
    var lineH = fr.height;
    var rowY = el.getBoundingClientRect().top - fr.top;
    var shift = Math.max(0, rowY - lineH);
    box.style.marginTop = -shift + "px";

    var letters = el.children, idx = (s.typed[s.wi] || "").length, x, y;
    if (idx < letters.length) {
      x = letters[idx].offsetLeft; y = letters[idx].offsetTop;
    } else {
      var last = letters[letters.length - 1];
      x = last.offsetLeft + last.offsetWidth; y = last.offsetTop;
    }
    caret.style.left = x + "px";
    caret.style.top = y + "px";
  }

  function poke() {
    var caret = $("caret");
    caret.classList.remove("idle");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () { caret.classList.add("idle"); }, 500);
  }

  // ---------- stats ----------
  function correctChars() {
    var c = s.wi; // spaces typed
    for (var i = 0; i <= s.wi && i < s.words.length; i++) {
      var w = s.words[i], t = s.typed[i] || "";
      for (var j = 0; j < Math.min(w.length, t.length); j++) if (w[j] === t[j]) c++;
    }
    return c;
  }

  function elapsedMs() { return s.started ? performance.now() - s.t0 : 0; }

  function wpm() {
    var min = elapsedMs() / 60000;
    return min > 0 ? (correctChars() / 5) / min : 0;
  }

  function accuracy() { return s.totalKeys ? s.correctKeys / s.totalKeys : 0; }

  function tick() {
    if (!s || !s.started) return;
    $("timer").textContent = Math.floor(elapsedMs() / 1000);
    $("liveWpm").textContent = Math.round(wpm());
  }

  // ---------- flow ----------
  function visible(id) { return !$(id).classList.contains("hidden"); }

  function restart() {
    s = newState();
    tabArmed = false;
    clearInterval(tickTimer);
    $("timer").textContent = "0";
    $("liveWpm").textContent = "0";
    if (PT.results) PT.results.hide();
    $("pretest").classList.add("hidden");
    $("test").classList.remove("hidden");
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    renderAll();
    $("caret").classList.add("idle");
    PT.capture.start();
  }

  function begin() {
    s.started = true;
    s.t0 = performance.now();
    s.startedAt = new Date().toISOString();
    tickTimer = setInterval(tick, 250);
  }

  function lastWordDone() {
    var i = s.words.length - 1;
    return s.wi > i || (s.wi === i && s.typed[i].length >= s.words[i].length);
  }

  function checkEnd() {
    if (!lastWordDone()) return;
    if (s.keyCount >= MIN_KEYS) return finish();
    // not enough keystrokes yet: keep going with more words
    if (s.wi >= s.words.length) s.typed[s.wi] = s.typed[s.wi] || "";
    appendWords(EXTRA_WORDS);
    if (s.wi < s.words.length) renderWord(s.wi);
    placeCaret();
  }

  function finish() {
    s.ended = true;
    clearInterval(tickTimer);
    tick();
    var finalWpm = wpm(), finalAcc = accuracy(), st = s;
    // let the last key's keyup land before stopping capture (max 600 ms)
    var waited = 0;
    (function wait() {
      if (PT.capture.pendingCount && PT.capture.pendingCount() > 0 && waited < 600) {
        waited += 50;
        return setTimeout(wait, 50);
      }
      PT.capture.stop();
      if (st !== s) return; // restarted meanwhile
      var rows = PT.features.toRows(PT.capture.getRawLog());
      var session = {
        meta: { age: meta.age, gender: meta.gender, startedAt: st.startedAt, userAgent: navigator.userAgent },
        rows: rows,
        summary: PT.features.summary(rows)
      };
      PT.results.show({ session: session, wpm: finalWpm, accuracy: finalAcc });
    })();
  }

  function onKey(e) {
    if (visible("pretest")) return;
    if (PT.theme && PT.theme.isOpen && PT.theme.isOpen()) return;

    if (e.key === "Tab") { e.preventDefault(); tabArmed = true; return; }
    if (e.key === "Enter" && tabArmed) { e.preventDefault(); restart(); return; }
    if (e.key === "Escape") { e.preventDefault(); restart(); return; }
    tabArmed = false;

    if (e.repeat || !visible("test") || !s || s.ended) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    var key = e.key;
    if (key === " ") {
      e.preventDefault();
      if (!s.started) return;
      if (!s.typed[s.wi]) return; // nothing typed yet in this word
      if (PT.features.isTypingKey(e.code)) s.keyCount++;
      s.totalKeys++;
      if (s.typed[s.wi] === s.words[s.wi]) s.correctKeys++;
      s.wi++;
      s.typed[s.wi] = s.typed[s.wi] || "";
      renderWord(s.wi - 1);
      if (s.wi >= s.words.length) { checkEnd(); return; }
      renderWord(s.wi);
      placeCaret(); poke();
      return;
    }

    if (key === "Backspace") {
      e.preventDefault();
      var t = s.typed[s.wi];
      if (t.length) { s.typed[s.wi] = t.slice(0, -1); renderWord(s.wi); placeCaret(); poke(); }
      return;
    }

    if (key.length !== 1) return; // Shift, arrows, etc.
    if (!s.started) begin();
    if (PT.features.isTypingKey(e.code)) s.keyCount++;
    var w = s.words[s.wi], cur = s.typed[s.wi];
    if (cur.length >= w.length + MAX_EXTRA_CHARS) return;
    s.totalKeys++;
    if (key === w[cur.length]) s.correctKeys++;
    s.typed[s.wi] = cur + key;
    renderWord(s.wi);
    placeCaret(); poke();
    if (s.wi === s.words.length - 1) checkEnd();
  }

  function readMeta(skip) {
    if (skip) { meta = { age: null, gender: null }; return; }
    var a = parseInt($("age").value, 10);
    meta = { age: isFinite(a) && a > 0 ? a : null, gender: $("gender").value || null };
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("pretest").classList.remove("hidden");
    $("startBtn").onclick = function () { readMeta(false); restart(); };
    $("skipBtn").onclick = function () { readMeta(true); restart(); };
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", function () { if (s && visible("test")) placeCaret(); });
  });

  return { restart: restart };
})();
