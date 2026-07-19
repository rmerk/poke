/** Offline OCR via vendored Tesseract.js (no CDN). */

var MIN_CONF = 72;
/** @type {Promise<any> | null} */
var workerPromise = null;

var PATHS = {
  workerPath: "vendor/tesseract/worker.min.js",
  langPath: "vendor/tesseract/lang",
  corePath: "vendor/tesseract/tesseract-core.wasm.js",
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
    return Tesseract.createWorker("eng", 1, {
      workerPath: PATHS.workerPath,
      langPath: PATHS.langPath,
      corePath: PATHS.corePath,
      logger: function (/** @type {{ status?: string, progress?: number }} */ m) {
        if (onProgress && m && m.status) {
          var pct = m.progress != null ? " " + Math.round(m.progress * 100) + "%" : "";
          onProgress(m.status + pct);
        }
      },
    });
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
 * @param {HTMLImageElement | HTMLCanvasElement} img
 * @param {(status: string) => void} [onProgress]
 * @returns {Promise<OcrExtractResult>}
 */
function extractNameFromImage(img, onProgress) {
  return getWorker(onProgress).then(function (worker) {
    var canvas = cropNameRegion(img);
    return worker.recognize(canvas).then(function (/** @type {{ data?: { text?: string } }} */ result) {
      var raw = result && result.data ? result.data.text : "";
      return { text: cleanOcrText(raw || ""), rawText: raw || "" };
    });
  });
}

window.PokeOcr = {
  extractNameFromImage: extractNameFromImage,
  MIN_CONF: MIN_CONF,
};
