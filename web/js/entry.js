/** Show-host entry builder. */

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
