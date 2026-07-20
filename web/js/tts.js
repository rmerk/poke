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
  voiceManifestPromise = fetch("data/audio/manifest.json").then(function (res) {
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
 * @param {string} text
 * @returns {Promise<string>}
 */
function speakSynth(text) {
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

/**
 * @param {string} slug
 * @returns {Promise<string>}
 */
function speakClip(slug) {
  return new Promise(function (resolve, reject) {
    var audio = new Audio("data/audio/" + slug + ".mp3");
    currentAudio = audio;
    audio.onended = function () {
      if (currentAudio === audio) currentAudio = null;
      resolve("clip:" + slug);
    };
    audio.onerror = function () {
      reject(new Error("clip unavailable: " + slug));
    };
    var p = audio.play();
    if (p && p.catch) {
      p.catch(function (/** @type {any} */ err) {
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
  if (slug) {
    return speakClip(slug).catch(function () {
      return spokenTextFor(slug, text).then(speakSynth);
    });
  }
  return speakSynth(text);
}

function stopSpeaking() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

window.PokeTts = { speak: speak, stop: stopSpeaking };
