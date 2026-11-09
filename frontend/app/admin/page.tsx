"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type Dashboard = {
  business_date: string;
  total_customers: number;
  daily_active_customers: number;
  total_points_issued: number;
  outstanding_points: number;
  total_points_redeemed: number;
  total_chicken_grams_redeemed: number;
  pending_redemptions: number;
  completed_redemptions: number;
  expired_redemptions: number;
  cancelled_redemptions: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const format = new Intl.NumberFormat("en-US");

export default function AdminDashboardPage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/admin/dashboard`, { credentials: "include" });
      if (!response.ok) {
        throw new Error(response.status === 401 || response.status === 403
          ? "An administrator account is required."
          : "Could not load the shop dashboard.");
      }
      setDashboard(await response.json() as Dashboard);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load the shop dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadDashboard(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDashboard]);

  async function logout() {
    try {
      const response = await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
      if (!response.ok) {
        setError("Could not log out. Please try again.");
        return;
      }
      router.push("/");
    } catch {
      setError("Could not log out. Please check your connection and try again.");
    }
  }

  const metrics = dashboard ? [
    { label: "Registered customers", value: format.format(dashboard.total_customers), note: `${format.format(dashboard.daily_active_customers)} active today` },
    { label: "Points issued", value: format.format(dashboard.total_points_issued), note: "Lifetime reward and adjustment credits" },
    { label: "Outstanding points", value: format.format(dashboard.outstanding_points), note: "Current customer wallet balances" },
    { label: "Chicken redeemed", value: `${format.format(dashboard.total_chicken_grams_redeemed)}g`, note: `${format.format(dashboard.total_points_redeemed)} points fulfilled` },
  ] : [];

  return (
    <main className="dashboard-page operations-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <nav className="operations-nav" aria-label="Admin navigation">
          <Link className="button button-quiet" href="/admin/activities">Manage activities</Link>
          <Link className="button button-quiet" href="/staff/redemptions">Staff scanner</Link>
          <button className="button button-quiet" onClick={() => void logout()} type="button">Log out</button>
        </nav>
      </header>
      <section className="operations-content">
        <p className="section-kicker">SHOP MANAGEMENT · {dashboard?.business_date ?? "TODAY"}</p>
        <h1 className="operations-title">Shop overview</h1>
        <p className="activity-description operations-description">A clear view of customer activity, points liability, and in-store redemptions.</p>
        {loading && <p className="wallet-empty" role="status">Loading shop totals…</p>}
        {error && <div className="operations-error"><p className="activity-error" role="alert">{error}</p><button className="activity-retry" onClick={() => { setLoading(true); void loadDashboard(); }} type="button">Try again</button></div>}
        {dashboard && (
          <>
            <section aria-label="Shop totals" className="operations-metrics">
              {metrics.map((metric) => (
                <article className="operations-metric" key={metric.label}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.note}</small>
                </article>
              ))}
            </section>
            <section className="operations-panel" aria-labelledby="redemption-summary-title">
              <div className="wallet-activity-heading">
                <div>
                  <p className="section-kicker">IN-STORE REWARDS</p>
                  <h2 id="redemption-summary-title">Redemption status</h2>
                </div>
                <Link className="text-link" href="/staff/redemptions">Open scanner <span aria-hidden="true">↗</span></Link>
              </div>
              <div className="operations-status-grid">
                <p><span>Waiting at shop</span><strong>{format.format(dashboard.pending_redemptions)}</strong></p>
                <p><span>Completed</span><strong>{format.format(dashboard.completed_redemptions)}</strong></p>
                <p><span>Expired</span><strong>{format.format(dashboard.expired_redemptions)}</strong></p>
                <p><span>Cancelled</span><strong>{format.format(dashboard.cancelled_redemptions)}</strong></p>
              </div>
            </section>
            <section className="operations-panel" aria-labelledby="admin-tools-title">
              <p className="section-kicker">QUICK ACTIONS</p>
              <h2 id="admin-tools-title">Keep the club running</h2>
              <div className="activity-links">
                <Link className="activity-link-card" href="/admin/activities">
                  <span className="activity-link-icon">✳</span>
                  <span><strong>Rewards and puzzles</strong><small>Update spin odds, earning cap, and daily puzzles</small></span>
                  <span aria-hidden="true">↗</span>
                </Link>
                <Link className="activity-link-card" href="/staff/redemptions">
                  <span className="activity-link-icon puzzle-icon">✓</span>
                  <span><strong>Verify a redemption</strong><small>Scan a customer’s single-use QR code</small></span>
                  <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
