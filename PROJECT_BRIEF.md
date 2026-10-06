# Geir Life Hub — prosjektbrief (etablert kontekst, ikke til diskusjon)

## 1. Mål
Personlig/familieorientert "Life Hub" som samler/kobler sammen: kosthold, vekt, trening,
søvn, aktivitet, væske, kaffe, helseobservasjoner/symptomer, oppskrifter, handleliste
(senere evt. flere livsområder).

Life Hub skal **ikke** erstatte gode eksisterende apper. Den skal være:
- oversiktslag
- integrasjonslag
- logging av data som ikke allerede har et godt hjem
- analyse-/rapportlag
- familieapp for funksjoner som deles

**Prinsipp:** Ikke bygg en dårligere kopi av Garmin eller VG Vektklubb.

## 2. Eksisterende systemer (autoritative kilder)
- **Garmin/Garmin Connect**: autoritativ treningsdatabase (trening, skritt, aktivitet, søvn,
  puls, hvilepuls, stress, Body Battery, andre helsemetrikker).
- **VG Vektklubb**: primær kostholdsapp/matdagbok/kalorioppfølging/vektoppfølging.

### Verifiserte tekniske fakta (2026-10-06)
- VG Vektklubb har **ingen offentlig API**. Bekreftet via research — kun evt. manuell
  eksport fra UI. Ikke bygg integrasjon som antar et API finnes.
- Garmin Connect har **ingen personlig/hobbyist developer-API** (kun bedriftsavtaler via
  Garmin Health API-partnerskap). Uoffisielle Python-biblioteker (f.eks.
  `python-garminconnect`) finnes, men er TOS-gråsone og for tiden ustabile pga. Garmins
  Cloudflare/SSO-endringer (mars 2026).
- **Anbefalt integrasjonsvei: Android Health Connect.** Garmin Connect skriver trening/
  skritt/søvn/puls dit allerede; Vektklubb dokumenterer delvis bruk av Health Connect for
  enkelte aktivitets-/helsedata. En liten Android-companion som leser fra Health Connect og
  synker til Life Hub-backend er mer robust enn skraping, og unngår TOS-risiko.
- Data som Health Connect ikke dekker (f.eks. vekt/kalorier fra Vektklubb hvis ikke
  eksponert der) må ha manuell innlogging i Life Hub som fallback.

## 3. Deling med Kristin
Geir er gift med Kristin. **Alt deles åpent mellom de to** — ingen privat/delt-splitting av
data i denne omgang. Life Hub er en 2-brukers familiemodell (husholdningskonsept), ikke
single-user.

## 4. Bekreftet teknisk stack
- Backend: **Python/FastAPI** + **PostgreSQL**, kjørt i **Docker** (selvhostet, matcher
  mønsteret fra en tidligere vurdert app — KitchenOwl).
- Frontend: enkel **webapp/PWA**, delt mellom Geir og Kristin.
- Android-companion for Health Connect-sync (senere fase, etter kjerne-backend/webapp).

## 5. Vurderte svakheter / risikoer å holde øye med
- Garmin/Vektklubb-integrasjon er den mest usikre delen (ingen offisielle API-er) — bygg
  kjernen (manuell logging, oversikt, rapporter, oppskrifter/handleliste) først, så
  Health Connect-sync som eget, isolert modul som kan svikte uten å ta ned resten av appen.
  Unngå å gjøre produktet avhengig av sprø Garmin-scraping.
  - Oppskrifter/handleliste bør vurderes å **gjenbruke et selvhostet KitchenOwl**
    (allerede sikkerhetsgjennomgått og godkjent av Geir i en tidligere oppgave) via dets
    API, i stedet for å bygge disse funksjonene på nytt — i tråd med prinsippet om ikke å
    duplisere gode eksisterende løsninger.
  - 2-brukers familiemodell er enkel nok til at autentisering ikke bør overengineeres
    (f.eks. enkel sesjonsbasert auth med 2 kontoer i samme husholdning), men bør likevel
    bruke korrekt passord-hashing (bcrypt/argon2) og ikke gjenta svakhetene funnet i
    KitchenOwl-gjennomgangen (ingen passordpolicy).

## 6. Status
Dette er et **helt nytt prosjekt** (ingen eksisterende kodebase funnet). Dette dokumentet
er utgangspunktet for implementasjonen; videre arbeid skjer i denne repoen.
