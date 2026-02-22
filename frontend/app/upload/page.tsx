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
        body: form
      });
      const data = await parseJsonSafe(r);
      if (!r.ok) throw new Error(data?.detail || `Upload failed (${r.status})`);
      setMsg(`Uploaded job #${data.id}. Go to Jobs page to run/review.`);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Upload failed");
    }
  }

  return (
    <main className="stack">
      <section className="card">
        <h2>Upload dashcam video</h2>
        <p className="muted">Supported: MP4, MOV, MKV. Max upload size is configured on backend.</p>
        <form onSubmit={onSubmit} className="stack" style={{ maxWidth: 560 }}>
          <input type="file" name="file" accept="video/mp4,video/quicktime,video/x-matroska" required />
          <button type="submit">Upload</button>
        </form>
        {msg && <p className={msg.toLowerCase().includes("uploaded") ? "success" : "error"}>{msg}</p>}
      </section>
    </main>
  );
}
