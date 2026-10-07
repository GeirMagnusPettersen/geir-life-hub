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

export interface WeeklyTrendPoint {
  week_start: string;
  week_end: string;
  avg_weight_kg: number | null;
  fluids_ml_per_day: number | null;
  coffee_cups_per_day: number | null;
  symptom_count: number;
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
  weekly_trend: WeeklyTrendPoint[];
}

export interface DashboardReport {
  period_days: number;
  trend_weeks: number;
  generated_at: string;
  users: UserReportSummary[];
}

export interface SleepActivityOut {
  id: string;
  user_id: string;
  summary_date: string;
  sleep_minutes: number | null;
  steps: number | null;
  source: string;
}

export interface HealthObservationOut {
  id: string;
  user_id: string;
  category: string;
  description: string;
  severity: number | null;
  recorded_at: string;
}

export interface KitchenOwlStatus {
  configured: boolean;
}

export interface KitchenOwlShoppingListItem {
  id: number;
  name: string;
  checked?: boolean;
  [key: string]: unknown;
}

export interface AssistantStatus {
  configured: boolean;
}

export interface AssistantChatMessage {
  role: "user" | "assistant";
  content: string;
  image?: string;
}

export interface AssistantAddedItem {
  name: string;
  ok: boolean;
  detail?: string | null;
}

export interface AssistantChatReply {
  reply: string;
  added_items: AssistantAddedItem[];
  cleared_list: boolean;
}

export const api = {
  login: (username: string, password: string) =>
    request<UserOut>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<UserOut>("/auth/me"),
  dashboard: (days = 7, weeks = 4) =>
    request<DashboardReport>(`/reports/dashboard?days=${days}&weeks=${weeks}`),
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
  logHealthObservation: (category: string, description: string, severity?: number | null) =>
    request<HealthObservationOut>("/health-observations", {
      method: "POST",
      body: JSON.stringify({ category, description, severity: severity ?? null }),
    }),
  logSleepActivity: (summaryDate: string, sleepMinutes?: number | null, steps?: number | null) =>
    request("/sleep-activity", {
      method: "POST",
      body: JSON.stringify({
        summary_date: summaryDate,
        sleep_minutes: sleepMinutes ?? null,
        steps: steps ?? null,
        source: "manual",
      }),
    }),
  listSleepActivity: (limit = 14) =>
    request<SleepActivityOut[]>(`/sleep-activity?limit=${limit}`),
  kitchenowlStatus: () => request<KitchenOwlStatus>("/integrations/kitchenowl/status"),
  kitchenowlShoppingList: () =>
    request<KitchenOwlShoppingListItem[]>("/integrations/kitchenowl/shopping-list"),
  kitchenowlAddShoppingListItem: (name: string, description?: string) =>
    request<KitchenOwlShoppingListItem>("/integrations/kitchenowl/shopping-list", {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    }),
  kitchenowlSetItemChecked: (itemId: number, checked: boolean) =>
    request<KitchenOwlShoppingListItem>(`/integrations/kitchenowl/shopping-list/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ checked }),
    }),
  kitchenowlClearShoppingList: () =>
    request<{ removed: number }>("/integrations/kitchenowl/shopping-list", {
      method: "DELETE",
    }),
  assistantStatus: () => request<AssistantStatus>("/assistant/status"),
  assistantChat: (messages: AssistantChatMessage[]) =>
    request<AssistantChatReply>("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ messages }),
    }),
};
