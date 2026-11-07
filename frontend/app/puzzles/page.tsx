"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Puzzle = { id: string; prompt: string; reward_points: number; attempted: boolean };
type AttemptResult = { is_correct: boolean; points_awarded: number; daily_points_remaining: number };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export default function PuzzlesPage() {
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const loadPuzzle = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/puzzles/today`, { credentials: "include" });
      if (!response.ok) throw new Error(response.status === 401 ? "Please log in to try today’s puzzle." : "Could not load today’s puzzle.");
      setPuzzle(await response.json() as Puzzle | null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load today’s puzzle.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadPuzzle(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadPuzzle]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!puzzle) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/puzzles/${puzzle.id}/attempt`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer }),
      });
      const data = await response.json() as AttemptResult & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Your answer could not be submitted.");
      setResult(data);
      setPuzzle({ ...puzzle, attempted: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Your answer could not be submitted.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="activity-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <Link className="button button-quiet" href="/dashboard">My wallet</Link>
      </header>
      <section className="activity-card puzzle-card">
        <p className="section-kicker">A QUICK BRAIN BREAK</p>
        <h1 className="activity-title">Today’s puzzle</h1>
        <p className="activity-description">Get it right to earn points. You get one answer per daily puzzle, and all activity rewards share your daily cap.</p>
        {loading ? <p className="activity-message" role="status">Finding today’s puzzle…</p> : error && !puzzle ? <p className="activity-error" role="alert">{error}</p> : null}
        {!loading && !error && !puzzle && <p className="activity-message">No puzzle is available today. Please check back soon.</p>}
        {puzzle && (
          <>
            <div className="puzzle-prompt"><span>DAILY QUESTION</span><p>{puzzle.prompt}</p><small>Correct answer reward: {puzzle.reward_points} points</small></div>
            {result ? (
              <p className="activity-result" role="status">
                {result.is_correct
                  ? `That’s right! ${result.points_awarded} ${result.points_awarded === 1 ? "point" : "points"} added to your wallet.`
                  : "Not quite. Your answer has been recorded; come back for tomorrow’s puzzle."}
              </p>
            ) : puzzle.attempted ? (
              <p className="activity-message">You’ve already answered today’s puzzle. Come back tomorrow for another.</p>
            ) : (
              <form className="puzzle-form" onSubmit={(event) => void submit(event)}>
                <label htmlFor="puzzle-answer">Your answer</label>
                <input id="puzzle-answer" maxLength={200} onChange={(event) => setAnswer(event.target.value)} required value={answer} />
                <button className="button button-dark activity-button" disabled={submitting || !answer.trim()} type="submit">
                  {submitting ? "Checking your answer…" : "Submit answer"}
                </button>
              </form>
            )}
          </>
        )}
        {error && puzzle && <p className="activity-error" role="alert">{error}</p>}
        {error && !puzzle && <button className="activity-retry" onClick={() => { setError(""); setLoading(true); void loadPuzzle(); }} type="button">Try again</button>}
        <p className="activity-policy">Your answer is checked privately by the server. One submission per puzzle prevents repeat rewards.</p>
        <Link className="text-link" href="/spin">Go to daily spin <span aria-hidden="true">↗</span></Link>
      </section>
    </main>
  );
}
