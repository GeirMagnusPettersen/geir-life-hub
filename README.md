# Geir Life Hub

Selvhostet personlig/familie Life Hub for husholdningen Geir + Kristin. Se
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for de bindende kravene.

Dette er grunnmuren ("scaffold"): backend-API, Postgres, en PWA-frontend som
konsumerer API-et (innlogging, logg-skjemaer, dashboard med ukentlig trend,
KitchenOwl-handleliste), og en adapter mot et separat, selvhostet
KitchenOwl-instans for oppskrifter/handleliste. Vekt-/kosthold-/trening-
integrasjon mot Vektklubb og Garmin er bevisst **ikke** bygget ennå – det er
en egen, senere fase.

## Arkitektur

| Del | Teknologi | Ansvar |
|---|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL | Auth, loggbare livsområder (vekt, væske, kaffe, helseobservasjoner, søvn/aktivitet-plassholder), dashboard-aggregering, KitchenOwl-adapter |
| `frontend/` | Vite + TypeScript, PWA (manifest + service worker) | Delt (ikke privat) visning for begge brukere: innlogging, logg-skjemaer for vekt/væske/kaffe/helseobservasjoner/søvn-aktivitet, dashboard med ukentlig trend, KitchenOwl-handleliste |
| `docker-compose.yml` | Postgres 16.4 + backend + frontend, versjonspinnet images | Selvhostet drift |

Husholdningen er en fast 2-brukers-modell (ingen åpen selvregistrering) med
enkel sesjonsbasert cookie-auth. Passord hashes med Argon2 (passlib), og et
minimum passordlengde-krav håndheves server-side (`MIN_PASSWORD_LENGTH`,
standard 10 tegn) – både i API-et og i CLI-et som oppretter brukere.

Oppskrifter og handleliste bygges **ikke** på nytt her. `app/integrations/kitchenowl.py`
er en tynn HTTP-klient (JWT-auth, household-scoped) mot en separat,
selvhostet KitchenOwl-instans, eksponert via `/integrations/kitchenowl/*`.
Uten `KITCHENOWL_BASE_URL` satt svarer disse endepunktene `503` (ikke
konfigurert) i stedet for å feile tungt.

## Kom i gang (Docker Compose)

1. Kopiér miljøvariabel-malen og fyll inn hemmeligheter:

   ```powershell
   Copy-Item .env.example .env
   ```

   Sett minst `POSTGRES_PASSWORD` og `SESSION_SECRET_KEY` til egne, lange,
   tilfeldige verdier. Det finnes **ingen** placeholder-fallback for disse i
   `docker-compose.yml` – oppstart feiler bevisst hvis de mangler.

2. Bygg og start alt:

   ```powershell
   docker compose up --build
   ```

   Dette starter `db` (Postgres 16.4), `backend` (FastAPI på port 8000) og
   `frontend` (statisk PWA via nginx på port 5173). Databaseskjemaet
   opprettes/oppdateres automatisk ved oppstart av backend-containeren via
   `alembic upgrade head` (kjøres før `uvicorn` starter, se `backend/Dockerfile`).

   `ollama` (selvhostet lokal vision-modell for bildechat, se
   [Måltidsassistent](#måltidsassistent-chat--handleliste) under) starter
   **ikke** med denne kommandoen - den ligger bak profilen `vision` (som
   `kitchenowl` ligger bak profilen `kitchenowl`) siden imaget er 900 MB+.
   Slå den på ved behov: `docker compose --profile vision up -d ollama`.

3. Opprett de to husholdningsbrukerne (kjøres inne i backend-containeren):

   ```powershell
   docker compose exec backend python -m app.cli create-user --username geir --display-name Geir
   docker compose exec backend python -m app.cli create-user --username kristin --display-name Kristin
   ```

   CLI-et spør om passord (skjult input) og håndhever samme passordpolicy som API-et.

4. Åpne frontend på <http://localhost:5173> og logg inn, eller test API-et
   direkte på <http://localhost:8000/docs> (FastAPI sin auto-genererte Swagger-UI).

### Live-reload for lokal utvikling (Docker)

`docker compose up --build` over bygger produksjonslike images (backend uten
`--reload`, frontend som en statisk nginx-bygd PWA) – praktisk for å verifisere
at alt fungerer likt som i Azure, men upraktisk når du endrer kode ofte siden
du må rebuilde for hver endring.

For rask iterasjon uten rebuild, bruk `docker-compose.dev.yml` i tillegg:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Dette overstyrer kun reload-/mount-oppførselen (samme Postgres, samme
miljøvariabler):

- **backend** kjører `uvicorn --reload` med `./backend/app` og
  `./backend/migrations` bind-mountet – kodeendringer tar effekt umiddelbart,
  ingen rebuild nødvendig.
- **frontend** kjører Vite sin dev-server (med hot module replacement) i
  stedet for nginx-bygget, med `./frontend` bind-mountet – fortsatt på
  <http://localhost:5173>.

Rebuild er fortsatt nødvendig etter endringer i `requirements.txt` eller
`package.json`. `docker-compose.dev.yml` lastes **ikke** automatisk av
`docker compose up` alene – den må alltid spesifiseres eksplisitt med `-f`
slik at vanlig `docker compose up --build` fortsatt gir en produksjonslik
oppsett.

### KitchenOwl-adapter (valgfritt)

Sett `KITCHENOWL_BASE_URL`, `KITCHENOWL_USERNAME`, `KITCHENOWL_PASSWORD` og
`KITCHENOWL_HOUSEHOLD_ID` i `.env` for å koble på en eksisterende,
selvhostet KitchenOwl-instans. La dem stå tomme for å kjøre uten
oppskrifter/handleliste (endepunktene returnerer `503`).

Klienten (`app/integrations/kitchenowl.py`) logger inn mot KitchenOwls
`/auth` (JWT), cacher access-tokenet og logger inn på nytt automatisk
ved `401`. Den eksponerer både lesing (oppskrifter, handleliste) og skriving
(legge til vare på handlelista, kvittere ut en vare) via
`/integrations/kitchenowl/*`.

#### Kjøre en lokal KitchenOwl-instans (valgfritt, for testing uten egen server)

`docker-compose.yml` har en valgfri `kitchenowl`-profil som starter en full,
lokal KitchenOwl-stack (`kitchenowl-backend` + `kitchenowl-frontend`, pinnet
`v0.7.10`) ved siden av Life Hub, uten at du trenger en separat selvhostet
server bare for å prøve integrasjonen:

```powershell
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"  # om nødvendig
docker compose --profile kitchenowl up -d --build backend kitchenowl-backend kitchenowl-frontend
```

> **Viktig:** `kitchenowl-backend` sin egen port snakker rått uWSGI-protokoll,
> ikke HTTP – treff mot den direkte (f.eks. `curl` mot port 5001) henger eller
> feiler stille. `kitchenowl-frontend` (nginx, port 5002) er inngangspunktet:
> den reverse-proxyer `/api/*` til backend-en over HTTP. Sett derfor
> `KITCHENOWL_BASE_URL=http://kitchenowl-frontend/api` (internt Docker-nettverksnavn,
> `/api`-prefiks påkrevd siden adapterens stier er relative til denne URL-en).

Første gang: KitchenOwl har ingen selvregistrering som standard, så bruk
onboarding-endepunktet til å opprette første bruker, og opprett deretter en
husholdning:

```powershell
# Opprett første KitchenOwl-bruker (kun mulig når ingen brukere finnes fra før):
curl.exe -s -X POST http://localhost:5002/api/onboarding `
  -H "Content-Type: application/json" `
  -d '{"username":"lifehub","password":"<ditt-passord>","name":"Life Hub"}'

# Logg inn og lagre access_token fra svaret:
curl.exe -s -X POST http://localhost:5002/api/auth `
  -H "Content-Type: application/json" `
  -d '{"username":"lifehub","password":"<ditt-passord>"}'

# Opprett en husholdning (bruk access_token fra forrige steg):
curl.exe -s -X POST http://localhost:5002/api/household `
  -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" `
  -d '{"name":"Geir Life Hub"}'
# -> responsen inneholder "id" - bruk denne som KITCHENOWL_HOUSEHOLD_ID
```

Sett deretter `KITCHENOWL_USERNAME`/`KITCHENOWL_PASSWORD` til kontoen du
opprettet, `KITCHENOWL_HOUSEHOLD_ID` til husholdnings-ID-en fra svaret over,
generer en `KITCHENOWL_JWT_SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
og start Life Hub-backenden på nytt (`docker compose up -d --force-recreate backend`).
KitchenOwls egen web-UI er tilgjengelig på <http://localhost:5002> hvis du vil
se/administrere handlelisten direkte.

### Måltidsassistent (chat → handleliste)

`app/assistant/` er en tynn, LLM-drevet "måltidsassistent": brukeren fører en
vanlig samtale om hva de skal lage mat, og modellen kan på eksplisitt
forespørsel legge ingrediensene rett inn i KitchenOwl-handlelisten via
adapteren over – uten at bruker manuelt må skrive inn hver vare.

- `GET /assistant/status` → `{"configured": bool}`, brukes av frontend for å
  vise en "ikke konfigurert ennå"-melding når `ASSISTANT_API_KEY` mangler.
- `POST /assistant/chat` med `{"messages": [{"role": "user"|"assistant", "content": "...", "image": "data:image/...;base64,... (valgfritt)"}]}`
  (klienten sender hele samtalehistorikken hver gang – backend er stateless)
  → `{"reply": "...", "added_items": [{"name": "...", "ok": true, "detail": null}]}`.
- Sett `ASSISTANT_API_KEY`, `ASSISTANT_BASE_URL` (default
  `https://api.groq.com/openai/v1`) og `ASSISTANT_MODEL` (default
  `llama-3.3-70b-versatile`) i `.env` for å aktivere funksjonen. Default-
  leverandøren er valgt til [Groq](https://console.groq.com/keys) fordi den
  har et reelt gratis nivå (ingen kredittkort, ~1000 forespørsler/dag) som
  passer prosjektets selvhostede/no-cost-mål bedre enn en betalt-som-standard
  leverandør. Alle OpenAI-kompatible chat-completions-API-er (OpenAI selv,
  Azure OpenAI med kompatibel sti, lokale servere som Ollama/LM Studio) kan
  likevel brukes ved å overstyre `ASSISTANT_BASE_URL`/`ASSISTANT_MODEL`. Uten
  `ASSISTANT_API_KEY` svarer `/assistant/chat` `503` i stedet for å feile
  tungt, og frontend skjuler chat-UI-et.
- Modellen kaller et `add_shopping_list_items`-verktøy kun når brukeren
  eksplisitt ber om å legge varer til handlelisten (systemprompten
  instruerer den om dette), og bekrefter deretter hvilke varer som faktisk
  ble lagt til (via KitchenOwl-adapteren) i svaret.
- Krever at KitchenOwl-adapteren (over) er konfigurert, siden varene legges
  til der.
- **Bilde av en rett → forslag til handleliste**: frontend lar brukeren
  legge ved et bilde (f.eks. av en middag) til en melding via 📷-knappen i
  chat-en. Bildet skaleres/komprimeres client-side (maks ~1024px, JPEG) før
  det sendes som en `data:image/...`-URL.
  Så snart en melding i historikken inneholder et bilde, kjøres turen i to
  steg i stedet for ett:
  1. Bildet beskrives som ren tekst i et eget, verktøy-fritt kall til en
     multimodal (vision-kapabel) modell satt via `ASSISTANT_VISION_MODEL`
     (default `meta-llama/llama-4-scout-17b-16e-instruct` – Groqs
     bilde-modell), eller en egen leverandør satt via
     `ASSISTANT_VISION_BASE_URL`/`ASSISTANT_VISION_API_KEY` (se under).
  2. Bildebeskrivelsen limes inn i brukerens melding som
     `[Bildeanalyse: ...]`-tekst, og resten av samtalen (inkl. eventuelt
     verktøykall for å legge varer i handlelisten) kjøres som vanlig på
     `ASSISTANT_MODEL`.
  Dette er bevisst splittet opp fordi flere mindre/lokale vision-modeller
  (bl.a. Ollamas `moondream`, se under) rett og slett avviser en
  forespørsel som inneholder både bilde og verktøy samtidig (`400 ...does
  not support tools`) - selv om modellen aldri ville trengt å kalle et
  verktøy fra en ren bildebeskrivelse. Ved å alltid la den tekst-/
  verktøykapable modellen eie verktøykallene, og la vision-modellen kun
  beskrive bildet som tekst, unngår vi den begrensningen uansett hvilken
  vision-modell som er konfigurert.
  Assistenten foreslår ingredienser ut fra bildet, men legger dem – som
  ellers – aldri til handlelisten uten eksplisitt bekreftelse fra brukeren.
  Merk: tilgang til Groqs vision-modell avhenger av din Groq-konto/-tier;
  bytt `ASSISTANT_VISION_MODEL` til en annen OpenAI-kompatibel multimodal
  modell om nødvendig, eller bruk den lokale Ollama-oppsettet under for å
  slippe å være avhengig av en ekstern leverandørs bilde-tilgang i det hele
  tatt.
  - **Kjøre bildechat helt lokalt og gratis (Ollama)**: repoet har en
    `ollama`-tjeneste i `docker-compose.yml` (image `ollama/ollama:0.40.0`,
    port 11434, persistent volum), bak profilen `vision` (samme mønster
    som `kitchenowl`-tjenestene), siden imaget er 900 MB+ og de fleste ikke
    trenger den. Slå den på ved behov, første gang:
    ```powershell
    docker compose --profile vision up -d ollama
    docker compose exec ollama ollama pull moondream
    ```
    Sett deretter i `.env` (se `.env.example`) og restart backend:
    ```
    ASSISTANT_VISION_BASE_URL=http://ollama:11434/v1
    ASSISTANT_VISION_API_KEY=ollama
    ASSISTANT_VISION_MODEL=moondream
    ```
    Når disse tre er satt rutes kun bildebeskrivelses-kallet (steg 1 over)
    til den lokale Ollama-instansen; selve samtalen/verktøykallene (steg 2)
    bruker fortsatt `ASSISTANT_BASE_URL`/`ASSISTANT_MODEL` (f.eks. Groq) som
    før. La alle tre stå tomme/kommentert ut for å bruke samme leverandør
    for både tekst og bilder.

### Dashboard-rapport

`GET /reports/dashboard?days=7&weeks=4` returnerer, per bruker, et
øyeblikksbilde (siste `days` dager) og en `weekly_trend`-serie med `weeks`
ukes-bøtter (snitt vekt, væske/kaffe per dag, symptomtelling, snitt
søvnvarighet og hvilepuls). Frontend-dashboardet viser dette per bruker, med
trendserien i en utvidbar tabell (`<details>`).

### Søvn-/pulstrend

`GET /reports/sleep-trend?days=30` returnerer en delt (ikke bruker-splittet
i responsen, men med `user_id`/`display_name` per punkt) daglig tidsserie
for søvnvarighet, skritt, hvilepuls og snittpuls på tvers av begge brukere
– kildedataen er den samme `SleepActivitySummary` som synkes inn fra Health
Connect via `/sleep-activity/sync`. Frontend-dashboardet viser dette i en
egen "Søvn"-fane med to hånd-tegnede SVG-linjediagrammer (søvnvarighet og
puls, én linje per bruker, hvilepuls heltrukket/snittpuls stiplet) og en
periodevelger (7/30/90 dager).

## Kom i gang (skyhosting)

Docker Compose over er ment for selvhosting på egen maskin/VPS. Den eneste
sky-løsningen for Geir Life Hub er **Azure** (via FTE-kreditten, se under) –
ingen andre skytjenester er i bruk eller vedlikeholdes for dette prosjektet.

> **Hvorfor Azure og ikke f.eks. Render/Neon:** disse ble vurdert tidligere,
> men forkastet. Render krever kredittkort-verifisering før det oppretter en
> Web Service, selv på $0/mnd-planen (bekreftet live, gjelder både Blueprint-
> og manuell opprettelse, Docker- og native runtime). Andre gratisalternativer
> for compute (Koyeb, PythonAnywhere) har tilsvarende eller verre
> begrensninger. Azure via **Microsoft FTE-ansattgodet** ($150 Azure-kreditt
> per måned, ~$1 800/år, via Visual Studio Enterprise/FTE-abonnementet – se
> intern SharePoint-side *"Activating Your Azure Visual Studio FTE
> Subscription"*, `AELBootCamp`) er det eneste skyalternativet som verken
> krever eget kredittkort eller har disse begrensningene, og det er allerede
> satt opp og kjører. (Vanlig **Azure Free Account** krever for øvrig kort
> ved registrering, i likhet med Render – det er FTE-godet spesifikt som gjør
> Azure kortfritt her. Uten FTE-tilgang finnes
> **[Azure for Students](https://azure.microsoft.com/free/students/)** som
> alternativ: ingen kort, kun skole-e-post/studentbevis, $100 kreditt/år.)

### Azure-deployment

Et ferdig script ligger i [`azure/deploy.ps1`](azure/deploy.ps1). Det er vanlig
`az` CLI (ingen Bicep/Terraform) og oppretter en resource group, en Azure
Database for PostgreSQL Flexible Server (billigste Burstable B1ms-tier) og to
Azure Container Apps (backend + frontend), bygget direkte fra de eksisterende
Dockerfile-ene.

**Forutsetninger (gjør dette selv, scriptet kan ikke gjøre det for deg):**
1. Aktiver FTE Azure-kreditten via SharePoint-siden nevnt over, med en
   **personlig** Microsoft-konto (ikke `@microsoft.com`).
2. Kjør `az login` lokalt på din egen maskin med den personlige kontoen.
3. Kjør `az account set --subscription "<navn-eller-ID>"` for å velge riktig
   abonnement (bruk `az account list -o table` for å finne det – se etter
   noe i retning "Visual Studio Enterprise" eller lignende, ikke en intern
   Microsoft-subscription).

**Kjør scriptet:**
```powershell
cd azure
./deploy.ps1
```

Scriptet skriver ut frontend- og backend-URL-ene når det er ferdig, og en
kommando for å slette alt igjen (`az group delete`) hvis du vil rydde opp.
Kostnad holder seg godt innenfor $150/måned-kreditten for et 2-brukers
hobbyoppsett.

> **Verifisert live:** Scriptet er faktisk kjørt og verifisert, med
> `az login --use-device-code` mot en personlig FTE-koblet konto (ikke
> agentens interne Microsoft-subscription). Både backend
> (`/health` → `{"status":"ok"}`) og frontend (HTTP 200) ble bekreftet
> nådbare etter kjøring. Noen gotchas ble funnet og fikset underveis, se
> under hvis du støter på de samme feilene selv:
> - **Region kan være stengt for nye kunder:** `westeurope` kan feile med
>   `RequestDisallowedByPolicy` / region restriction på enkelte FTE-
>   subscriptions. Scriptet bruker `norwayeast` som default av denne grunn –
>   bytt `$Location` i toppen av scriptet hvis den også er stengt for deg.
> - **`UnicodeEncodeError`/colorama-krasj:** eldre versjoner av dette
>   scriptet brukte `az containerapp up --source`, som strømmer ACR-build-
>   logger gjennom `azure-cli`s colorama-wrapper og kan krasje på ikke-ASCII
>   tegn i build-output (f.eks. pip/npm-pakkemetadata), selv med tvunget
>   UTF-8-konsoll. Fikset ved å aldri bruke `--source`: images bygges separat
>   med `az acr build --no-logs`, og deployes deretter med
>   `az containerapp up --image` + eksplisitte `--registry-server/-username/-password`.
> - **Frontend Docker-build feilet med `tsc: Permission denied`:** manglende
>   `frontend/.dockerignore` gjorde at `COPY . .` i `frontend/Dockerfile`
>   overskrev containerens nylig-installerte (Linux-rettigheter)
>   `node_modules/.bin/tsc` med en lokalt Windows-bygget `node_modules`-mappe
>   fra build-konteksten. Fikset med en `frontend/.dockerignore` som
>   ekskluderer `node_modules`, `dist`, `.git`, `.env`, `*.log` – en generell
>   gotcha for enhver Dockerfile som gjør `COPY . .` etter `npm install` når
>   du utvikler på en annen OS enn containeren.
> - **`(ResourceNotProvisioned)` ved re-deploy:** hvis en container app
>   havner i `ProvisioningState: Failed` (f.eks. fra et tidligere mislykket
>   forsøk), er ikke `az containerapp up` selvhelbredende – den feiler med
>   denne spesifikke feilen i stedet for å fikse ressursen. Scriptet
>   sjekker nå provisioning-state og sletter+gjenoppretter automatisk hvis
>   den henger fast i `Failed`, før det forsøker å deploye på nytt.

Etter at scriptet er ferdig, opprett de to husholdningsbrukerne via
`az containerapp exec` mot `lifehub-backend` (tilsvarende `docker compose exec`
lokalt):

```bash
python -m app.cli create-user --username geir --display-name Geir
python -m app.cli create-user --username kristin --display-name Kristin
```

KitchenOwl-adapteren er valgfri også her – sett `KITCHENOWL_BASE_URL` m.fl.
som miljøvariabler på `lifehub-backend`-container-appen hvis du har en egen
selvhostet KitchenOwl-instans å koble på (se `azure/deploy.ps1` for hvordan
miljøvariabler settes på appene).

### Health Connect-sync-kontrakt (forberedelse for Android-companion)

Backend-siden av den fremtidige Android Health Connect-companionen (se
`PROJECT_BRIEF.md` seksjon 2/4) er klar til bruk, selv om selve Android-appen
ikke er bygget ennå – det krever Android SDK/Gradle/Kotlin-verktøy som ikke er
tilgjengelig i dette utviklingsmiljøet. Kontrakten companionen skal bruke:

1. En innlogget bruker (via PWA-et) oppretter en enhetstoken:
   `POST /devices {"label": "Geirs telefon"}` → responsen inneholder
   klarteksttokenet **én gang** (`token`-feltet) – det vises aldri igjen.
   `GET /devices` lister enheter (uten klartekst), `DELETE /devices/{id}`
   tilbakekaller en enhet.
2. Companionen autentiserer synk-kall med `Authorization: Bearer <token>`
   (ikke sesjonscookie): `POST /sleep-activity/sync` med
   `{"entries": [{"summary_date": "...", "sleep_minutes": ..., "steps": ...}]}`.
   Rader upsertes per dato og stemples alltid `source="health_connect"` og
   `synced_at`, uavhengig av hva klienten sender.
3. Et tilbakekalt token gir `401` på alle påfølgende synk-kall.

Dette gir et testet, stabilt API-kontraktpunkt å bygge Android-companionen
mot når det blir neste fase, uten å måtte endre backend-skjemaet da.

## Lokal utvikling

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

> Backend krever Python 3.12 (eller eldre 3.x). Python 3.14 mangler per nå
> ferdigbygde wheels for `pydantic-core`, så bruk `py -3.12` eksplisitt hvis
> flere Python-versjoner er installert (`py -0p` lister dem).

Kjør API-et lokalt mot en SQLite-fil (for rask iterasjon uten Postgres):

```powershell
$env:DATABASE_URL = "sqlite:///./dev.db"
$env:SESSION_SECRET_KEY = "dev-only-not-for-production"
alembic upgrade head
uvicorn app.main:app --reload
```

### Database-migrasjoner (Alembic)

Skjemaet er versjonert med [Alembic](https://alembic.sqlalchemy.org/) under
`backend/migrations/`. `DATABASE_URL` (samme miljøvariabel som appen selv
bruker) styrer hvilken database migrasjonene kjører mot – det finnes ingen
hardkodet URL i `alembic.ini`.

```powershell
cd backend
# Kjør alle migrasjoner mot databasen i $env:DATABASE_URL:
alembic upgrade head

# Etter en modellendring i app/models.py, generer en ny migrasjon:
alembic revision --autogenerate -m "beskriv endringen"
# ... inspiser den genererte filen i migrations/versions/ før commit ...

# Rull tilbake én migrasjon:
alembic downgrade -1
```

I Docker Compose kjøres `alembic upgrade head` automatisk som del av
backend-containerens oppstart (før `uvicorn` starter), så Postgres-skjemaet
holdes alltid oppdatert ved deploy. Testsuiten (`pytest`) bruker sin egen
in-memory SQLite-database bygget direkte fra `Base.metadata` (se
`tests/conftest.py`) og er uavhengig av Alembic-migrasjonene.

Kjør testene:

```powershell
cd backend
pytest -q
```

Alle 65 tester (auth/passordpolicy, kjernemodeller for vekt/væske/kaffe/
helseobservasjoner/søvn-aktivitet, enhetstoken-administrasjon, Health
Connect-synk-kontrakten, dashboard-aggregering inkl. ukentlig trend og
søvn/puls-tidsserie, KitchenOwl-adapter) skal passere. Testene kjører mot en
SQLite in-memory-database og trenger ikke Postgres eller Docker.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Dev-serveren kjører på <http://localhost:5173> og forventer backend på
<http://localhost:8000> (konfigurerbart via `VITE_API_BASE_URL`).

Bygg for produksjon (brukes også av `frontend/Dockerfile`):

```powershell
npm run build
```

## Omfang i denne omgangen

Implementert:

- 2-brukers sesjonsbasert auth (Argon2-hashing, server-side minimumslengde på passord)
- Manuell logging: vekt, væske, kaffe, helseobservasjoner
- Søvn/aktivitet: datamodell/endepunkt som plassholder for senere Health Connect-sync
- Enhetstoken-API (`/devices`) + `/sleep-activity/sync`: ferdig, testet
  backend-kontrakt for den fremtidige Health Connect Android-companionen
  (selve Android-appen er ikke bygget – krever Android-verktøy som ikke er
  tilgjengelig her)
- Dashboard-/rapportendepunkt som aggregerer på tvers av områdene, inkludert
  et eget `/reports/sleep-trend`-endepunkt med daglig søvnvarighet og
  hvile-/snittpuls per bruker for en valgfri periode (standard 30 dager)
- KitchenOwl-adapter (grensesnitt mot separat selvhostet instans, ingen lokal duplisering av dens datamodell)
- Måltidsassistent: chat-grensesnitt (LLM tool-calling) som legger
  ingredienser til KitchenOwl-handlelisten på forespørsel, krever en egen
  API-nøkkel (`ASSISTANT_API_KEY`) for å aktiveres
- Alembic-databasemigrasjoner (versjonert skjema, kjøres automatisk ved containeroppstart)
- Docker Compose for backend + Postgres + frontend, versjonspinnet, uten hardkodede hemmeligheter
- PWA-frontend (delt visning, ingen privat/delt-splitting) med innlogging,
  logg-skjemaer for alle livsområdene, dashboard med ukentlig trend og
  KitchenOwl-handleliste-UI (vis/legg til/kvitter ut varer), samt en egen
  "Søvn"-fane med linjediagrammer (hånd-tegnet SVG, ingen ekstern
  grafbibliotek) over søvnvarighet og hvile-/snittpuls for begge brukere
  over tid, med periodevelger (7/30/90 dager)
- pytest-dekning for auth og kjernemodellene

Bevisst utelatt (egen, senere fase per brief):

- Garmin-integrasjon (krever Health Connect-companion)
- Vektklubb-integrasjon (krever Health Connect-companion)
- Full kosthold-/kalorisporing (eies av Vektklubb)
- Full treningslogg (eies av Garmin)
- Egen oppskrifts-/handleliste-datamodell (eies av KitchenOwl – kun adapter her)
