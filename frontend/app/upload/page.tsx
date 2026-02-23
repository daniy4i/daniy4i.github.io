"use client";
import { useState } from "react";
import { apiFetch, login, parseJsonSafe } from "../../lib/api";

export default function UploadPage() {
  const [msg, setMsg] = useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMsg("Uploading...");
    try {
      const form = new FormData(e.currentTarget);
      const token = await login();
      const r = await apiFetch("/videos/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await parseJsonSafe(r);
      if (!r.ok) throw new Error(data?.detail || `Upload failed (${r.status})`);
      setMsg(`Uploaded job #${data.id}. Open Jobs to run/review analytics.`);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Upload failed");
    }
  }

  return (
    <main className="stack">
      <section className="card">
        <h2>Upload Dashcam Video</h2>
        <p className="muted">Formats: MP4 / MOV / MKV or ZIP of clips. Upload starts secure processing for tracked traffic analytics.</p>
        <form onSubmit={onSubmit} className="stack" style={{ maxWidth: 640 }}>
          <input type="file" name="file" accept="video/mp4,video/quicktime,video/x-matroska,.zip,application/zip" required />
          <button type="submit" className="btn btn-primary">Upload & Create Job</button>
        </form>
        {msg && <p className={msg.toLowerCase().includes("uploaded") ? "success" : "error"}>{msg}</p>}
      </section>
    </main>
  );
}
