// ---------------------------------------------------------------------------
// Open FLEX — utilities: escaping, canonical JSON, genuine SHA-256, UUIDs.
// No substitute algorithms: if Web Crypto is unavailable, hashing reports
// "unavailable" instead of producing a look-alike digest.
// ---------------------------------------------------------------------------
var OF = window.OF || {};
window.OF = OF;

OF.esc = function (s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
};

// Canonical JSON: object keys sorted recursively, no insignificant whitespace.
// The same rule is implemented in tools/canonical_json.py so hashes can be
// recomputed independently.
OF.canonicalJSON = function (v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(OF.canonicalJSON).join(",") + "]";
  return "{" + Object.keys(v).sort().map(function (k) {
    return JSON.stringify(k) + ":" + OF.canonicalJSON(v[k]);
  }).join(",") + "}";
};

OF.hashAvailable = function () {
  return !!(window.crypto && window.crypto.subtle && typeof window.crypto.subtle.digest === "function");
};

// Returns a lowercase hex SHA-256 string, or null when SHA-256 is unavailable.
OF.sha256Hex = async function (str) {
  if (!OF.hashAvailable()) return null;
  try {
    var buf = new TextEncoder().encode(str);
    var h = await window.crypto.subtle.digest("SHA-256", buf);
    return Array.from(new Uint8Array(h)).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
  } catch (e) {
    return null;
  }
};

// RFC 4122 v4 UUID from a cryptographic RNG; null if none is available.
OF.uuid4 = function () {
  var c = window.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  if (c && typeof c.getRandomValues === "function") {
    var b = new Uint8Array(16); c.getRandomValues(b);
    b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
    var h = Array.from(b).map(function (x) { return x.toString(16).padStart(2, "0"); }).join("");
    return h.slice(0, 8) + "-" + h.slice(8, 12) + "-" + h.slice(12, 16) + "-" + h.slice(16, 20) + "-" + h.slice(20);
  }
  return null;
};

OF.toast = function (msg) {
  var t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(OF._toastTimer);
  OF._toastTimer = setTimeout(function () { t.style.display = "none"; }, 4000);
};

OF.libStatus = function () {
  return { three: typeof THREE !== "undefined", plotly: typeof Plotly !== "undefined" };
};
