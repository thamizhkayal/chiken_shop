"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";

type AuthMode = "login" | "register";
type AuthResponse = { id: string; email: string | null; phone: string | null; full_name: string; role: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const [formError, setFormError] = useState("");
  const [contact, setContact] = useState("");
  const [pending, setPending] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    setPending(true);
    const formData = new FormData(event.currentTarget);
    const body = isRegister
      ? {
          [contact.includes("@") ? "email" : "phone"]: contact,
          full_name: String(formData.get("full_name") ?? ""),
          password: String(formData.get("password") ?? ""),
        }
      : { identifier: contact, password: String(formData.get("password") ?? "") };
    try {
      const response = await fetch(`${API_URL}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        let error: { detail?: string } | null = null;
        try {
          error = await response.json() as { detail?: string };
        } catch {
          error = null;
        }
        throw new Error(error?.detail ?? "We couldn’t complete that request. Please try again.");
      }
      await response.json() as AuthResponse;
      router.push("/dashboard");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <Link aria-label="Cluck Club home" className="brand auth-brand" href="/">
          <span className="brand-mark">C</span><span>cluck club</span>
        </Link>
        <p className="section-kicker">{isRegister ? "A LITTLE MORE GOOD IN YOUR DAY" : "WELCOME BACK"}</p>
        <h1 className="auth-title">{isRegister ? "Join the club." : "Good to see you."}</h1>
        <p className="auth-description">
          {isRegister ? "Create your free account and start earning fresh rewards." : "Log in to check in on your points and rewards."}
        </p>
        <form className="auth-form" onSubmit={submit}>
          {isRegister && (
            <label>
              Your name
              <input autoComplete="name" name="full_name" maxLength={120} required />
            </label>
          )}
          <label>
            {isRegister ? "Email or mobile number" : "Email or mobile number"}
            <input
              autoComplete={isRegister ? "username" : "username"}
              name="identifier"
              onChange={(event) => setContact(event.target.value.trim())}
              placeholder={isRegister ? "you@example.com or +15551234567" : "you@example.com"}
              required
              type="text"
              value={contact}
            />
          </label>
          <label>
            Password
            <input
              autoComplete={isRegister ? "new-password" : "current-password"}
              minLength={isRegister ? 12 : 1}
              name="password"
              required
              type="password"
            />
            {isRegister && <span className="field-note">Use at least 12 characters.</span>}
          </label>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <button className="button button-dark auth-submit" disabled={pending} type="submit">
            {pending ? "One moment…" : isRegister ? "Create my account" : "Log in"}
            <span aria-hidden="true">↗</span>
          </button>
        </form>
        <p className="auth-switch">
          {isRegister ? "Already a member?" : "New around here?"}{" "}
          <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Log in" : "Join for free"}</Link>
        </p>
        {isRegister && <p className="policy-note">By joining, you agree to our <Link href="/terms">Terms</Link> and <Link href="/privacy">Privacy Policy</Link>.</p>}
      </section>
      <aside className="auth-aside">
        <div className="auth-aside-flower" aria-hidden="true">✳</div>
        <p>GOOD CHICKEN.<br /><span>GOOD KARMA.</span></p>
        <div className="auth-aside-note"><span>✦</span><strong>1 point = 1 gram</strong><small>Simple rewards, made fresh.</small></div>
      </aside>
    </main>
  );
}
