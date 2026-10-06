import { api, type DashboardReport } from "./api";

const app = document.getElementById("app");

if (!app) {
  throw new Error("Missing #app root element");
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

function renderSummaryCard(report: DashboardReport): string {
  return report.users
    .map(
      (user) => `
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
        </article>
      `,
    )
    .join("");
}

async function renderDashboard(): Promise<void> {
  try {
    const me = await api.me();
    const report = await api.dashboard(7);

    app!.innerHTML = `
      <main class="dashboard">
        <header>
          <h1>Geir Life Hub</h1>
          <p>Innlogget som ${me.display_name}</p>
          <button id="logout">Logg ut</button>
        </header>
        <section class="summaries">
          ${renderSummaryCard(report)}
        </section>
        <p class="hint">
          Dette er et skjelett – flere logg-skjemaer (vekt, væske, kaffe,
          helseobservasjoner, søvn/aktivitet) kan bygges videre her mot de
          eksisterende backend-endepunktene.
        </p>
      </main>
    `;

    document.getElementById("logout")?.addEventListener("click", async () => {
      await api.logout();
      renderLogin();
    });
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
