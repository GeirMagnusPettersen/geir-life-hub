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

3. Opprett de to husholdningsbrukerne (kjøres inne i backend-containeren):

   ```powershell
   docker compose exec backend python -m app.cli create-user --username geir --display-name Geir
   docker compose exec backend python -m app.cli create-user --username kristin --display-name Kristin
   ```

   CLI-et spør om passord (skjult input) og håndhever samme passordpolicy som API-et.

4. Åpne frontend på <http://localhost:5173> og logg inn, eller test API-et
   direkte på <http://localhost:8000/docs> (FastAPI sin auto-genererte Swagger-UI).

### KitchenOwl-adapter (valgfritt)

Sett `KITCHENOWL_BASE_URL`, `KITCHENOWL_USERNAME`, `KITCHENOWL_PASSWORD` og
`KITCHENOWL_HOUSEHOLD_ID` i `.env` for å koble på en eksisterende,
selvhostet KitchenOwl-instans. La dem stå tomme for å kjøre uten
oppskrifter/handleliste (endepunktene returnerer `503`).

Klienten (`app/integrations/kitchenowl.py`) logger inn mot KitchenOwls
`/auth/login` (JWT), cacher access-tokenet og logger inn på nytt automatisk
ved `401`. Den eksponerer både lesing (oppskrifter, handleliste) og skriving
(legge til vare på handlelista, kvittere ut en vare) via
`/integrations/kitchenowl/*`.

### Dashboard-rapport

`GET /reports/dashboard?days=7&weeks=4` returnerer, per bruker, et
øyeblikksbilde (siste `days` dager) og en `weekly_trend`-serie med `weeks`
ukes-bøtter (snitt vekt, væske/kaffe per dag, symptomtelling). Frontend-
dashboardet viser dette per bruker, med trendserien i en utvidbar tabell
(`<details>`).

## Kom i gang (skyhosting)

Docker Compose over er ment for selvhosting på egen maskin/VPS. Hvis du i
stedet vil ha appen kjørende på en administrert skytjeneste, er dette
fremgangsmåten (bekreftet live i Render/Neon sine dashbord):

> **Viktig oppdagelse (oppdatert, testet live nov. 2025):** Vi antok
> tidligere at det å opprette enkelttjenester manuelt på Render
> (**New +** → **Web Service**, ikke Blueprint) unngår kredittkort-kravet
> som Renders **Blueprint**-flyt (`render.yaml`) og egen **Postgres**-
> provisjonering har. **Dette viste seg å være feil.** Et faktisk forsøk på
> å opprette én enkelt Web Service manuelt – testet både med Docker-runtime
> og med native Python 3-runtime – viste at Render ber om kortverifisering
> ("Add Card", en midlertidig $1 USD-autorisasjon, ifølge Render selv ikke
> en reell belastning) idet du trykker **Deploy web service**, uavhengig av
> hvilken plan (inkludert $0/mnd Free) eller runtime du har valgt. Dette
> ser ut til å være en konto-/anti-svindel-policy på Render, ikke knyttet
> til Blueprint vs. manuell opprettelse eller Docker vs. native runtime.
>
> [Neon](https://neon.tech) (database) krever fortsatt **ikke** kort og
> fungerer fint som ekstern Postgres uansett hvilken vei du velger for
> compute. Andre undersøkte gratisalternativer for compute (Koyeb,
> PythonAnywhere) har tilsvarende eller verre begrensninger: Koyeb krever
> også kort ved registrering, og PythonAnywheres gratisnivå tillater ikke
> utgående nettverkstilkobling til en ekstern Postgres-database som Neon.
>
> **Praktisk konklusjon:** et *helt* kortfritt cloud-oppsett for
> backend-compute har vi ikke funnet en fungerende løsning for per nå for
> allmenn bruk. De reelle alternativene er (a) legge inn et kort hos Render
> for verifiseringssteget og bli på gratisplanen (ingen løpende kostnad så
> lenge ressursgrensene ikke overskrides), (b) kjøre backend/frontend selv
> via Docker Compose-oppsettet over, på egen maskin/NAS/VPS – som aldri
> krever kort siden det er din egen maskinvare, eller (c) **Azure for
> Students** hvis du er fulltidsstudent (se under) – eneste undersøkte
> skyalternativ som verken krever kort eller er begrenset av nettverks-
> policy, men krever skole-e-post/studentbevis for verifisering.
>
> **Microsoft/Azure-alternativ:** vanlig **Azure Free Account** krever
> kredittkort ved registrering (samme type identitetsverifisering som
> Render), så det er ikke et kortfritt alternativ for de fleste. Det finnes
> derimot et **bekreftet internt Microsoft-ansattgode** som er relevant her:
> som **Microsoft FTE** er du kvalifisert for **$150 Azure-kreditt per
> måned** (~$1 800/år) via Visual Studio Enterprise/FTE-abonnementet – se
> intern side *"Activating Your Azure Visual Studio FTE Subscription"* på
> SharePoint (`AELBootCamp`). Aktivering krever en **personlig
> Microsoft-konto/e-post** (ikke bare `@microsoft.com`) koblet til FTE-
> identiteten din. Dette dekker trygt både backend (App Service eller
> Container Apps) og database (Azure Database for PostgreSQL) for et
> hobbyoppsett som Geir Life Hub, og krever ikke eget kredittkort utover det
> som eventuelt kreves for selve FTE-/VS-abonnementsaktiveringen internt.
> Dette er det anbefalte sky-alternativet fremfor Render, siden det er
> bekreftet gratis innenfor kreditten og ikke avhenger av studentstatus.
> (Alternativt finnes **[Azure for Students](https://azure.microsoft.com/free/students/)**
> for de uten FTE-tilgang: ingen kort, kun skole-e-post/studentbevis, $100
> kreditt/år.)

1. Push repoet til GitHub (allerede gjort for `geir-life-hub`).
2. **Database (Neon, gratis, uten kort):**
   - Gå til [neon.tech](https://neon.tech) → **Get started** → logg inn med
     GitHub/Google/e-post (ingen kort kreves).
   - Opprett et nytt prosjekt (f.eks. `lifehub`). Neon oppretter automatisk
     en database og gir deg en tilkoblingsstreng av typen
     `postgresql://bruker:passord@host/db?sslmode=require`.
   - Kopier denne – den brukes som `DATABASE_URL` under. Backend normaliserer
     selv `postgres://`/`postgresql://` til `postgresql+psycopg://`, så du
     trenger ikke redigere strengen manuelt.
3. **Backend (Render Web Service, gratis plan – krever kortverifisering, se boks over):**
   - Render-dashbord → **New +** → **Web Service** (ikke Blueprint) → koble
     til GitHub (autoriser Render-appen for repoet) → velg `geir-life-hub`.
   - Velg compute-plan **Free** ($0/mnd).
   - Sett **Root Directory** = `backend` og **Dockerfile Path** =
     `backend/Dockerfile` (build-contexten må være `backend/`-mappen siden
     Dockerfilens `COPY`-instruksjoner er relative til den).
   - Legg til miljøvariabler:
     - `ENVIRONMENT` = `production`
     - `SESSION_SECRET_KEY` = bruk Renders **Generate**-knapp (ikke skriv
       inn en egen verdi)
     - `DATABASE_URL` = tilkoblingsstrengen fra Neon (steg 2)
     - `CORS_ORIGINS` = frontendens URL (steg 4 – kan oppdateres etterpå)
     - `MIN_PASSWORD_LENGTH` = `10` (valgfritt, dette er default)
   - Klikk **Deploy web service**.
4. **Frontend (Render Static Site, gratis):**
   - **New +** → **Static Site** → velg samme repo.
   - **Root Directory** = `frontend`, **Build Command** = `npm run build`,
     **Publish Directory** = `dist`.
   - Miljøvariabel `VITE_API_BASE_URL` = backendens Render-URL fra steg 3
     (f.eks. `https://lifehub-backend.onrender.com`).
5. Gå tilbake til backend-tjenesten og oppdater `CORS_ORIGINS` til
   frontendens faktiske URL fra steg 4, så redeploy.
6. Opprett de to husholdningsbrukerne via Render sitt **Shell**-fane for
   `lifehub-backend`-tjenesten (tilsvarende `docker compose exec` lokalt):

   ```bash
   python -m app.cli create-user --username geir --display-name Geir
   python -m app.cli create-user --username kristin --display-name Kristin
   ```

7. Åpne frontendens Render-URL i nettleseren.

KitchenOwl-adapteren er valgfri også her – sett `KITCHENOWL_BASE_URL` m.fl.
som miljøvariabler på `lifehub-backend`-tjenesten i Render-dashbordet hvis du
har en egen selvhostet KitchenOwl-instans å koble på.

> Merk: den gratis Render-planen "sover" tjenester etter ca. 15 minutters
> inaktivitet (første forespørsel etter en pause kan ta 30–60 sekunder), og
> Neons gratisplan har også en "scale-to-zero"-oppførsel for inaktive
> databaser (vekkes automatisk ved neste spørring). Ingen av delene koster
> noe på gratisnivå (Render ber bare om kortet som en midlertidig $1-
> verifisering, ikke en løpende belastning, se boksen over). Oppgrader til
> betalte planer hos Render/Neon hvis du vil ha alltid-på drift.

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

Alle 37 tester (auth/passordpolicy, kjernemodeller for vekt/væske/kaffe/
helseobservasjoner/søvn-aktivitet, enhetstoken-administrasjon, Health
Connect-synk-kontrakten, dashboard-aggregering inkl. ukentlig trend,
KitchenOwl-adapter) skal passere. Testene kjører mot en SQLite
in-memory-database og trenger ikke Postgres eller Docker.

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
- Dashboard-/rapportendepunkt som aggregerer på tvers av områdene
- KitchenOwl-adapter (grensesnitt mot separat selvhostet instans, ingen lokal duplisering av dens datamodell)
- Alembic-databasemigrasjoner (versjonert skjema, kjøres automatisk ved containeroppstart)
- Docker Compose for backend + Postgres + frontend, versjonspinnet, uten hardkodede hemmeligheter
- PWA-frontend (delt visning, ingen privat/delt-splitting) med innlogging,
  logg-skjemaer for alle livsområdene, dashboard med ukentlig trend og
  KitchenOwl-handleliste-UI (vis/legg til/kvitter ut varer)
- pytest-dekning for auth og kjernemodellene

Bevisst utelatt (egen, senere fase per brief):

- Garmin-integrasjon (krever Health Connect-companion)
- Vektklubb-integrasjon (krever Health Connect-companion)
- Full kosthold-/kalorisporing (eies av Vektklubb)
- Full treningslogg (eies av Garmin)
- Egen oppskrifts-/handleliste-datamodell (eies av KitchenOwl – kun adapter her)
