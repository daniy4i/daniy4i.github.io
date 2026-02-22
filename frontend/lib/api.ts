const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function parseJsonSafe(response: Response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function login() {
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "admin", password: "admin" })
  });
  const data = await parseJsonSafe(r);
  if (!r.ok || !data?.access_token) {
    const detail = data?.detail || `Login failed (${r.status})`;
    throw new Error(detail);
  }
  return data.access_token as string;
}

export { API };
