"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type Redemption = {
  redemption_id: string;
  customer_name: string;
  points_reserved: number;
  status: string;
  fulfilled_grams: number | null;
  created_at: string;
  fulfilled_at: string | null;
};
type Dashboard = {
  business_date: string;
  pending_redemptions: number;
  fulfilled_today: number;
  chicken_grams_fulfilled_today: number;
  recent_redemptions: Redemption[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const format = new Intl.NumberFormat("en-US");

export default function StaffDashboardPage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/staff/dashboard`, { credentials: "include" });
      if (!response.ok) {
        throw new Error(response.status === 401 || response.status === 403
          ? "A shop staff account is required."
          : "Could not load today’s shop activity.");
      }
      setDashboard(await response.json() as Dashboard);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load today’s shop activity.");
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

  return (
    <main className="dashboard-page operations-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <nav className="operations-nav" aria-label="Staff navigation">
          <Link className="button button-quiet" href="/staff/redemptions">Verify redemption</Link>
          <button className="button button-quiet" onClick={() => void logout()} type="button">Log out</button>
        </nav>
      </header>
      <section className="operations-content">
        <p className="section-kicker">SHOP STAFF · {dashboard?.business_date ?? "TODAY"}</p>
        <h1 className="operations-title">Today at the shop</h1>
        <p className="activity-description operations-description">Verify the customer’s QR code and record the actual chicken weight provided.</p>
        <Link className="button button-dark staff-primary-action" href="/staff/redemptions">Scan or verify a QR code <span aria-hidden="true">↗</span></Link>
        {loading && <p className="wallet-empty" role="status">Loading today’s redemptions…</p>}
        {error && <div className="operations-error"><p className="activity-error" role="alert">{error}</p><button className="activity-retry" onClick={() => { setLoading(true); void loadDashboard(); }} type="button">Try again</button></div>}
        {dashboard && (
          <>
            <section aria-label="Today’s redemption totals" className="operations-metrics operations-staff-metrics">
              <article className="operations-metric"><span>Waiting for fulfilment</span><strong>{format.format(dashboard.pending_redemptions)}</strong><small>Active customer reservations</small></article>
              <article className="operations-metric"><span>Fulfilled today</span><strong>{format.format(dashboard.fulfilled_today)}</strong><small>Completed redemptions</small></article>
              <article className="operations-metric"><span>Chicken provided</span><strong>{format.format(dashboard.chicken_grams_fulfilled_today)}g</strong><small>Recorded fulfilled weight</small></article>
            </section>
            <section className="operations-panel" aria-labelledby="recent-redemptions-title">
              <div className="wallet-activity-heading">
                <div><p className="section-kicker">CUSTOMER REWARDS</p><h2 id="recent-redemptions-title">Recent redemptions</h2></div>
                <Link className="text-link" href="/staff/redemptions">Scan code <span aria-hidden="true">↗</span></Link>
              </div>
              {dashboard.recent_redemptions.length === 0 ? (
                <p className="wallet-empty">No redemption activity yet. New reservations will appear here.</p>
              ) : (
                <ul className="staff-history">
                  {dashboard.recent_redemptions.map((redemption) => (
                    <li key={redemption.redemption_id}>
                      <div><strong>{redemption.customer_name}</strong><small>{format.format(redemption.points_reserved)}g reserved · {new Date(redemption.created_at).toLocaleString()}</small></div>
                      <span className={`redemption-status redemption-status-${redemption.status.toLowerCase()}`}>{redemption.status === "FULFILLED" && redemption.fulfilled_grams !== null ? `${format.format(redemption.fulfilled_grams)}g fulfilled` : redemption.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
