/** Shared types for Pocket Pokedex web JS (checkJs / tsc). */

interface PokemonRecord {
  name: string;
  displayName: string;
  types: string[];
  heightM: number;
  weightKg: number;
  abilities: string[];
  category: string;
  flavorText: string;
  evolutionNote: string;
  dexNumber: number | null;
}

interface SpeciesDbPayload {
  version: number;
  count: number;
  bySlug: { [slug: string]: PokemonRecord };
  aliases: { [key: string]: string };
}

interface MatchCandidate {
  name: string;
  score: number;
}

interface MatchResult {
  name: string;
  score: number;
  accepted: boolean;
  /** Top candidate was not separated from the runner-up; never auto-accepted. */
  ambiguous: boolean;
  candidates: MatchCandidate[];
}

interface DexEntryView {
  title: string;
  typesLine: string;
  category: string;
  heightWeight: string;
  narration: string;
  facts: string[];
  attribution: string;
}

interface VoiceClipRecord {
  file: string;
  /** sha1 of the narration template output. */
  sha1: string;
  /** sha1 of `spoken` — the text the clip was actually rendered from. */
  ttsSha1: string;
  /** Normalized narration, built by poke/tts_text.py. */
  spoken: string;
}

interface VoiceManifest {
  version: number;
  count: number;
  engine: string;
  pitchCents: number;
  bySlug: { [slug: string]: VoiceClipRecord };
}

interface OcrExtractResult {
  text: string;
  rawText: string;
}

interface PokeApiApi {
  fetchPokemon(name: string): Promise<PokemonRecord>;
  loadDb(): Promise<SpeciesDbPayload>;
  listSpeciesNames(payload: SpeciesDbPayload): string[];
  /** Cache-busting tag shared by every bundled-data fetch. */
  dataVersion: string;
}

interface PokeMatchApi {
  matchName(query: string, names: string[], minConfidence?: number): MatchResult;
  scorePair(query: string, name: string): number;
}

interface PokeEntryApi {
  buildEntry(data: PokemonRecord): DexEntryView;
}

interface PokeOcrApi {
  extractNameFromImage(
    img: HTMLImageElement | HTMLCanvasElement,
    onProgress?: (status: string) => void
  ): Promise<OcrExtractResult>;
  MIN_CONF: number;
}

interface PokeTtsApi {
  speak(text: string, slug?: string): Promise<string>;
  stop(): void;
}

interface Window {
  PokeApi: PokeApiApi;
  PokeMatch: PokeMatchApi;
  PokeEntry: PokeEntryApi;
  PokeOcr: PokeOcrApi;
  PokeTts: PokeTtsApi;
  Tesseract?: any;
}

declare var PokeApi: PokeApiApi;
declare var PokeMatch: PokeMatchApi;
declare var PokeEntry: PokeEntryApi;
declare var PokeOcr: PokeOcrApi;
declare var PokeTts: PokeTtsApi;
