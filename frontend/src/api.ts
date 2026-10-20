const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export type UserStat = { user_id: string; found: boolean; followers: number; followees: number };
export type Summary = {
  run_id: string;
  raw_lines?: number;
  malformed_lines?: number;
  self_loop_lines?: number;
  duplicate_lines_removed?: number;
  unique_edges?: number;
  users?: number;
};
export type Health = { status: string; results_run_id: string | null; users_loaded: number };
export type Job = {
  job_run_id: string;
  run_id?: string | null;
  name?: string;
  state: string;
  state_details?: string;
  created_at?: string;
  updated_at?: string;
  results_run_id?: string | null;
};
export type TopRow = { user_id: string; followers: number; followees: number };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  users: (ids: string[]) =>
    request<{ run_id: string; users: UserStat[] }>(`/api/users?ids=${encodeURIComponent(ids.join(","))}`),
  summary: () => request<Summary>("/api/summary"),
  top: (by: "followers" | "followees", limit = 10) =>
    request<{ by: string; users: TopRow[] }>(`/api/top?by=${by}&limit=${limit}`),
  startJob: () => request<Job>("/api/jobs", { method: "POST" }),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  jobs: () => request<{ jobs: Job[] }>("/api/jobs?limit=5"),
};
