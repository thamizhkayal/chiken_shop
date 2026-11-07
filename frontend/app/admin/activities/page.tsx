"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type Reward = { points: number; probability_basis_points: number };
type Configuration = {
  enabled: boolean;
  puzzle_enabled: boolean;
  daily_activity_cap: number;
  rewards: Reward[];
};

export default function AdminActivitiesPage() {
  const [configuration, setConfiguration] = useState<Configuration | null>(null);
  const [businessDate, setBusinessDate] = useState("");
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [puzzleReward, setPuzzleReward] = useState(5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadConfiguration = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/admin/activities/configuration`, { credentials: "include" });
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? "An administrator account is required." : "Could not load activity settings.");
      setConfiguration(await response.json() as Configuration);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load activity settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadConfiguration(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadConfiguration]);

  function updateReward(index: number, field: keyof Reward, value: number) {
    if (!configuration) return;
    setConfiguration({
      ...configuration,
      rewards: configuration.rewards.map((reward, currentIndex) =>
        currentIndex === index ? { ...reward, [field]: value } : reward
      ),
    });
  }

  async function saveConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configuration) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/admin/activities/configuration`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configuration),
      });
      const data = await response.json() as Configuration & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Settings could not be saved.");
      setConfiguration(data);
      setMessage("Activity settings saved and recorded in the audit log.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Settings could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function createPuzzle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/admin/puzzles`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_date: businessDate,
          prompt,
          answer,
          reward_points: puzzleReward,
          is_active: true,
        }),
      });
      const data = await response.json() as { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Puzzle could not be created.");
      setPrompt("");
      setAnswer("");
      setMessage("Puzzle created and recorded in the audit log.");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Puzzle could not be created.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="activity-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <Link className="button button-quiet" href="/dashboard">Customer wallet</Link>
      </header>
      <section className="activity-card admin-activity-card">
        <p className="section-kicker">SHOP MANAGEMENT</p>
        <h1 className="activity-title">Daily activities</h1>
        <p className="activity-description">Configure spin odds and the shared daily activity cap, then publish a puzzle for a business-local date.</p>
        {loading && <p className="activity-message" role="status">Loading settings…</p>}
        {error && <p className="activity-error" role="alert">{error}</p>}
        {error && !configuration && <button className="activity-retry" onClick={() => { setError(""); setLoading(true); void loadConfiguration(); }} type="button">Try again</button>}
        {message && <p className="activity-result" role="status">{message}</p>}
        {configuration && (
          <form className="admin-activity-form" onSubmit={(event) => void saveConfiguration(event)}>
            <h2>Spin and earning limits</h2>
            <label className="admin-check"><input checked={configuration.enabled} onChange={(event) => setConfiguration({ ...configuration, enabled: event.target.checked })} type="checkbox" /> Enable daily spin</label>
            <label className="admin-check"><input checked={configuration.puzzle_enabled} onChange={(event) => setConfiguration({ ...configuration, puzzle_enabled: event.target.checked })} type="checkbox" /> Enable puzzles</label>
            <label>Activity points cap per customer per day
              <input min={1} max={10000} onChange={(event) => setConfiguration({ ...configuration, daily_activity_cap: Number(event.target.value) })} type="number" value={configuration.daily_activity_cap} />
            </label>
            <div className="admin-rewards">
              <strong>Spin outcomes</strong>
              {configuration.rewards.map((reward, index) => (
                <div className="admin-reward-row" key={`reward-${index}`}>
                  <label>Points<input min={0} max={20} onChange={(event) => updateReward(index, "points", Number(event.target.value))} type="number" value={reward.points} /></label>
                  <label>Probability (%)<input min={0.01} max={100} onChange={(event) => updateReward(index, "probability_basis_points", Math.round(Number(event.target.value) * 100))} step={0.01} type="number" value={reward.probability_basis_points / 100} /></label>
                  <button aria-label={`Remove ${reward.points}-point reward`} className="admin-remove" disabled={configuration.rewards.length <= 1} onClick={() => setConfiguration({ ...configuration, rewards: configuration.rewards.filter((_, currentIndex) => currentIndex !== index) })} type="button">Remove</button>
                </div>
              ))}
              <button className="activity-retry" disabled={configuration.rewards.length >= 20} onClick={() => setConfiguration({ ...configuration, rewards: [...configuration.rewards, { points: 1, probability_basis_points: 1 }] })} type="button">Add reward outcome</button>
              <p className="activity-policy">Probabilities must add up to exactly 100%. Daily cap: spin and puzzle rewards combined; login points are separate.</p>
            </div>
            <button className="button button-dark activity-button" disabled={saving} type="submit">{saving ? "Saving…" : "Save activity settings"}</button>
          </form>
        )}
        <form className="admin-activity-form puzzle-admin-form" onSubmit={(event) => void createPuzzle(event)}>
          <h2>Publish a daily puzzle</h2>
          <label>Business date<input onChange={(event) => setBusinessDate(event.target.value)} required type="date" value={businessDate} /></label>
          <label>Question<textarea maxLength={500} onChange={(event) => setPrompt(event.target.value)} required rows={3} value={prompt} /></label>
          <label>Correct answer<input maxLength={200} onChange={(event) => setAnswer(event.target.value)} required type="text" value={answer} /></label>
          <label>Reward points<input min={1} max={10000} onChange={(event) => setPuzzleReward(Number(event.target.value))} required type="number" value={puzzleReward} /></label>
          <button className="button button-dark activity-button" disabled={saving || !configuration?.puzzle_enabled} type="submit">{saving ? "Publishing…" : "Publish puzzle"}</button>
        </form>
      </section>
    </main>
  );
}
