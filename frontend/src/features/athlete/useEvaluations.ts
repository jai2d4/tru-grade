import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { athletes as athletesApi, evaluations as evaluationsApi } from "@/api/coachClient";
import type { Athlete, Evaluation } from "@/api/types";

export interface UseEvaluations {
  athlete: Athlete | null;
  /** Newest first — same order the backend returns. */
  evaluationList: Evaluation[];
  /** The Truth Report these pages read from: evaluationId if given, else the most recent. */
  selected: Evaluation | null;
  loading: boolean;
  error: string | null;
}

/** Shared data loading for the three athlete-facing screens that read Module 5 Truth Report history. */
export function useEvaluations(athleteId: string, evaluationId: string | null): UseEvaluations {
  const [athlete, setAthlete] = useState<Athlete | null>(null);
  const [evaluationList, setEvaluationList] = useState<Evaluation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([athletesApi.get(athleteId), evaluationsApi.list(athleteId)])
      .then(([athleteResult, evaluationsResult]) => {
        setAthlete(athleteResult);
        setEvaluationList(evaluationsResult);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError && err.status === 404
            ? "This athlete could not be found."
            : "Could not reach the TruGrade backend.",
        );
      })
      .finally(() => setLoading(false));
  }, [athleteId]);

  useEffect(() => {
    load();
  }, [load]);

  const selected = evaluationId
    ? (evaluationList.find((evaluation) => evaluation.id === evaluationId) ?? null)
    : (evaluationList[0] ?? null);

  return { athlete, evaluationList, selected, loading, error };
}
