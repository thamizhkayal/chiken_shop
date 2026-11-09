"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type WalletTransaction = {
  transaction_type: string;
  points_delta: number;
  description: string;
  created_at: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const PAGE_SIZE = 25;
const format = new Intl.NumberFormat("en-US");

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/wallet/transactions?limit=${PAGE_SIZE}&offset=${offset}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(response.status === 401
          ? "Your session has expired. Please log in again."
          : "Could not load your transaction history.");
      }
      setTransactions(await response.json() as WalletTransaction[]);
      setError("");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load your transaction history.");
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadTransactions(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadTransactions]);

  return (
    <main className="dashboard-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <Link className="button button-quiet" href="/dashboard">Back to dashboard</Link>
      </header>
      <section className="operations-content transaction-history-page">
        <p className="section-kicker">YOUR WALLET · 1 POINT = 1 GRAM</p>
        <h1 className="operations-title">Transaction history</h1>
        <p className="activity-description operations-description">A record of points earned, reserved, and returned to your wallet.</p>
        {loading && <p className="wallet-empty" role="status">Loading transactions…</p>}
        {error && <div className="operations-error"><p className="activity-error" role="alert">{error}</p><button className="activity-retry" onClick={() => void loadTransactions()} type="button">Try again</button></div>}
        {!loading && !error && (
          <>
            {transactions.length === 0 ? (
              <p className="wallet-empty">
                {offset === 0
                  ? "No wallet transactions yet. Earn or redeem points to see your history here."
                  : "You’ve reached the end of your transaction history."}
              </p>
            ) : (
              <ul className="wallet-transactions transaction-history-list">
                {transactions.map((transaction, index) => (
                  <li className="wallet-transaction" key={`${transaction.transaction_type}-${transaction.created_at}-${index}`}>
                    <div>
                      <strong>{transaction.description}</strong>
                      <small>{transaction.transaction_type.replaceAll("_", " ")}</small>
                      <time dateTime={transaction.created_at}>{new Date(transaction.created_at).toLocaleString()}</time>
                    </div>
                    <span className={transaction.points_delta < 0 ? "transaction-debit" : "transaction-credit"}>
                      {transaction.points_delta > 0 ? "+" : ""}{format.format(transaction.points_delta)} pts
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <nav aria-label="Transaction pages" className="transaction-pagination">
              <button className="button button-light" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} type="button">Newer</button>
              <span>Showing {format.format(offset + 1)}–{format.format(offset + transactions.length)}</span>
              <button className="button button-light" disabled={transactions.length < PAGE_SIZE || loading} onClick={() => setOffset(offset + PAGE_SIZE)} type="button">Older</button>
            </nav>
          </>
        )}
      </section>
    </main>
  );
}
