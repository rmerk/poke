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
 * @param {(status: string) => void} [onProgress]
 * @returns {Promise<OcrExtractResult>}
 */
function extractNameFromImage(img, onProgress) {
  var work = getWorker(onProgress).then(function (worker) {
    var canvas = cropNameRegion(img);
    return worker.recognize(canvas).then(function (/** @type {{ data?: { text?: string } }} */ result) {
      var raw = result && result.data ? result.data.text : "";
      return { text: cleanOcrText(raw || ""), rawText: raw || "" };
    });
  });
  return withTimeout(work, OCR_TIMEOUT_MS, "OCR timed out — try search");
}

window.PokeOcr = {
  extractNameFromImage: extractNameFromImage,
  MIN_CONF: MIN_CONF,
};
