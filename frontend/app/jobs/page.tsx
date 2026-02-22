"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { API, login } from "../../lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      const token = await login();
      const r = await fetch(`${API}/jobs`, { headers: { Authorization: `Bearer ${token}` } });
      setJobs(await r.json());
    })();
  }, []);
  return <main style={{ padding: 24 }}><h2>Jobs</h2><table><thead><tr><th>ID</th><th>Status</th><th>File</th></tr></thead><tbody>{jobs.map(j => <tr key={j.id}><td><Link href={`/jobs/${j.id}`}>{j.id}</Link></td><td>{j.status}</td><td>{j.filename}</td></tr>)}</tbody></table></main>;
}
