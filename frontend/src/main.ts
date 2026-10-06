import {
  api,
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
            <li>
              <label>
                <input type="checkbox" data-item-id="${item.id}" ${item.checked ? "checked" : ""} />
                ${item.name}
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
    `;

    container.querySelectorAll<HTMLInputElement>("input[data-item-id]").forEach((checkbox) => {
      checkbox.addEventListener("change", async () => {
        const itemId = Number(checkbox.dataset.itemId);
        try {
          await api.kitchenowlSetItemChecked(itemId, checkbox.checked);
        } catch (err) {
          console.error(err);
          checkbox.checked = !checkbox.checked;
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
        <section class="summaries">
          ${report.users.map(renderSummaryCard).join("")}
        </section>
        ${renderLogForms()}
        ${renderKitchenOwlSection()}
      </main>
    `;

    document.getElementById("logout")?.addEventListener("click", async () => {
      await api.logout();
      renderLogin();
    });

    wireLogForms(() => {
      void refreshSummaries();
    });
    void loadKitchenOwlSection();
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
