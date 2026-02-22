"use client";
import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, BarChart, Bar } from "recharts";
import { apiFetch, login, parseJsonSafe } from "../../../lib/api";

export default function JobDetail({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>();
  const [events, setEvents] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = await login();
        const headers = { Authorization: `Bearer ${token}` };
        const [jobResp, eventsResp, analyticsResp] = await Promise.all([
          apiFetch(`/jobs/${params.id}`, { headers }),
          apiFetch(`/jobs/${params.id}/events`, { headers }),
          apiFetch(`/jobs/${params.id}/analytics`, { headers }),
        ]);
        const [jobData, eventsData, analyticsData] = await Promise.all([
          parseJsonSafe(jobResp), parseJsonSafe(eventsResp), parseJsonSafe(analyticsResp),
        ]);
        if (!jobResp.ok) throw new Error(jobData?.detail || `Failed to load job (${jobResp.status})`);
        if (!eventsResp.ok) throw new Error(eventsData?.detail || `Failed to load events (${eventsResp.status})`);
        if (!analyticsResp.ok) throw new Error(analyticsData?.detail || `Failed to load analytics (${analyticsResp.status})`);
        setJob(jobData);
        setEvents(eventsData || []);
        setAnalytics(analyticsData || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load job details");
      }
    })();
  }, [params.id]);

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
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card chart-wrap">
        <h3>Congestion Over Time</h3>
        <AreaChart width={900} height={260} data={analytics}>
          <XAxis dataKey="t_start" stroke="#a8bef2" />
          <YAxis stroke="#a8bef2" />
          <Tooltip />
          <Area dataKey="congestion_score" stroke="#37e8ff" fill="#37e8ff44" />
        </AreaChart>
      </section>

      <section className="card chart-wrap">
        <h3>Detected Behavior Events</h3>
        <BarChart width={900} height={260} data={events}>
          <XAxis dataKey="type" stroke="#a8bef2" />
          <YAxis stroke="#a8bef2" />
          <Tooltip />
          <Bar dataKey="confidence" fill="#9b7dff" />
        </BarChart>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Timestamp</th><th>Type</th><th>Confidence</th><th>Track</th><th>Review</th></tr></thead>
            <tbody>
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
