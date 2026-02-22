function getApiBase() {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000/api`;
  }
  return "http://localhost:8000/api";
}

const API = getApiBase();

async function parseJsonSafe(response: Response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiFetch(path: string, init?: RequestInit) {
  try {
    return await fetch(`${API}${path}`, init);
  } catch {
    throw new Error(`Cannot reach backend at ${API}. Start services with: make do-it-all`);
  }
}

export async function login() {
  const r = await apiFetch("/auth/login", {
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

export { API, parseJsonSafe };
