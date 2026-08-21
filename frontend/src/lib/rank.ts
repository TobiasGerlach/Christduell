// Display helpers for the rank ladder. The backend owns the ladder itself
// (names, emojis, divisions, ladder_step); this file formats it and maps each
// rank to its badge artwork (assets/ranks/, MMO-style: same smiley, more gear
// per rank — SVG sources sit next to the PNGs).

import type { ImageSourcePropType } from "react-native";

const RANK_IMAGES: Record<string, ImageSourcePropType> = {
  Ketzer: require("../../assets/ranks/rank-1.png"),
  Heide: require("../../assets/ranks/rank-2.png"),
  Umgekehrter: require("../../assets/ranks/rank-3.png"),
  Jünger: require("../../assets/ranks/rank-4.png"),
  Apostel: require("../../assets/ranks/rank-5.png"),
};

/** Badge artwork for a rank; unknown ranks fall back to the entry badge. */
export function rankImage(rank: string): ImageSourcePropType {
  return RANK_IMAGES[rank] ?? RANK_IMAGES.Ketzer;
}

const ROMAN: Record<number, string> = { 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V" };

export function romanDivision(division: number): string {
  return ROMAN[division] ?? String(division);
}

/** "Jünger III" — the full rank as players talk about it. */
export function formatRank(rank: string, division: number): string {
  return `${rank} ${romanDivision(division)}`;
}
