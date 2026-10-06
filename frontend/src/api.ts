// Base URL for the backend API. In dev, Vite proxies nothing by default, so
// point directly at the backend dev server; override via VITE_API_BASE_URL
// (e.g. when both services run behind a reverse proxy in Docker).
export const API_BASE_URL: string =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
  "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`${response.status}: ${detail}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export interface UserOut {
  id: string;
  username: string;
  display_name: string;
}

export interface UserReportSummary {
  user_id: string;
  display_name: string;
  latest_weight_kg: number | null;
  latest_weight_at: string | null;
  fluids_ml_total: number;
  coffee_cups_total: number;
  health_observation_count: number;
  sleep_minutes_avg: number | null;
  steps_avg: number | null;
}

export interface DashboardReport {
  period_days: number;
  generated_at: string;
  users: UserReportSummary[];
}

export const api = {
  login: (username: string, password: string) =>
    request<UserOut>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<UserOut>("/auth/me"),
  dashboard: (days = 7) => request<DashboardReport>(`/reports/dashboard?days=${days}`),
  logWeight: (weightKg: number, note?: string) =>
    request("/weight", {
      method: "POST",
      body: JSON.stringify({ weight_kg: weightKg, note: note || null }),
    }),
  logFluid: (amountMl: number, fluidType: "water" | "other" = "water") =>
    request("/fluids", {
      method: "POST",
      body: JSON.stringify({ amount_ml: amountMl, fluid_type: fluidType }),
    }),
  logCoffee: (cups: number) =>
    request("/coffee", {
      method: "POST",
      body: JSON.stringify({ cups }),
    }),
};
