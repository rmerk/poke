/** TTS via Web Speech API (iPhone system voice). */

function speak(text) {
  return new Promise(function (resolve, reject) {
    if (!window.speechSynthesis) {
      reject(new Error("speechSynthesis not available"));
      return;
    }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05;
    u.pitch = 1.05;
    u.onend = function () {
      resolve("speechSynthesis");
    };
    u.onerror = function (e) {
      reject(new Error("TTS error"));
    };
    window.speechSynthesis.speak(u);
  });
}

function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

window.PokeTts = { speak: speak, stop: stopSpeaking };
