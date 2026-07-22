/** TTS styled after the show's Pokédex ("Dexter"), two tiers:
 * 1. Bundled pre-rendered clips (web/data/audio/<slug>.mp3, built by
 *    scripts/build-voice-clips.py) — one fixed robotic voice on every
 *    device, played fully offline via <audio>.
 * 2. Web Speech API fallback when a clip is missing or fails: the most
 *    robotic system voice available (Fred, the classic MacInTalk robot
 *    voice iOS ships) with flattened low-pitch prosody. */

/** Ranked by how close each voice gets to the show's robotic register. */
var DEX_VOICE_PREFS = ["fred", "alex", "aaron", "daniel"];
var DEX_RATE = 0.95;
var DEX_PITCH = 0.5;

/** @type {HTMLAudioElement | null} */
var currentAudio = null;

/** True while a clip or speechSynthesis utterance is active. */
var speaking = false;

/**
 * Bumped on every stop (and at the start of each speak) so in-flight
 * onend/onerror handlers from a cancelled utterance don't flip state or
 * reject as a real failure.
 */
var speakGen = 0;

/** @type {Array<(active: boolean) => void>} */
var speakingListeners = [];

/** @type {Promise<VoiceManifest> | null} */
var voiceManifestPromise = null;

/**
 * The manifest carries the same normalized text the clips were rendered from
 * (see poke/tts_text.py), so the fallback speaks "Pokemon" and "Number 150"
 * rather than the raw "POKéMON" / "No. 150" the synthesizer mangles. Loaded
 * lazily: every species ships a clip, so this normally never fetches.
 * @returns {Promise<VoiceManifest>}
 */
function loadVoiceManifest() {
  if (voiceManifestPromise) return voiceManifestPromise;
  // The manifest tracks species_db.json, so a stale cached copy would
  // mis-describe the clip set. Share api.js's tag rather than repeating it —
  // a second literal here would drift the next time it is bumped.
  var url = "data/audio/manifest.json?v=" + window.PokeApi.dataVersion;
  voiceManifestPromise = fetch(url).then(function (res) {
    if (!res.ok) throw new Error("Missing voice manifest");
    return res.json();
  });
  return voiceManifestPromise;
}

/**
 * Resolves to the normalized line for `slug`, or `fallback` if the manifest
 * is unreachable — never rejects, since the caller is already a fallback.
 * @param {string} slug
 * @param {string} fallback
 * @returns {Promise<string>}
 */
function spokenTextFor(slug, fallback) {
  return loadVoiceManifest()
    .then(function (manifest) {
      var record = manifest.bySlug[slug];
      return (record && record.spoken) || fallback;
    })
    .catch(function () {
      return fallback;
    });
}

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
 * @param {boolean} next
 * @returns {void}
 */
function setSpeaking(next) {
  if (speaking === next) return;
  speaking = next;
  for (var i = 0; i < speakingListeners.length; i++) {
    speakingListeners[i](speaking);
  }
}

/**
 * @returns {boolean}
 */
function isSpeaking() {
  return speaking;
}

/**
 * @param {(active: boolean) => void} fn
 * @returns {() => void}
 */
function subscribeSpeaking(fn) {
  speakingListeners.push(fn);
  fn(speaking);
  return function () {
    var idx = speakingListeners.indexOf(fn);
    if (idx >= 0) speakingListeners.splice(idx, 1);
  };
}

/**
 * @param {string} text
 * @param {number} gen
 * @returns {Promise<string>}
 */
function speakSynth(text, gen) {
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
      if (gen !== speakGen) {
        resolve("cancelled");
        return;
      }
      setSpeaking(false);
      resolve("speechSynthesis" + (voice ? ":" + voice.name : ""));
    };
    u.onerror = function () {
      // cancel() surfaces as onerror — treat a stale gen as a clean stop.
      if (gen !== speakGen) {
        resolve("cancelled");
        return;
      }
      setSpeaking(false);
      reject(new Error("TTS error"));
    };
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  });
}

/**
 * @param {string} slug
 * @param {number} gen
 * @returns {Promise<string>}
 */
function speakClip(slug, gen) {
  return new Promise(function (resolve, reject) {
    var audio = new Audio("data/audio/" + slug + ".mp3");
    currentAudio = audio;
    audio.onended = function () {
      if (currentAudio === audio) currentAudio = null;
      if (gen !== speakGen) {
        resolve("cancelled");
        return;
      }
      setSpeaking(false);
      resolve("clip:" + slug);
    };
    audio.onerror = function () {
      if (currentAudio === audio) currentAudio = null;
      if (gen !== speakGen) {
        resolve("cancelled");
        return;
      }
      setSpeaking(false);
      reject(new Error("clip unavailable: " + slug));
    };
    setSpeaking(true);
    var p = audio.play();
    if (p && p.catch) {
      p.catch(function (/** @type {any} */ err) {
        if (gen !== speakGen) {
          resolve("cancelled");
          return;
        }
        setSpeaking(false);
        reject(err instanceof Error ? err : new Error(String(err)));
      });
    }
  });
}

/**
 * @param {string} text
 * @param {string} [slug]
 * @returns {Promise<string>}
 */
function speak(text, slug) {
  stopSpeaking();
  var gen = speakGen;
  if (slug) {
    return speakClip(slug, gen).catch(function () {
      if (gen !== speakGen) return "cancelled";
      return spokenTextFor(slug, text).then(function (spoken) {
        if (gen !== speakGen) return "cancelled";
        return speakSynth(spoken, gen);
      });
    });
  }
  return speakSynth(text, gen);
}

function stopSpeaking() {
  speakGen += 1;
  if (currentAudio) {
    currentAudio.pause();
    // Drop the src so iOS releases the decoder; pause alone can leave audio
    // buffered and briefly audible after a rapid Speak→Stop.
    try {
      currentAudio.removeAttribute("src");
      currentAudio.load();
    } catch (_e) {
      /* ignore */
    }
    currentAudio = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  setSpeaking(false);
}

window.PokeTts = {
  speak: speak,
  stop: stopSpeaking,
  isSpeaking: isSpeaking,
  subscribe: subscribeSpeaking,
};
