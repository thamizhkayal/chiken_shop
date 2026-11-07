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
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(startupTimer);
    };
  }, [loadWallet]);

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
            <span><strong>Daily spin</strong><small>One free spin each day</small></span>
            <span aria-hidden="true">↗</span>
          </Link>
          <Link className="activity-link-card" href="/puzzles">
            <span className="activity-link-icon puzzle-icon" aria-hidden="true">?</span>
            <span><strong>Daily puzzle</strong><small>Answer correctly to earn points</small></span>
            <span aria-hidden="true">↗</span>
          </Link>
        </nav>
        <section className="wallet-activity" aria-labelledby="wallet-activity-title">
          <div className="wallet-activity-heading">
            <div>
              <p className="section-kicker">YOUR WALLET</p>
              <h2 id="wallet-activity-title">Recent activity</h2>
            </div>
            <span className="wallet-rule">1 point = 1 gram</span>
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
