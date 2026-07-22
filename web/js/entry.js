/** Show-host entry builder. */

/**
 * Tidy raw PokéAPI flavor text for on-screen display: old-game copy SHOUTS
 * "POKéMON", and the source often carries stray line breaks. Kept in step with
 * poke/entry.py:_clean_flavor. (Speech normalization is separate — tts_text.py.)
 * @param {string} text
 * @returns {string}
 */
function cleanFlavor(text) {
  return (text || "")
    .replace(/POKéMON/g, "Pokémon")
    .replace(/POKÉMON/g, "Pokémon")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * PokéAPI gender_rate → chip label. Mirrors poke/entry.py:gender_label.
 * @param {number} rate
 * @returns {string}
 */
function genderLabel(rate) {
  if (rate < 0) return "—";
  if (rate === 0) return "♂";
  if (rate === 8) return "♀";
  return "♂ ♀";
}

/**
 * @param {PokemonRecord} data
 * @returns {DexEntryView}
 */
function buildEntry(data) {
  var typesLine = data.types && data.types.length ? data.types.join(" / ") : "Unknown";
  var hw =
    data.heightM.toFixed(1) + " m · " + data.weightKg.toFixed(1) + " kg";
  var dexBit = data.dexNumber ? "National No. " + data.dexNumber + ". " : "";
  var abilities =
    data.abilities && data.abilities.length ? data.abilities.slice() : [];
  var weaknesses =
    data.weaknesses && data.weaknesses.length ? data.weaknesses.slice() : [];
  var stats = data.baseStats || {
    hp: 0,
    attack: 0,
    defense: 0,
    specialAttack: 0,
    specialDefense: 0,
    speed: 0,
  };
  var chain =
    data.evolutionChain && data.evolutionChain.length
      ? data.evolutionChain.map(function (s) {
          return { slug: s.slug, displayName: s.displayName };
        })
      : [{ slug: data.name, displayName: data.displayName }];

  var narration =
    data.displayName +
    "! " +
    dexBit +
    "The " +
    data.category +
    ". This Pokémon is " +
    typesLine +
    " type, standing " +
    data.heightM.toFixed(1) +
    " meters tall and weighing " +
    data.weightKg.toFixed(1) +
    " kilograms. " +
    data.flavorText +
    " " +
    data.evolutionNote;

  if (narration.length > 520) {
    narration = narration.slice(0, 500).replace(/\s+\S*$/, "") + "…";
  }

  return {
    title: data.displayName,
    dexNumber: data.dexNumber,
    typesLine: typesLine,
    category: data.category,
    heightWeight: hw,
    genderLabel: genderLabel(typeof data.genderRate === "number" ? data.genderRate : -1),
    abilities: abilities,
    weaknesses: weaknesses,
    baseStats: {
      hp: stats.hp || 0,
      attack: stats.attack || 0,
      defense: stats.defense || 0,
      specialAttack: stats.specialAttack || 0,
      specialDefense: stats.specialDefense || 0,
      speed: stats.speed || 0,
    },
    evolutionChain: chain,
    narration: narration.trim(),
    description: cleanFlavor(data.flavorText) || data.evolutionNote,
    attribution: "Data: PokéAPI snapshot (offline). Fan demo only.",
  };
}

window.PokeEntry = { buildEntry: buildEntry };
