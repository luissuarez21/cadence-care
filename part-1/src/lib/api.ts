/**
 * Patient API client — thin wrapper over fetch.
 *
 * All calls go to VITE_API_URL (defaults to http://localhost:8000).
 * patient_id is passed as a query param; backend auth.py accepts it in
 * demo mode (no session cookie required until the JWT story lands).
 *
 * Usage:
 *   import { api, PATIENT_ID } from "@/lib/api";
 *   const data = await api.get<WatchForResponse>("/patient/watchfor");
 */

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export const PATIENT_ID = "maria-chen";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(`/api${path}`, BASE);
  url.searchParams.set("patient_id", PATIENT_ID);

  const res = await fetch(url.toString(), {
    credentials: "include",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${path}: ${text}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
};
