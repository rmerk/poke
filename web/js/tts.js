/** TTS via Web Speech API, styled after the show's Pokédex ("Dexter"):
 * a flat, deadpan, robotic delivery. True voice cloning is impossible
 * offline on iOS 12 Safari, so we pick the most robotic system voice
 * available (Fred, the classic MacInTalk robot voice iOS ships) and
 * flatten the prosody with a low pitch and measured rate. */

/** Ranked by how close each voice gets to the show's robotic register. */
var DEX_VOICE_PREFS = ["fred", "alex", "aaron", "daniel"];
var DEX_RATE = 0.95;
var DEX_PITCH = 0.5;

/**
 * iOS populates getVoices() asynchronously and voiceschanged is unreliable
 * on iOS 12, so query fresh on every speak() instead of caching a pick.
 * @returns {SpeechSynthesisVoice | null}
 */
function pickDexVoice() {
  if (!window.speechSynthesis || !window.speechSynthesis.getVoices) return null;
  var voices = window.speechSynthesis.getVoices() || [];
  var i;
  var j;
  for (i = 0; i < DEX_VOICE_PREFS.length; i++) {
    for (j = 0; j < voices.length; j++) {
      if (voices[j].name && voices[j].name.toLowerCase().indexOf(DEX_VOICE_PREFS[i]) === 0) {
        return voices[j];
      }
    }
  }
  for (j = 0; j < voices.length; j++) {
    if (voices[j].lang && voices[j].lang.toLowerCase().indexOf("en-us") === 0) {
      return voices[j];
    }
  }
  for (j = 0; j < voices.length; j++) {
    if (voices[j].lang && voices[j].lang.toLowerCase().indexOf("en") === 0) {
      return voices[j];
    }
  }
  return null;
}

/**
 * @param {string} text
 * @returns {Promise<string>}
 */
function speak(text) {
  return new Promise(function (resolve, reject) {
    if (!window.speechSynthesis) {
      reject(new Error("speechSynthesis not available"));
      return;
    }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    var voice = pickDexVoice();
    if (voice) u.voice = voice;
    u.lang = "en-US";
    u.rate = DEX_RATE;
    u.pitch = DEX_PITCH;
    u.onend = function () {
      resolve("speechSynthesis" + (voice ? ":" + voice.name : ""));
    };
    u.onerror = function () {
      reject(new Error("TTS error"));
    };
    window.speechSynthesis.speak(u);
  });
}

function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

window.PokeTts = { speak: speak, stop: stopSpeaking };
