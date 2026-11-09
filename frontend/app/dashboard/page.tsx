"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type User = { id: string; email: string | null; phone: string | null; full_name: string; role: string };
type Wallet = {
  balance_points: number;
  raw_chicken_grams: number;
  minimum_redemption_points: number;
  points_to_grams_rule: string;
};
type WalletTransaction = {
  transaction_type: string;
  points_delta: number;
  description: string;
  created_at: string;
};
type SpinStatus = { enabled: boolean; spun_today: boolean; spins_remaining: number; spin_limit: number };
type PuzzleStatus = { attempted: boolean } | null;
type Redemption = { id: string; points: number; status: string; created_at: string; fulfilled_grams: number | null };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const numberFormat = new Intl.NumberFormat("en-US");

export default function DashboardPage() {
  const router = useRouter();
  const [account, setAccount] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [walletLoading, setWalletLoading] = useState(true);
  const [walletError, setWalletError] = useState("");
  const [logoutError, setLogoutError] = useState("");
  const [spinStatus, setSpinStatus] = useState<SpinStatus | null>(null);
  const [puzzleStatus, setPuzzleStatus] = useState<PuzzleStatus>(null);
  const [redemptions, setRedemptions] = useState<Redemption[]>([]);
  const [activityError, setActivityError] = useState("");

  const loadWallet = useCallback(async () => {
    try {
      const [walletResponse, transactionsResponse] = await Promise.all([
        fetch(`${API_URL}/wallet`, { credentials: "include" }),
        fetch(`${API_URL}/wallet/transactions?limit=5`, { credentials: "include" }),
      ]);
      if (walletResponse.status === 401 || transactionsResponse.status === 401) {
        throw new Error("Your session has expired. Please log in again.");
      }
      if (!walletResponse.ok || !transactionsResponse.ok) {
        throw new Error("We couldn’t load your wallet. Please try again.");
      }
      const walletData = await walletResponse.json() as Wallet;
      const transactionData = await transactionsResponse.json() as WalletTransaction[];
      setWallet(walletData);
      setTransactions(transactionData);
    } catch (loadError) {
      setWalletError(loadError instanceof Error ? loadError.message : "Unable to load your wallet.");
    } finally {
      setWalletLoading(false);
    }
  }, []);

  const loadActivities = useCallback(async () => {
    try {
      const [spinResponse, puzzleResponse, redemptionResponse] = await Promise.all([
        fetch(`${API_URL}/spin/status`, { credentials: "include" }),
        fetch(`${API_URL}/puzzles/today`, { credentials: "include" }),
        fetch(`${API_URL}/redemptions?limit=5`, { credentials: "include" }),
      ]);
      if ([spinResponse, puzzleResponse, redemptionResponse].some((response) => response.status === 401)) {
        throw new Error("Your session has expired. Please log in again.");
      }
      if ([spinResponse, puzzleResponse, redemptionResponse].some((response) => !response.ok)) {
        throw new Error("Some dashboard activity could not be loaded.");
      }
      setSpinStatus(await spinResponse.json() as SpinStatus);
      setPuzzleStatus(await puzzleResponse.json() as PuzzleStatus);
      setRedemptions(await redemptionResponse.json() as Redemption[]);
      setActivityError("");
    } catch (loadError) {
      setActivityError(loadError instanceof Error ? loadError.message : "Dashboard activity is unavailable.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function loadProfile() {
      try {
        const response = await fetch(`${API_URL}/users/me`, { credentials: "include" });
        if (!response.ok) throw new Error("Please log in to view your account.");
        const profile = await response.json() as User;
        if (active) setAccount(profile);
      } catch (loadError) {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load your account.");
      } finally {
        if (active) setLoading(false);
      }
    }
    const startupTimer = window.setTimeout(() => {
      void loadProfile();
      void loadWallet();
      void loadActivities();
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(startupTimer);
    };
  }, [loadActivities, loadWallet]);

  async function handleLogout() {
    setLogoutError("");
    try {
      const response = await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
      if (!response.ok) throw new Error("Couldn’t log out. Please try again.");
      router.push("/");
    } catch (logoutFailure) {
      setLogoutError(logoutFailure instanceof Error ? logoutFailure.message : "Couldn’t log out.");
    }
  }

  if (loading) return <main className="dashboard-page"><p className="dashboard-state">Getting your account ready…</p></main>;
  if (error || !account) return <main className="dashboard-page"><div className="auth-card"><h1 className="auth-title">Please log in.</h1><p className="auth-description">{error}</p><Link className="button button-dark" href="/login">Log in <span aria-hidden="true">↗</span></Link></div></main>;

  return (
    <main className="dashboard-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <button className="button button-quiet" onClick={() => void handleLogout()} type="button">Log out</button>
      </header>
      <section className="dashboard-welcome">
        <p className="section-kicker">YOUR LITTLE CORNER OF THE CLUB</p>
        <h1 className="auth-title">Hey, {account.full_name.split(" ")[0]}.</h1>
        <p className="auth-description">Your points and recent wallet activity, all in one place.</p>
        <div className="dashboard-balance">
          <span>YOUR POINTS BALANCE</span>
          {walletLoading ? (
            <p className="wallet-loading" role="status">Loading your wallet…</p>
          ) : walletError ? (
            <div className="wallet-error">
              <p className="form-error" role="alert">{walletError}</p>
              <button className="button button-light" onClick={() => { setWalletLoading(true); setWalletError(""); void loadWallet(); }} type="button">Try again</button>
            </div>
          ) : wallet ? (
            <>
              <strong>{numberFormat.format(wallet.balance_points)} <small>pts</small></strong>
              <p>That’s {numberFormat.format(wallet.raw_chicken_grams)} grams of raw chicken. {wallet.points_to_grams_rule}.</p>
              <p className="wallet-redemption-note">
                {wallet.balance_points >= wallet.minimum_redemption_points
                  ? `You have enough points to redeem at the shop (minimum ${numberFormat.format(wallet.minimum_redemption_points)} points).`
                  : `Earn ${numberFormat.format(wallet.minimum_redemption_points - wallet.balance_points)} more points to reach the ${numberFormat.format(wallet.minimum_redemption_points)}-point redemption minimum.`}
              </p>
              <p className="wallet-login-note">Log in once each day to earn 1 point.</p>
            </>
          ) : null}
        </div>
        <nav className="activity-links" aria-label="Earn points">
          <Link className="activity-link-card" href="/spin">
            <span className="activity-link-icon" aria-hidden="true">↻</span>
            <span><strong>Daily spin</strong><small>
              {spinStatus
                ? !spinStatus.enabled
                  ? "Temporarily unavailable"
                  : spinStatus.spins_remaining > 0
                    ? `${spinStatus.spins_remaining} spin${spinStatus.spins_remaining === 1 ? "" : "s"} available today`
                    : "Come back tomorrow"
                : "Check today’s spin"}
            </small></span>
            <span aria-hidden="true">↗</span>
          </Link>
          <Link className="activity-link-card" href="/puzzles">
            <span className="activity-link-icon puzzle-icon" aria-hidden="true">?</span>
            <span><strong>Daily puzzle</strong><small>
              {puzzleStatus ? puzzleStatus.attempted ? "You’ve tried today’s puzzle" : "Ready for today’s challenge" : "Check today’s challenge"}
            </small></span>
            <span aria-hidden="true">↗</span>
          </Link>
          <Link className="activity-link-card" href="/redeem">
            <span className="activity-link-icon" aria-hidden="true">✓</span>
            <span><strong>Redeem chicken</strong><small>Use your points at the shop</small></span>
            <span aria-hidden="true">↗</span>
          </Link>
        </nav>
        {activityError && <p className="form-error" role="alert">{activityError}</p>}
        <section className="redemption-history dashboard-redemption-history" aria-labelledby="dashboard-redemption-title">
          <div className="wallet-activity-heading">
            <div>
              <p className="section-kicker">AT THE SHOP</p>
              <h2 id="dashboard-redemption-title">Recent redemptions</h2>
            </div>
            <Link className="text-link" href="/redeem">Redeem <span aria-hidden="true">↗</span></Link>
          </div>
          {redemptions.length === 0 ? (
            <p className="wallet-empty">Your chicken redemptions will appear here.</p>
          ) : (
            <ul>
              {redemptions.map((redemption) => (
                <li key={redemption.id}>
                  <div>
                    <strong>{numberFormat.format(redemption.fulfilled_grams ?? redemption.points)}g chicken</strong>
                    <small>{new Date(redemption.created_at).toLocaleDateString()}</small>
                  </div>
                  <span className={`redemption-status redemption-status-${redemption.status.toLowerCase()}`}>{redemption.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="wallet-activity" aria-labelledby="wallet-activity-title">
          <div className="wallet-activity-heading">
            <div>
              <p className="section-kicker">YOUR WALLET</p>
              <h2 id="wallet-activity-title">Recent activity</h2>
            </div>
            <div className="wallet-history-actions">
              <span className="wallet-rule">1 point = 1 gram</span>
              <Link className="text-link" href="/transactions">Full history <span aria-hidden="true">↗</span></Link>
            </div>
          </div>
          {walletLoading ? (
            <p className="wallet-empty" role="status">Loading recent activity…</p>
          ) : walletError ? (
            <p className="wallet-empty">Activity is unavailable until your wallet loads.</p>
          ) : transactions.length === 0 ? (
            <p className="wallet-empty">No wallet activity yet. Your points will show up here when you earn or use them.</p>
          ) : (
            <ul className="wallet-transactions">
              {transactions.map((transaction, index) => (
                <li className="wallet-transaction" key={`${transaction.transaction_type}-${transaction.created_at}-${index}`}>
                  <div>
                    <strong>{transaction.description}</strong>
                    <time dateTime={transaction.created_at}>
                      {new Date(transaction.created_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </time>
                  </div>
                  <span className={transaction.points_delta < 0 ? "transaction-debit" : "transaction-credit"}>
                    {transaction.points_delta > 0 ? "+" : ""}{numberFormat.format(transaction.points_delta)} pts
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <Link className="text-link" href="/">Back to the club <span aria-hidden="true">↗</span></Link>
        {logoutError && <p className="form-error" role="alert">{logoutError}</p>}
      </section>
    </main>
  );
}
