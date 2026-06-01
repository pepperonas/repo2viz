#!/usr/bin/env python3
"""
repo2viz GUI
============

Grafische Oberfläche (PySide6 / Qt 6) für repo2viz im Material-3-Dark-Design.
Nimmt eine GitHub-/Azure-DevOps-URL entgegen und erzeugt per Klick die
interaktive HTML-Aktivitätsvisualisierung.

Start:
    python3 repo2viz_gui.py

Benötigt PySide6 (`pip install PySide6`) sowie `git` im PATH. Die eigentliche
Report-Logik kommt aus dem Modul `repo2viz` (generate_report).
"""

import os
import sys
import webbrowser

from PySide6.QtCore import Qt, QObject, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QPainter, QColor, QBrush
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QPlainTextEdit, QProgressBar, QFrame,
    QFileDialog, QSizePolicy,
)

import repo2viz as core


# --------------------------------------------------------------------------- #
#  Material-3-Dark-Stylesheet (passend zum HTML-Output)
# --------------------------------------------------------------------------- #
QSS = """
* { font-family: 'Roboto', 'Segoe UI', 'Helvetica Neue', sans-serif; }
QWidget#root { background: #141218; }
QLabel { color: #e6e0e9; background: transparent; }
QLabel#title { font-size: 22px; font-weight: 700; color: #e6e0e9; }
QLabel#subtitle { font-size: 12px; color: #cac4d0; }
QLabel#logo {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d0bcff, stop:1 #efb8c8);
    color: #381e72; border-radius: 14px; font-size: 24px; font-weight: 700;
}
QLabel#badge {
    background: #4f378b; color: #d0bcff; border-radius: 10px;
    padding: 3px 12px; font-size: 11px; font-weight: 600;
}
QLabel#fieldlabel { font-size: 12px; color: #cac4d0; font-weight: 600; }

QFrame#card {
    background: #1d1b20; border: 1px solid #2a282f; border-radius: 20px;
}

QLineEdit {
    background: #211f26; border: 1px solid #49454f; border-radius: 12px;
    padding: 10px 14px; color: #e6e0e9; font-size: 13px;
    selection-background-color: #4f378b; selection-color: #ffffff;
}
QLineEdit:focus { border: 1px solid #d0bcff; }
QLineEdit:disabled { color: #8a8595; }

QPushButton#primary {
    background: #d0bcff; color: #381e72; border: none; border-radius: 20px;
    padding: 11px 24px; font-size: 13px; font-weight: 700;
}
QPushButton#primary:hover { background: #e9ddff; }
QPushButton#primary:pressed { background: #c0a9f5; }
QPushButton#primary:disabled { background: #3a3543; color: #8a8595; }

QPushButton#tonal {
    background: #2b2930; color: #d0bcff; border: none; border-radius: 20px;
    padding: 11px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#tonal:hover { background: #353241; }
QPushButton#tonal:pressed { background: #403c4c; }
QPushButton#tonal:disabled { color: #6a6573; }

QPlainTextEdit {
    background: #121016; border: 1px solid #2a282f; border-radius: 12px;
    color: #cac4d0; padding: 10px;
    font-family: 'Roboto Mono', 'SF Mono', 'Consolas', monospace; font-size: 12px;
}

QProgressBar {
    border: none; background: #2b2930; border-radius: 4px; height: 6px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background: #d0bcff; border-radius: 4px; }
"""

PROVIDER_LABEL = {"github": "GitHub", "azure": "Azure DevOps", "generic": "git"}


def _flabel(text):
    lbl = QLabel(text)
    lbl.setObjectName("fieldlabel")
    return lbl


def _tonal(text):
    btn = QPushButton(text)
    btn.setObjectName("tonal")
    return btn


# --------------------------------------------------------------------------- #
#  Worker (läuft im Hintergrund-Thread, damit die UI nicht einfriert)
# --------------------------------------------------------------------------- #
class Worker(QObject):
    log = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, url, output, token):
        super().__init__()
        self.url, self.output, self.token = url, output, token

    def run(self):
        try:
            result = core.generate_report(
                self.url,
                output=self.output or None,
                token=self.token or None,
                log=self.log.emit,
            )
            self.done.emit(result)
        except Exception as e:  # noqa: BLE001 - Fehler an die UI weiterreichen
            self.failed.emit(str(e))


# --------------------------------------------------------------------------- #
#  Hauptfenster
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"repo2viz {core.__version__}")
        self.setMinimumSize(720, 620)
        self.thread = None
        self.worker = None
        self.last_output = None

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(18)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_form_card())
        outer.addLayout(self._build_actions())
        outer.addWidget(self._build_progress())
        outer.addWidget(self._build_log(), stretch=1)

        self.setStyleSheet(QSS)
        self._on_url_changed("")

    # ---- UI-Bausteine ----------------------------------------------------- #
    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        logo = QLabel("⟳", objectName="logo")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        row.addWidget(logo)

        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(QLabel("repo2viz", objectName="title"))
        col.addWidget(QLabel(
            "Repository-Aktivität als interaktive HTML — GitHub & Azure DevOps",
            objectName="subtitle"))
        row.addLayout(col)
        row.addStretch(1)

        ver = QLabel(f"v{core.__version__}", objectName="subtitle")
        ver.setAlignment(Qt.AlignTop | Qt.AlignRight)
        row.addWidget(ver)
        return row

    def _build_form_card(self):
        card = QFrame(objectName="card")
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 22, 22, 22)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        # URL + Provider-Badge
        url_head = QHBoxLayout()
        url_head.addWidget(_flabel("Repository-URL"))
        url_head.addStretch(1)
        self.badge = QLabel("git", objectName="badge")
        url_head.addWidget(self.badge)
        grid.addLayout(url_head, 0, 0, 1, 2)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/user/repo  ·  https://dev.azure.com/org/projekt/_git/repo")
        self.url_edit.textChanged.connect(self._on_url_changed)
        self.url_edit.returnPressed.connect(self.start)
        grid.addWidget(self.url_edit, 1, 0, 1, 2)

        # Token
        grid.addWidget(_flabel("Token / PAT (optional, private Repos)"), 2, 0, 1, 2)
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("leer lassen für öffentliche Repos")
        grid.addWidget(self.token_edit, 3, 0, 1, 2)

        # Ausgabedatei
        grid.addWidget(_flabel("Ausgabedatei (optional)"), 4, 0, 1, 2)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Standard: <repo-name>-activity.html im aktuellen Ordner")
        grid.addWidget(self.out_edit, 5, 0)
        browse = _tonal("Durchsuchen…")
        browse.clicked.connect(self._browse_output)
        grid.addWidget(browse, 5, 1)
        grid.setColumnStretch(0, 1)
        return card

    def _build_actions(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        self.gen_btn = QPushButton("Report generieren", objectName="primary")
        self.gen_btn.clicked.connect(self.start)
        row.addWidget(self.gen_btn)

        self.open_btn = _tonal("Im Browser öffnen")
        self.open_btn.clicked.connect(self._open_report)
        self.open_btn.setEnabled(False)
        row.addWidget(self.open_btn)

        self.folder_btn = _tonal("Ordner öffnen")
        self.folder_btn.clicked.connect(self._open_folder)
        self.folder_btn.setEnabled(False)
        row.addWidget(self.folder_btn)
        row.addStretch(1)
        return row

    def _build_progress(self):
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setVisible(False)
        return self.progress

    def _build_log(self):
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Bereit. URL eingeben und „Report generieren“ klicken.")
        return self.log_view

    # ---- Verhalten -------------------------------------------------------- #
    def _on_url_changed(self, text):
        provider = core.detect_provider(text.strip()) if text.strip() else "generic"
        self.badge.setText(PROVIDER_LABEL.get(provider, "git"))

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Report speichern unter", "repo-activity.html", "HTML-Dateien (*.html)")
        if path:
            self.out_edit.setText(path)

    def _append(self, msg):
        self.log_view.appendPlainText(msg)

    def start(self):
        url = self.url_edit.text().strip()
        if not url:
            self._append("⚠  Bitte zuerst eine Repository-URL eingeben.")
            return
        self.log_view.clear()
        self._set_running(True)
        self.last_output = None

        self.thread = QThread()
        self.worker = Worker(url, self.out_edit.text().strip(), self.token_edit.text().strip())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        # Aufräumen
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _on_done(self, result):
        self.last_output = result["output"]
        self._append("")
        self._append(f"✓ Fertig — {result['output']}")
        self.open_btn.setEnabled(True)
        self.folder_btn.setEnabled(True)
        self._set_running(False)
        self._open_report()  # Komfort: direkt anzeigen

    def _on_failed(self, msg):
        self._append("")
        self._append(f"✗ Fehler: {msg}")
        self._set_running(False)

    def _set_running(self, running):
        self.gen_btn.setEnabled(not running)
        self.gen_btn.setText("Generiere …" if running else "Report generieren")
        self.url_edit.setEnabled(not running)
        self.token_edit.setEnabled(not running)
        self.out_edit.setEnabled(not running)
        self.progress.setVisible(running)

    def _open_report(self):
        if self.last_output and os.path.exists(self.last_output):
            webbrowser.open(QUrl.fromLocalFile(self.last_output).toString())

    def _open_folder(self):
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.last_output)))


def _app_icon() -> QIcon:
    """Erzeugt programmatisch ein abgerundetes MD3-Icon (kein externes Asset nötig)."""
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor("#d0bcff")))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(8, 8, 112, 112, 28, 28)
    p.setPen(QColor("#381e72"))
    f = QFont(); f.setPointSize(58); f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "⟳")
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("repo2viz")
    app.setApplicationDisplayName("repo2viz")
    app.setWindowIcon(_app_icon())
    app.setFont(QFont("Roboto", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
