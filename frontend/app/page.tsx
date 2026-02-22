import Link from "next/link";

export default function Home() {
  return (
    <main className="stack">
      <section className="card hero">
        <h1>Neon-grade traffic intelligence for modern city operations</h1>
        <p>
          Upload dashcam footage, run YOLO-based tracking jobs, and transform behavior/congestion signals into powerful operational insights.
        </p>
        <div className="hero-actions">
          <Link href="/upload" className="btn btn-primary">Upload Video</Link>
          <Link href="/jobs" className="btn btn-secondary">Open Jobs Dashboard</Link>
        </div>
      </section>

      <section className="grid cols-3">
        <article className="card">
          <h3>Realtime Detection</h3>
          <p className="muted">YOLO tracking with stable IDs and confidence-scored behavior events.</p>
        </article>
        <article className="card">
          <h3>Async Processing</h3>
          <p className="muted">Reliable queue-based video processing with logs and retries.</p>
        </article>
        <article className="card">
          <h3>Data Product Layer</h3>
          <p className="muted">Anonymized aggregate traffic analytics with SHA-256 integrity hash.</p>
        </article>
      </section>
    </main>
  );
}
