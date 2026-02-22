"use client";
import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, BarChart, Bar } from "recharts";
import { API, login } from "../../../lib/api";

export default function JobDetail({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<any>();
  const [events, setEvents] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      const token = await login();
      const headers = { Authorization: `Bearer ${token}` };
      setJob(await (await fetch(`${API}/jobs/${params.id}`, { headers })).json());
      setEvents(await (await fetch(`${API}/jobs/${params.id}/events`, { headers })).json());
      setAnalytics(await (await fetch(`${API}/jobs/${params.id}/analytics`, { headers })).json());
    })();
  }, [params.id]);

  async function review(eventId: number, review_status: "confirm" | "reject") {
    const token = await login();
    await fetch(`${API}/events/${eventId}/review`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ review_status }) });
  }

  return <main style={{ padding: 24 }}>
    <h2>Job {params.id}</h2>
    <p>Status: {job?.status} | Duration: {job?.duration_s ?? 0}s</p>
    <h3>Congestion Over Time</h3>
    <AreaChart width={700} height={200} data={analytics}><XAxis dataKey="t_start" /><YAxis /><Tooltip /><Area dataKey="congestion_score" /></AreaChart>
    <h3>Events</h3>
    <BarChart width={700} height={200} data={events}><XAxis dataKey="type" /><YAxis /><Tooltip /><Bar dataKey="confidence" /></BarChart>
    <table><thead><tr><th>ts</th><th>type</th><th>conf</th><th>track</th><th>review</th></tr></thead><tbody>{events.map(e => <tr key={e.id}><td>{e.timestamp}</td><td>{e.type}</td><td>{e.confidence}</td><td>{e.track_id}</td><td><button onClick={()=>review(e.id,'confirm')}>Confirm</button><button onClick={()=>review(e.id,'reject')}>Reject</button></td></tr>)}</tbody></table>
  </main>;
}
