# Geir Life Hub

Selvhostet personlig/familie Life Hub for husholdningen Geir + Kristin. Se
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for de bindende kravene.

Dette er grunnmuren ("scaffold"): backend-API, Postgres, en minimal PWA-frontend
og en adapter mot et separat, selvhostet KitchenOwl-instans for
oppskrifter/handleliste. Vekt-/kosthold-/trening-integrasjon mot Vektklubb og
Garmin er bevisst **ikke** bygget ennå – det er en egen, senere fase.

## Arkitektur

| Del | Teknologi | Ansvar |
|---|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL | Auth, loggbare livsområder (vekt, væske, kaffe, helseobservasjoner, søvn/aktivitet-plassholder), dashboard-aggregering, KitchenOwl-adapter |
| `frontend/` | Vite + TypeScript, PWA (manifest + service worker) | Delt (ikke privat) visning for begge brukere, logg-skjemaer, dashboard |
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
   `frontend` (statisk PWA via nginx på port 5173). Databasetabeller
   opprettes automatisk ved oppstart av backend (`Base.metadata.create_all`).
   For produksjon med ekte data bør dette etter hvert erstattes med Alembic-migrasjoner.

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
uvicorn app.main:app --reload
```

Kjør testene:

```powershell
cd backend
pytest -q
```

Alle 22 tester (auth/passordpolicy, kjernemodeller for vekt/væske/kaffe/
helseobservasjoner/søvn-aktivitet, dashboard-aggregering, KitchenOwl-adapter)
skal passere. Testene kjører mot en SQLite in-memory-database og trenger
ikke Postgres eller Docker.

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
- Dashboard-/rapportendepunkt som aggregerer på tvers av områdene
- KitchenOwl-adapter (grensesnitt mot separat selvhostet instans, ingen lokal duplisering av dens datamodell)
- Docker Compose for backend + Postgres + frontend, versjonspinnet, uten hardkodede hemmeligheter
- Minimal PWA-frontend (delt visning, ingen privat/delt-splitting)
- pytest-dekning for auth og kjernemodellene

Bevisst utelatt (egen, senere fase per brief):

- Garmin-integrasjon (krever Health Connect-companion)
- Vektklubb-integrasjon (krever Health Connect-companion)
- Full kosthold-/kalorisporing (eies av Vektklubb)
- Full treningslogg (eies av Garmin)
- Egen oppskrifts-/handleliste-datamodell (eies av KitchenOwl – kun adapter her)
