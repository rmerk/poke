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
 * @param {PokemonRecord} data
 * @returns {DexEntryView}
 */
function buildEntry(data) {
  var typesLine = data.types && data.types.length ? data.types.join(" / ") : "Unknown";
  var hw =
    data.heightM.toFixed(1) + " m · " + data.weightKg.toFixed(1) + " kg";
  var dexBit = data.dexNumber ? "National No. " + data.dexNumber + ". " : "";
  var abilities =
    data.abilities && data.abilities.length ? data.abilities.join(", ") : "Unknown";

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
    narration: narration.trim(),
    description: cleanFlavor(data.flavorText) || data.evolutionNote,
    facts: [
      "Type: " + typesLine,
      "Category: " + data.category,
      "Height / Weight: " + hw,
      "Ability: " + abilities,
      data.evolutionNote,
    ],
    attribution: "Data: PokéAPI snapshot (offline). Fan demo only.",
  };
}

window.PokeEntry = { buildEntry: buildEntry };
