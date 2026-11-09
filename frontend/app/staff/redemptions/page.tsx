"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type BarcodeResult = { rawValue: string };
type QrDetector = { detect: (source: HTMLVideoElement) => Promise<BarcodeResult[]> };
type QrDetectorConstructor = new (options: { formats: string[] }) => QrDetector;
type WindowWithBarcodeDetector = Window & { BarcodeDetector?: QrDetectorConstructor };
type VerifiedRedemption = {
  redemption_id: string;
  customer_name: string;
  points_reserved: number;
  maximum_grams: number;
  status: string;
  expires_at: string;
};
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const format = new Intl.NumberFormat("en-US");

export default function StaffRedemptionPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [token, setToken] = useState("");
  const [grams, setGrams] = useState("");
  const [verified, setVerified] = useState<VerifiedRedemption | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!cameraActive) return;
    let active = true;
    let stream: MediaStream | undefined;
    let timer = 0;
    const videoElement = videoRef.current;
    const detectorConstructor = (window as WindowWithBarcodeDetector).BarcodeDetector;
    async function startCamera() {
      if (!detectorConstructor || !navigator.mediaDevices?.getUserMedia) {
        setError("Camera QR scanning is not supported here. Use a QR scanner connected as a keyboard, or enter the scanned code.");
        setCameraActive(false);
        return;
      }
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } });
      const video = videoElement;
      if (!video || !active) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      video.srcObject = stream;
      await video.play();
      const detector = new detectorConstructor({ formats: ["qr_code"] });
      const scan = async () => {
        if (!active) return;
        try {
          const codes = await detector.detect(video);
          if (codes[0]?.rawValue) {
            setToken(codes[0].rawValue);
            setCameraActive(false);
            setError("");
            setNotice("Code scanned. Verify it before entering the fulfilled weight.");
            return;
          }
        } catch (scanError) {
          setError(scanError instanceof Error ? scanError.message : "Could not read the QR code.");
          setCameraActive(false);
          return;
        }
        timer = window.setTimeout(() => { void scan(); }, 250);
      };
      void scan();
    }
    void startCamera().catch((cameraError: unknown) => {
      if (active) {
        setError(cameraError instanceof Error ? cameraError.message : "Could not start the camera.");
        setCameraActive(false);
      }
    });
    return () => {
      active = false;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
      if (videoElement) videoElement.srcObject = null;
    };
  }, [cameraActive]);

  async function verifyToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setNotice("");
    setVerified(null);
    try {
      const response = await fetch(`${API_URL}/staff/redemptions/verify`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await response.json() as VerifiedRedemption & { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "This QR code could not be verified.");
      setVerified(data);
      setGrams(String(data.maximum_grams));
    } catch (verifyError) {
      setError(verifyError instanceof Error ? verifyError.message : "This QR code could not be verified.");
    } finally {
      setLoading(false);
    }
  }

  async function fulfill(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!verified) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_URL}/staff/redemptions/fulfill`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, grams: Number(grams) }),
      });
      const data = await response.json() as { fulfilled_grams: number; refunded_points: number; detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "The redemption could not be completed.");
      setNotice(
        `${format.format(data.fulfilled_grams)}g fulfilled. ${format.format(data.refunded_points)} unused points refunded.`,
      );
      setVerified(null);
      setToken("");
      setGrams("");
    } catch (fulfillError) {
      setError(fulfillError instanceof Error ? fulfillError.message : "The redemption could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="activity-page">
      <header className="site-header dashboard-header">
        <Link className="brand" href="/"><span className="brand-mark">C</span><span>cluck club</span></Link>
        <span className="section-kicker">SHOP STAFF</span>
      </header>
      <section className="activity-card redemption-card">
        <p className="section-kicker">SINGLE-USE CODE CHECK</p>
        <h1 className="activity-title">Verify redemption</h1>
        <p className="activity-description">Scan the customer’s QR code, confirm the weight provided, then fulfill the redemption.</p>
        <button
          className="button button-light"
          disabled={cameraActive || loading}
          onClick={() => { setError(""); setCameraActive(true); }}
          type="button"
        >
          {cameraActive ? "Camera is scanning…" : "Scan with camera"}
        </button>
        {cameraActive && <video aria-label="Camera view for scanning redemption QR codes" className="redemption-camera" muted playsInline ref={videoRef} />}
        <form className="redemption-form staff-scan-form" onSubmit={(event) => void verifyToken(event)}>
          <label htmlFor="qr-token">QR token</label>
          <input
            autoComplete="off"
            id="qr-token"
            onChange={(event) => { setToken(event.target.value); setVerified(null); }}
            placeholder="Scan or enter the code"
            required
            value={token}
          />
          <p className="redemption-help">A connected handheld QR scanner can type directly into this field.</p>
          <button className="button button-dark activity-button" disabled={loading || !token.trim()} type="submit">
            {loading ? "Checking…" : "Verify code"}
          </button>
        </form>
        {error && <p className="activity-error" role="alert">{error}</p>}
        {notice && <p className="activity-result" role="status">{notice}</p>}
        {verified && (
          <section className="staff-redemption-details" aria-label="Verified reservation">
            <p><span>Customer</span><strong>{verified.customer_name}</strong></p>
            <p><span>Reserved</span><strong>{format.format(verified.points_reserved)} points · up to {format.format(verified.maximum_grams)}g</strong></p>
            <p><span>Valid until</span><strong>{new Date(verified.expires_at).toLocaleString()}</strong></p>
            <form className="redemption-form" onSubmit={(event) => void fulfill(event)}>
              <label htmlFor="fulfilled-grams">Chicken weight provided (grams)</label>
              <input
                id="fulfilled-grams"
                max={verified.maximum_grams}
                min="1"
                onChange={(event) => setGrams(event.target.value)}
                required
                step="1"
                type="number"
                value={grams}
              />
              <p className="redemption-help">Cannot exceed {format.format(verified.maximum_grams)}g. Unused points are refunded.</p>
              <button className="button button-dark activity-button" disabled={loading} type="submit">
                {loading ? "Completing…" : "Confirm and fulfill"}
              </button>
            </form>
          </section>
        )}
      </section>
    </main>
  );
}
