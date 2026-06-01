# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
und das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

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

[2.1.0]: https://example.com/repo2viz/releases/tag/v2.1.0
[2.0.0]: https://example.com/repo2viz/releases/tag/v2.0.0
[1.0.0]: https://example.com/repo2viz/releases/tag/v1.0.0
