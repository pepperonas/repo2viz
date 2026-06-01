<p align="center"><img src="screenshots/banner.png" alt="repo2viz" width="100%"></p>

# repo2viz

> Repository-Aktivität auf einen Blick — als eigenständige, interaktive HTML-Datei.

<p>
  <a href="https://github.com/pepperonas/repo2viz/releases"><img alt="Version" src="https://img.shields.io/badge/version-2.4.0-d0bcff"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow"></a>
  <a href="https://github.com/pepperonas/repo2viz/releases/latest"><img alt="Downloads" src="https://img.shields.io/github/downloads/pepperonas/repo2viz/total?label=downloads&color=blueviolet"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-stdlib%20%2B%20git-2ea44f">
  <img alt="No build" src="https://img.shields.io/badge/build-none-success">
  <img alt="Single file" src="https://img.shields.io/badge/output-single%20HTML-orange">
  <br>
  <img alt="GitHub" src="https://img.shields.io/badge/source-GitHub-181717?logo=github&logoColor=white">
  <img alt="Azure DevOps" src="https://img.shields.io/badge/source-Azure%20DevOps-0078D7?logo=azuredevops&logoColor=white">
  <img alt="Chart.js" src="https://img.shields.io/badge/charts-Chart.js-FF6384?logo=chartdotjs&logoColor=white">
  <img alt="PySide6" src="https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt%206-41CD52?logo=qt&logoColor=white">
  <img alt="Azure DevOps" src="https://img.shields.io/badge/PO%20Dashboard-Azure%20Work%20Items-0078D7?logo=azuredevops&logoColor=white">
  <img alt="DORA metrics" src="https://img.shields.io/badge/metrics-DORA-7ddfa0">
  <img alt="Material Design 3" src="https://img.shields.io/badge/design-Material%203-6750A4?logo=materialdesign&logoColor=white">
  <img alt="Mobile ready" src="https://img.shields.io/badge/mobile-ready-34d399">
  <br>
  <img alt="SemVer" src="https://img.shields.io/badge/semver-2.0.0-blue">
  <img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey">
  <a href="https://github.com/pepperonas/repo2viz/commits"><img alt="Last commit" src="https://img.shields.io/github/last-commit/pepperonas/repo2viz?color=informational"></a>
  <a href="https://github.com/pepperonas/repo2viz"><img alt="Repo size" src="https://img.shields.io/github/repo-size/pepperonas/repo2viz"></a>
  <a href="https://github.com/pepperonas/repo2viz"><img alt="Top language" src="https://img.shields.io/github/languages/top/pepperonas/repo2viz"></a>
  <a href="https://github.com/pepperonas/repo2viz/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/pepperonas/repo2viz?style=social"></a>
</p>

`repo2viz` nimmt eine **GitHub-** oder **Azure-DevOps**-Repository-URL entgegen, klont das
Repo lesend, analysiert die git-Historie und erzeugt **eine einzelne, eigenständige
HTML-Datei** mit interaktiven Charts und automatischen Analysen — im
**Material-3-Expressive-Design (Dark)**, mit umschaltbaren Zeiträumen und Heatmaps.

Kein Build, keine Dependencies, kein Server: Skript ausführen → HTML im Browser öffnen.

---

## Nutzung

### Schnellstart

```bash
# 1 · Repo klonen
git clone https://github.com/pepperonas/repo2viz.git
cd repo2viz

# 2 · Report für ein beliebiges öffentliches Repo erzeugen
python3 repo2viz.py https://github.com/pallets/click

# 3 · Die erzeugte  <repo-name>-activity.html  im Browser öffnen
```

> **Voraussetzung:** Python 3.11+ und `git` im `PATH` — sonst nichts zu installieren.
> Details unter [Voraussetzungen](#voraussetzungen).

### Aufruf

```bash
python3 repo2viz.py <repo-url> [-o ausgabe.html] [--token TOKEN] [--keep-clone]
```

| Option | Beschreibung |
|--------|--------------|
| `url` | Repository-URL (GitHub oder Azure DevOps) — **erforderlich** |
| `-o`, `--output` | Ziel-HTML-Datei (Standard: `<repo-name>-activity.html`) |
| `--token` | Auth-Token / PAT für private Repos (& Azure-DevOps-Work-Item-API) |
| `--keep-clone` | Temporären Bare-Clone nicht löschen (Debugging) |
| `--anonymize` | Contributor-Namen im HTML pseudonymisieren (DSGVO) |
| `--no-po` | PO-/Delivery-Dashboard nicht erzeugen |
| `--ado-api-version` | Azure-DevOps-REST-api-version (Default `7.1`) |
| `--version` | Version ausgeben |

### Beispiele

```bash
# Öffentliches GitHub-Repo (Ausgabedatei wird automatisch benannt)
python3 repo2viz.py https://github.com/pallets/click

# Azure DevOps
python3 repo2viz.py https://dev.azure.com/org/projekt/_git/repo

# Eigene Ausgabedatei
python3 repo2viz.py https://github.com/me/repo -o report.html

# Privates Repo mit Token
python3 repo2viz.py https://github.com/me/private --token ghp_xxx
```

### Authentifizierung privater Repos

Token per `--token` **oder** Umgebungsvariable (in dieser Reihenfolge geprüft):

| Provider | Umgebungsvariablen |
|----------|--------------------|
| GitHub | `GITHUB_TOKEN`, `GH_TOKEN` |
| Azure DevOps | `AZURE_DEVOPS_PAT`, `AZURE_DEVOPS_TOKEN`, `SYSTEM_ACCESSTOKEN` |
| beliebig | `GIT_TOKEN` (Fallback) |

```bash
export GITHUB_TOKEN=ghp_xxx
python3 repo2viz.py https://github.com/me/private
```

Das Token wird nur für den Clone verwendet, nicht in der HTML gespeichert, und aus
etwaigen Fehlermeldungen maskiert.

---

![Übersicht des repo2viz-Dashboards](screenshots/overview.png)

<sub>Beispiel-Dashboard für <code>vuejs/core</code> (7022 Commits · 632 Contributors · 280 Tags).</sub>

---

## Features

| | |
|---|---|
| 📊 **10 KPI-Karten** | Commits, Contributors, Zeilen +/−, aktive Tage, Ø Commits/Tag, Median-Commit-Größe, Conventional-Commits-Anteil, Peak-Stunde, Top-Wochentag |
| 🧠 **Auto-Analyse** | Bus-Faktor, Wochenend-/Kernzeit-Anteil, Churn-Verhältnis, Aktivitätstrend, längste Commit-Serie & Pause — automatisch abgeleitet |
| 📈 **Commit-Timeline** | Commits über Zeit mit gleitendem Durchschnitt + **Release-Tag-Markern**; Granularität (Tag/Woche/Monat) passt sich dem Zeitraum an |
| 🔥 **Heatmap** | Wochentag × Tageszeit — wann wird committet? (Autor-lokale Stunde) |
| 🟩 **Contribution-Kalender** | Tägliche Commits der letzten 12 Monate im GitHub-Style |
| 🩹 **Code-Churn + Wachstum** | Hinzugefügte / gelöschte Zeilen pro Zeiteinheit + kumulative Netto-Zeilen-Kurve |
| 🏷️ **Commit-Qualität** | Conventional-Commit-Typen (feat/fix/docs…) + Commit-Größen-Histogramm |
| 👥 **Contributor-Analyse** | Top-Contributors-Tabelle, Anteils-Doughnut + **Lebensdauer-Gantt** (erste→letzte Aktivität) |
| 📁 **Datei-Insights** | Meist geänderte Dateien + Dateityp-Verteilung nach Churn |
| 🔥 **Hotspots & Risiko** | Häufig geänderte Dateien mit wenigen Autoren (Wissensrisiko/Refactoring-Kandidaten) |
| 🗂️ **Verzeichnis-Bus-Faktor** | Commits & Contributor-Zahl je Top-Verzeichnis — wo hängt Wissen an wenigen? |
| 🔗 **Co-Change-Kopplung** | Dateien, die häufig zusammen geändert werden — impliziter Architektur-Zusammenhang |
| 🙋 **Contributor-Filter** | Statistiken pro Person — Dropdown im Header oder Klick auf eine Tabellenzeile filtert das ganze Dashboard |
| 📅 **Tagesdetail** | Klick auf einen Kalendertag → Stundenverteilung, Churn & Beteiligte dieses Tages |
| 🕘 **Stoßzeiten** | Radiales 24h-Zifferblatt der Commit-Verteilung über die Tageszeit |
| ⏱️ **Zeitraum-Umschaltung** | 30 T / 90 T / 180 T / 1 Jahr / Gesamt — clientseitig, sofort |
| 📱 **Mobile-Ready** | Responsives Layout für Smartphone & Tablet |
| 📋 **PO-/Delivery-Dashboard** | Eigener View, der Engineering-Daten in PO-Sprache übersetzt — mit Azure-DevOps-Work-Item-Anreicherung ([Details](#po--delivery-dashboard)) |
| 📐 **DORA & Qualität** | Rework-Rate (Change-Failure), Defekt-Module, Test-Begleitung, verwaistes Wissen, Release-Kadenz/Time-to-release + Monte-Carlo-Forecast ([Details](#dora--qualität)) |
| 🔐 **GitHub & Azure DevOps** | Provider-Auto-Erkennung, Token-Auth für private Repos |

---

## Screenshots

### KPI-Karten & Contributor-Filter
Zehn Kennzahlen auf einen Blick; das Dropdown oben rechts (bzw. ein Klick in der
Contributor-Tabelle) löst alle Statistiken nach Person auf.

![KPI-Karten](screenshots/kpis.png)

### Commit-Timeline mit Release-Tags
Commits über Zeit mit gleitendem Durchschnitt; gestrichelte Marker = `git tag`-Releases.

![Commit-Timeline](screenshots/timeline.png)

### Aktivitäts-Heatmap & Stoßzeiten
Wochentag × Tageszeit (links) und das radiale 24-Stunden-Zifferblatt der Stoßzeiten (rechts).

| Heatmap (Wochentag × Stunde) | Stoßzeiten (24h-Uhr) |
|---|---|
| ![Heatmap](screenshots/heatmap.png) | ![Stoßzeiten](screenshots/clock.png) |

### Tagesdetail
Klick auf eine Kalenderzelle öffnet die Detailansicht eines einzelnen Tages —
Stundenverteilung, Churn und Beteiligte.

![Tagesdetail](screenshots/daydetail.png)

### Contribution-Kalender
Tägliche Commits der letzten 12 Monate (GitHub-Style), klickbar für das Tagesdetail.

![Contribution-Kalender](screenshots/calendar.png)

### Commit-Typen & Hotspots
Conventional-Commit-Verteilung und Dateien mit hohem Wissensrisiko (oft geändert, wenige Autoren).

| Commit-Typen | Hotspots & Wissensrisiko |
|---|---|
| ![Commit-Typen](screenshots/commit-types.png) | ![Hotspots](screenshots/hotspots.png) |

### Mobile
Das Layout ist vollständig responsiv (hier ein iPhone-Viewport):

<p align="center"><img src="screenshots/mobile.png" alt="Mobile-Ansicht" width="320"></p>

---

## GUI (Desktop-App)

Wer keine Kommandozeile nutzen möchte: Es gibt eine **Desktop-App** (PySide6 / Qt 6)
im selben Material-3-Dark-Design — URL eingeben, „Report generieren" klicken, fertig.

![repo2viz GUI](screenshots/gui.png)

### Fertige Pakete herunterladen

Vorgefertigte Builds für alle Betriebssysteme gibt es in den
**[Releases](https://github.com/pepperonas/repo2viz/releases/latest)**:

| OS | Paket | Nutzung |
|----|-------|---------|
| 🍎 **macOS** | `repo2viz-gui-macos.zip` | entpacken → `repo2viz-gui.app` starten |
| 🪟 **Windows** | `repo2viz-gui-windows-x86_64.zip` | entpacken → `repo2viz-gui.exe` starten |
| 🐧 **Linux** | `repo2viz-gui-linux-x86_64.tar.gz` | entpacken → `./repo2viz-gui` ausführen |

> **Laufzeit-Voraussetzung:** `git` muss installiert und im `PATH` sein. Die Pakete
> sind unsigniert — unter macOS ggf. über *Rechtsklick → Öffnen* bzw.
> *Systemeinstellungen → Datenschutz & Sicherheit* freigeben.

### Aus dem Quellcode starten

```bash
pip install -r requirements-gui.txt   # PySide6
python3 repo2viz_gui.py
```

---

## PO-/Delivery-Dashboard

Neben der Engineering-Sicht gibt es einen zweiten View **„Product / Delivery"** (Umschalter
oben im Header). Leitprinzip: **übersetzen statt nur darstellen.** Ein Product Owner liest
keinen Code-Churn — er fragt *„Liefern wir Wert, vorhersagbar, ohne Risiko für die Roadmap?"*
Jede Kennzahl wird in dieser Sprache beantwortet (mit Ein-Satz-Erklärung im UI).

![PO-/Delivery-Dashboard](screenshots/po-dashboard.png)

<sub>PO-Ansicht im eingeschränkten Modus (GitHub, ohne Work-Item-Metadaten).</sub>

### Module

| Modul | Beantwortet für den PO |
|-------|------------------------|
| **Investment-Mix** | Wo ging die Kapazität hin? Anteil nach Feature/Story · Bug · Tech-Debt (Donut + Trend über Zeit). |
| **Delivery-Throughput** | Wie viele Work Items hatten pro Woche/Monat Code-Aktivität? (Velocity-Trend-Proxy) |
| **Cycle-Time-Proxy** | Wie lange brauchen Items typischerweise von erster bis letzter Code-Berührung? (Median + Verteilung) |
| **Roadmap-Risiko** | Welche Area Paths/Epics hängen an einer Person oder sind instabil (viel Nacharbeit)? |
| **Rework-Indikator** | Wie viel ist Nacharbeit statt Neubau? (Churn-Ratio, Bug-Anteil) |
| **Prozess-Hygiene** | Anteil Commits **ohne** Work-Item-Bezug — Traceability/Datenqualität fürs Reporting. |

### Azure-DevOps-Integration

Der größte Hebel ist die Verknüpfung von Commits mit **Azure DevOps Work Items**:

1. **Immer (ohne API):** Commit-Messages werden auf Work-Item-Referenzen geparst
   (`#1234` und `AB#1234`) → Mapping Commit → Work-Item-ID rein aus git.
2. **Mit PAT (Azure DevOps):** Über die REST-API (`workitemsbatch`, api-version 7.1) werden
   Typ, State, Parent (für **Epic-Rollup**), Area Path, Iteration und Tags nachgeladen
   (Batch ≤ 200 IDs, robustes Error-Handling, Parent-Ketten-Auflösung).

```bash
export AZURE_DEVOPS_PAT=xxxxxxxx        # Scope: Work Items (Read)
python3 repo2viz.py https://dev.azure.com/org/projekt/_git/repo
```

Das PAT wird **nur** für die API-Authentifizierung verwendet, landet **nie** in der HTML und
wird aus Fehlermeldungen maskiert. Self-hosted **Azure DevOps Server** wird über den
`/_git/`-Pfad erkannt; die API-Basis wird aus der Repo-URL abgeleitet (ggf. `--ado-api-version`
auf `6.0`/`5.0` setzen).

### Graceful Degradation

| Situation | PO-Dashboard |
|-----------|--------------|
| **Azure DevOps + PAT** | Voll: angereicherte Work Items (Typ, State, Epic, Area Path). |
| **Azure DevOps ohne PAT** | Nur aus Commit-Messages geparste IDs — mit Hinweis „PAT für volle Auswertung setzen". |
| **GitHub** | Provider-unabhängige Teile (Conventional-Commit-basierter Investment-Mix, Rework, Hygiene), klar als eingeschränkt gekennzeichnet. |

Fehlt etwas, stürzt nichts ab — alle Felder werden defensiv behandelt.

### Relevante Optionen

| Option / Env | Beschreibung |
|--------------|--------------|
| `AZURE_DEVOPS_PAT` (Env) | PAT für die Work-Item-Anreicherung (auch `AZURE_DEVOPS_TOKEN`, `SYSTEM_ACCESSTOKEN`, `--token`). |
| `--ado-api-version` | Azure-DevOps-REST-api-version (Default `7.1`; on-prem ggf. `6.0`/`5.0`). |
| `--anonymize` | Contributor-Namen im HTML pseudonymisieren — sinnvoll, da PO-Dashboards breiter geteilt werden (DSGVO). |
| `--no-po` | PO-Dashboard nicht erzeugen. |

---

## DORA & Qualität

Zusätzliche Metriken, die Liefer- und Codequalität messbar machen — **alle clone-only**
(keine API, kein Token nötig). Im Engineering-View ergänzen sie die bestehenden Charts,
ein Forecast liegt im PO-View.

![Rework-Rate](screenshots/dora-rework.png)

| Metrik | Was sie misst | Wie sie ermittelt wird |
|--------|---------------|------------------------|
| **Rework-Rate** (Change-Failure-Proxy) | Wie oft frisch Geliefertes sofort nachgebessert wird | Anteil der **Nicht-Fix-Commits**, denen binnen **14 Tagen** ein `fix:`-Commit auf **derselben Datei** folgt (monatlicher Trend + Gesamtquote). |
| **Defekt-anfällige Module** | Wo sich Bugs sammeln | Dateien mit den meisten `fix:`-Commits (≥ 2). |
| **Test-Begleitung** | Ob Testabdeckung mitwächst | Monatliche Quote des Churns in Test-/Spec-Dateien (`tests/`, `*.test.*`, `*_spec.*` …) am Gesamt-Churn. |
| **Verwaistes Wissen** | Code ohne aktiven Betreuer | Dateien, deren **letzter** Autor seit **> 180 Tagen** keinen Commit mehr gemacht hat. |
| **Release-Kadenz & Time-to-release** | Wie oft & wie schnell wir ausliefern | Releases je Quartal, Median-Abstand zwischen Tags, Median-Zeit Commit → nächster Tag (Deployment-Frequency-Proxy). |
| **Throughput-Forecast** (Monte-Carlo) | „Schaffen wir den Plan?" | 2000 Simulationen über die Verteilung des Wochentempos der letzten 26 Wochen → erwarteter Durchsatz der nächsten 8 Wochen (50 % / 85 % Konfidenz). |

| Release-Kadenz & Time-to-release | Throughput-Forecast (PO-View) |
|---|---|
| ![Release-Kadenz](screenshots/dora-cadence.png) | ![Forecast](screenshots/dora-forecast.png) |

> Damit deckt repo2viz die vier **DORA-Metriken** praktisch ab: Lead Time, Deployment
> Frequency, Change Failure Rate und Rework als MTTR-Näherung. Die Schwellen
> (14-Tage-Rework-Fenster, 180-Tage-Orphan-Grenze) stehen als Konstanten im Code.

---

## Voraussetzungen

* **Python 3.11+** — die CLI nutzt nur die Standardbibliothek, keine Pakete zu installieren
* **git** im `PATH`
* **Internet beim Öffnen der HTML** — Chart.js + Matrix- und Annotation-Plugin werden per
  CDN geladen (mit verifizierten SRI-Integritäts-Hashes als Schutz gegen CDN-Manipulation)
* **nur für die GUI:** [PySide6](https://pypi.org/project/PySide6/) (`pip install -r requirements-gui.txt`)
  — die fertigen Release-Pakete bringen alles mit, dann ist nichts zu installieren

---

## Funktionsweise

```
URL ──▶ Provider erkennen ──▶ git clone --bare (temp) ──▶ git log --no-merges --numstat
                                                                      │
                                                                      ▼
        HTML mit eingebetteten Daten ◀── Aggregation in Python ◀── Parsing
                     │
                     ▼
   Browser: clientseitige Aggregation je Zeitraum (Chart.js)
```

1. **Provider-Erkennung** über den Host der URL (github.com / dev.azure.com / visualstudio.com).
2. **Bare-Clone** in ein temporäres Verzeichnis (kein Working-Tree → schnell), das danach
   automatisch entfernt wird.
3. **Analyse** via `git log --no-merges --numstat` — Commits, Autoren, Zeitstempel (Autor-lokal)
   und Zeilen-Churn pro Datei.
4. **Einbettung**: Die komplette Historie wird kompakt (wenige Integer pro Commit) als JSON in
   die HTML eingebettet. **Alle Zeitraum-Aggregationen passieren clientseitig in JavaScript** —
   deshalb ist das Umschalten der Zeiträume sofort und ohne erneute Datenbeschaffung.

---

## Hinweise & Designentscheidungen

* Analysiert wird die git-Historie **ohne Merge-Commits** (`--no-merges`), damit Churn nicht
  doppelt gezählt wird.
* **Zeitraumunabhängig (gesamtbezogen)** sind: Dateien, Dateitypen, Hotspots, Verzeichnis-Bus-Faktor,
  Co-Change-Kopplung, Contributor-Lebensdauer und der Contribution-Kalender — sie sind entsprechend
  beschriftet. Alle übrigen Charts reagieren auf den Zeitraum-Umschalter.
* **Commit-Typen** werden per [Conventional-Commits](https://www.conventionalcommits.org/)-Muster
  aus der Message-Zeile klassifiziert (`feat:`, `fix:`, `docs:` …); nicht typisierte Messages
  fallen unter „sonstige".
* **Hotspots** = häufig geänderte Dateien geteilt durch Autorenzahl → hoher Wert = oft geändert
  *und* von wenigen betreut (Wissensrisiko). Nur Dateien mit ≥ 3 Änderungen.
* **Co-Change-Kopplung** betrachtet nur Commits mit 2–40 berührten Dateien (vermeidet quadratische
  Explosion bei Massen-Commits) und listet Paare ab 3 gemeinsamen Commits.
* **Release-Marker** in der Timeline stammen aus `git tag` (Erstell-/Commit-Datum des Tags).
* Contributors werden **per E-Mail-Adresse** zusammengeführt; unterschiedliche E-Mails derselben
  Person erscheinen als getrennte Einträge.
* Stunden in der Heatmap sind **Autor-lokal** (aus dem Zeitzonen-Offset des Commits), nicht UTC.
* Der **Contribution-Kalender** zeigt fix die letzten 12 Monate, unabhängig vom Zeitraum-Umschalter.
* Der **Contributor-Filter** wirkt auf alle zeitbasierten Charts, KPIs, Insights, Heatmaps und den
  Kalender. Strukturelle Analysen (Hotspots, Verzeichnis-Bus-Faktor, Co-Change-Kopplung,
  Lebensdauer) bleiben gesamtbezogen, und die Top-Contributors-Tabelle zeigt immer alle Personen
  (damit man weiterhin umschalten kann).

---

## Versionierung

Das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/) (`MAJOR.MINOR.PATCH`).
Die aktuelle Version steht in `repo2viz.py` (`__version__`) und ist über `--version` abrufbar:

```bash
python3 repo2viz.py --version     # -> repo2viz 2.1.0
```

Sie erscheint außerdem im Footer jeder generierten HTML. Alle Änderungen sind im
[CHANGELOG.md](CHANGELOG.md) dokumentiert.

---

## Troubleshooting

| Problem | Ursache / Lösung |
|---------|------------------|
| `git clone fehlgeschlagen` | URL prüfen; bei privaten Repos Token setzen (`--token` / Env-Variable). |
| Charts bleiben leer | Internetzugang beim Öffnen der HTML nötig (Chart.js per CDN). |
| `Keine Commit-Daten gefunden` | Repo ist leer oder enthält nur Merge-Commits. |
| Falsche/fehlende Contributors | Mehrere E-Mail-Adressen pro Person — ggf. `.mailmap` im Repo pflegen. |

---

## Lizenz

[MIT](LICENSE) © 2026 Martin Pfeffer ([pepperonas](https://github.com/pepperonas))
