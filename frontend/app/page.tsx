"use client";

import Link from "next/link";

const rewards = [
  { icon: "🎡", title: "Daily spin", description: "Start every visit with a chance to earn points." },
  { icon: "🧩", title: "Quick puzzles", description: "Solve a fresh challenge and grow your balance." },
  { icon: "🍗", title: "Real rewards", description: "1 point is always worth 1 gram of chicken." },
];

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden">
      <header className="site-header">
        <Link aria-label="Cluck Club home" className="brand" href="/">
          <span className="brand-mark">C</span>
          <span>cluck club</span>
        </Link>
        <nav aria-label="Main navigation" className="header-nav">
          <a className="nav-link" href="#how-it-works">How it works</a>
          <Link className="button button-quiet" href="/login">Log in</Link>
          <Link className="button button-dark" href="/register">Join free <span aria-hidden="true">↗</span></Link>
        </nav>
      </header>

      <section className="hero-section">
        <div className="hero-copy">
          <div className="eyebrow fade-in">
            <span className="eyebrow-dot" /> GOOD CHICKEN. GOOD KARMA.
          </div>
          <h1 className="headline fade-in fade-delay">
            Your next
            <br />
            <span className="headline-accent">meal is</span> on us.
          </h1>
          <p className="hero-description">
            Play a little. Earn points. Take home fresh chicken. Loyalty has never tasted this good.
          </p>
          <div className="hero-actions">
            <Link className="button button-dark button-large" href="/register">
              Start earning <span aria-hidden="true">↗</span>
            </Link>
            <a className="text-link" href="#how-it-works">See how it works <span aria-hidden="true">↓</span></a>
          </div>
          <div className="member-proof">
            <div aria-hidden="true" className="avatar-stack">
              <span>J</span><span>M</span><span>A</span><span>+</span>
            </div>
            <p><strong>Your neighborhood’s</strong><br />favorite little perk</p>
          </div>
        </div>

        <div className="hero-art fade-in art-delay">
          <div className="art-sun" />
          <div className="art-label"><span>FRESHLY</span><span>REWARDED</span></div>
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div aria-hidden="true" className="chicken-illustration">
            <span className="chicken-wing" />
            <span className="chicken-leg chicken-leg-one" />
            <span className="chicken-leg chicken-leg-two" />
            <span className="chicken-eye" />
            <span className="chicken-beak" />
            <span className="chicken-comb" />
          </div>
          <div className="floating-chip chip-points"><span>✦</span> +25 points</div>
          <div className="floating-chip chip-fresh"><span>✳</span> farm fresh</div>
          <div className="art-sticker">100 pts<br /><small>= 100g</small></div>
          <div className="art-footer"><span>GOOD THINGS<br />ARE GROWING</span><span>✳</span></div>
        </div>
        <div className="hero-scribble" aria-hidden="true">✳</div>
      </section>

      <section aria-label="How the loyalty programme works" className="steps-section" id="how-it-works">
        <div className="section-intro">
          <span className="section-kicker">THE GOOD STUFF</span>
          <h2>Small moments.<br /><span>Delicious rewards.</span></h2>
        </div>
        <div className="reward-grid">
          {rewards.map((reward, index) => (
            <article className="reward-card" key={reward.title}>
              <div className="reward-number">0{index + 1}</div>
              <div aria-hidden="true" className="reward-icon">{reward.icon}</div>
              <h3>{reward.title}</h3>
              <p>{reward.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="points-banner">
        <div className="banner-sparkle" aria-hidden="true">✳</div>
        <p>STRAIGHTFORWARD, JUST LIKE IT SHOULD BE</p>
        <h2>1 point = 1 gram.<br /><span>No funny business.</span></h2>
        <Link className="button button-light" href="/register">Get in on the good stuff <span aria-hidden="true">↗</span></Link>
      </section>

      <footer className="site-footer">
        <Link aria-label="Cluck Club home" className="brand" href="/">
          <span className="brand-mark">C</span><span>cluck club</span>
        </Link>
        <p>Good chicken. Good karma. © 2026</p>
        <div><a href="/terms">Terms</a><a href="/privacy">Privacy</a></div>
      </footer>
    </main>
  );
}
