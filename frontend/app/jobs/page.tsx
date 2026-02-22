"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, login, parseJsonSafe } from "../../lib/api";

type Job = { id: number; status: string; filename: string; created_at?: string };

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");

  const loadJobs = useCallback(async () => {
    try {
      const token = await login();
      const r = await apiFetch("/jobs", { headers: { Authorization: `Bearer ${token}` } });
      const data = await parseJsonSafe(r);
      if (!r.ok) throw new Error(data?.detail || `Failed to load jobs (${r.status})`);
      setJobs(data || []);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    }
  }, []);

  useEffect(() => {
    loadJobs();
    const id = setInterval(loadJobs, 5000);
    return () => clearInterval(id);
  }, [loadJobs]);

  async function runJob(jobId: number) {
    try {
      const token = await login();
      const r = await apiFetch(`/jobs/${jobId}/run`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      const data = await parseJsonSafe(r);
      if (!r.ok) throw new Error(data?.detail || `Failed to run job (${r.status})`);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to run job");
    }
  }

  return (
    <main className="stack">
      <section className="card">
        <h2>Processing Jobs</h2>
        <p className="muted">Track every uploaded video from queue to analytics review.</p>
        {error && <p className="error">{error}</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Status</th><th>File</th><th>Action</th></tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td><Link href={`/jobs/${j.id}`} className="btn btn-secondary" style={{ padding: "6px 10px" }}>{j.id}</Link></td>
                  <td><span className={`tag ${j.status}`}>{j.status}</span></td>
                  <td>{j.filename}</td>
                  <td>{j.status === "queued" ? <button onClick={() => runJob(j.id)} className="btn btn-primary" style={{ padding: "6px 10px" }}>Run now</button> : <span className="muted">Auto</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
