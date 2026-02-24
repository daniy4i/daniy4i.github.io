"use client";
import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, BarChart, Bar } from "recharts";
import { API, apiFetch, login, parseJsonSafe } from "../../../lib/api";

export default function JobDetail({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>();
  const [events, setEvents] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [artifacts, setArtifacts] = useState<any[]>([]);
  const [clips, setClips] = useState<any[]>([]);
  const [clipFilter, setClipFilter] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = await login();
        const headers = { Authorization: `Bearer ${token}` };
        const clipQ = clipFilter ? `?clip_id=${encodeURIComponent(clipFilter)}` : "";
        const [jobResp, eventsResp, analyticsResp, artifactsResp, clipsResp, previewResp] = await Promise.all([
          apiFetch(`/jobs/${params.id}`, { headers }),
          apiFetch(`/jobs/${params.id}/events${clipQ}`, { headers }),
          apiFetch(`/jobs/${params.id}/analytics${clipQ}`, { headers }),
          apiFetch(`/jobs/${params.id}/artifacts`, { headers }),
          apiFetch(`/jobs/${params.id}/clips`, { headers }),
          apiFetch(`/jobs/${params.id}/artifacts/preview_tracking.mp4`, { headers }),
        ]);
        const [jobData, eventsData, analyticsData, artifactsData, clipsData, previewData] = await Promise.all([
          parseJsonSafe(jobResp), parseJsonSafe(eventsResp), parseJsonSafe(analyticsResp), parseJsonSafe(artifactsResp), parseJsonSafe(clipsResp), parseJsonSafe(previewResp),
        ]);
        if (!jobResp.ok) throw new Error(jobData?.detail || `Failed to load job (${jobResp.status})`);
        if (!eventsResp.ok) throw new Error(eventsData?.detail || `Failed to load events (${eventsResp.status})`);
        if (!analyticsResp.ok) throw new Error(analyticsData?.detail || `Failed to load analytics (${analyticsResp.status})`);
        setJob(jobData);
        setEvents(eventsData || []);
        setAnalytics(analyticsData || []);
        setArtifacts(artifactsData?.artifacts || []);
        setClips(clipsData?.clips || []);
        if (previewResp.ok) setPreviewUrl(previewData?.url || "");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load job details");
      }
    })();
  }, [params.id, clipFilter]);

  const eventsByType = Object.entries(events.reduce((acc, e) => {
    acc[e.type] = (acc[e.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>)).map(([type, count]) => ({ type, count }));

  const eventsOverTime = Object.entries(events.reduce((acc, e) => {
    const bucket = Math.floor(Number(e.timestamp || 0) / 10) * 10;
    acc[bucket] = (acc[bucket] || 0) + 1;
    return acc;
  }, {} as Record<string, number>))
    .map(([t, count]) => ({ t: Number(t), count }))
    .sort((a, b) => a.t - b.t);

  async function review(eventId: number, review_status: "confirm" | "reject") {
    const token = await login();
    await apiFetch(`/events/${eventId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ review_status }),
    });
  }

  return (
    <main className="stack">
      <section className="card">
        <h2>Job {params.id}</h2>
        <p className="muted">Status: {job?.status || "..."} • Duration: {job?.duration_s ?? 0}s</p>
        <p className="muted">Analytics windows: {analytics.length} • Events: {events.length}</p>
        <label className="muted">Clip filter:&nbsp;
          <select value={clipFilter} onChange={(e) => setClipFilter(e.target.value)}>
            <option value="">All clips</option>
            {clips.map((c) => <option key={c.clip_id} value={c.clip_id}>{c.clip_id}</option>)}
          </select>
        </label>
        {clips.length > 0 && <p className="muted">Clips: {clips.map((c) => c.clip_id).join(", ")}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h3>Processed Preview Video</h3>
        {!previewUrl && <p className="muted">Preview will appear after processing succeeds.</p>}
        {previewUrl && (
          <>
            <video controls style={{ width: "100%", borderRadius: 12, marginTop: 8 }} src={previewUrl} />
            <p style={{ marginTop: 10 }}>
              <a className="btn btn-primary" href={previewUrl} target="_blank" rel="noreferrer">Download result video</a>
            </p>
          </>
        )}
      </section>

      <section className="card">
        <h3>Download Artifacts</h3>
        <p>
          <a className="btn btn-primary" href={`${API}/jobs/${params.id}/data_pack?format=zip`} target="_blank" rel="noreferrer">
            Download Data Pack (ZIP)
          </a>
        </p>
        {artifacts.length === 0 && <p className="muted">Artifacts will appear after processing completes.</p>}
        <ul>
          {artifacts.map((a) => (
            <li key={a.name}>
              <a href={`${API}/jobs/${params.id}/artifacts/${a.name}`} target="_blank" rel="noreferrer">
                {a.name}
              </a>
              <span className="muted"> ({Math.round((a.size_bytes || 0) / 1024)} KB)</span>
              {a.sha256 && <code style={{ marginLeft: 8 }}>{String(a.sha256).slice(0, 12)}…</code>}
            </li>
          ))}
        </ul>
      </section>

      <section className="card chart-wrap">
        <h3>Congestion Over Time</h3>
        {analytics.length === 0 && <p className="muted">No congestion analytics yet. Wait for processing to complete.</p>}
        <AreaChart width={900} height={260} data={analytics}>
          <XAxis dataKey="t_start" stroke="#a8bef2" />
          <YAxis stroke="#a8bef2" />
          <Tooltip />
          <Area dataKey="congestion_score" stroke="#37e8ff" fill="#37e8ff44" />
        </AreaChart>
      </section>

      <section className="card chart-wrap">
        <h3>Detected Behavior Events (Count by Type)</h3>
        {eventsByType.length === 0 && <p className="muted">No behavior events detected for this video.</p>}
        <BarChart width={900} height={260} data={eventsByType}>
          <XAxis dataKey="type" stroke="#a8bef2" />
          <YAxis stroke="#a8bef2" />
          <Tooltip />
          <Bar dataKey="count" fill="#9b7dff" />
        </BarChart>
      </section>

      <section className="card chart-wrap">
        <h3>Events Over Time (10s buckets)</h3>
        {eventsOverTime.length === 0 && <p className="muted">No event timeline available yet.</p>}
        <AreaChart width={900} height={260} data={eventsOverTime}>
          <XAxis dataKey="t" stroke="#a8bef2" />
          <YAxis stroke="#a8bef2" />
          <Tooltip />
          <Area dataKey="count" stroke="#40ffa3" fill="#40ffa344" />
        </AreaChart>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Timestamp</th><th>Type</th><th>Confidence</th><th>Track</th><th>Review</th></tr></thead>
            <tbody>
              {events.length === 0 && (
                <tr><td colSpan={5} className="muted">No events for this job.</td></tr>
              )}
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{e.timestamp}</td>
                  <td>{e.type}</td>
                  <td>{e.confidence}</td>
                  <td>{e.track_id}</td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <button onClick={() => review(e.id, "confirm")} className="btn btn-primary" style={{ padding: "6px 10px" }}>Confirm</button>
                    <button onClick={() => review(e.id, "reject")} className="btn btn-secondary" style={{ padding: "6px 10px" }}>Reject</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
