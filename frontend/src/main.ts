import {
  api,
  type AssistantChatMessage,
  type DashboardReport,
  type KitchenOwlShoppingListItem,
  type SleepActivityOut,
  type SleepTrendPoint,
  type UserReportSummary,
} from "./api";

const app = document.getElementById("app");

if (!app) {
  throw new Error("Missing #app root element");
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

// Maps user_id -> display_name, kept up to date whenever the dashboard
// report is (re)loaded, so the sleep history list can attribute entries to
// a person even though the API itself only returns the raw user_id.
let usersById: Record<string, string> = {};

function formatSleepDuration(minutes: number | null): string {
  if (minutes === null || minutes === undefined) return "–";
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins ? `${hours}t ${mins}min` : `${hours}t`;
}

function formatSummaryDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  return new Intl.DateTimeFormat("nb-NO", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(date);
}

function renderLogin(): void {
  app!.innerHTML = `
    <main class="login">
      <h1>Geir Life Hub</h1>
      <form id="login-form">
        <label>
          Brukernavn
          <input name="username" autocomplete="username" required />
        </label>
        <label>
          Passord
          <input name="password" type="password" autocomplete="current-password" required />
        </label>
        <button type="submit">Logg inn</button>
        <p id="login-error" role="alert"></p>
      </form>
    </main>
  `;

  const form = document.getElementById("login-form") as HTMLFormElement;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const username = String(data.get("username") ?? "");
    const password = String(data.get("password") ?? "");
    const errorEl = document.getElementById("login-error")!;
    errorEl.textContent = "";

    try {
      await api.login(username, password);
      await renderDashboard();
    } catch (err) {
      errorEl.textContent = "Feil brukernavn eller passord.";
      console.error(err);
    }
  });
}

function renderSummaryCard(user: UserReportSummary): string {
  const trendRows = user.weekly_trend
    .map(
      (point) => `
        <tr>
          <td>${point.week_start} – ${point.week_end}</td>
          <td>${point.avg_weight_kg !== null ? point.avg_weight_kg.toFixed(1) + " kg" : "–"}</td>
          <td>${point.fluids_ml_per_day !== null ? Math.round(point.fluids_ml_per_day) + " ml/d" : "–"}</td>
          <td>${point.coffee_cups_per_day !== null ? point.coffee_cups_per_day.toFixed(1) + "/d" : "–"}</td>
          <td>${point.symptom_count}</td>
          <td>${point.avg_sleep_minutes !== null ? formatSleepDuration(Math.round(point.avg_sleep_minutes)) : "–"}</td>
          <td>${point.avg_resting_heart_rate !== null ? Math.round(point.avg_resting_heart_rate) + " bpm" : "–"}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <article class="user-summary">
      <h2>${user.display_name}</h2>
      <ul>
        <li>Vekt: ${user.latest_weight_kg ?? "–"} kg</li>
        <li>Væske (periode): ${user.fluids_ml_total} ml</li>
        <li>Kaffe (periode): ${user.coffee_cups_total} kopper</li>
        <li>Helseobservasjoner: ${user.health_observation_count}</li>
        <li>Snitt søvn: ${user.sleep_minutes_avg ? Math.round(user.sleep_minutes_avg) + " min" : "–"}</li>
        <li>Snitt skritt: ${user.steps_avg ? Math.round(user.steps_avg) : "–"}</li>
      </ul>
      ${
        user.weekly_trend.length
          ? `
            <details>
              <summary>Ukentlig trend</summary>
              <table class="trend-table">
                <thead>
                  <tr>
                    <th>Uke</th>
                    <th>Snitt vekt</th>
                    <th>Væske</th>
                    <th>Kaffe</th>
                    <th>Symptomer</th>
                    <th>Snitt søvn</th>
                    <th>Hvilepuls</th>
                  </tr>
                </thead>
                <tbody>${trendRows}</tbody>
              </table>
            </details>
          `
          : ""
      }
    </article>
  `;
}

function renderLogForms(): string {
  return `
    <section class="log-forms">
      <h2>Registrer</h2>
      <div class="log-forms-grid">
        <form id="weight-form" class="log-form">
          <h3>Vekt</h3>
          <label>
            Kg
            <input name="weight_kg" type="number" step="0.1" min="0.1" max="499" required />
          </label>
          <label>
            Notat
            <input name="note" type="text" maxlength="200" />
          </label>
          <button type="submit">Lagre vekt</button>
        </form>

        <form id="weight-import-form" class="log-form">
          <h3>Importer vekt fra Vektklubb (CSV)</h3>
          <p class="log-form-hint">
            Last opp en CSV-eksport fra Vektklubb (eller tilsvarende) for å legge inn
            historiske vektmålinger manuelt. Kolonner for dato og vekt gjenkjennes
            automatisk (norsk eller engelsk).
          </p>
          <label>
            CSV-fil
            <input name="file" type="file" accept=".csv,text/csv" required />
          </label>
          <button type="submit">Importer</button>
        </form>

        <form id="fluid-form" class="log-form">
          <h3>Væske</h3>
          <label>
            Mengde (ml)
            <input name="amount_ml" type="number" step="10" min="1" max="5000" required />
          </label>
          <label>
            Type
            <select name="fluid_type">
              <option value="water">Vann</option>
              <option value="other">Annet</option>
            </select>
          </label>
          <button type="submit">Lagre væske</button>
        </form>

        <form id="coffee-form" class="log-form">
          <h3>Kaffe</h3>
          <label>
            Kopper
            <input name="cups" type="number" step="0.5" min="0.5" max="20" required />
          </label>
          <button type="submit">Lagre kaffe</button>
        </form>

        <form id="health-form" class="log-form">
          <h3>Helseobservasjon</h3>
          <label>
            Kategori
            <input name="category" type="text" maxlength="64" required placeholder="f.eks. hodepine" />
          </label>
          <label>
            Beskrivelse
            <input name="description" type="text" required />
          </label>
          <label>
            Alvorlighet (1–5)
            <input name="severity" type="number" min="1" max="5" />
          </label>
          <button type="submit">Lagre observasjon</button>
        </form>

        <form id="sleep-form" class="log-form">
          <h3>Søvn/aktivitet (manuell)</h3>
          <label>
            Dato
            <input name="summary_date" type="date" value="${todayIsoDate()}" required />
          </label>
          <label>
            Søvn (minutter)
            <input name="sleep_minutes" type="number" min="0" max="1440" />
          </label>
          <label>
            Skritt
            <input name="steps" type="number" min="0" />
          </label>
          <button type="submit">Lagre søvn/aktivitet</button>
        </form>
      </div>
      <p id="log-feedback" role="status"></p>
      <section class="sleep-history-section">
        <h3>Siste søvn/aktivitet</h3>
        <div id="sleep-history">Laster...</div>
      </section>
    </section>
  `;
}

const SLEEP_BAR_MAX_MINUTES = 600; // 10h, used only to scale the visual bar

function renderSleepHistory(entries: SleepActivityOut[]): string {
  if (!entries.length) {
    return "<p>Ingen søvndata registrert ennå.</p>";
  }
  return `
    <ul class="sleep-history-list">
      ${entries
        .map((entry) => {
          const barPct = entry.sleep_minutes
            ? Math.min(100, Math.round((entry.sleep_minutes / SLEEP_BAR_MAX_MINUTES) * 100))
            : 0;
          const who = escapeHtml(usersById[entry.user_id] ?? "Ukjent");
          return `
            <li class="sleep-history-row">
              <div class="sleep-history-meta">
                <span class="sleep-history-date">${formatSummaryDate(entry.summary_date)}</span>
                <span class="sleep-history-who">${who}</span>
              </div>
              <div class="sleep-history-bar-track" title="${formatSleepDuration(entry.sleep_minutes)}">
                <div class="sleep-history-bar" style="width: ${barPct}%"></div>
              </div>
              <div class="sleep-history-values">
                <span class="sleep-history-duration">${formatSleepDuration(entry.sleep_minutes)}</span>
                <span class="sleep-history-steps">${
                  entry.steps !== null ? `${entry.steps.toLocaleString("nb-NO")} skritt` : "–"
                }</span>
                <span class="sleep-history-hr">${
                  entry.resting_heart_rate !== null ? `${Math.round(entry.resting_heart_rate)} bpm (hvile)` : "–"
                }</span>
              </div>
            </li>
          `;
        })
        .join("")}
    </ul>
  `;
}

async function loadSleepHistory(): Promise<void> {
  const container = document.getElementById("sleep-history");
  if (!container) return;
  try {
    const entries = await api.listSleepActivity(14);
    container.innerHTML = renderSleepHistory(entries);
  } catch (err) {
    container.innerHTML = "<p>Kunne ikke laste søvnhistorikk.</p>";
    console.error(err);
  }
}

// ---- Sleep & heart rate trend chart (shared view, both users) ----

interface ChartPoint {
  date: string;
  value: number | null;
}

interface ChartSeries {
  label: string;
  color: string;
  dashed?: boolean;
  points: ChartPoint[];
}

// Stable two-color palette reused for both users across both charts, so the
// same person is always the same color in the duration and heart-rate charts.
const USER_CHART_COLORS = ["#1f6f54", "#b5541f"];

const CHART_WIDTH = 600;
const CHART_HEIGHT = 180;
const CHART_PADDING = { top: 12, right: 12, bottom: 24, left: 34 };

// Hand-rolled SVG line chart (no charting library in this project). Renders
// one or more series sharing a common date axis, with a simple min/max
// y-scale and first/middle/last date labels.
function buildLineChartSvg(series: ChartSeries[], unit: string): string {
  const allDates = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.date)))).sort();
  const allValues = series.flatMap((s) => s.points.map((p) => p.value)).filter((v): v is number => v !== null);

  if (!allDates.length || !allValues.length) {
    return "<p>Ingen data for valgt periode.</p>";
  }

  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(...allValues);
  const valueRange = maxValue - minValue || 1;

  const innerWidth = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right;
  const innerHeight = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom;
  const dateIndex = new Map(allDates.map((d, i) => [d, i]));

  const xForIndex = (i: number): number =>
    CHART_PADDING.left + (allDates.length > 1 ? (i / (allDates.length - 1)) * innerWidth : innerWidth / 2);
  const yForValue = (v: number): number =>
    CHART_PADDING.top + innerHeight - ((v - minValue) / valueRange) * innerHeight;

  const seriesSvg = series
    .map((s) => {
      const pts = s.points.filter((p): p is { date: string; value: number } => p.value !== null);
      if (!pts.length) return "";
      const path = pts
        .map((p, idx) => {
          const x = xForIndex(dateIndex.get(p.date)!).toFixed(1);
          const y = yForValue(p.value).toFixed(1);
          return `${idx === 0 ? "M" : "L"}${x},${y}`;
        })
        .join(" ");
      const dashArray = s.dashed ? ' stroke-dasharray="4 3"' : "";
      const dots = pts
        .map((p) => {
          const x = xForIndex(dateIndex.get(p.date)!).toFixed(1);
          const y = yForValue(p.value).toFixed(1);
          return `<circle cx="${x}" cy="${y}" r="2.5" fill="${s.color}"><title>${escapeHtml(
            s.label,
          )} – ${formatSummaryDate(p.date)}: ${p.value}${unit}</title></circle>`;
        })
        .join("");
      return `<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2"${dashArray} /> ${dots}`;
    })
    .join("");

  const labelIndices = Array.from(
    new Set(allDates.length > 1 ? [0, Math.floor((allDates.length - 1) / 2), allDates.length - 1] : [0]),
  );
  const xLabels = labelIndices
    .map(
      (i) =>
        `<text x="${xForIndex(i).toFixed(1)}" y="${CHART_HEIGHT - 6}" class="chart-axis-label" text-anchor="middle">${formatSummaryDate(
          allDates[i],
        )}</text>`,
    )
    .join("");

  const yLabels = `
    <text x="2" y="${(CHART_PADDING.top + 4).toFixed(1)}" class="chart-axis-label">${Math.round(maxValue)}</text>
    <text x="2" y="${(CHART_HEIGHT - CHART_PADDING.bottom).toFixed(1)}" class="chart-axis-label">${Math.round(minValue)}</text>
  `;

  return `
    <svg viewBox="0 0 ${CHART_WIDTH} ${CHART_HEIGHT}" class="trend-chart" role="img" aria-label="Linjediagram over tid">
      <line x1="${CHART_PADDING.left}" y1="${CHART_PADDING.top}" x2="${CHART_PADDING.left}" y2="${CHART_HEIGHT - CHART_PADDING.bottom}" class="chart-axis-line" />
      <line x1="${CHART_PADDING.left}" y1="${CHART_HEIGHT - CHART_PADDING.bottom}" x2="${CHART_WIDTH - CHART_PADDING.right}" y2="${CHART_HEIGHT - CHART_PADDING.bottom}" class="chart-axis-line" />
      ${yLabels}
      ${xLabels}
      ${seriesSvg}
    </svg>
    <div class="chart-legend">
      ${series
        .map(
          (s) =>
            `<span class="chart-legend-item"><span class="chart-legend-swatch${
              s.dashed ? " chart-legend-swatch-dashed" : ""
            }" style="background:${s.dashed ? "transparent" : s.color}; border-color:${s.color}"></span>${escapeHtml(
              s.label,
            )}</span>`,
        )
        .join("")}
    </div>
  `;
}

const SLEEP_TREND_PERIODS = [7, 30, 90] as const;
let sleepTrendDays: number = 30;

function renderSleepTrendSection(): string {
  return `
    <section class="sleep-trend-section">
      <h2>Søvn og puls over tid</h2>
      <p class="sleep-trend-intro">
        Delt oversikt for hele husstanden, basert på søvndata synkronisert fra Health Connect.
      </p>
      <div class="period-selector" role="group" aria-label="Velg periode">
        ${SLEEP_TREND_PERIODS.map(
          (d) =>
            `<button type="button" data-days="${d}" class="period-btn${
              d === sleepTrendDays ? " active" : ""
            }">${d} dager</button>`,
        ).join("")}
      </div>
      <div class="chart-container">
        <h3>Søvnvarighet</h3>
        <div id="sleep-duration-chart">Laster...</div>
      </div>
      <div class="chart-container">
        <h3>Puls (hvile – heltrukket, snitt – stiplet)</h3>
        <div id="heart-rate-chart">Laster...</div>
      </div>
    </section>
  `;
}

function groupSleepTrendByUser(points: SleepTrendPoint[]): Map<string, SleepTrendPoint[]> {
  const byUser = new Map<string, SleepTrendPoint[]>();
  for (const point of points) {
    if (!byUser.has(point.user_id)) byUser.set(point.user_id, []);
    byUser.get(point.user_id)!.push(point);
  }
  return byUser;
}

async function loadSleepTrendSection(days: number): Promise<void> {
  sleepTrendDays = days;
  const durationEl = document.getElementById("sleep-duration-chart");
  const hrEl = document.getElementById("heart-rate-chart");
  if (!durationEl || !hrEl) return;
  durationEl.innerHTML = "Laster...";
  hrEl.innerHTML = "Laster...";

  try {
    const trend = await api.sleepTrend(days);
    const byUser = groupSleepTrendByUser(trend.points);
    const userIds = Array.from(byUser.keys()).sort((a, b) =>
      (usersById[a] ?? "").localeCompare(usersById[b] ?? "", "nb-NO"),
    );
    const colorFor = (userId: string): string =>
      USER_CHART_COLORS[userIds.indexOf(userId) % USER_CHART_COLORS.length];

    const durationSeries: ChartSeries[] = userIds.map((userId) => ({
      label: usersById[userId] ?? "Ukjent",
      color: colorFor(userId),
      points: (byUser.get(userId) ?? []).map((p) => ({ date: p.summary_date, value: p.sleep_minutes })),
    }));
    durationEl.innerHTML = buildLineChartSvg(durationSeries, " min");

    const hrSeries: ChartSeries[] = userIds.flatMap((userId) => {
      const color = colorFor(userId);
      const name = usersById[userId] ?? "Ukjent";
      const pts = byUser.get(userId) ?? [];
      return [
        {
          label: `${name} – hvilepuls`,
          color,
          points: pts.map((p) => ({ date: p.summary_date, value: p.resting_heart_rate })),
        },
        {
          label: `${name} – snittpuls`,
          color,
          dashed: true,
          points: pts.map((p) => ({ date: p.summary_date, value: p.avg_heart_rate })),
        },
      ];
    });
    hrEl.innerHTML = buildLineChartSvg(hrSeries, " bpm");
  } catch (err) {
    durationEl.innerHTML = "<p>Kunne ikke laste søvntrend.</p>";
    hrEl.innerHTML = "";
    console.error(err);
  }
}

function wireSleepTrendPeriodButtons(): void {
  document.querySelectorAll<HTMLButtonElement>(".period-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const days = Number(btn.dataset.days);
      document
        .querySelectorAll<HTMLButtonElement>(".period-btn")
        .forEach((b) => b.classList.toggle("active", b === btn));
      void loadSleepTrendSection(days);
    });
  });
}

function renderKitchenOwlSection(): string {
  return `
    <section class="kitchenowl">
      <h2>Handleliste (KitchenOwl)</h2>
      <div id="kitchenowl-content">Laster status...</div>
    </section>
  `;
}

function renderAssistantSection(): string {
  return `
    <section class="assistant">
      <h2>Middagsassistent</h2>
      <div id="assistant-content">Laster status...</div>
    </section>
  `;
}

const assistantHistory: AssistantChatMessage[] = [];

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderAssistantHistory(): string {
  if (!assistantHistory.length) {
    return `
      <p class="assistant-empty">
        Diskuter en middag, og be assistenten legge ingrediensene til handlelisten når du har bestemt deg.
        Du kan også laste opp et bilde av en rett.
      </p>
    `;
  }
  return assistantHistory
    .map((msg) => {
      const isUser = msg.role === "user";
      const image = msg.image
        ? `<img class="chat-image" src="${msg.image}" alt="Opplastet bilde" />`
        : "";
      return `
        <div class="chat-row chat-row-${isUser ? "user" : "assistant"}">
          <div class="chat-bubble chat-bubble-${isUser ? "user" : "assistant"}">
            <span class="chat-sender">${isUser ? "Du" : "Assistent"}</span>
            ${image}
            <span class="chat-text">${escapeHtml(msg.content)}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function scrollAssistantHistoryToBottom(): void {
  const historyEl = document.getElementById("assistant-history");
  if (!historyEl) return;
  // Defer until after the browser has laid out the new content, otherwise
  // scrollHeight can still reflect the previous (shorter) message list.
  requestAnimationFrame(() => {
    historyEl.scrollTop = historyEl.scrollHeight;
  });
}

// Holds a base64 data URL for a photo the user picked but hasn't sent yet,
// so it can be attached to the next submitted chat message.
let pendingAssistantImage: string | null = null;

const ASSISTANT_IMAGE_MAX_DIMENSION = 1024;
const ASSISTANT_IMAGE_JPEG_QUALITY = 0.8;

// Resizes/compresses a picked photo client-side (via an offscreen canvas)
// before it is base64-encoded and sent to the backend, so phone-camera
// photos don't blow past request-size/LLM token limits.
async function resizeImageToDataUrl(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(
    1,
    ASSISTANT_IMAGE_MAX_DIMENSION / Math.max(bitmap.width, bitmap.height)
  );
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Kunne ikke behandle bildet.");
  ctx.drawImage(bitmap, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", ASSISTANT_IMAGE_JPEG_QUALITY);
}

function renderAssistantImagePreview(): string {
  if (!pendingAssistantImage) return "";
  return `
    <div class="assistant-image-preview">
      <img src="${pendingAssistantImage}" alt="Valgt bilde" />
      <button type="button" id="assistant-image-remove" aria-label="Fjern bilde">✕</button>
    </div>
  `;
}

function renderAssistantChatUI(): string {
  return `
    <div id="assistant-history" class="assistant-history">${renderAssistantHistory()}</div>
    <div id="assistant-image-preview-slot">${renderAssistantImagePreview()}</div>
    <form id="assistant-form" class="log-form assistant-input-row">
      <label class="assistant-input-label">
        Melding
        <input name="message" type="text" maxlength="4000" required placeholder="f.eks. jeg tenkte på taco i kveld" autocomplete="off" />
      </label>
      <label class="assistant-image-label" title="Last opp bilde av en rett">
        📷
        <input id="assistant-image-input" name="image" type="file" accept="image/*" capture="environment" hidden />
      </label>
      <button type="submit">Send</button>
    </form>
    <p id="assistant-feedback" role="status"></p>
  `;
}

async function handleAssistantImageChange(event: Event): Promise<void> {
  const input = event.currentTarget as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const feedbackEl = document.getElementById("assistant-feedback");
  try {
    pendingAssistantImage = await resizeImageToDataUrl(file);
    const slot = document.getElementById("assistant-image-preview-slot");
    if (slot) slot.innerHTML = renderAssistantImagePreview();
    document
      .getElementById("assistant-image-remove")
      ?.addEventListener("click", () => {
        pendingAssistantImage = null;
        input.value = "";
        if (slot) slot.innerHTML = renderAssistantImagePreview();
      });
  } catch (err) {
    console.error(err);
    if (feedbackEl) {
      feedbackEl.textContent = "Kunne ikke laste bildet.";
      feedbackEl.classList.add("error");
    }
  } finally {
    input.value = "";
  }
}

async function handleAssistantSubmit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const data = new FormData(form);
  const text = String(data.get("message") ?? "").trim();
  const image = pendingAssistantImage ?? undefined;
  if (!text && !image) return;

  assistantHistory.push({ role: "user", content: text || "(bilde)", image });
  pendingAssistantImage = null;
  const historyEl = document.getElementById("assistant-history");
  const previewSlot = document.getElementById("assistant-image-preview-slot");
  const feedbackEl = document.getElementById("assistant-feedback");
  if (historyEl) historyEl.innerHTML = renderAssistantHistory();
  if (previewSlot) previewSlot.innerHTML = renderAssistantImagePreview();
  scrollAssistantHistoryToBottom();
  form.reset();

  try {
    const reply = await api.assistantChat(assistantHistory);
    assistantHistory.push({ role: "assistant", content: reply.reply });
    if (historyEl) historyEl.innerHTML = renderAssistantHistory();
    scrollAssistantHistoryToBottom();
    if (feedbackEl) {
      if (reply.cleared_list) {
        feedbackEl.textContent = "Handlelisten ble tømt.";
      } else if (reply.added_items.length) {
        feedbackEl.textContent = `Lagt til handlelisten: ${reply.added_items
          .filter((i) => i.ok)
          .map((i) => i.name)
          .join(", ")}`;
      } else {
        feedbackEl.textContent = "";
      }
      feedbackEl.classList.remove("error");
    }
    // Refresh the shopping list widget so confirmed items/clears show up
    // immediately, without requiring a manual page reload.
    if (reply.cleared_list || reply.added_items.some((i) => i.ok)) {
      await loadKitchenOwlSection();
    }
  } catch (err) {
    console.error(err);
    if (feedbackEl) {
      feedbackEl.textContent = describeAssistantError(err);
      feedbackEl.classList.add("error");
    }
  }
}

// `request()` in api.ts throws `Error("<status>: <json-or-text-body>")`. Pull
// out FastAPI's `detail` field (set by our 502/503 handlers in
// routers/assistant.py) so provider/config problems show up as a specific,
// actionable message instead of a generic "couldn't reach the assistant".
function describeAssistantError(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err);
  const separatorIndex = message.indexOf(": ");
  const status = separatorIndex >= 0 ? message.slice(0, separatorIndex) : "";
  const rawBody = separatorIndex >= 0 ? message.slice(separatorIndex + 2) : message;

  let detail = rawBody;
  try {
    const parsed = JSON.parse(rawBody) as { detail?: string };
    if (parsed.detail) detail = parsed.detail;
  } catch {
    // rawBody wasn't JSON; fall back to using it as-is.
  }

  if (status === "503") {
    return "Assistenten er ikke konfigurert ennå.";
  }
  if (status === "502") {
    return `Assistenten fikk et feilsvar fra AI-tjenesten: ${detail}`;
  }
  return "Kunne ikke nå assistenten.";
}

async function loadAssistantSection(): Promise<void> {
  const container = document.getElementById("assistant-content");
  if (!container) return;

  try {
    const status = await api.assistantStatus();
    if (!status.configured) {
      container.innerHTML = `
        <p>
          Middagsassistenten er ikke konfigurert ennå. Sett
          <code>ASSISTANT_API_KEY</code> (og ev. <code>ASSISTANT_BASE_URL</code>/
          <code>ASSISTANT_MODEL</code>) i backend-miljøet for å aktivere den.
        </p>
      `;
      return;
    }

    container.innerHTML = renderAssistantChatUI();
    scrollAssistantHistoryToBottom();
    const form = document.getElementById("assistant-form") as HTMLFormElement | null;
    form?.addEventListener("submit", handleAssistantSubmit);
    const imageInput = document.getElementById(
      "assistant-image-input"
    ) as HTMLInputElement | null;
    imageInput?.addEventListener("change", handleAssistantImageChange);
  } catch (err) {
    container.innerHTML = "<p>Kunne ikke laste assistentstatus.</p>";
    console.error(err);
  }
}

function setLogFeedback(message: string, isError = false): void {
  const el = document.getElementById("log-feedback");
  if (!el) return;
  el.textContent = message;
  el.classList.toggle("error", isError);
}

function wireLogForms(onLogged: () => void): void {
  const weightForm = document.getElementById("weight-form") as HTMLFormElement;
  weightForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(weightForm);
    try {
      await api.logWeight(Number(data.get("weight_kg")), String(data.get("note") ?? ""));
      setLogFeedback("Vekt lagret.");
      weightForm.reset();
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke lagre vekt.", true);
      console.error(err);
    }
  });

  const weightImportForm = document.getElementById("weight-import-form") as HTMLFormElement;
  weightImportForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = weightImportForm.querySelector<HTMLInputElement>('input[name="file"]');
    const file = fileInput?.files?.[0];
    if (!file) {
      setLogFeedback("Velg en CSV-fil først.", true);
      return;
    }
    try {
      const result = await api.importWeightCsv(file);
      if (result.errors.length > 0) {
        setLogFeedback(
          `Importerte ${result.imported} rad(er), hoppet over ${result.skipped}. Se konsoll for detaljer.`,
          result.imported === 0,
        );
        console.warn("Weight import errors:", result.errors);
      } else {
        setLogFeedback(`Importerte ${result.imported} rad(er) fra Vektklubb.`);
      }
      weightImportForm.reset();
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke importere CSV-fil.", true);
      console.error(err);
    }
  });

  const fluidForm = document.getElementById("fluid-form") as HTMLFormElement;
  fluidForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(fluidForm);
    try {
      await api.logFluid(
        Number(data.get("amount_ml")),
        String(data.get("fluid_type") ?? "water") as "water" | "other",
      );
      setLogFeedback("Væske lagret.");
      fluidForm.reset();
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke lagre væske.", true);
      console.error(err);
    }
  });

  const coffeeForm = document.getElementById("coffee-form") as HTMLFormElement;
  coffeeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(coffeeForm);
    try {
      await api.logCoffee(Number(data.get("cups")));
      setLogFeedback("Kaffe lagret.");
      coffeeForm.reset();
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke lagre kaffe.", true);
      console.error(err);
    }
  });

  const healthForm = document.getElementById("health-form") as HTMLFormElement;
  healthForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(healthForm);
    const severityRaw = data.get("severity");
    try {
      await api.logHealthObservation(
        String(data.get("category") ?? ""),
        String(data.get("description") ?? ""),
        severityRaw ? Number(severityRaw) : null,
      );
      setLogFeedback("Helseobservasjon lagret.");
      healthForm.reset();
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke lagre helseobservasjon.", true);
      console.error(err);
    }
  });

  const sleepForm = document.getElementById("sleep-form") as HTMLFormElement;
  sleepForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(sleepForm);
    const sleepMinutesRaw = data.get("sleep_minutes");
    const stepsRaw = data.get("steps");
    try {
      await api.logSleepActivity(
        String(data.get("summary_date") ?? todayIsoDate()),
        sleepMinutesRaw ? Number(sleepMinutesRaw) : null,
        stepsRaw ? Number(stepsRaw) : null,
      );
      setLogFeedback("Søvn/aktivitet lagret.");
      onLogged();
    } catch (err) {
      setLogFeedback("Kunne ikke lagre søvn/aktivitet.", true);
      console.error(err);
    }
  });
}

function renderShoppingListItems(items: KitchenOwlShoppingListItem[]): string {
  if (!items.length) {
    return "<p>Handlelisten er tom.</p>";
  }
  return `
    <ul class="shopping-list">
      ${items
        .map(
          (item) => `
            <li class="shopping-item${item.checked ? " shopping-item-checked" : ""}" data-item-row="${item.id}">
              <label>
                <input type="checkbox" data-item-id="${item.id}" ${item.checked ? "checked" : ""} />
                <span class="shopping-item-check" aria-hidden="true">✓</span>
                <span class="shopping-item-name">${escapeHtml(item.name)}</span>
              </label>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

async function loadKitchenOwlSection(): Promise<void> {
  const container = document.getElementById("kitchenowl-content");
  if (!container) return;

  try {
    const status = await api.kitchenowlStatus();
    if (!status.configured) {
      container.innerHTML = `
        <p>
          KitchenOwl er ikke konfigurert ennå. Sett
          <code>KITCHENOWL_BASE_URL</code>, <code>KITCHENOWL_USERNAME</code> og
          <code>KITCHENOWL_PASSWORD</code> i backend-miljøet for å koble til en
          selvhostet KitchenOwl-instans.
        </p>
      `;
      return;
    }

    const items = await api.kitchenowlShoppingList();
    container.innerHTML = `
      ${renderShoppingListItems(items)}
      <form id="kitchenowl-add-form" class="log-form">
        <label>
          Legg til vare
          <input name="name" type="text" maxlength="200" required />
        </label>
        <button type="submit">Legg til</button>
      </form>
      <button type="button" id="kitchenowl-clear-btn" class="secondary-btn" ${
        items.length ? "" : "disabled"
      }>Tøm handleliste</button>
    `;

    container.querySelectorAll<HTMLInputElement>("input[data-item-id]").forEach((checkbox) => {
      checkbox.addEventListener("change", async () => {
        const itemId = Number(checkbox.dataset.itemId);
        const row = checkbox.closest<HTMLLIElement>(".shopping-item");

        // Optimistic, immediate visual feedback before the API call resolves.
        row?.classList.toggle("shopping-item-checked", checkbox.checked);
        if (checkbox.checked && row) {
          row.classList.remove("shopping-item-pulse");
          // Force reflow so the animation restarts if toggled quickly.
          void row.offsetWidth;
          row.classList.add("shopping-item-pulse");
          row.addEventListener(
            "animationend",
            () => row.classList.remove("shopping-item-pulse"),
            { once: true },
          );
        }

        try {
          await api.kitchenowlSetItemChecked(itemId, checkbox.checked);
        } catch (err) {
          console.error(err);
          checkbox.checked = !checkbox.checked;
          row?.classList.toggle("shopping-item-checked", checkbox.checked);
        }
      });
    });

    const addForm = document.getElementById("kitchenowl-add-form") as HTMLFormElement | null;
    addForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(addForm);
      try {
        await api.kitchenowlAddShoppingListItem(String(data.get("name") ?? ""));
        await loadKitchenOwlSection();
      } catch (err) {
        console.error(err);
      }
    });

    const clearBtn = document.getElementById("kitchenowl-clear-btn") as HTMLButtonElement | null;
    clearBtn?.addEventListener("click", async () => {
      if (!window.confirm("Tømme hele handlelisten? Dette kan ikke angres.")) return;
      try {
        await api.kitchenowlClearShoppingList();
        await loadKitchenOwlSection();
      } catch (err) {
        console.error(err);
      }
    });
  } catch (err) {
    container.innerHTML = "<p>Kunne ikke laste handleliste fra KitchenOwl.</p>";
    console.error(err);
  }
}

async function loadDashboardData(): Promise<DashboardReport> {
  return api.dashboard(7, 4);
}

async function refreshSummaries(): Promise<void> {
  const summariesEl = document.querySelector(".summaries");
  if (!summariesEl) return;
  try {
    const report = await loadDashboardData();
    usersById = Object.fromEntries(report.users.map((u) => [u.user_id, u.display_name]));
    summariesEl.innerHTML = report.users.map(renderSummaryCard).join("");
  } catch (err) {
    console.error(err);
  }
}

type TabId = "assistant" | "overview" | "sleep" | "log";

const TABS: { id: TabId; label: string }[] = [
  { id: "assistant", label: "Middagsassistent" },
  { id: "overview", label: "Oversikt" },
  { id: "sleep", label: "Søvn" },
  { id: "log", label: "Registrer" },
];

function renderNav(activeTab: TabId): string {
  return `
    <nav class="main-nav">
      ${TABS.map(
        (tab) => `
          <button type="button" data-tab="${tab.id}" class="nav-tab${tab.id === activeTab ? " active" : ""}">
            ${tab.label}
          </button>
        `,
      ).join("")}
    </nav>
  `;
}

function wireNav(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>("button[data-tab]");
  const panels = document.querySelectorAll<HTMLElement>("[data-tab-panel]");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.tab as TabId;
      buttons.forEach((b) => b.classList.toggle("active", b.dataset.tab === target));
      panels.forEach((p) => {
        p.hidden = p.dataset.tabPanel !== target;
      });
    });
  });
}

async function renderDashboard(): Promise<void> {
  try {
    const me = await api.me();
    const report = await loadDashboardData();
    usersById = Object.fromEntries(report.users.map((u) => [u.user_id, u.display_name]));

    app!.innerHTML = `
      <main class="dashboard">
        <header>
          <h1>Geir Life Hub</h1>
          <p>Innlogget som ${me.display_name}</p>
          <button id="logout">Logg ut</button>
        </header>
        ${renderNav("assistant")}
        <section data-tab-panel="assistant" class="tab-panel">
          ${renderAssistantSection()}
          ${renderKitchenOwlSection()}
        </section>
        <section data-tab-panel="overview" class="tab-panel" hidden>
          <div class="summaries">
            ${report.users.map(renderSummaryCard).join("")}
          </div>
        </section>
        <section data-tab-panel="sleep" class="tab-panel" hidden>
          ${renderSleepTrendSection()}
        </section>
        <section data-tab-panel="log" class="tab-panel" hidden>
          ${renderLogForms()}
        </section>
      </main>
    `;

    document.getElementById("logout")?.addEventListener("click", async () => {
      await api.logout();
      renderLogin();
    });

    wireNav();
    wireLogForms(() => {
      void refreshSummaries();
      void loadSleepHistory();
    });
    void loadKitchenOwlSection();
    void loadAssistantSection();
    void loadSleepHistory();
    wireSleepTrendPeriodButtons();
    void loadSleepTrendSection(sleepTrendDays);
  } catch (err) {
    console.error(err);
    renderLogin();
  }
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => console.error("SW registration failed", err));
  });
}

void renderDashboard();
