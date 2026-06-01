# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
und das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [2.5.0] – 2026-06-02

### Hinzugefügt
- **Team-Trend** (clone-only): aktive Entwickler pro Monat + After-Hours-/Wochenend-Anteil
  (Dual-Achse) sowie **Bus-Faktor-Trend** je Quartal — Team-Gesundheit & Resilienz über Zeit.
- **Cross-Modul-Kopplung**: Anteil der Multi-File-Commits, die Modulgrenzen überspannen
  (Trend) plus Liste der am stärksten verschränkten Modul-Paare — Indikator für
  Architektur-Erosion. Module werden über bis zu zwei Pfad-Ebenen bestimmt
  (z. B. `packages/ui`), Wurzeldateien ausgenommen.
- **Codebase-IST-Zustand**: aktuelle Sprach-/Dateityp-Verteilung nach Größe und größte
  Dateien in HEAD (via `git ls-tree --long`, ohne Checkout) — schließt die Lücke zwischen
  „Veränderung" (Churn) und „aktuellem Stand".

## [2.4.0] – 2026-06-01

### Hinzugefügt
- **DORA- & Qualitäts-Metriken** (alle clone-only, keine neue Abhängigkeit):
  - **Rework-Rate / Change-Failure-Proxy** — Anteil Nicht-Fix-Commits, denen binnen 14 Tagen
    ein Fix auf derselben Datei folgt (monatlicher Trend + Gesamtquote).
  - **Defekt-anfällige Module** — Dateien mit den meisten `fix:`-Commits.
  - **Test-Begleitung** — monatliche Quote des Churns in Test-/Spec-Dateien.
  - **Verwaistes Wissen** — Dateien, deren letzter Autor seit > 180 Tagen inaktiv ist
    (Code ohne aktiven Betreuer).
  - **Release-Kadenz & Time-to-release** — Releases je Quartal, Median-Abstand zwischen
    Tags und Median-Zeit Commit → nächster Tag (DORA-Deployment-Frequency-Proxy).
- **Throughput-Forecast (Monte-Carlo)** im PO-Dashboard — projiziert den Liefer-Durchsatz
  der nächsten 8 Wochen (50 % / 85 %-Konfidenz) aus dem historischen Wochentempo.

Damit sind die vier DORA-Metriken praktisch abgedeckt (Lead Time, Deployment Frequency,
Change Failure Rate, Rework als MTTR-Näherung).

## [2.3.0] – 2026-06-01

### Hinzugefügt
- **PO-/Delivery-Dashboard** als eigener Top-Level-View (Umschalter „Engineering ↔
  Product / Delivery"), der Engineering-Daten in PO-Sprache übersetzt:
  - **Investment-Mix** (Kapazität nach Feature/Bug/Tech-Debt, Donut + Trend)
  - **Delivery-Throughput** (Work Items mit Code-Aktivität je Zeiteinheit)
  - **Cycle-Time-Proxy** (Spanne erster→letzter Commit je Work Item, Median + Verteilung)
  - **Roadmap-Risiko** (Bus-Faktor & Instabilität je Area Path/Epic)
  - **Rework-Indikator** (Churn-Ratio, Bug-Anteil)
  - **Prozess-Hygiene / Traceability** (Anteil Commits mit Work-Item-Bezug)
  - Jede Kennzahl mit Ein-Satz-Erklärung in PO-Sprache.
- **Azure-DevOps-Work-Item-Anreicherung** über die REST-API (`workitemsbatch`,
  api-version 7.1, nur stdlib `urllib`): Typ, State, Parent (Epic-Rollup), Area Path,
  Iteration, Tags. Batch ≤ 200 IDs, `errorPolicy: omit`, Parent-Ketten-Auflösung.
- **Work-Item-IDs aus Commit-Messages** (`#123`, `AB#123`) — funktioniert auch ohne API.
- **Graceful Degradation**: volles Dashboard mit ADO + PAT; reduziert ohne PAT bzw. bei
  GitHub (Conventional-Commit-basiert, mit sichtbarem Hinweis).
- Self-hosted **Azure DevOps Server** wird erkannt (`/_git/`-Pfad); API-Basis wird aus der
  Repo-URL abgeleitet. Neue Option `--ado-api-version` (Default 7.1).
- `--anonymize` pseudonymisiert Contributor-Namen im HTML (DSGVO-freundliches Teilen).
- `--no-po` deaktiviert das PO-Dashboard.

### Sicherheit
- Das PAT wird ausschließlich für API-Auth (Basic-Header) verwendet, niemals in die HTML
  geschrieben und aus Fehlermeldungen herausgehalten (bestehendes Masking beibehalten).

## [2.2.0] – 2026-06-01

### Hinzugefügt
- **GUI-Desktop-App** (`repo2viz_gui.py`, PySide6 / Qt 6) im Material-3-Dark-Design:
  URL-Eingabe mit Provider-Erkennung, Token-/Ausgabe-Felder, Live-Log, Fortschritts-
  anzeige und „Im Browser öffnen" — die Generierung läuft in einem Worker-Thread.
- **Vorgefertigte Download-Pakete** für macOS, Windows und Linux über die GitHub-
  Releases (gebaut via PyInstaller in GitHub Actions, `.github/workflows/release.yml`).
- Wiederverwendbare API `generate_report(url, …, log=callback)` in `repo2viz.py`,
  die von CLI und GUI gemeinsam genutzt wird.
- `requirements-gui.txt` (PySide6).

### Geändert
- `clone_repo()` gibt keine Meldung mehr direkt aus; Fortschritt läuft über den
  `log`-Callback (saubere Trennung für die GUI).

## [2.1.0] – 2026-06-01

### Hinzugefügt
- **Contributor-Filter** (global): Dropdown im Header + Klick auf eine Zeile der
  Top-Contributors-Tabelle filtert das gesamte zeitbasierte Dashboard auf eine Person.
- **Tagesdetail**: Klick auf eine Kalenderzelle zeigt Stundenverteilung, Commit-Zahl,
  Churn und Contributor-Aufschlüsselung eines einzelnen Tages (Default: aktivster Tag).
- **Stoßzeiten**: radiales 24-Stunden-Zifferblatt (Polar-Chart) der Commit-Verteilung
  über die Tageszeit.
- **Mobile-Ready**: zusätzliche Breakpoints (≤ 880 px / ≤ 600 px), full-width Controls,
  horizontal scrollbare Tabellen, kompaktere Paddings.
- **Versionierung**: `--version`-Flag, Versions-/Generierungs-Footer in der HTML,
  dieses Changelog.
- README mit Screenshot-Galerie aller Features.

### Geändert
- KPI-Karten und Insights respektieren jetzt den aktiven Contributor-Filter.

## [2.0.0] – 2026-06-01

### Hinzugefügt
- **Release-Tag-Marker** in der Commit-Timeline (`git tag`).
- **Wachstumskurve** (kumulierte Netto-Zeilen).
- **Commit-Typen** (Conventional-Commit-Klassifikation) + **Commit-Größen-Histogramm**.
- **Hotspots & Wissensrisiko** (häufig geänderte Dateien mit wenigen Autoren).
- **Verzeichnis-Bus-Faktor** und **Co-Change-Kopplung**.
- **Contributor-Lebensdauer** (Gantt: erste → letzte Aktivität).
- KPIs: Median-Commit-Größe und Conventional-Commits-Anteil.
- Insight: längste Commit-Serie & längste Pause.

## [1.0.0] – 2026-06-01

### Hinzugefügt
- Erste Version: GitHub-/Azure-DevOps-URL → eigenständige HTML-Visualisierung.
- Commit-Timeline mit gleitendem Durchschnitt, Heatmap (Wochentag × Stunde),
  Contribution-Kalender, Contributor-Analyse mit Bus-Faktor, Code-Churn,
  Top-Dateien & Dateityp-Verteilung.
- Umschaltbare Zeiträume (30 T / 90 T / 180 T / 1 Jahr / Gesamt), clientseitig.
- Material-3-Expressive-Dark-Design, Chart.js via CDN mit SRI-Hashes.

[2.5.0]: https://github.com/pepperonas/repo2viz/releases/tag/v2.5.0
[2.4.0]: https://github.com/pepperonas/repo2viz/releases/tag/v2.4.0
[2.3.0]: https://github.com/pepperonas/repo2viz/releases/tag/v2.3.0
[2.2.0]: https://github.com/pepperonas/repo2viz/releases/tag/v2.2.0
[2.1.0]: https://example.com/repo2viz/releases/tag/v2.1.0
[2.0.0]: https://example.com/repo2viz/releases/tag/v2.0.0
[1.0.0]: https://example.com/repo2viz/releases/tag/v1.0.0
