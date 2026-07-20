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

/* ---------- State machine (web/js/machine.js) ---------- */

/** Why a match didn't resolve to an entry. Data, never display copy. */
type UnresolvedReason =
  | { kind: "low-confidence"; score: number }
  | { kind: "ambiguous"; count: number }
  | { kind: "ocr-timeout" }
  | { kind: "ocr-failed"; message: string }
  | { kind: "empty-query" };

/** What the busy screen is waiting on. */
type BusyPhase =
  | { kind: "demo"; forcedName: string }
  | { kind: "ocr" }
  | { kind: "lookup"; name: string };

/** Exactly one variant per screen in index.html. */
type PokeState =
  | { screen: "idle" }
  | { screen: "busy"; phase: BusyPhase; detail: string }
  | { screen: "preview"; image: HTMLImageElement }
  | { screen: "search"; candidates: MatchCandidate[]; reason: UnresolvedReason | null }
  | { screen: "entry"; entry: DexEntryView; slug: string }
  | { screen: "error"; message: string };

/** Everything a user gesture can express. */
type PokeIntent =
  | { type: "PHOTO_SELECTED"; file: File }
  | { type: "IDENTIFY_REQUESTED" }
  | { type: "DEMO_REQUESTED" }
  | { type: "SEARCH_OPENED" }
  | { type: "SEARCH_SUBMITTED"; query: string }
  | { type: "CANDIDATE_PICKED"; index: number }
  | { type: "SPEAK_REQUESTED" }
  | { type: "BACK_PRESSED" };

/** The five collaborators. Injectable so a headless test can stub them. */
interface PokeMachineDeps {
  api: PokeApiApi;
  match: PokeMatchApi;
  entry: PokeEntryApi;
  ocr: PokeOcrApi;
  tts: PokeTtsApi;
}

interface PokeMachineApi {
  /** Loads the offline DB, then settles on idle (or error). Defaults deps to the window globals. */
  start(deps?: Partial<PokeMachineDeps>): void;
  /** Fire a user intent. Never throws; an intent that makes no sense in the current state is ignored. */
  dispatch(intent: PokeIntent): void;
  /** Called immediately with the current state, then on every change. Returns an unsubscribe fn. */
  subscribe(listener: (state: PokeState, prev: PokeState | null) => void): () => void;
  /** Frozen current state, for debugging and button routing. */
  getState(): PokeState;
  /** Ring buffer of the last ~20 {intent, screen} pairs — an on-device debugging aid. */
  history(): ReadonlyArray<{ intent: string; screen: string }>;
}

interface Window {
  PokeApi: PokeApiApi;
  PokeMatch: PokeMatchApi;
  PokeEntry: PokeEntryApi;
  PokeOcr: PokeOcrApi;
  PokeTts: PokeTtsApi;
  PokeMachine: PokeMachineApi;
  Tesseract?: any;
}

declare var PokeMachine: PokeMachineApi;
