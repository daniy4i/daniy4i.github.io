"use client";
import { useState } from "react";
import { API, login } from "../../lib/api";

export default function UploadPage() {
  const [msg, setMsg] = useState("");
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMsg("Uploading...");
    try {
      const form = new FormData(e.currentTarget);
      const token = await login();
      const r = await fetch(`${API}/videos/upload`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data?.detail || `Upload failed (${r.status})`);
      }
      setMsg(`Uploaded job #${data.id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed";
      setMsg(message);
    }
  }
  return <main style={{ padding: 24 }}><h2>Upload Video</h2><form onSubmit={onSubmit}><input type="file" name="file" accept="video/mp4,video/quicktime,video/x-matroska" required /><button type="submit">Upload</button></form><p>{msg}</p></main>;
}
