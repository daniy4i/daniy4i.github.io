"use client";
import { useEffect, useState } from "react";
import { API, apiFetch, login, parseJsonSafe } from "../../lib/api";

export default function DataProductPage() {
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = await login();
        const r = await apiFetch("/org/data_catalog", { headers: { Authorization: `Bearer ${token}` } });
        const data = await parseJsonSafe(r);
        if (!r.ok) throw new Error(data?.detail || "Failed loading catalog");
        setItems(data?.items || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed loading data catalog");
      }
    })();
  }, []);

  return (
    <main className="stack">
      <section className="card">
        <h2>Data Product Catalog</h2>
        {error && <p className="error">{error}</p>}
        <ul>
          {items.map((i) => (
            <li key={i.job_id}>
              Job #{i.job_id} • v{i.datapack_version} • hash {String(i.hash || "").slice(0, 12)}…
              <a className="btn btn-primary" style={{ marginLeft: 8 }} href={`${API}${i.download}`} target="_blank" rel="noreferrer">Download</a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
