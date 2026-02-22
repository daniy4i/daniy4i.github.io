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
          apiFetch(`/jobs/${params.id}/analytics`, { headers })
        ]);
        const [jobData, eventsData, analyticsData] = await Promise.all([
          parseJsonSafe(jobResp),
          parseJsonSafe(eventsResp),
          parseJsonSafe(analyticsResp),
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
    await apiFetch(`/events/${eventId}/review`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ review_status }) });
  }

  return <main style={{ padding: 24 }}>
    <h2>Job {params.id}</h2>
    <p>Status: {job?.status} | Duration: {job?.duration_s ?? 0}s</p>{error && <p>{error}</p>}
    <h3>Congestion Over Time</h3>
    <AreaChart width={700} height={200} data={analytics}><XAxis dataKey="t_start" /><YAxis /><Tooltip /><Area dataKey="congestion_score" /></AreaChart>
    <h3>Events</h3>
    <BarChart width={700} height={200} data={events}><XAxis dataKey="type" /><YAxis /><Tooltip /><Bar dataKey="confidence" /></BarChart>
    <table><thead><tr><th>ts</th><th>type</th><th>conf</th><th>track</th><th>review</th></tr></thead><tbody>{events.map(e => <tr key={e.id}><td>{e.timestamp}</td><td>{e.type}</td><td>{e.confidence}</td><td>{e.track_id}</td><td><button onClick={()=>review(e.id,'confirm')}>Confirm</button><button onClick={()=>review(e.id,'reject')}>Reject</button></td></tr>)}</tbody></table>
  </main>;
}
