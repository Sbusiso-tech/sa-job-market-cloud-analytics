import { useCallback, useEffect, useState } from 'react';

export interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
  /** Replace the loaded data locally (e.g. after a mutation) without refetching. */
  setData: (update: (prev: T | undefined) => T | undefined) => void;
}

interface Result<T> {
  source: () => Promise<T>;
  attempt: number;
  data: T | undefined;
  error: unknown;
}

/**
 * Runs `load` whenever its identity changes (wrap it in useCallback) or `reload` is called.
 * Stale data stays visible while a reload is in flight.
 */
export function useAsync<T>(load: () => Promise<T>): AsyncState<T> {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);

  useEffect(() => {
    let active = true;
    load().then(
      (data) => {
        if (active) setResult({ source: load, attempt, data, error: undefined });
      },
      (error: unknown) => {
        if (active) setResult((prev) => ({ source: load, attempt, data: prev?.data, error }));
      },
    );
    return () => {
      active = false;
    };
  }, [load, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  const setData = useCallback(
    (update: (prev: T | undefined) => T | undefined) =>
      setResult((prev) => (prev ? { ...prev, data: update(prev.data) } : prev)),
    [],
  );

  const current = result !== null && result.source === load && result.attempt === attempt;
  return {
    data: result?.data,
    error: current ? result.error : undefined,
    loading: !current,
    reload,
    setData,
  };
}
