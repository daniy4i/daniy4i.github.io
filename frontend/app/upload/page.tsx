"use client";
import { useState } from "react";
import { API, login } from "../../lib/api";

export default function UploadPage() {
  const [msg, setMsg] = useState("");
  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const token = await login();
    const r = await fetch(`${API}/videos/upload`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
    const data = await r.json();
    setMsg(`Uploaded job #${data.id}`);
  }
  return <main style={{ padding: 24 }}><h2>Upload Video</h2><form onSubmit={onSubmit}><input type="file" name="file" accept="video/mp4,video/quicktime,video/x-matroska" required /><button type="submit">Upload</button></form><p>{msg}</p></main>;
}
