"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

type Wallet = { balance_points: number; minimum_redemption_points: number };
type Redemption = {
  id: string;
  points: number;
  raw_chicken_grams: number;
  status: "PENDING" | "RESERVED" | "FULFILLED" | "EXPIRED" | "CANCELLED";
  expires_at: string;
  fulfilled_grams: number | null;
  fulfilled_at: string | null;
  created_at: string;
};
type RedemptionCreated = Redemption & { qr_svg: string };
type QrState = { id: string; svg: string; expires_at: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const format = new Intl.NumberFormat("en-US");

function qrImageSource(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export default function RedeemPage() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [redemptions, setRedemptions] = useState<Redemption[]>([]);
  const [amount, setAmount] = useState("100");
  const [qr, setQr] = useState<QrState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [walletResponse, redemptionResponse] = await Promise.all([
        fetch(`${API_URL}/wallet`, { credentials: "include" }),
        fetch(`${API_URL}/redemptions`, { credentials: "include" }),
      ]);
      const walletData = await walletResponse.json() as Wallet & { detail?: string };
      const redemptionData = await redemptionResponse.json() as Redemption[] & { detail?: string };
      if (!walletResponse.ok || !redemptionResponse.ok) {
        throw new Error(walletData.detail ?? redemptionData.detail ?? "Your wallet could not be loaded.");
      }
      setWallet(walletData);
      setRedemptions(redemptionData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Your wallet could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  async function createReservation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/redemptions`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ points: Number(amount) }),
      });
      const data = await response.json() as RedemptionCreated & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "The reservation could not be created.");
      setQr({ id: data.id, svg: data.qr_svg, expires_at: data.expires_at });
      setNotice(`${format.format(data.points)} points reserved. Show this QR code to shop staff before it expires.`);
      await loadData();
    } catch (reservationError) {
      setError(reservationError instanceof Error ? reservationError.message : "The reservation could not be created.");
    } finally {
      setSubmitting(false);
    }
  }

  async function showQr(redemption: Redemption) {
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_URL}/redemptions/${redemption.id}/qr`, {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json() as {
        redemption_id: string;
        expires_at: string;
        qr_svg: string;
        detail?: string;
      };
      if (!response.ok) throw new Error(data.detail ?? "A QR code is not available for this reservation.");
      setQr({ id: data.redemption_id, svg: data.qr_svg, expires_at: data.expires_at });
      setNotice("A fresh QR code is ready. Any previously issued code has been replaced.");
    } catch (qrError) {
      setError(qrError instanceof Error ? qrError.message : "A QR code is not available.");
      await loadData();
    }
  }

  async function cancelReservation(redemption: Redemption) {
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_URL}/redemptions/${redemption.id}/cancel`, {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json() as { status: string; refunded_points: number; detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "This reservation could not be cancelled.");
      setQr((current) => current?.id === redemption.id ? null : current);
      setNotice(`${format.format(data.refunded_points)} points were returned to your wallet.`);
      await loadData();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "This reservation could not be cancelled.");
    }
  }

  return (
    <main className="activity-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <Link className="button button-quiet" href="/dashboard">My wallet</Link>
      </header>
      <section className="activity-card redemption-card">
        <p className="section-kicker">REDEEM IN PERSON</p>
        <h1 className="activity-title">Chicken, on us.</h1>
        <p className="activity-description">
          Use your points for raw chicken at the shop. Every point is one gram; at least 100 points are needed.
          Your points are reserved until the QR code is fulfilled, cancelled, or expires.
        </p>
        {loading ? <p className="activity-message" role="status">Loading your wallet…</p> : null}
        {wallet && (
          <div className="redemption-balance">
            <span>AVAILABLE POINTS</span>
            <strong>{format.format(wallet.balance_points)} <small>pts</small></strong>
            <p>{format.format(wallet.balance_points)} grams of raw chicken · 1 point = 1 gram</p>
          </div>
        )}
        {wallet && (
          <form className="redemption-form" onSubmit={(event) => void createReservation(event)}>
            <label htmlFor="redemption-points">Points to redeem</label>
            <input
              id="redemption-points"
              max={wallet.balance_points}
              min={wallet.minimum_redemption_points}
              onChange={(event) => setAmount(event.target.value)}
              required
              step="1"
              type="number"
              value={amount}
            />
            <p className="redemption-help">Minimum {format.format(wallet.minimum_redemption_points)} points. That amount equals the chicken weight in grams.</p>
            <button
              className="button button-dark activity-button"
              disabled={submitting || wallet.balance_points < wallet.minimum_redemption_points}
              type="submit"
            >
              {submitting ? "Reserving points…" : "Reserve points and get QR"}
            </button>
          </form>
        )}
        {error && <p className="activity-error" role="alert">{error}</p>}
        {notice && <p className="activity-result" role="status">{notice}</p>}
        {qr && (
          <div className="redemption-qr">
            <Image
              alt="Single-use redemption QR code for shop staff"
              height={240}
              src={qrImageSource(qr.svg)}
              unoptimized
              width={240}
            />
            <p>Valid until {new Date(qr.expires_at).toLocaleString()}.</p>
            <p>Show this code to staff at the physical shop. It can only be used once.</p>
          </div>
        )}
        <section className="redemption-history" aria-labelledby="redemption-history-title">
          <h2 id="redemption-history-title">Your redemptions</h2>
          {redemptions.length === 0 ? (
            <p className="redemption-help">Your redemption history will appear here.</p>
          ) : (
            <ul>
              {redemptions.map((redemption) => (
                <li key={redemption.id}>
                  <div>
                    <strong>{format.format(redemption.points)} points · {format.format(redemption.raw_chicken_grams)}g</strong>
                    <small>{new Date(redemption.created_at).toLocaleString()}</small>
                    {redemption.fulfilled_grams !== null && (
                      <small>{format.format(redemption.fulfilled_grams)}g fulfilled</small>
                    )}
                  </div>
                  <span className={`redemption-status redemption-status-${redemption.status.toLowerCase()}`}>
                    {redemption.status}
                  </span>
                  {redemption.status === "RESERVED" && (
                    <div className="redemption-actions">
                      <button className="text-button" onClick={() => void showQr(redemption)} type="button">Show QR</button>
                      <button className="text-button" onClick={() => void cancelReservation(redemption)} type="button">Cancel and refund</button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}
