/** Offline OCR via vendored Tesseract.js (no CDN). */

var MIN_CONF = 72;
/** Soft ceiling for Tesseract on A1533 — timeout opens search, never hangs. */
var OCR_TIMEOUT_MS = 15000;
/** @type {Promise<any> | null} */
var workerPromise = null;

/**
 * Tesseract spawns its worker from a blob: URL, so relative paths resolve
 * against the blob and fail with "invalid URL" inside importScripts. Every
 * path handed to Tesseract must be absolute.
 * @param {string} p
 * @returns {string}
 */
function abs(p) {
  return new URL(p, window.location.href).href;
}

var PATHS = {
  workerPath: abs("vendor/tesseract/worker.min.js"),
  langPath: abs("vendor/tesseract/lang"),
  corePath: abs("vendor/tesseract/tesseract-core.wasm.js"),
};

/**
 * Name-band crop as `[x, y, w, h]` fractions of the source image. `tight` is the
 * historical default (mirrors the red guide box in the UI and poke/ocr.py).
 * `wide` is a fallback pass for a card held slightly far away or not perfectly
 * aligned — a bit more margin so a name band that spilled just outside the box is
 * still captured.
 * @type {{ tight: number[], wide: number[] }}
 */
var CROP_PROFILES = {
  tight: [0.08, 0.04, 0.55, 0.14],
  wide: [0.04, 0.0, 0.66, 0.2],
};

/** Never blow up RAM on the 1GB A1533: cap the upscaled crop's pixel count. */
var MAX_OUT_PIXELS = 1400000;

/**
 * @param {string} src
 * @returns {Promise<any>}
 */
function loadScript(src) {
  return new Promise(function (resolve, reject) {
    if (window.Tesseract) {
      resolve(window.Tesseract);
      return;
    }
    var s = document.createElement("script");
    s.src = src;
    s.onload = function () {
      resolve(window.Tesseract);
    };
    s.onerror = function () {
      reject(new Error("Failed to load local Tesseract: " + src));
    };
    document.head.appendChild(s);
  });
}

/**
 * @param {(status: string) => void} [onProgress]
 * @returns {Promise<any>}
 */
function getWorker(onProgress) {
  if (workerPromise) return workerPromise;
  workerPromise = loadScript("vendor/tesseract/tesseract.min.js").then(function (Tesseract) {
    // Vendored Tesseract.js is v4: createWorker takes ONE options argument, and
    // the language must be loaded + initialized explicitly. The v5 signature
    // (createWorker(lang, oem, opts)) silently drops these paths and falls back
    // to the CDN defaults — which cannot work offline.
    return Tesseract.createWorker({
      workerPath: PATHS.workerPath,
      langPath: PATHS.langPath,
      corePath: PATHS.corePath,
      // Bundled eng.traineddata is uncompressed; v4 expects .traineddata.gz otherwise.
      gzip: false,
      logger: function (/** @type {{ status?: string, progress?: number }} */ m) {
        if (onProgress && m && m.status) {
          var pct = m.progress != null ? " " + Math.round(m.progress * 100) + "%" : "";
          onProgress(m.status + pct);
        }
      },
    }).then(function (/** @type {any} */ worker) {
      return worker
        .loadLanguage("eng")
        .then(function () {
          return worker.initialize("eng");
        })
        .then(function () {
          // Single text line matches the one-line name band (Python uses --psm 7),
          // and the whitelist mirrors poke/ocr.py. cleanOcrText is still the
          // post-OCR filter, so dropping the whitelist here is safe if it regresses.
          return worker.setParameters({
            tessedit_pageseg_mode: "7",
            tessedit_char_whitelist:
              "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-",
          });
        })
        .then(function () {
          return worker;
        });
    });
  });
  // Don't cache a rejected worker — otherwise one failed init poisons every
  // later scan for the life of the page.
  workerPromise.catch(function () {
    workerPromise = null;
  });
  return workerPromise;
}

/**
 * @param {HTMLImageElement | HTMLCanvasElement} img
 * @param {number[]} [region]
 * @returns {HTMLCanvasElement}
 */
function cropNameRegion(img, region) {
  region = region || [0.08, 0.04, 0.55, 0.14];
  var canvas = document.createElement("canvas");
  var w = /** @type {HTMLImageElement} */ (img).naturalWidth || img.width;
  var h = /** @type {HTMLImageElement} */ (img).naturalHeight || img.height;
  var x0 = Math.floor(w * region[0]);
  var y0 = Math.floor(h * region[1]);
  var cw = Math.floor(w * region[2]);
  var ch = Math.floor(h * region[3]);
  canvas.width = Math.max(1, cw);
  canvas.height = Math.max(1, ch);
  var ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  ctx.drawImage(img, x0, y0, cw, ch, 0, 0, cw, ch);
  return canvas;
}

/**
 * Decide the integer upscale factor for a cropped name band. Mirrors the intent
 * of poke/ocr.py (3× for small crops, else 2×) but also guarantees the band is
 * tall enough for the LSTM and clamps total pixels for the 1GB device.
 * @param {number} cw
 * @param {number} ch
 * @param {"tight" | "wide"} profile
 * @returns {number}
 */
function upscaleFactor(cw, ch, profile) {
  var scale = Math.max(cw, ch) < 400 ? 3 : 2;
  // Small/distant cards produce a short band; push it up to a legible height.
  var minH = profile === "wide" ? 96 : 80;
  if (ch > 0 && ch * scale < minH) scale = Math.ceil(minH / ch);
  if (scale > 4) scale = 4;
  while (scale > 1 && cw * scale * (ch * scale) > MAX_OUT_PIXELS) scale -= 1;
  return scale < 1 ? 1 : scale;
}

/**
 * Preprocess a cropped name band the way poke/ocr.py does, in cheap ES2017
 * canvas ops: grayscale → adaptive upscale → light contrast stretch → local
 * (Bradley) adaptive threshold. Returns a black-text-on-white canvas that
 * Tesseract reads far more reliably than the raw photo crop.
 * @param {HTMLCanvasElement} src
 * @param {"tight" | "wide"} profile
 * @returns {HTMLCanvasElement}
 */
function preprocessForOcr(src, profile) {
  var cw = src.width;
  var ch = src.height;
  var scale = upscaleFactor(cw, ch, profile);
  var ow = Math.max(1, cw * scale);
  var oh = Math.max(1, ch * scale);

  var out = document.createElement("canvas");
  out.width = ow;
  out.height = oh;
  var ctx = out.getContext("2d");
  if (!ctx) return src; // Preprocessing is best-effort; fall back to the raw crop.
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(src, 0, 0, cw, ch, 0, 0, ow, oh);

  var imageData = ctx.getImageData(0, 0, ow, oh);
  var px = imageData.data;
  var n = ow * oh;

  // Grayscale (luma) into a compact array + histogram for the contrast stretch.
  var gray = new Uint8Array(n);
  var hist = new Uint32Array(256);
  var i;
  for (i = 0; i < n; i++) {
    var o = i << 2;
    var v = (px[o] * 299 + px[o + 1] * 587 + px[o + 2] * 114) / 1000;
    var g = v > 255 ? 255 : v < 0 ? 0 : v | 0;
    gray[i] = g;
    hist[g]++;
  }

  // Percentile contrast stretch (2%..98%) so faint low-contrast text separates
  // from the card stock before thresholding.
  var lowCut = n * 0.02;
  var highCut = n * 0.98;
  var acc = 0;
  var lo = 0;
  var hi = 255;
  for (i = 0; i < 256; i++) {
    acc += hist[i];
    if (acc <= lowCut) lo = i;
    if (acc < highCut) hi = i;
  }
  if (hi <= lo) {
    lo = 0;
    hi = 255;
  }
  var span = hi - lo;
  for (i = 0; i < n; i++) {
    var s = ((gray[i] - lo) * 255) / span;
    gray[i] = s > 255 ? 255 : s < 0 ? 0 : s | 0;
  }

  bradleyThreshold(gray, ow, oh);

  // Write the binarized values back (r=g=b, opaque).
  for (i = 0; i < n; i++) {
    var b = gray[i];
    var q = i << 2;
    px[q] = b;
    px[q + 1] = b;
    px[q + 2] = b;
    px[q + 3] = 255;
  }
  ctx.putImageData(imageData, 0, 0);
  return out;
}

/**
 * Bradley–Roth adaptive threshold via an integral image (O(n), one pass). Local
 * thresholding tolerates the uneven lighting and glare of a handheld photo the
 * way a single global cutoff cannot. Mutates `gray` in place to 0/255.
 * @param {Uint8Array} gray
 * @param {number} w
 * @param {number} h
 * @returns {void}
 */
function bradleyThreshold(gray, w, h) {
  // Integral image with a zero-filled first row/column so window sums need no
  // bounds checks. Max sum is 255 * w * h < 2^32 for our capped pixel count.
  var iw = w + 1;
  var integral = new Uint32Array(iw * (h + 1));
  var x;
  var y;
  for (y = 0; y < h; y++) {
    var rowSum = 0;
    for (x = 0; x < w; x++) {
      rowSum += gray[y * w + x];
      integral[(y + 1) * iw + (x + 1)] = integral[y * iw + (x + 1)] + rowSum;
    }
  }
  var s = Math.max(3, (w / 8) | 0); // window side ≈ width/8 (Bradley's default)
  var half = (s / 2) | 0;
  var t = 15; // pixel is text if ≥15% darker than its local mean
  for (y = 0; y < h; y++) {
    for (x = 0; x < w; x++) {
      var x1 = x - half;
      var y1 = y - half;
      var x2 = x + half;
      var y2 = y + half;
      if (x1 < 0) x1 = 0;
      if (y1 < 0) y1 = 0;
      if (x2 >= w) x2 = w - 1;
      if (y2 >= h) y2 = h - 1;
      var count = (x2 - x1 + 1) * (y2 - y1 + 1);
      var sum =
        integral[(y2 + 1) * iw + (x2 + 1)] -
        integral[y1 * iw + (x2 + 1)] -
        integral[(y2 + 1) * iw + x1] +
        integral[y1 * iw + x1];
      var idx = y * w + x;
      gray[idx] = gray[idx] * count <= (sum * (100 - t)) / 100 ? 0 : 255;
    }
  }
}

/**
 * @param {string} raw
 * @returns {string}
 */
function cleanOcrText(raw) {
  return String(raw || "")
    .replace(/[^A-Za-z\s\-']/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * @template T
 * @param {Promise<T>} promise
 * @param {number} ms
 * @param {string} [message]
 * @returns {Promise<T>}
 */
function withTimeout(promise, ms, message) {
  return new Promise(function (resolve, reject) {
    var settled = false;
    var timer = setTimeout(function () {
      if (settled) return;
      settled = true;
      reject(new Error(message || "Timed out after " + ms + "ms"));
    }, ms);
    promise.then(
      function (value) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(value);
      },
      function (err) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

/**
 * @param {HTMLImageElement | HTMLCanvasElement} img
 * @param {{ profile?: "tight" | "wide", timeoutMs?: number }} [opts]
 * @param {(status: string) => void} [onProgress]
 * @returns {Promise<OcrExtractResult>}
 */
function extractNameFromImage(img, opts, onProgress) {
  opts = opts || {};
  /** @type {"tight" | "wide"} */
  var profile = opts.profile === "wide" ? "wide" : "tight";
  var timeoutMs = opts.timeoutMs != null ? opts.timeoutMs : OCR_TIMEOUT_MS;
  var work = getWorker(onProgress).then(function (worker) {
    var cropped = cropNameRegion(img, CROP_PROFILES[profile]);
    var canvas = preprocessForOcr(cropped, profile);
    return worker.recognize(canvas).then(function (/** @type {{ data?: { text?: string } }} */ result) {
      var raw = result && result.data ? result.data.text : "";
      return { text: cleanOcrText(raw || ""), rawText: raw || "" };
    });
  });
  return withTimeout(work, timeoutMs, "OCR timed out — try search");
}

window.PokeOcr = {
  extractNameFromImage: extractNameFromImage,
  MIN_CONF: MIN_CONF,
  OCR_TIMEOUT_MS: OCR_TIMEOUT_MS,
};
