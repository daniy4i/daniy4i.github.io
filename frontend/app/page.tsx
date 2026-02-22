import Link from "next/link";

export default function Home() {
  return (
    <main className="stack">
      <section className="card hero">
        <h1>Traffic intelligence for safer city operations</h1>
        <p>
          Upload dashcam video, run event detection jobs, and review congestion and traffic behavior trends in one dashboard.
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link href="/upload"><button>Upload Video</button></Link>
          <Link href="/jobs"><button className="secondary">View Jobs</button></Link>
        </div>
      </section>

      <section className="grid cols-3">
        <article className="card">
          <h3>1. Ingest</h3>
          <p className="muted">Secure upload with file type and size checks.</p>
        </article>
        <article className="card">
          <h3>2. Process</h3>
          <p className="muted">Asynchronous analysis jobs with progress + retries.</p>
        </article>
        <article className="card">
          <h3>3. Review</h3>
          <p className="muted">Explore events, confidence scores, and congestion trends.</p>
        </article>
      </section>
    </main>
  );
}
