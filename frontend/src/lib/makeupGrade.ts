/**
 * Profile and makeup grade-down — mirrors app/services/makeup_grade.py, and is
 * carried over from the Phase 15 inline script unchanged.
 */
import type { MakeupRank } from "@/api/types";

export const RANK_ORDER: MakeupRank[] = [
  "GAME_CHANGER",
  "ALL_CONF",
  "WIN_PLUS",
  "WIN",
  "WIN_MINUS",
  "NGE",
];

export const RANK_LABEL: Record<MakeupRank, string> = {
  GAME_CHANGER: "Game-Changer",
  ALL_CONF: "All-Conf",
  WIN_PLUS: "Win+",
  WIN: "Win",
  WIN_MINUS: "Win-",
  NGE: "NGE",
};

/** Display a rank the backend sent, without inventing a label for one we do not know. */
export function rankLabel(rank: string): string {
  return RANK_LABEL[rank as MakeupRank] ?? rank;
}

export function averageMakeupGrade(
  grades: Record<string, MakeupRank | null | undefined>,
): MakeupRank | null {
  const provided = Object.values(grades).filter((g): g is MakeupRank => Boolean(g));
  if (!provided.length) return null;
  const indices = provided.map((g) => RANK_ORDER.indexOf(g));
  const avgIndex = Math.round(indices.reduce((a, b) => a + b, 0) / indices.length);
  return RANK_ORDER[avgIndex] ?? null;
}

export function shiftRank(rank: MakeupRank, steps: number): MakeupRank {
  return RANK_ORDER[Math.max(0, RANK_ORDER.indexOf(rank) - steps)] as MakeupRank;
}

export interface GradeDown {
  overall: MakeupRank;
  p4: MakeupRank;
  group_of_5: MakeupRank;
  fcs: MakeupRank;
  d2_d3_naia_juco: MakeupRank;
}

export function gradeDown(overall: MakeupRank): GradeDown {
  return {
    overall,
    p4: shiftRank(overall, 0),
    group_of_5: shiftRank(overall, 1),
    fcs: shiftRank(overall, 2),
    d2_d3_naia_juco: shiftRank(overall, 3),
  };
}

/** The five headline film metrics shown on the Truth Report. */
export const FILM_METRICS = [
  "Field Speed",
  "Contact",
  "Play Recognition",
  "Tackling",
  "Versatility",
] as const;
