import {
  api,
  type AssistantChatMessage,
  type DashboardReport,
  type KitchenOwlShoppingListItem,
  type UserReportSummary,
} from "./api";

const app = document.getElementById("app");

if (!app) {
  throw new Error("Missing #app root element");
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
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
    </section>
  `;
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
      </p>
    `;
  }
  return assistantHistory
    .map((msg) => {
      const isUser = msg.role === "user";
      return `
        <div class="chat-row chat-row-${isUser ? "user" : "assistant"}">
          <div class="chat-bubble chat-bubble-${isUser ? "user" : "assistant"}">
            <span class="chat-sender">${isUser ? "Du" : "Assistent"}</span>
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

function renderAssistantChatUI(): string {
  return `
    <div id="assistant-history" class="assistant-history">${renderAssistantHistory()}</div>
    <form id="assistant-form" class="log-form assistant-input-row">
      <label class="assistant-input-label">
        Melding
        <input name="message" type="text" maxlength="4000" required placeholder="f.eks. jeg tenkte på taco i kveld" autocomplete="off" />
      </label>
      <button type="submit">Send</button>
    </form>
    <p id="assistant-feedback" role="status"></p>
  `;
}

async function handleAssistantSubmit(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const data = new FormData(form);
  const text = String(data.get("message") ?? "").trim();
  if (!text) return;

  assistantHistory.push({ role: "user", content: text });
  const historyEl = document.getElementById("assistant-history");
  const feedbackEl = document.getElementById("assistant-feedback");
  if (historyEl) historyEl.innerHTML = renderAssistantHistory();
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
      feedbackEl.textContent = "Kunne ikke nå assistenten.";
      feedbackEl.classList.add("error");
    }
  }
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
    summariesEl.innerHTML = report.users.map(renderSummaryCard).join("");
  } catch (err) {
    console.error(err);
  }
}

type TabId = "assistant" | "overview" | "log";

const TABS: { id: TabId; label: string }[] = [
  { id: "assistant", label: "Middagsassistent" },
  { id: "overview", label: "Oversikt" },
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
    });
    void loadKitchenOwlSection();
    void loadAssistantSection();
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
