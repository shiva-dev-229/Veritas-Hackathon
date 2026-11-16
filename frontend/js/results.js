window.PT = window.PT || {};

PT.results = (function () {
  var BINS = 20;
  var CHART_H = 160;
  var PAD_B = 20;
  // colors come from the active theme's CSS variables, read at draw time
  function themeVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  var FONT = '11px "Roboto Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace';

  var lastRows = null; // redraw the histogram with new colors on theme change
  window.addEventListener("peas:themechange", function () {
    var r = document.getElementById("results");
    if (lastRows && r && !r.classList.contains("hidden")) drawHistogram(document.getElementById("histogram"), lastRows);
  });

  var seq = 0;          // request counter: stale predict() responses are ignored
  var copyTimer = null;
  var copyOrigText = "";

  function $(id) { return document.getElementById(id); }

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function fmtMs(v) { return isNum(v) ? Math.round(v) + " ms" : "-"; }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function stamp() {
    var d = new Date();
    return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + "-" +
      pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
  }

  function download(filename, text, mime) {
    var blob = new Blob([text], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(url);
      a.remove();
    }, 1000);
  }

  function flashCopied(btn) {
    if (copyTimer) {
      clearTimeout(copyTimer);
    } else {
      copyOrigText = btn.textContent;
    }
    btn.textContent = "copied!";
    copyTimer = setTimeout(function () {
      btn.textContent = copyOrigText;
      copyTimer = null;
    }, 1500);
  }

  function copyText(text, btn) {
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      ta.remove();
      if (ok) flashCopied(btn);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        flashCopied(btn);
      }, fallback);
    } else {
      fallback();
    }
  }

  function drawHistogram(canvas, rows) {
    var dpr = window.devicePixelRatio || 1;
    canvas.style.width = "100%";
    canvas.style.height = CHART_H + "px";
    var cssW = canvas.clientWidth || 800;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(CHART_H * dpr);

    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, CHART_H);
    ctx.font = FONT;
    ctx.fillStyle = themeVar("--sub");
    ctx.textBaseline = "top";

    var vals = [];
    for (var i = 0; i < rows.length; i++) {
      var h = rows[i] && rows[i].hold_time;
      if (isNum(h)) vals.push(h);
    }
    if (!vals.length) {
      ctx.textAlign = "left";
      ctx.fillText("no data", 0, 0);
      return;
    }

    vals.sort(function (a, b) { return a - b; });
    // clip the axis at the 98th percentile so outliers do not flatten the bars
    var p98 = vals[Math.min(vals.length - 1, Math.floor(0.98 * (vals.length - 1)))];
    var lo = vals[0];
    var max = p98 > lo ? p98 : lo + 1;

    var counts = [];
    for (var b = 0; b < BINS; b++) counts.push(0);
    for (var j = 0; j < vals.length; j++) {
      var bin = Math.min(BINS - 1, Math.floor(((Math.min(vals[j], max) - lo) / (max - lo)) * BINS));
      counts[bin]++;
    }
    var peak = Math.max.apply(null, counts) || 1;

    var plotH = CHART_H - PAD_B;
    var slot = cssW / BINS;
    ctx.fillStyle = themeVar("--main");
    for (var k = 0; k < BINS; k++) {
      var barH = (counts[k] / peak) * (plotH - 4);
      ctx.fillRect(k * slot + slot * 0.1, plotH - barH, slot * 0.8, barH);
    }

    ctx.strokeStyle = themeVar("--sub");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, plotH + 0.5);
    ctx.lineTo(cssW, plotH + 0.5);
    ctx.stroke();

    ctx.fillStyle = themeVar("--sub");
    ctx.textAlign = "left";
    ctx.fillText(Math.round(lo) + " ms", 0, plotH + 4);
    ctx.textAlign = "right";
    ctx.fillText(Math.round(max) + " ms", cssW, plotH + 4);
  }

  // <ul id="scoreWarnings"> inside the score panel; created before #scoreNote if missing
  function warningsList() {
    var ul = $("scoreWarnings");
    if (!ul) {
      ul = document.createElement("ul");
      ul.id = "scoreWarnings";
      var note = $("scoreNote");
      if (note && note.parentNode) note.parentNode.insertBefore(ul, note);
    }
    return ul;
  }

  function showWarnings(list) {
    var ul = warningsList();
    ul.textContent = "";
    if (!Array.isArray(list)) return;
    for (var i = 0; i < list.length; i++) {
      var li = document.createElement("li");
      li.textContent = String(list[i]);
      ul.appendChild(li);
    }
  }

  function errorMessage(err) {
    var kind = err && err.kind;
    var msg = err && err.message ? err.message : "unknown error";
    if (kind === "input") return msg;
    if (kind === "network") return "Model not reachable, you can still download your data";
    if (kind === "timeout") return "Model not reachable, you can still download your data (timed out after 15 s)";
    return "Model error: " + msg + ". You can still download your data";
  }

  function loadScore(session, my) {
    var body = $("scoreBody");
    showWarnings([]);
    body.textContent = "Analyzing…";
    body.classList.add("loading");
    body.classList.remove("error-text");
    Promise.resolve()
      .then(function () { return PT.api.predict(session); })
      .then(function (res) {
        if (my !== seq) return;
        body.classList.remove("loading");
        body.classList.remove("error-text");
        var pct = Math.round(res.score * 100);
        body.textContent = pct + "%" + (res.label ? " · " + res.label : "");
        showWarnings(res.details && res.details.warnings);
      }, function (err) {
        if (my !== seq) return;
        body.classList.remove("loading");
        body.textContent = errorMessage(err);
        body.classList.add("error-text");
      })
      .then(function () {
        // the note is part of the contract: it must always read this
        var note = $("scoreNote");
        if (note) note.textContent = "screening aid, not a diagnosis";
      });
  }

  function show(opts) {
    var session = opts.session;
    var my = ++seq;
    var summary = session.summary || {};

    $("test").classList.add("hidden");
    $("results").classList.remove("hidden");

    $("resWpm").textContent = isNum(opts.wpm) ? String(Math.round(opts.wpm)) : "-";
    $("resAcc").textContent = isNum(opts.accuracy) ? Math.round(opts.accuracy * 100) + "%" : "-";
    $("resKeys").textContent = summary.count != null ? String(summary.count) : "-";
    $("resHold").textContent = fmtMs(summary.meanHold);
    $("resLatency").textContent = fmtMs(summary.meanLatency);
    $("resFlight").textContent = fmtMs(summary.meanFlight);

    $("scoreNote").textContent = "screening aid, not a diagnosis";
    lastRows = session.rows || [];
    drawHistogram($("histogram"), lastRows);

    $("btnCsv").onclick = function () {
      download("peas-session-" + stamp() + ".csv", PT.features.toCSV(session.rows || []), "text/csv;charset=utf-8");
    };
    $("btnJson").onclick = function () {
      download("peas-session-" + stamp() + ".json", PT.features.toJSON(session), "application/json;charset=utf-8");
    };
    $("btnCopy").onclick = function () {
      copyText(PT.features.toJSON(session), $("btnCopy"));
    };
    $("btnRestart").onclick = function () {
      PT.test.restart();
    };

    loadScore(session, my);
  }

  function hide() {
    $("results").classList.add("hidden");
  }

  return { show: show, hide: hide };
})();

if (typeof module !== "undefined") module.exports = PT.results;
