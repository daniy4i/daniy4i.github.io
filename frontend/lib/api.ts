const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function login() {
  const r = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "admin", password: "admin" }) });
  const data = await r.json();
  return data.access_token as string;
}

export { API };
