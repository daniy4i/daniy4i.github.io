"use client";
import { useEffect, useState } from "react";
import { apiFetch, login, parseJsonSafe } from "../../lib/api";

export default function OrgPage() {
  const [usage, setUsage] = useState<any>(null);
  const [tokens, setTokens] = useState<any[]>([]);
  const [created, setCreated] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const token = await login();
      const headers = { Authorization: `Bearer ${token}` };
      const [u, t] = await Promise.all([apiFetch("/org/usage", { headers }), apiFetch("/org/tokens", { headers })]);
      const [ud, td] = await Promise.all([parseJsonSafe(u), parseJsonSafe(t)]);
      if (!u.ok) throw new Error(ud?.detail || "Failed usage");
      if (!t.ok) throw new Error(td?.detail || "Failed tokens");
      setUsage(ud);
      setTokens(td || []);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed loading org");
    }
  }

  useEffect(() => { load(); }, []);

  async function createToken() {
    const token = await login();
    const r = await apiFetch("/org/tokens?name=web", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    const data = await parseJsonSafe(r);
    if (!r.ok) return setError(data?.detail || "Failed creating token");
    setCreated(data.token || "");
    await load();
  }

  async function revokeToken(id: number) {
    const token = await login();
    await apiFetch(`/org/tokens/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    await load();
  }

  return (
    <main className="stack">
      <section className="card">
        <h2>Organization Settings</h2>
        {error && <p className="error">{error}</p>}
        {usage && (
          <p className="muted">
            Usage {usage.year_month}: {usage.processed_minutes.toFixed(1)} / {usage.limits.processed_minutes} min, jobs {usage.jobs_total}/{usage.limits.jobs}, exports {usage.exports_total}/{usage.limits.exports}
          </p>
        )}
        <button className="btn btn-primary" onClick={createToken}>Create API Token</button>
        {created && <p className="success">New token (copy now): <code>{created}</code></p>}
      </section>
      <section className="card">
        <h3>API Tokens</h3>
        <ul>
          {tokens.map((t) => (
            <li key={t.id}>{t.name} {t.revoked_at ? "(revoked)" : "(active)"} {!t.revoked_at && <button className="btn btn-secondary" onClick={() => revokeToken(t.id)} style={{ marginLeft: 8 }}>Revoke</button>}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
