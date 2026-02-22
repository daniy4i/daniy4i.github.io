import Link from "next/link";

export default function Home() {
  return (
    <main style={{ padding: 24, fontFamily: "sans-serif" }}>
      <h1>NYC Traffic Intelligence</h1>
      <p>Enterprise-ready MVP for dashcam ingestion and behavior analytics.</p>
      <ul>
        <li><Link href="/upload">Upload</Link></li>
        <li><Link href="/jobs">Jobs</Link></li>
      </ul>
    </main>
  );
}
