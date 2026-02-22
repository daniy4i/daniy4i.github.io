"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, login, parseJsonSafe } from "../../lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    (async () => {
      try {
        const token = await login();
        const r = await apiFetch(`/jobs`, { headers: { Authorization: `Bearer ${token}` } });
        const data = await parseJsonSafe(r);
        if (!r.ok) throw new Error(data?.detail || `Failed to load jobs (${r.status})`);
        setJobs(data || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load jobs");
      }
    })();
  }, []);
  return <main style={{ padding: 24 }}><h2>Jobs</h2>{error && <p>{error}</p>}<table><thead><tr><th>ID</th><th>Status</th><th>File</th></tr></thead><tbody>{jobs.map(j => <tr key={j.id}><td><Link href={`/jobs/${j.id}`}>{j.id}</Link></td><td>{j.status}</td><td>{j.filename}</td></tr>)}</tbody></table></main>;
}
