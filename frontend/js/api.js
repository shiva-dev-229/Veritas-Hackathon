window.PT = window.PT || {};
PT.config = { API_URL: "http://localhost:8000/predict" };

PT.api = (function () {
  var TIMEOUT_MS = 15000;

  // Error with a machine-readable kind:
  // "timeout" | "network" | "input" (HTTP 422) | "server" (other non-2xx) | "bad_response"
  function fail(kind, message) {
    var err = new Error(message);
    err.kind = kind;
    return err;
  }

  // FastAPI errors use {detail: string}; validation errors may use {detail: [{msg: ...}]}.
  function detailMessage(body) {
    if (!body || body.detail == null) return "";
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map(function (d) {
        return d && typeof d.msg === "string" ? d.msg : String(d);
      }).join("; ");
    }
    return "";
  }

  async function predict(session) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);
    try {
      var res;
      try {
        res = await fetch(PT.config.API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(session),
          signal: controller.signal
        });
      } catch (err) {
        if (err && err.name === "AbortError") throw fail("timeout", "model request timed out");
        throw fail("network", "network error: " + (err && err.message ? err.message : err));
      }

      // Body may be non-JSON (e.g. proxy error page); keep null and decide by status.
      var body = null;
      try {
        body = await res.json();
      } catch (err) {
        if (err && err.name === "AbortError") throw fail("timeout", "model request timed out");
        body = null;
      }

      if (res.status === 422) {
        throw fail("input", detailMessage(body) || "input was rejected by the model");
      }
      if (!res.ok) {
        throw fail("server", detailMessage(body) || "model returned HTTP " + res.status);
      }
      if (!body || typeof body !== "object") {
        throw fail("bad_response", "model response is not valid JSON");
      }
      if (typeof body.score !== "number" || !isFinite(body.score)) {
        throw fail("bad_response", "model response has no numeric score");
      }
      if (body.score < 0 || body.score > 1) {
        throw fail("bad_response", "model score is outside [0, 1]");
      }
      return body;
    } finally {
      clearTimeout(timer);
    }
  }

  return { predict: predict };
})();
