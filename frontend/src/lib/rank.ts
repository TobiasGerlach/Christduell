// Display helpers for the rank ladder. The backend owns the ladder itself
// (names, emojis, divisions, ladder_step); this file only formats it.

const ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V" };

export function romanDivision(division: number): string {
  return ROMAN[division] ?? String(division);
}

/** "Jünger III" — the full rank as players talk about it. */
export function formatRank(rank: string, division: number): string {
  return `${rank} ${romanDivision(division)}`;
}
