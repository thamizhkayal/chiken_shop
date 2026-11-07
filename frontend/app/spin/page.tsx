"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";

type SpinStatus = {
  enabled: boolean;
  spun_today: boolean;
  daily_points_earned: number;
  daily_points_remaining: number;
  rewards: { points: number; probability_basis_points: number }[];
};
type SpinResult = {
  points_awarded: number;
  reward_points: number;
  reward_index: number;
  daily_points_earned: number;
  daily_points_remaining: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const format = new Intl.NumberFormat("en-US");
const wheelColors = ["#e9683c", "#e7a97d", "#49634d", "#f2c65d", "#bb6d43"];

export default function SpinPage() {
  const [status, setStatus] = useState<SpinStatus | null>(null);
  const [result, setResult] = useState<SpinResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [spinning, setSpinning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const wheelStops: string[] = [];
  let probabilityOffset = 0;
  status?.rewards.forEach((reward, index) => {
    const start = probabilityOffset / 100;
    probabilityOffset += reward.probability_basis_points;
    wheelStops.push(`${wheelColors[index % wheelColors.length]} ${start}% ${probabilityOffset / 100}%`);
  });
  const targetReward = result && status?.rewards[result.reward_index];
  const midpointBasisPoints = targetReward
    ? status!.rewards.slice(0, result!.reward_index).reduce((sum, item) => sum + item.probability_basis_points, 0)
      + targetReward.probability_basis_points / 2
    : 0;
  const targetRotation = result
    ? `${1980 + ((360 - midpointBasisPoints / 10_000 * 360 + 360) % 360)}deg`
    : "1980deg";
  const wheelStyle = {
    background: wheelStops.length > 0 ? `conic-gradient(${wheelStops.join(", ")})` : undefined,
    "--wheel-target-rotation": targetRotation,
  } as CSSProperties & { "--wheel-target-rotation": string };
  const loadStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/spin/status`, { credentials: "include" });
      if (!response.ok) throw new Error(response.status === 401 ? "Please log in to use your daily spin." : "Could not load spin status.");
      setStatus(await response.json() as SpinStatus);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load spin status.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadStatus(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  async function spin() {
    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/spin`, { method: "POST", credentials: "include" });
      const data = await response.json() as SpinResult & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Your spin could not be completed.");
      setResult(data);
      setSpinning(true);
      await loadStatus();
    } catch (spinError) {
      setError(spinError instanceof Error ? spinError.message : "Your spin could not be completed.");
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
      <section className="activity-card">
        <p className="section-kicker">A LITTLE DAILY EXTRA</p>
        <h1 className="activity-title">Daily spin</h1>
        <p className="activity-description">One free spin each day. Spin and puzzle rewards share a daily points cap; daily login points are separate.</p>
        {loading ? <p className="activity-message" role="status">Loading your spin…</p> : error && !result ? <p className="activity-error" role="alert">{error}</p> : null}
        <div
          aria-label={spinning ? "Spinning for your server-selected reward" : "Daily reward wheel"}
          className={`reward-wheel${spinning ? " reward-wheel-spinning" : ""}`}
          onAnimationEnd={() => setSpinning(false)}
          role="img"
          style={wheelStyle}
        >
          <span className="reward-wheel-center">C</span>
        </div>
        {result && !spinning && (
          <p className="activity-result" role="status">
            {result.points_awarded > 0
              ? result.points_awarded < result.reward_points
                ? `Your spin landed on ${format.format(result.reward_points)} points. ${format.format(result.points_awarded)} added because of today’s activity cap.`
                : `You earned ${format.format(result.points_awarded)} ${result.points_awarded === 1 ? "point" : "points"}!`
              : "Your activity points allowance is used up for today."}
          </p>
        )}
        {error && result && <p className="activity-error" role="alert">{error}</p>}
        <p className="activity-cap">Today: {format.format(status?.daily_points_earned ?? 0)} earned · {format.format(status?.daily_points_remaining ?? 0)} remaining</p>
        <button
          className="button button-dark activity-button"
          disabled={loading || submitting || spinning || !status?.enabled || status?.spun_today}
          onClick={() => void spin()}
          type="button"
        >
          {submitting ? "Getting your result…" : status?.spun_today ? "Come back tomorrow" : status?.enabled ? "Spin once today" : "Spin is unavailable"}
        </button>
        {error && !result && <button className="activity-retry" onClick={() => { setError(""); setLoading(true); void loadStatus(); }} type="button">Try again</button>}
        <p className="activity-policy">Your reward is selected by the server before the wheel moves. Published reward odds are shown below.</p>
        <ul className="activity-odds">
          {(status?.rewards ?? []).map((reward) => (
            <li key={reward.points}><span>{reward.points} points</span><span>{(reward.probability_basis_points / 100).toFixed(2)}%</span></li>
          ))}
        </ul>
        <Link className="text-link" href="/puzzles">Try today’s puzzle <span aria-hidden="true">↗</span></Link>
      </section>
    </main>
  );
}
