#!/usr/bin/env python3
"""
repo2viz - Repository Activity Visualizer
=======================================

Nimmt eine GitHub- oder Azure-DevOps-Repository-URL entgegen, klont sie
(bare, read-only), analysiert die git-Historie und erzeugt eine einzelne,
eigenstaendige HTML-Datei mit interaktiven Charts im Material-3-Expressive-
Dark-Design.

Features
--------
* Commit-Timeline mit gleitendem Durchschnitt + Release-Tag-Markern
* Heatmap Wochentag x Stunde
* GitHub-Style Contribution-Kalender (letzte 12 Monate)
* Contributor-Analyse inkl. Bus-Faktor und Lebensdauer (erste->letzte Aktivitaet)
* Code-Churn + kumulative Wachstumskurve
* Commit-Typen (Conventional Commits) und Commit-Groessen-Verteilung
* Hotspots/Wissensrisiko, Verzeichnis-Bus-Faktor, Co-Change-Kopplung
* Top-Dateien & Dateityp-Verteilung
* Umschaltbare Zeitraeume (30 T / 90 T / 180 T / 1 J / Gesamt) - clientseitig, instant

Nutzung
-------
    python3 repo2viz.py <repo-url> [-o output.html] [--token TOKEN]

Private Repos: Token via --token oder Umgebungsvariable
(GITHUB_TOKEN / AZURE_DEVOPS_PAT / GIT_TOKEN).

Nur Python-Standardbibliothek + git erforderlich.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from urllib.parse import quote, urlparse

__version__ = "2.1.0"

# Datensatz-Trenner (ASCII-Steuerzeichen, kommen in git-Metadaten praktisch nie vor)
REC = "\x1e"   # record separator
FLD = "\x1f"   # field separator


# --------------------------------------------------------------------------- #
#  Provider-Erkennung & Authentifizierung
# --------------------------------------------------------------------------- #
def detect_provider(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "github" in host:
        return "github"
    if "dev.azure.com" in host or "visualstudio.com" in host:
        return "azure"
    return "generic"


def resolve_token(provider: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    candidates = {
        "github": ["GITHUB_TOKEN", "GH_TOKEN"],
        "azure": ["AZURE_DEVOPS_PAT", "AZURE_DEVOPS_TOKEN", "SYSTEM_ACCESSTOKEN"],
        "generic": [],
    }.get(provider, [])
    candidates.append("GIT_TOKEN")
    for name in candidates:
        if os.environ.get(name):
            return os.environ[name]
    return None


def build_clone_url(url: str, provider: str, token: str | None) -> str:
    """Baut bei Bedarf eine Clone-URL mit eingebettetem Token (nur fuer privates Cloning)."""
    if not token:
        return url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return url
    # Azure DevOps erwartet das PAT als Passwort (User beliebig), GitHub akzeptiert Token als User.
    if provider == "azure":
        userinfo = f"pat:{quote(token, safe='')}"
    else:
        userinfo = quote(token, safe="")
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    return f"{parts.scheme}://{userinfo}@{netloc}{parts.path}"


def repo_display_name(url: str) -> str:
    path = urlparse(url).path.strip("/")
    path = re.sub(r"\.git$", "", path)
    # Azure: org/project/_git/repo -> repo (mit Projekt-Kontext)
    if "/_git/" in path:
        org_proj, repo = path.split("/_git/", 1)
        proj = org_proj.split("/")[-1]
        return f"{proj}/{repo}" if proj and proj != repo else repo
    parts = path.split("/")
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return path or "repository"


# --------------------------------------------------------------------------- #
#  Clone & git-Log-Parsing
# --------------------------------------------------------------------------- #
def clone_repo(clone_url: str, dest: str) -> None:
    print("  -> Klone Repository (bare) ...", flush=True)
    res = subprocess.run(
        ["git", "clone", "--bare", "--quiet", clone_url, dest],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        msg = res.stderr.strip() or res.stdout.strip()
        # Token nicht in der Fehlermeldung ausgeben
        msg = re.sub(r"//[^@/]+@", "//***@", msg)
        raise RuntimeError(f"git clone fehlgeschlagen:\n{msg}")


def git_log(repo_dir: str) -> str:
    fmt = f"{REC}%H{FLD}%aI{FLD}%aN{FLD}%aE{FLD}%s"
    res = subprocess.run(
        ["git", "-C", repo_dir, "log", "--no-merges", "--numstat",
         "--date=iso-strict", f"--pretty=format:{fmt}"],
        capture_output=True, text=True, errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"git log fehlgeschlagen:\n{res.stderr.strip()}")
    return res.stdout


def git_tags(repo_dir: str):
    """Liefert [[tag-name, day-ordinal], ...], sortiert nach Datum."""
    res = subprocess.run(
        ["git", "-C", repo_dir, "for-each-ref", "--sort=creatordate",
         f"--format=%(refname:short){FLD}%(creatordate:short)", "refs/tags"],
        capture_output=True, text=True, errors="replace",
    )
    if res.returncode != 0:
        return []
    tags = []
    for line in res.stdout.splitlines():
        if FLD not in line:
            continue
        name, date_s = line.split(FLD, 1)
        try:
            d = dt.date.fromisoformat(date_s.strip())
        except ValueError:
            continue
        tags.append([name, d.toordinal() - EPOCH])
    return tags


EPOCH = dt.date(1970, 1, 1).toordinal()

# Conventional-Commit-Typen -> Kategorie-Index (Reihenfolge = Index)
COMMIT_CATS = ["feat", "fix", "docs", "style", "refactor", "perf",
               "test", "build", "ci", "chore", "revert", "sonstige"]
_CAT_INDEX = {c: i for i, c in enumerate(COMMIT_CATS)}
_CONV_RE = re.compile(r"^([a-zA-Z]+)(?:\([^)]*\))?!?:\s")
_CAT_ALIASES = {"feature": "feat", "bugfix": "fix", "fixes": "fix", "doc": "docs",
                "tests": "test", "refac": "refactor", "performance": "perf"}


def classify_commit(subject: str) -> int:
    """Ordnet eine Commit-Message einer Conventional-Commit-Kategorie zu."""
    m = _CONV_RE.match(subject or "")
    if m:
        t = m.group(1).lower()
        t = _CAT_ALIASES.get(t, t)
        if t in _CAT_INDEX:
            return _CAT_INDEX[t]
    return _CAT_INDEX["sonstige"]


def _top_dir(path: str) -> str:
    """Oberstes Verzeichnis eines Pfads (oder '(root)' fuer Dateien im Wurzelverzeichnis)."""
    i = path.find("/")
    return path[:i] if i > 0 else "(root)"


def parse_log(raw: str):
    """Zerlegt die git-log-Ausgabe in kompakte, JSON-faehige Strukturen."""
    authors: list[str] = []
    author_index: dict[str, int] = {}
    commits = []                       # [day, weekday, hour, authorIdx, ins, del, msgCat]
    file_changes: dict[str, list] = defaultdict(lambda: [0, 0, 0, set()])  # path -> [commits, ins, del, {authorIdx}]
    ext_changes: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])     # ext  -> [commits, ins, del]
    dir_changes: dict[str, list] = defaultdict(lambda: [0, 0, set()])      # dir  -> [commits, churn, {authorIdx}]
    couples: dict[tuple, int] = defaultdict(int)                           # (fileA,fileB) -> gemeinsame Commits
    msg_len_total = 0
    msg_count = 0

    records = raw.split(REC)
    for rec in records:
        rec = rec.strip("\n")
        if not rec:
            continue
        lines = rec.split("\n")
        header = lines[0]
        fields = header.split(FLD, 4)
        if len(fields) < 4:
            continue
        _sha, iso, name, email = fields[0], fields[1], fields[2], fields[3]
        subject = fields[4] if len(fields) > 4 else ""
        try:
            when = dt.datetime.fromisoformat(iso)
        except ValueError:
            continue

        key = email.lower() or name.lower()
        if key not in author_index:
            author_index[key] = len(authors)
            authors.append(name or email or "unbekannt")
        a_idx = author_index[key]

        local = when  # Autor-lokale Zeit (inkl. Offset aus %aI)
        day = local.date().toordinal() - EPOCH
        weekday = local.weekday()      # Mo=0 .. So=6
        hour = local.hour
        cat = classify_commit(subject)
        msg_len_total += len(subject); msg_count += 1

        c_ins = c_del = 0
        touched_files = []
        touched_dirs = set()
        for ln in lines[1:]:
            if not ln.strip():
                continue
            cols = ln.split("\t")
            if len(cols) < 3:
                continue
            ins_s, del_s, path = cols[0], cols[1], cols[2]
            if ins_s == "-" or del_s == "-":
                ins_n = del_n = 0          # Binaerdatei
            else:
                try:
                    ins_n, del_n = int(ins_s), int(del_s)
                except ValueError:
                    ins_n = del_n = 0
            c_ins += ins_n
            c_del += del_n
            # Rename-Notation "a => b" auf Zielpfad reduzieren
            if "=>" in path:
                path = re.sub(r"\{[^{}]*=>\s*([^{}]*)\}", r"\1", path)
                path = path.split("=>")[-1].strip()
            fc = file_changes[path]
            fc[0] += 1; fc[1] += ins_n; fc[2] += del_n; fc[3].add(a_idx)
            touched_files.append(path)
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "(ohne)"
            if len(ext) > 12:
                ext = "(ohne)"
            ec = ext_changes[ext]
            ec[0] += 1; ec[1] += ins_n; ec[2] += del_n
            d = _top_dir(path)
            touched_dirs.add(d)
            dir_changes[d][1] += ins_n + del_n

        for d in touched_dirs:
            dir_changes[d][0] += 1
            dir_changes[d][2].add(a_idx)

        # Co-Change-Kopplung (nur ueberschaubare Commits, sonst quadratische Explosion)
        if 2 <= len(touched_files) <= 40:
            uniq = sorted(set(touched_files))
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    couples[(uniq[i], uniq[j])] += 1

        commits.append([day, weekday, hour, a_idx, c_ins, c_del, cat])

    # Top-Dateien (nach Aenderungs-Commits) & Top-Dateitypen (nach Churn)
    top_files = sorted(file_changes.items(), key=lambda kv: kv[1][0], reverse=True)[:15]
    top_files = [[p, v[0], v[1], v[2]] for p, v in top_files]
    top_exts = sorted(ext_changes.items(), key=lambda kv: kv[1][1] + kv[1][2], reverse=True)[:12]
    top_exts = [[e, v[0], v[1], v[2]] for e, v in top_exts]

    # Hotspots: oft geaendert UND von wenigen Autoren betreut (Wissensrisiko).
    # Score = Aenderungen / Autorenzahl  -> hoch = haeufig + konzentriert.
    hot = [(p, v[0], len(v[3]), v[1], v[2]) for p, v in file_changes.items() if v[0] >= 3]
    hot.sort(key=lambda t: t[1] / t[2], reverse=True)
    hotspots = [[p, ch, na, ins, dl] for p, ch, na, ins, dl in hot[:15]]

    # Verzeichnis-Bus-Faktor
    dirs = sorted(dir_changes.items(), key=lambda kv: kv[1][0], reverse=True)[:12]
    dir_bus = [[d, v[0], v[1], len(v[2])] for d, v in dirs]

    # Co-Change-Kopplung (Top-Paare ab 3 gemeinsamen Commits)
    coup = [(a, b, n) for (a, b), n in couples.items() if n >= 3]
    coup.sort(key=lambda t: t[2], reverse=True)
    coupling = [[a, b, n] for a, b, n in coup[:15]]

    avg_msg = round(msg_len_total / msg_count, 1) if msg_count else 0

    return {
        "authors": authors,
        "commits": commits,
        "topFiles": top_files,
        "topExts": top_exts,
        "hotspots": hotspots,
        "dirBus": dir_bus,
        "coupling": coupling,
        "cats": COMMIT_CATS,
        "avgMsgLen": avg_msg,
    }


# --------------------------------------------------------------------------- #
#  HTML-Generierung
# --------------------------------------------------------------------------- #
def build_html(data: dict, meta: dict) -> str:
    payload = {
        "authors": data["authors"],
        "commits": data["commits"],
        "topFiles": data["topFiles"],
        "topExts": data["topExts"],
        "hotspots": data["hotspots"],
        "dirBus": data["dirBus"],
        "coupling": data["coupling"],
        "cats": data["cats"],
        "avgMsgLen": data["avgMsgLen"],
        "tags": data.get("tags", []),
        "meta": meta,
    }
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    blob = blob.replace("</", "<\\/")  # script-Tag-sicher
    return HTML_TEMPLATE.replace("/*__DATA__*/null", blob)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Repository Activity</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Roboto+Flex:opsz,wght@8..144,300..800&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js" integrity="sha256-1G2Xof0CLF+yn6L0Xry8MiAtc67r8HbOX3JI9UmPx9c=" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-matrix@2.0.1/dist/chartjs-chart-matrix.min.js" integrity="sha256-yNUdbELnNeTiZZpVr1F8fUXCHauRzeh7xjtiIIzjF8Y=" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js" integrity="sha256-8BDDxChCyYOB80/6VhOpmr7qI5EIDyDPzxsWePPFVfo=" crossorigin="anonymous"></script>
<style>
:root{
  --bg:#141218; --surface:#1d1b20; --surface-2:#211f26; --surface-3:#2b2930;
  --on-surface:#e6e0e9; --on-surface-var:#cac4d0; --outline:#49454f;
  --primary:#d0bcff; --on-primary:#381e72; --primary-c:#4f378b;
  --secondary:#ccc2dc; --tertiary:#efb8c8; --accent:#7dd3c0;
  --pos:#7ddfa0; --neg:#ff9b9b;
  --r-xl:28px; --r-l:20px; --r-m:14px; --r-s:10px;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--on-surface);
  font-family:'Roboto Flex',system-ui,sans-serif;
  font-variation-settings:'wght' 400;
  -webkit-font-smoothing:antialiased; line-height:1.5;
}
.wrap{max-width:1200px;margin:0 auto;padding:24px 20px 80px}
header{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin:8px 0 28px}
.logo{
  width:52px;height:52px;border-radius:var(--r-m);flex:none;
  background:linear-gradient(135deg,var(--primary),var(--tertiary));
  display:grid;place-items:center;color:var(--on-primary);
  font-variation-settings:'wght' 700;font-size:24px;
}
.htext h1{margin:0;font-size:1.55rem;font-variation-settings:'wght' 600;letter-spacing:-.5px}
.htext .sub{color:var(--on-surface-var);font-size:.9rem;margin-top:2px}
.badge{
  font-size:.72rem;padding:3px 10px;border-radius:999px;
  background:var(--primary-c);color:var(--primary);
  font-variation-settings:'wght' 600;letter-spacing:.3px;text-transform:uppercase;
}
.spacer{flex:1}

/* Segmented control */
.ranges{display:inline-flex;background:var(--surface-2);border:1px solid var(--outline);
  border-radius:999px;padding:4px;gap:2px;flex-wrap:wrap}
.ranges button{
  border:0;background:transparent;color:var(--on-surface-var);
  font:inherit;font-size:.85rem;padding:7px 16px;border-radius:999px;cursor:pointer;
  transition:background .18s,color .18s;font-variation-settings:'wght' 500;
}
.ranges button:hover{color:var(--on-surface)}
.ranges button.active{background:var(--primary);color:var(--on-primary);
  font-variation-settings:'wght' 600}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.csel{background:var(--surface-2);color:var(--on-surface);border:1px solid var(--outline);
  border-radius:999px;padding:8px 16px;font:inherit;font-size:.85rem;cursor:pointer;
  font-variation-settings:'wght' 500;max-width:220px}
.csel:focus{outline:2px solid var(--primary);outline-offset:1px}

/* Tagesdetail */
.day-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 18px;margin-bottom:14px}
.day-head .date{font-size:1.15rem;font-variation-settings:'wght' 700}
.day-head .stat{font-size:.85rem;color:var(--on-surface-var)}
.day-head .stat b{color:var(--on-surface);font-variation-settings:'wght' 600}
.day-split{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}
@media(max-width:720px){.day-split{grid-template-columns:1fr}}
.day-contribs{list-style:none;margin:0;padding:0;display:grid;gap:6px;align-content:start}
.day-contribs li{display:flex;align-items:center;gap:8px;font-size:.84rem}
.day-contribs .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.day-contribs .n{font-family:'Roboto Mono',monospace;color:var(--on-surface-var)}
.day-hint{color:var(--on-surface-var);font-size:.78rem;margin-top:10px}
.cal-cell{cursor:pointer}
.cal-cell.sel{outline:2px solid var(--primary);outline-offset:1px}

/* Tabellen horizontal scrollbar auf kleinen Screens */
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch}

/* KPI cards */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:22px 0}
.kpi{background:var(--surface);border-radius:var(--r-l);padding:18px 18px 16px;
  border:1px solid #2a282f;position:relative;overflow:hidden}
.kpi::after{content:"";position:absolute;inset:0 auto 0 0;width:4px;background:var(--primary);opacity:.8}
.kpi .label{font-size:.74rem;color:var(--on-surface-var);text-transform:uppercase;letter-spacing:.6px}
.kpi .val{font-size:1.9rem;font-variation-settings:'wght' 700;margin-top:6px;letter-spacing:-1px}
.kpi .meta{font-size:.78rem;color:var(--on-surface-var);margin-top:2px}
.kpi.pos .val{color:var(--pos)} .kpi.neg .val{color:var(--neg)}

/* Card grid */
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.card{background:var(--surface);border:1px solid #2a282f;border-radius:var(--r-xl);
  padding:20px 22px;min-width:0}
.card h2{margin:0 0 2px;font-size:1.05rem;font-variation-settings:'wght' 600}
.card .desc{color:var(--on-surface-var);font-size:.82rem;margin-bottom:14px}
.col-12{grid-column:span 12}.col-8{grid-column:span 8}.col-6{grid-column:span 6}.col-4{grid-column:span 4}
@media(max-width:880px){.col-8,.col-6,.col-4{grid-column:span 12}}
.cv{position:relative;width:100%}
.h260{height:260px}.h300{height:300px}.h200{height:200px}

/* Insights */
.insights{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.insights li{display:flex;gap:12px;align-items:flex-start;background:var(--surface-2);
  border-radius:var(--r-m);padding:12px 14px;font-size:.9rem}
.insights .ic{flex:none;width:30px;height:30px;border-radius:9px;display:grid;place-items:center;
  background:var(--primary-c);color:var(--primary);font-size:15px}

/* Contribution calendar */
.cal{display:flex;gap:14px;align-items:flex-start;overflow-x:auto;padding-bottom:6px}
.cal-grid{display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,1fr);gap:3px}
.cal-cell{width:13px;height:13px;border-radius:3px;background:#2a2830}
.cal-months{display:grid;grid-auto-flow:column;font-size:.68rem;color:var(--on-surface-var);
  gap:3px;margin-bottom:4px;margin-left:26px}
.cal-days{display:grid;grid-template-rows:repeat(7,1fr);gap:3px;font-size:.62rem;
  color:var(--on-surface-var);margin-top:0}
.cal-days span{height:13px;line-height:13px}
.cal-legend{display:flex;align-items:center;gap:6px;font-size:.72rem;color:var(--on-surface-var);
  margin-top:12px;justify-content:flex-end}
.cal-legend .cal-cell{width:11px;height:11px}

/* Contributor table */
.ctable{width:100%;border-collapse:collapse;font-size:.86rem}
.ctable th,.ctable td{text-align:left;padding:8px 10px;border-bottom:1px solid #2a282f}
.ctable th{color:var(--on-surface-var);font-variation-settings:'wght' 600;font-size:.74rem;
  text-transform:uppercase;letter-spacing:.4px}
.ctable td.num{text-align:right;font-family:'Roboto Mono',monospace}
.ctable td.path{font-family:'Roboto Mono',monospace;font-size:.8rem;word-break:break-all}
.ctable .bar{height:6px;border-radius:3px;background:var(--primary);min-width:2px}
.ctable tr[data-author]:hover td{background:var(--surface-2)}
.ctable tr.rowsel td{background:var(--primary-c)}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:7px;vertical-align:middle}
.pill{font-size:.7rem;padding:2px 8px;border-radius:999px;font-variation-settings:'wght' 600;white-space:nowrap}
.pill.risk-hi{background:#5c2b2b;color:#ffb4b4}
.pill.risk-md{background:#5c4a2b;color:#ffd9a0}
.pill.risk-lo{background:#2b4a3a;color:#a0e8c0}
.couple{display:flex;flex-direction:column;gap:8px}
.couple .row{display:flex;align-items:center;gap:10px;background:var(--surface-2);
  border-radius:var(--r-m);padding:10px 12px;font-size:.82rem}
.couple .files{flex:1;min-width:0;font-family:'Roboto Mono',monospace;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.couple .files b{color:var(--primary);font-variation-settings:'wght' 600}
.couple .cnt{flex:none;background:var(--primary-c);color:var(--primary);
  border-radius:999px;padding:2px 10px;font-size:.74rem;font-variation-settings:'wght' 600}
.muted{color:var(--on-surface-var)}

footer{margin-top:40px;text-align:center;color:var(--on-surface-var);font-size:.78rem;
  border-top:1px solid #2a282f;padding-top:20px}
a{color:var(--primary)}
.empty{padding:60px 20px;text-align:center;color:var(--on-surface-var)}
.tag{font-family:'Roboto Mono',monospace;font-size:.8rem;color:var(--on-surface-var);
  word-break:break-all}

/* ---- Responsive / Mobile ---- */
@media(max-width:880px){
  header{gap:12px}
  .controls{width:100%}
  .htext{flex:1 1 auto}
}
@media(max-width:600px){
  .wrap{padding:16px 12px 60px}
  header{margin-bottom:18px}
  .logo{width:42px;height:42px;font-size:20px}
  .htext h1{font-size:1.25rem}
  .ranges{width:100%;justify-content:space-between}
  .ranges button{padding:7px 10px;font-size:.8rem;flex:1}
  .csel{max-width:none;width:100%}
  .grid{gap:14px}
  .card{padding:16px 14px;border-radius:20px}
  .kpis{grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:10px}
  .kpi{padding:14px 14px 12px}
  .kpi .val{font-size:1.5rem}
  .h300{height:240px}.h260{height:230px}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">⟳</div>
    <div class="htext">
      <h1 id="repoName">Repository</h1>
      <div class="sub"><span class="badge" id="provBadge">git</span> <span class="tag" id="repoUrl"></span></div>
    </div>
    <div class="spacer"></div>
    <div class="controls">
      <select id="contribSel" class="csel" title="Contributor filtern"></select>
      <div class="ranges" id="ranges">
        <button data-d="30">30 T</button>
        <button data-d="90">90 T</button>
        <button data-d="180">180 T</button>
        <button data-d="365">1 Jahr</button>
        <button data-d="0" class="active">Gesamt</button>
      </div>
    </div>
  </header>

  <div id="app"></div>
  <footer id="footer"></footer>
</div>

<script>
const DATA = /*__DATA__*/null;

const DAY_MS = 86400000;
const WD = ["Mo","Di","Mi","Do","Fr","Sa","So"];
const MONTHS = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
const css = (v)=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n)=> n>=1000 ? (n/1000).toFixed(n>=10000?0:1).replace(".0","")+"k" : ""+n;
const dayToDate = (d)=> new Date(d*DAY_MS);

Chart.defaults.color = css('--on-surface-var');
Chart.defaults.borderColor = '#2a282f';
Chart.defaults.font.family = "'Roboto Flex',sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.animation.duration = 500;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.boxWidth = 8;

let charts = {};
function destroy(){ Object.values(charts).forEach(c=>c&&c.destroy()); charts={}; }

// ----- Header -----
function initHeader(){
  document.getElementById('repoName').textContent = DATA.meta.name;
  document.getElementById('repoUrl').textContent = DATA.meta.url;
  const b = document.getElementById('provBadge');
  b.textContent = DATA.meta.provider==='azure' ? 'Azure DevOps'
                 : DATA.meta.provider==='github' ? 'GitHub' : 'git';
  document.getElementById('footer').innerHTML =
    `Generiert mit <b>repo2viz v${DATA.meta.version||''}</b> · ${DATA.meta.generated||''} · `+
    `<a href="${DATA.meta.url}" target="_blank" rel="noopener">${DATA.meta.url}</a>`;
}

// ----- Aggregation -----
function maxDay(){ let m=0; for(const c of DATA.commits) if(c[0]>m)m=c[0]; return m; }
const MAXDAY = DATA.commits.length ? maxDay() : Math.floor(Date.now()/DAY_MS);

function filtered(days){
  if(!days) return DATA.commits;
  const from = MAXDAY - days + 1;
  return DATA.commits.filter(c=>c[0]>=from);
}

// bucket: 'day' | 'week' | 'month'
function bucketKey(days){
  if(!days){
    const span = DATA.commits.length ? MAXDAY - Math.min(...DATA.commits.map(c=>c[0])) : 0;
    return span>730 ? 'month' : span>180 ? 'week' : 'day';
  }
  return days<=90 ? 'day' : days<=365 ? 'week' : 'month';
}
function bucketOf(day, kind){
  const dte = dayToDate(day);
  if(kind==='day') return day;
  if(kind==='week') return day - ((dte.getUTCDay()+6)%7); // auf Montag
  // month
  return Date.UTC(dte.getUTCFullYear(), dte.getUTCMonth(), 1)/DAY_MS;
}
function bucketLabel(day, kind){
  const d = dayToDate(day);
  if(kind==='month') return MONTHS[d.getUTCMonth()]+" '"+String(d.getUTCFullYear()).slice(2);
  return d.getUTCDate()+". "+MONTHS[d.getUTCMonth()];
}

// ----- Renderers -----
function renderKPIs(rows){
  const commits=rows.length;
  let ins=0,del=0; const authors=new Set(); const dayset=new Set();
  const perDay={};
  for(const c of rows){ ins+=c[4]; del+=c[5]; authors.add(c[3]); dayset.add(c[0]);
    perDay[c[0]]=(perDay[c[0]]||0)+1; }
  const activeDays=dayset.size;
  // busiest hour & weekday
  const hours=new Array(24).fill(0), wds=new Array(7).fill(0);
  for(const c of rows){ hours[c[2]]++; wds[c[1]]++; }
  const peakH=hours.indexOf(Math.max(...hours,0));
  const peakWd=wds.indexOf(Math.max(...wds,0));
  let busiest=0,busiestDay=null;
  for(const d in perDay) if(perDay[d]>busiest){busiest=perDay[d];busiestDay=+d;}
  const avg = activeDays? (commits/activeDays):0;
  // Median-Commit-Größe (Zeilen) & Conventional-Commits-Anteil
  const sizes=rows.map(c=>c[4]+c[5]).sort((a,b)=>a-b);
  const mid=sizes.length?(sizes.length%2?sizes[(sizes.length-1)/2]
    :Math.round((sizes[sizes.length/2-1]+sizes[sizes.length/2])/2)):0;
  const sonst=DATA.cats.indexOf('sonstige');
  let conv=0; for(const c of rows) if(c[6]!==sonst) conv++;
  const convPct=commits?Math.round(conv/commits*100):0;

  const cards=[
    {l:'Commits',v:fmt(commits),m:'ohne Merges'},
    {l:'Contributors',v:authors.size,m:'aktiv im Zeitraum'},
    {l:'Zeilen +',v:fmt(ins),m:'hinzugefügt',cls:'pos'},
    {l:'Zeilen −',v:fmt(del),m:'gelöscht',cls:'neg'},
    {l:'Aktive Tage',v:activeDays,m:'mit Commits'},
    {l:'Ø Commits/Tag',v:avg.toFixed(1),m:'an aktiven Tagen'},
    {l:'Median-Commit',v:fmt(mid),m:'Zeilen pro Commit'},
    {l:'Conventional',v:convPct+'%',m:'typisierte Messages'},
    {l:'Peak-Stunde',v:commits?String(peakH).padStart(2,'0')+':00':'–',m:'meiste Commits'},
    {l:'Top-Wochentag',v:commits?WD[peakWd]:'–',m:'meiste Commits'},
  ];
  return `<div class="kpis">${cards.map(c=>`
    <div class="kpi ${c.cls||''}">
      <div class="label">${c.l}</div>
      <div class="val">${c.v}</div>
      <div class="meta">${c.m||''}</div>
    </div>`).join('')}</div>`;
}

function renderInsights(rows){
  if(!rows.length) return '';
  const ins = computeInsights(rows);
  return `<div class="card col-12">
    <h2>Analyse</h2><div class="desc">Automatisch abgeleitete Beobachtungen für den gewählten Zeitraum</div>
    <ul class="insights">${ins.map(t=>`<li><span class="ic">◆</span><span>${t}</span></li>`).join('')}</ul>
  </div>`;
}

function computeInsights(rows){
  const out=[];
  const commits=rows.length;
  // Bus-Faktor
  const perAuthor={}; let ins=0,del=0;
  for(const c of rows){ perAuthor[c[3]]=(perAuthor[c[3]]||0)+1; ins+=c[4]; del+=c[5]; }
  const sorted=Object.entries(perAuthor).sort((a,b)=>b[1]-a[1]);
  let acc=0,bus=0; for(const [,n] of sorted){acc+=n;bus++; if(acc>=commits*0.5)break;}
  const topName=DATA.authors[sorted[0][0]];
  const topShare=Math.round(sorted[0][1]/commits*100);
  out.push(`<b>Bus-Faktor ${bus}</b>: ${bus} von ${sorted.length} Contributor${sorted.length!==1?'n':''} verantworten ≥ 50 % der Commits.`);
  out.push(`<b>${topName}</b> ist mit ${topShare}% der Commits am aktivsten.`);

  // Wochenende vs. Werktag
  let we=0; for(const c of rows) if(c[1]>=5) we++;
  out.push(`<b>${Math.round(we/commits*100)}%</b> der Commits entstehen am Wochenende.`);

  // Arbeitszeit-Fenster
  let office=0; for(const c of rows) if(c[2]>=9&&c[2]<18) office++;
  out.push(`<b>${Math.round(office/commits*100)}%</b> der Commits fallen in die Kernzeit (09–18 Uhr).`);

  // Churn-Verhältnis
  if(ins+del>0){
    const ratio = del? (ins/del):Infinity;
    const txt = ratio===Infinity ? 'fast ausschließlich Hinzufügungen'
      : ratio>2 ? `stark wachsend (${ratio.toFixed(1)}× mehr Zeilen hinzugefügt als gelöscht)`
      : ratio<0.5 ? 'überwiegend Aufräum-/Löscharbeit'
      : 'ausgewogen zwischen Hinzufügen und Löschen';
    out.push(`Code-Entwicklung: <b>${txt}</b> (+${fmt(ins)} / −${fmt(del)}).`);
  }

  // Trend (erste vs. zweite Hälfte des Zeitraums)
  const days=rows.map(c=>c[0]); const lo=Math.min(...days),hi=Math.max(...days);
  if(hi>lo){
    const mid=(lo+hi)/2; let a=0,b=0;
    for(const c of rows){ if(c[0]<mid)a++; else b++; }
    const trend = b>a*1.25?'steigend ↗':a>b*1.25?'rückläufig ↘':'stabil →';
    out.push(`Aktivitätstrend über den Zeitraum: <b>${trend}</b>.`);
  }

  // Längste Commit-Serie & längste Pause (aufeinanderfolgende aktive Tage)
  const uniq=[...new Set(rows.map(c=>c[0]))].sort((a,b)=>a-b);
  let streak=1,maxStreak=1,maxGap=0;
  for(let i=1;i<uniq.length;i++){
    const diff=uniq[i]-uniq[i-1];
    if(diff===1){ streak++; if(streak>maxStreak)maxStreak=streak; }
    else { streak=1; if(diff-1>maxGap)maxGap=diff-1; }
  }
  if(uniq.length>1)
    out.push(`Längste Commit-Serie: <b>${maxStreak} Tag${maxStreak!==1?'e':''}</b> in Folge · längste Pause: <b>${maxGap} Tag${maxGap!==1?'e':''}</b>.`);

  return out;
}

function renderTimeline(rows, days){
  const kind=bucketKey(days);
  const m={};
  for(const c of rows){ const k=bucketOf(c[0],kind); m[k]=(m[k]||0)+1; }
  let keys=Object.keys(m).map(Number).sort((a,b)=>a-b);
  // Lücken auffüllen für saubere Linie
  if(keys.length>1){
    const step = kind==='day'?1:kind==='week'?7:null;
    if(step){
      const full=[]; for(let d=keys[0];d<=keys[keys.length-1];d+=step) full.push(d);
      keys=full;
    }
  }
  const vals=keys.map(k=>m[k]||0);
  // gleitender Durchschnitt
  const win = kind==='day'?7:kind==='week'?4:3;
  const ma=vals.map((_,i)=>{const s=Math.max(0,i-win+1);const seg=vals.slice(s,i+1);
    return seg.reduce((a,b)=>a+b,0)/seg.length;});
  const labels=keys.map(k=>bucketLabel(k,kind));

  // Release-Tags auf die passenden Buckets abbilden (pro Bucket nur eine Linie,
  // damit tag-reiche Repos die Timeline nicht zukleistern)
  const annotations={};
  if(DATA.tags && DATA.tags.length && keys.length){
    const lo=keys[0], hi=keys[keys.length-1];
    const idxOf=(d)=>{ const b=bucketOf(d,kind); let best=-1,bd=1e9;
      for(let i=0;i<keys.length;i++){const dd=Math.abs(keys[i]-b); if(dd<bd){bd=dd;best=i;}}
      return best; };
    const inRange=DATA.tags.filter(t=>t[1]>=lo-7 && t[1]<=hi+31);
    // pro Bucket-Index gruppieren: jüngsten Tag-Namen + Anzahl behalten
    const byIdx=new Map();
    for(const t of inRange){ const idx=idxOf(t[1]); if(idx<0) continue;
      const e=byIdx.get(idx); if(e){ e.n++; if(t[1]>=e.day){e.day=t[1];e.name=t[0];} }
      else byIdx.set(idx,{name:t[0],day:t[1],n:1}); }
    // nur die jüngsten ~10 Bucket-Marker beschriften (sonst Label-Wust)
    const sortedIdx=[...byIdx.keys()].sort((a,b)=>a-b);
    const labelSet=new Set(sortedIdx.slice(-10));
    for(const idx of sortedIdx){ const e=byIdx.get(idx);
      const content=e.n>1?`${e.name} +${e.n-1}`:e.name;
      annotations['tag'+idx]={type:'line',xMin:idx,xMax:idx,
        borderColor:'rgba(239,184,200,.5)',borderWidth:1,borderDash:[3,3],
        label:{display:labelSet.has(idx),content,position:'start',rotation:90,
          backgroundColor:'rgba(45,41,48,.92)',color:css('--tertiary'),
          font:{size:9},padding:3,yAdjust:2}};
    }
  }

  const ctx=document.getElementById('cvTimeline');
  const grad=ctx.getContext('2d').createLinearGradient(0,0,0,260);
  grad.addColorStop(0,'rgba(208,188,255,.35)'); grad.addColorStop(1,'rgba(208,188,255,0)');
  charts.tl=new Chart(ctx,{type:'line',data:{labels,datasets:[
    {label:'Commits',data:vals,borderColor:css('--primary'),backgroundColor:grad,
     fill:true,tension:.35,pointRadius:0,borderWidth:2},
    {label:'Gleitender Ø',data:ma,borderColor:css('--tertiary'),borderDash:[5,4],
     fill:false,tension:.4,pointRadius:0,borderWidth:1.5},
  ]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkipPadding:18}},
      y:{beginAtZero:true,grid:{color:'#262430'}}},
    plugins:{legend:{position:'top',align:'end'},annotation:{annotations}}}});
}

function renderChurn(rows, days){
  const kind=bucketKey(days);
  const mi={},md={};
  for(const c of rows){ const k=bucketOf(c[0],kind); mi[k]=(mi[k]||0)+c[4]; md[k]=(md[k]||0)+c[5]; }
  const keys=Object.keys(mi).map(Number).sort((a,b)=>a-b);
  const labels=keys.map(k=>bucketLabel(k,kind));
  const ctx=document.getElementById('cvChurn');
  charts.churn=new Chart(ctx,{type:'bar',data:{labels,datasets:[
    {label:'Hinzugefügt',data:keys.map(k=>mi[k]),backgroundColor:'rgba(125,223,160,.85)',
     stack:'s',borderRadius:3},
    {label:'Gelöscht',data:keys.map(k=>-md[k]),backgroundColor:'rgba(255,155,155,.85)',
     stack:'s',borderRadius:3},
  ]},options:{responsive:true,maintainAspectRatio:false,
    scales:{x:{stacked:true,grid:{display:false},ticks:{maxRotation:0,autoSkipPadding:18}},
      y:{stacked:true,grid:{color:'#262430'},ticks:{callback:v=>fmt(Math.abs(v))}}},
    plugins:{tooltip:{callbacks:{label:c=>c.dataset.label+': '+fmt(Math.abs(c.parsed.y))}},
      legend:{position:'top',align:'end'}}}});
}

function renderHeatmap(rows){
  // 7 (Wochentag) x 24 (Stunde)
  const grid=Array.from({length:7},()=>new Array(24).fill(0));
  let mx=0;
  for(const c of rows){ grid[c[1]][c[2]]++; if(grid[c[1]][c[2]]>mx)mx=grid[c[1]][c[2]]; }
  const points=[];
  for(let w=0;w<7;w++)for(let h=0;h<24;h++) points.push({x:h,y:w,v:grid[w][h]});
  const ctx=document.getElementById('cvHeat');
  charts.heat=new Chart(ctx,{type:'matrix',data:{datasets:[{
    label:'Commits',data:points,
    backgroundColor:c=>{const v=c.raw.v; if(!v)return '#232128';
      const t=Math.pow(v/(mx||1),.6);
      return `rgba(208,188,255,${.12+t*.88})`;},
    borderColor:'transparent',
    width:(c)=>{const a=c.chart.chartArea||{}; return (a.width||0)/24-2;},
    height:(c)=>{const a=c.chart.chartArea||{}; return (a.height||0)/7-2;},
  }]},options:{responsive:true,maintainAspectRatio:false,
    scales:{x:{type:'linear',min:-.5,max:23.5,offset:false,grid:{display:false},
      ticks:{stepSize:2,callback:v=>String(v).padStart(2,'0')},title:{display:true,text:'Stunde (Autor-lokal)'}},
      y:{type:'linear',min:-.5,max:6.5,reverse:true,grid:{display:false},
      ticks:{stepSize:1,callback:v=>WD[v]||''}}},
    plugins:{legend:{display:false},
      tooltip:{callbacks:{title:()=>'', label:c=>`${WD[c.raw.y]} ${String(c.raw.x).padStart(2,'0')}:00 — ${c.raw.v} Commits`}}}}});
}

function renderContributors(rows){
  const per={};
  for(const c of rows){ const a=per[c[3]]||(per[c[3]]={c:0,i:0,d:0}); a.c++;a.i+=c[4];a.d+=c[5]; }
  let arr=Object.entries(per).map(([k,v])=>({name:DATA.authors[k],idx:+k,...v}))
    .sort((a,b)=>b.c-a.c);
  const total=rows.length;
  const palette=['#d0bcff','#efb8c8','#7dd3c0','#ffd8a8','#a5b4ff','#f6a6c1','#9ae6b4','#c4b5fd'];
  const top=arr.slice(0,8);
  const rest=arr.slice(8).reduce((s,a)=>s+a.c,0);

  // Doughnut
  const dctx=document.getElementById('cvContrib');
  const labels=top.map(a=>a.name).concat(rest?['Übrige']:[]);
  const dvals=top.map(a=>a.c).concat(rest?[rest]:[]);
  const colors=top.map((_,i)=>palette[i%palette.length]).concat(rest?['#4a4754']:[]);
  charts.contrib=new Chart(dctx,{type:'doughnut',data:{labels,datasets:[{data:dvals,
    backgroundColor:colors,borderColor:css('--surface'),borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:'62%',
      plugins:{legend:{position:'right',labels:{boxWidth:8,padding:8}}}}});

  // Tabelle (Klick auf Zeile filtert das Dashboard auf die Person)
  const maxc=arr[0]?arr[0].c:1;
  const body=arr.slice(0,15).map((a,i)=>`<tr data-author="${a.idx}" style="cursor:pointer"
      class="${curAuthor===a.idx?'rowsel':''}" title="Auf ${a.name} filtern">
    <td><span class="dot" style="background:${palette[i%palette.length]}"></span>${a.name}</td>
    <td class="num">${a.c}</td>
    <td class="num">${Math.round(a.c/total*100)}%</td>
    <td class="num" style="color:var(--pos)">+${fmt(a.i)}</td>
    <td class="num" style="color:var(--neg)">−${fmt(a.d)}</td>
    <td style="width:120px"><div class="bar" style="width:${Math.max(4,a.c/maxc*100)}%"></div></td>
  </tr>`).join('');
  const tb=document.getElementById('ctableBody');
  tb.innerHTML=body;
  tb.onclick=(e)=>{const tr=e.target.closest('tr[data-author]'); if(!tr)return;
    const idx=+tr.dataset.author; setAuthor(curAuthor===idx?null:idx);};
}

function renderCalendar(){
  // Letzte 53 Wochen, fix (unabhängig vom Range-Toggle, aber Contributor-gefiltert)
  const cont={};
  for(const c of authorFilter(DATA.commits)) cont[c[0]]=(cont[c[0]]||0)+1;
  const end=MAXDAY;
  const endDate=dayToDate(end);
  const endWd=(endDate.getUTCDay()+6)%7; // Mo=0
  const lastSun=end+(6-endWd);
  const start=lastSun-53*7+1;
  let mx=0; for(let d=start;d<=lastSun;d++) if((cont[d]||0)>mx)mx=cont[d]||0;
  const lvl=(v)=>{ if(!v)return 0; const t=v/(mx||1);
    return t>.66?4:t>.33?3:t>.12?2:1; };
  const colors=['#2a2830','#27543e','#2f8f5b','#54c98a','#9af0bf'];

  // Monats-Labels
  let cells='',months='',lastM=-1,weeks=0;
  for(let d=start;d<=lastSun;d+=7){ weeks++;
    const mo=dayToDate(d).getUTCMonth();
    months+=`<span>${mo!==lastM?MONTHS[mo]:''}</span>`; lastM=mo;
  }
  for(let d=start;d<=lastSun;d++){
    const v=cont[d]||0; const future=d>end;
    cells+=`<div class="cal-cell" data-day="${d}" title="${dayToDate(d).toISOString().slice(0,10)}: ${v} Commits" style="background:${future?'transparent':colors[lvl(v)]}"></div>`;
  }
  document.getElementById('calMonths').innerHTML=months;
  document.getElementById('calMonths').style.gridTemplateColumns=`repeat(${weeks},13px)`;
  const g=document.getElementById('calGrid'); g.innerHTML=cells;
  g.onclick=(e)=>{const cell=e.target.closest('.cal-cell[data-day]'); if(!cell)return;
    const d=+cell.dataset.day; selectedDay=d; renderDayDetail(d);};
  document.getElementById('calLegend').innerHTML='Weniger '+
    colors.map(c=>`<span class="cal-cell" style="background:${c};cursor:default"></span>`).join('')+' Mehr';
}

function renderFiles(){
  // Top-Dateien (Bar) + Dateitypen (Doughnut) — gesamtbezogen
  const tf=DATA.topFiles;
  const fctx=document.getElementById('cvFiles');
  charts.files=new Chart(fctx,{type:'bar',data:{
    labels:tf.map(f=>f[0].length>34?'…'+f[0].slice(-33):f[0]),
    datasets:[{label:'Änderungen (Commits)',data:tf.map(f=>f[1]),
      backgroundColor:'rgba(208,188,255,.85)',borderRadius:4}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{color:'#262430'}},y:{grid:{display:false},ticks:{font:{size:10}}}},
      plugins:{legend:{display:false},
        tooltip:{callbacks:{afterLabel:c=>{const f=tf[c.dataIndex];
          return `+${fmt(f[2])} / −${fmt(f[3])} Zeilen`;}}}}}});

  const te=DATA.topExts;
  const palette=['#d0bcff','#efb8c8','#7dd3c0','#ffd8a8','#a5b4ff','#f6a6c1','#9ae6b4','#c4b5fd','#fbbf24','#fb7185','#34d399','#818cf8'];
  const ectx=document.getElementById('cvExts');
  charts.exts=new Chart(ectx,{type:'doughnut',data:{
    labels:te.map(e=>'.'+e[0]),datasets:[{data:te.map(e=>e[2]+e[3]),
      backgroundColor:te.map((_,i)=>palette[i%palette.length]),
      borderColor:css('--surface'),borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:'58%',
      plugins:{legend:{position:'right',labels:{boxWidth:8,padding:6,font:{size:10}}},
        tooltip:{callbacks:{label:c=>`${c.label}: ${fmt(c.parsed)} Zeilen Churn`}}}}});
}

const CAT_COLORS={feat:'#7ddfa0',fix:'#ff9b9b',docs:'#a5b4ff',style:'#c4b5fd',
  refactor:'#efb8c8',perf:'#fbbf24',test:'#7dd3c0',build:'#ffd8a8',ci:'#9ae6b4',
  chore:'#cac4d0',revert:'#fb7185',sonstige:'#4a4754'};

function renderCommitTypes(rows){
  const counts=new Array(DATA.cats.length).fill(0);
  for(const c of rows) counts[c[6]]++;
  const items=DATA.cats.map((name,i)=>({name,n:counts[i]})).filter(x=>x.n>0)
    .sort((a,b)=>b.n-a.n);
  const ctx=document.getElementById('cvTypes');
  charts.types=new Chart(ctx,{type:'doughnut',data:{
    labels:items.map(x=>x.name),datasets:[{data:items.map(x=>x.n),
      backgroundColor:items.map(x=>CAT_COLORS[x.name]||'#4a4754'),
      borderColor:css('--surface'),borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:'58%',
      plugins:{legend:{position:'right',labels:{boxWidth:8,padding:6,font:{size:10}}},
        tooltip:{callbacks:{label:c=>`${c.label}: ${c.parsed} Commits`}}}}});
}

function renderCommitSizes(rows){
  // Histogramm nach Zeilen pro Commit
  const buckets=[[0,'0'],[1,'1–9'],[10,'10–49'],[50,'50–199'],[200,'200–499'],[500,'500+']];
  const counts=new Array(buckets.length).fill(0);
  for(const c of rows){ const s=c[4]+c[5]; let bi=0;
    for(let i=0;i<buckets.length;i++) if(s>=buckets[i][0]) bi=i;
    counts[bi]++; }
  const ctx=document.getElementById('cvSizes');
  charts.sizes=new Chart(ctx,{type:'bar',data:{labels:buckets.map(b=>b[1]),
    datasets:[{label:'Commits',data:counts,backgroundColor:'rgba(208,188,255,.85)',
      borderRadius:4}]},
    options:{responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{display:false},title:{display:true,text:'Zeilen pro Commit'}},
        y:{beginAtZero:true,grid:{color:'#262430'}}},
      plugins:{legend:{display:false}}}});
}

function renderGrowth(rows, days){
  // kumulative Netto-Zeilen (add − del) über Zeit
  const kind=bucketKey(days);
  const m={};
  for(const c of rows){ const k=bucketOf(c[0],kind); m[k]=(m[k]||0)+c[4]-c[5]; }
  const keys=Object.keys(m).map(Number).sort((a,b)=>a-b);
  let run=0; const cum=keys.map(k=>run+=m[k]);
  const labels=keys.map(k=>bucketLabel(k,kind));
  const ctx=document.getElementById('cvGrowth');
  const grad=ctx.getContext('2d').createLinearGradient(0,0,0,260);
  grad.addColorStop(0,'rgba(125,211,192,.35)'); grad.addColorStop(1,'rgba(125,211,192,0)');
  charts.growth=new Chart(ctx,{type:'line',data:{labels,datasets:[
    {label:'Netto-Zeilen (kumuliert)',data:cum,borderColor:css('--accent'),
     backgroundColor:grad,fill:true,tension:.3,pointRadius:0,borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkipPadding:18}},
        y:{grid:{color:'#262430'},ticks:{callback:v=>fmt(v)}}},
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>'≈ '+fmt(c.parsed.y)+' Zeilen Netto'}}}}});
}

function renderLifespan(){
  // Gantt: erste→letzte Aktivität je Contributor (zeitraumunabhängig, Top nach Commits)
  const per={};
  for(const c of DATA.commits){ const a=per[c[3]]||(per[c[3]]={n:0,min:c[0],max:c[0]});
    a.n++; if(c[0]<a.min)a.min=c[0]; if(c[0]>a.max)a.max=c[0]; }
  let arr=Object.entries(per).map(([k,v])=>({name:DATA.authors[k],...v}))
    .sort((a,b)=>b.n-a.n).slice(0,12).reverse();
  const ctx=document.getElementById('cvLifespan');
  charts.life=new Chart(ctx,{type:'bar',data:{labels:arr.map(a=>a.name),
    datasets:[{label:'Aktiv von–bis',data:arr.map(a=>[a.min,a.max+1]),
      backgroundColor:'rgba(208,188,255,.75)',borderRadius:5,barThickness:13}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{color:'#262430'},
        ticks:{callback:v=>{const d=dayToDate(v);return MONTHS[d.getUTCMonth()]+" '"+String(d.getUTCFullYear()).slice(2);}}},
        y:{grid:{display:false},ticks:{font:{size:10}}}},
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>{const a=arr[c.dataIndex];
          const f=dayToDate(a.min).toISOString().slice(0,10), l=dayToDate(a.max).toISOString().slice(0,10);
          return `${f} → ${l} · ${a.n} Commits`;}}}}}});
}

function renderHotspots(){
  const hs=DATA.hotspots;
  const risk=(na)=> na===1?['Wissensrisiko','risk-hi']: na===2?['konzentriert','risk-md']:['verteilt','risk-lo'];
  const body=hs.map(h=>{const[p,ch,na,is,dl]=h; const[txt,cls]=risk(na);
    return `<tr>
      <td class="path">${p.length>46?'…'+p.slice(-45):p}</td>
      <td class="num">${ch}</td>
      <td class="num">${na}</td>
      <td><span class="pill ${cls}">${txt}</span></td>
      <td class="num"><span class="muted" style="color:var(--pos)">+${fmt(is)}</span> / <span style="color:var(--neg)">−${fmt(dl)}</span></td>
    </tr>`;}).join('');
  document.getElementById('hotBody').innerHTML=body||'<tr><td colspan="5" class="muted">Keine Datei mit ≥ 3 Änderungen.</td></tr>';
}

function renderDirBus(){
  const db=DATA.dirBus;
  const ctx=document.getElementById('cvDirBus');
  charts.dirbus=new Chart(ctx,{type:'bar',data:{
    labels:db.map(d=>d[0]),
    datasets:[
      {label:'Commits',data:db.map(d=>d[1]),backgroundColor:'rgba(208,188,255,.85)',
       borderRadius:4,yAxisID:'y'},
      {label:'Contributors',data:db.map(d=>d[3]),backgroundColor:'rgba(125,211,192,.9)',
       borderRadius:4,yAxisID:'y1',type:'bar'},
    ]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{color:'#262430'}},y:{grid:{display:false},ticks:{font:{size:10}}},
        y1:{display:false}},
      plugins:{legend:{position:'top',align:'end'},
        tooltip:{callbacks:{afterBody:items=>{const i=items[0].dataIndex;const d=db[i];
          return `${d[3]} Contributor${d[3]!==1?'s':''} · ${fmt(d[2])} Zeilen Churn`;}}}}}});
}

function renderCoupling(){
  const cp=DATA.coupling;
  const base=(p)=>p.split('/').pop();
  const html=cp.length? cp.map(c=>`<div class="row">
    <span class="files" title="${c[0]}  ↔  ${c[1]}"><b>${base(c[0])}</b> ↔ <b>${base(c[1])}</b></span>
    <span class="cnt">${c[2]}×</span></div>`).join('')
    : '<div class="muted">Keine nennenswerte Kopplung (≥ 3 gemeinsame Commits) gefunden.</div>';
  document.getElementById('coupleBox').innerHTML=html;
}

function renderClock(rows){
  // Radiales 24h-Zifferblatt: Commit-Volumen je Stunde (Stoßzeiten)
  const hours=new Array(24).fill(0);
  for(const c of rows) hours[c[2]]++;
  const mx=Math.max(...hours,1);
  const ctx=document.getElementById('cvClock');
  charts.clock=new Chart(ctx,{type:'polarArea',data:{
    labels:hours.map((_,h)=>String(h).padStart(2,'0')),
    datasets:[{data:hours,
      backgroundColor:hours.map(v=>{const t=Math.pow(v/mx,.65);
        return `rgba(208,188,255,${.1+t*.85})`;}),
      borderColor:'rgba(20,18,24,.6)',borderWidth:1}]},
    options:{responsive:true,maintainAspectRatio:false,
      scales:{r:{grid:{color:'#2a282f'},angleLines:{color:'#2a282f'},
        ticks:{display:false,backdropColor:'transparent'},
        pointLabels:{display:true,centerPointLabels:true,font:{size:9}}}},
      plugins:{legend:{display:false},
        tooltip:{callbacks:{title:items=>items[0].label+':00 Uhr',
          label:c=>`${c.parsed.r} Commits`}}}}});
}

function dayCommits(day){ return curRows.filter(c=>c[0]===day); }
function busiestDay(rows){
  const per={}; let best=null,mx=-1;
  for(const c of rows){ const n=(per[c[0]]=(per[c[0]]||0)+1); if(n>mx){mx=n;best=c[0];} }
  return best;
}

function renderDayDetail(day){
  const host=document.getElementById('dayDetail');
  if(day==null){ host.innerHTML='<div class="muted">Keine Daten im gewählten Zeitraum.</div>'; return; }
  const cs=dayCommits(day);
  let ins=0,del=0; const hours=new Array(24).fill(0); const per={};
  for(const c of cs){ ins+=c[4]; del+=c[5]; hours[c[2]]++; per[c[3]]=(per[c[3]]||0)+1; }
  const peakH=hours.indexOf(Math.max(...hours,0));
  const dstr=dayToDate(day).toISOString().slice(0,10);
  const wd=WD[(dayToDate(day).getUTCDay()+6)%7];
  const contribs=Object.entries(per).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const palette=['#d0bcff','#efb8c8','#7dd3c0','#ffd8a8','#a5b4ff','#f6a6c1','#9ae6b4','#c4b5fd'];

  host.innerHTML=`
    <div class="day-head">
      <span class="date">${wd}, ${dstr}</span>
      <span class="stat"><b>${cs.length}</b> Commits</span>
      <span class="stat" style="color:var(--pos)"><b>+${fmt(ins)}</b></span>
      <span class="stat" style="color:var(--neg)"><b>−${fmt(del)}</b></span>
      <span class="stat">Stoßzeit <b>${cs.length?String(peakH).padStart(2,'0')+':00':'–'}</b></span>
    </div>
    <div class="day-split">
      <div class="cv h200"><canvas id="cvDayHours"></canvas></div>
      <ul class="day-contribs">${contribs.map(([a,n],i)=>
        `<li><span class="dot" style="background:${palette[i%palette.length]}"></span>
          <span class="nm">${DATA.authors[a]}</span><span class="n">${n}</span></li>`).join('')
          || '<li class="muted">—</li>'}</ul>
    </div>
    <div class="day-hint">Tipp: Klick auf eine Zelle im Contribution-Kalender unten wählt einen anderen Tag.</div>`;

  charts.dayhours=new Chart(document.getElementById('cvDayHours'),{type:'bar',
    data:{labels:hours.map((_,h)=>String(h).padStart(2,'0')),
      datasets:[{label:'Commits',data:hours,backgroundColor:'rgba(208,188,255,.85)',borderRadius:2}]},
    options:{responsive:true,maintainAspectRatio:false,
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:12},
        title:{display:true,text:'Stunde'}},y:{beginAtZero:true,grid:{color:'#262430'},
        ticks:{precision:0}}},
      plugins:{legend:{display:false}}}});

  // Markierung im Kalender aktualisieren
  document.querySelectorAll('.cal-cell.sel').forEach(e=>e.classList.remove('sel'));
  const cell=document.querySelector(`.cal-cell[data-day="${day}"]`);
  if(cell) cell.classList.add('sel');
}

// ----- Layout -----
function gridHTML(){
  return `
  <div id="insightSlot"></div>
  <div class="card col-12">
    <h2>Commit-Aktivität</h2><div class="desc">Commits pro Zeiteinheit mit gleitendem Durchschnitt</div>
    <div class="cv h300"><canvas id="cvTimeline"></canvas></div>
  </div>

  <div class="card col-8">
    <h2>Aktivitäts-Heatmap</h2><div class="desc">Wochentag × Tageszeit — wann wird committet?</div>
    <div class="cv h260"><canvas id="cvHeat"></canvas></div>
  </div>
  <div class="card col-4">
    <h2>Contributor-Anteil</h2><div class="desc">Verteilung der Commits</div>
    <div class="cv h260"><canvas id="cvContrib"></canvas></div>
  </div>

  <div class="card col-12">
    <h2>Code-Churn</h2><div class="desc">Hinzugefügte (▲) und gelöschte (▼) Zeilen pro Zeiteinheit</div>
    <div class="cv h260"><canvas id="cvChurn"></canvas></div>
  </div>

  <div class="card col-12">
    <h2>Wachstum</h2><div class="desc">Kumulierte Netto-Zeilen (hinzugefügt − gelöscht) — grobe Codebase-Größe über Zeit</div>
    <div class="cv h260"><canvas id="cvGrowth"></canvas></div>
  </div>

  <div class="card col-6">
    <h2>Commit-Typen</h2><div class="desc">Conventional-Commit-Kategorien aus der Message (z. B. feat/fix/docs)</div>
    <div class="cv h260"><canvas id="cvTypes"></canvas></div>
  </div>
  <div class="card col-6">
    <h2>Commit-Größen</h2><div class="desc">Verteilung der geänderten Zeilen pro Commit</div>
    <div class="cv h260"><canvas id="cvSizes"></canvas></div>
  </div>

  <div class="card col-4">
    <h2>Stoßzeiten</h2><div class="desc">Commit-Volumen je Tageszeit als 24h-Zifferblatt</div>
    <div class="cv h260"><canvas id="cvClock"></canvas></div>
  </div>
  <div class="card col-8">
    <h2>Tagesdetail</h2><div class="desc">Stundenverteilung & Beteiligte eines einzelnen Tages</div>
    <div id="dayDetail"></div>
  </div>

  <div class="card col-12">
    <h2>Contribution-Kalender</h2><div class="desc">Tägliche Commits der letzten 12 Monate (zeitraumunabhängig) — Klick wählt den Tag im Detail oben</div>
    <div class="cal">
      <div class="cal-days"><span>Mo</span><span></span><span>Mi</span><span></span><span>Fr</span><span></span><span>So</span></div>
      <div>
        <div class="cal-months" id="calMonths"></div>
        <div class="cal-grid" id="calGrid"></div>
      </div>
    </div>
    <div class="cal-legend" id="calLegend"></div>
  </div>

  <div class="card col-12">
    <h2>Top-Contributors</h2><div class="desc">Commits, Anteil und Code-Churn pro Person (im Zeitraum) — Klick auf eine Zeile filtert das gesamte Dashboard</div>
    <div class="tscroll"><table class="ctable"><thead><tr>
      <th>Contributor</th><th class="num">Commits</th><th class="num">Anteil</th>
      <th class="num">Zeilen +</th><th class="num">Zeilen −</th><th></th>
    </tr></thead><tbody id="ctableBody"></tbody></table></div>
  </div>

  <div class="card col-8">
    <h2>Meist geänderte Dateien</h2><div class="desc">Nach Anzahl der Commits, die die Datei berühren (gesamt)</div>
    <div class="cv h300"><canvas id="cvFiles"></canvas></div>
  </div>
  <div class="card col-4">
    <h2>Dateitypen</h2><div class="desc">Churn-Anteil nach Endung (gesamt)</div>
    <div class="cv h300"><canvas id="cvExts"></canvas></div>
  </div>

  <div class="card col-12">
    <h2>Hotspots & Wissensrisiko</h2><div class="desc">Häufig geänderte Dateien mit wenigen Autoren — Kandidaten für Refactoring & Bus-Faktor-Risiko (gesamt)</div>
    <div class="tscroll"><table class="ctable"><thead><tr>
      <th>Datei</th><th class="num">Änderungen</th><th class="num">Autoren</th>
      <th>Risiko</th><th class="num">Churn (+/−)</th>
    </tr></thead><tbody id="hotBody"></tbody></table></div>
  </div>

  <div class="card col-6">
    <h2>Verzeichnis-Bus-Faktor</h2><div class="desc">Commits und Anzahl Contributors je Top-Verzeichnis — wo hängt Wissen an wenigen? (gesamt)</div>
    <div class="cv h300"><canvas id="cvDirBus"></canvas></div>
  </div>
  <div class="card col-6">
    <h2>Co-Change-Kopplung</h2><div class="desc">Dateien, die häufig im selben Commit geändert werden — impliziter Architektur-Zusammenhang (gesamt)</div>
    <div class="couple" id="coupleBox"></div>
  </div>

  <div class="card col-12">
    <h2>Contributor-Lebensdauer</h2><div class="desc">Erste bis letzte Aktivität je Contributor (Top 12 nach Commits, gesamt)</div>
    <div class="cv h300"><canvas id="cvLifespan"></canvas></div>
  </div>`;
}

let curDays=0, curAuthor=null, selectedDay=null, curRows=[];
function authorFilter(rows){ return curAuthor==null ? rows : rows.filter(c=>c[3]===curAuthor); }

function render(days){
  curDays=days;
  destroy();
  const app=document.getElementById('app');
  if(!DATA.commits.length){
    app.innerHTML='<div class="empty"><h2>Keine Commit-Daten gefunden</h2><p>Das Repository enthält keine analysierbare Historie.</p></div>';
    return;
  }
  const rows=filtered(days);            // nur Zeitraum (für Contributor-Übersicht)
  const arows=authorFilter(rows);       // Zeitraum + Contributor
  curRows=arows;
  if(!arows.length){
    const who=curAuthor!=null?` für <b>${DATA.authors[curAuthor]}</b>`:'';
    app.innerHTML=`<div class="empty"><h2>Keine Aktivität im gewählten Zeitraum${who}</h2><p>Versuche einen größeren Zeitraum oder einen anderen Contributor.</p></div>`;
    return;
  }
  app.innerHTML = `<div id="kpiSlot"></div><div class="grid">${gridHTML()}</div>`;
  document.getElementById('kpiSlot').innerHTML = renderKPIs(arows);
  document.getElementById('insightSlot').outerHTML = renderInsights(arows);
  renderTimeline(arows,days);
  renderHeatmap(arows);
  renderClock(arows);
  renderContributors(rows);             // immer alle (Klick-zum-Filtern)
  renderChurn(arows,days);
  renderGrowth(arows,days);
  renderCommitTypes(arows);
  renderCommitSizes(arows);
  renderCalendar();
  selectedDay = busiestDay(arows);
  renderDayDetail(selectedDay);
  renderFiles();
  renderHotspots();
  renderDirBus();
  renderCoupling();
  renderLifespan();
}

function setAuthor(idx){
  curAuthor = idx;
  const sel=document.getElementById('contribSel');
  if(sel) sel.value = idx==null ? '' : String(idx);
  render(curDays);
}

function initRanges(){
  document.getElementById('ranges').addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b)return;
    [...e.currentTarget.children].forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    render(+b.dataset.d);
  });
}

function initContribSel(){
  const sel=document.getElementById('contribSel');
  // Autoren nach Gesamt-Commits sortieren
  const cnt={}; for(const c of DATA.commits) cnt[c[3]]=(cnt[c[3]]||0)+1;
  const order=Object.keys(cnt).map(Number).sort((a,b)=>cnt[b]-cnt[a]);
  let html='<option value="">Alle Contributors ('+DATA.authors.length+')</option>';
  for(const idx of order)
    html+=`<option value="${idx}">${DATA.authors[idx]} · ${cnt[idx]}</option>`;
  sel.innerHTML=html;
  sel.addEventListener('change',()=>setAuthor(sel.value===''?null:+sel.value));
}

initHeader();
initRanges();
initContribSel();
render(0);
</script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description="Erzeugt aus einer GitHub-/Azure-DevOps-Repo-URL eine HTML-Aktivitätsvisualisierung.")
    ap.add_argument("url", help="Repository-URL (GitHub oder Azure DevOps)")
    ap.add_argument("-o", "--output", help="Ziel-HTML-Datei")
    ap.add_argument("--token", help="Auth-Token/PAT für private Repos (sonst aus Env)")
    ap.add_argument("--keep-clone", action="store_true", help="Temporären Clone nicht löschen")
    ap.add_argument("--version", action="version", version=f"repo2viz {__version__}")
    args = ap.parse_args()

    provider = detect_provider(args.url)
    token = resolve_token(provider, args.token)
    clone_url = build_clone_url(args.url, provider, token)
    name = repo_display_name(args.url)

    print(f"Repository : {name}")
    print(f"Provider   : {provider}{'  (Token aktiv)' if token else ''}")

    tmp = tempfile.mkdtemp(prefix="repo2viz-")
    repo_dir = os.path.join(tmp, "repo.git")
    try:
        clone_repo(clone_url, repo_dir)
        print("  -> Analysiere git-Historie ...", flush=True)
        raw = git_log(repo_dir)
        data = parse_log(raw)
        data["tags"] = git_tags(repo_dir)
        if not data["commits"]:
            print("WARNUNG: Keine Commits gefunden.", file=sys.stderr)
        meta = {
            "name": name,
            "url": args.url,
            "provider": provider,
            "merges": False,
            "version": __version__,
            "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        html = build_html(data, meta)
    finally:
        if args.keep_clone:
            print(f"  -> Clone behalten: {repo_dir}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    out = args.output or re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") + "-activity.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    n_commits = len(data["commits"])
    n_authors = len(data["authors"])
    n_tags = len(data.get("tags", []))
    print(f"  -> {n_commits} Commits · {n_authors} Contributors · {n_tags} Tags")
    print(f"\n✓ HTML erzeugt: {os.path.abspath(out)}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\nFEHLER: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
