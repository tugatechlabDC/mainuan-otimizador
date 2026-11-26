#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - interface gráfica (Qt)."""
import os
import sys
import json
import time
import glob
import math
import html
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402
from i18n import _  # noqa: E402

i18n.set_lang(i18n.detect_lang())  # idioma do sistema, detetado automaticamente

import common as C  # noqa: E402
import core  # noqa: E402
import sysmgr  # noqa: E402
import syspages  # noqa: E402

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal
except ImportError:  # alternativa: PyQt5
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt, pyqtSignal as Signal

# ---- Paletas derivadas do logo Mainuan (gradiente turquesa) ----
THEMES = {
    "dark": dict(BG="#0A1A1E", PANEL="#0F2329", CARD="#133038", BORDER="#1E4650", TEXT="#E8F8F9",
                 MUTED="#8DB8BD", ACCENT="#0CCFD9", ACCENT2="#06ADB7", DEEP="#018993",
                 WARN="#F5B83D", DANGER="#F0604D", OK="#2ED8A0", ONACC="#04262A"),
    "light": dict(BG="#EAF5F6", PANEL="#F7FCFC", CARD="#FFFFFF", BORDER="#C3DEE1", TEXT="#0B2A2E",
                  MUTED="#527C82", ACCENT="#0899A3", ACCENT2="#06ADB7", DEEP="#018993",
                  WARN="#B87400", DANGER="#CF3A2A", OK="#0E8F66", ONACC="#FFFFFF"),
}
T = dict(THEMES["dark"])
FONT = "sans-serif"
DISPLAY_FONT = "sans-serif"


def set_theme(dark):
    T.clear()
    T.update(THEMES["dark" if dark else "light"])


def build_qss():
    return Template("""
QWidget { background: $BG; color: $TEXT; font-family: "$FONT"; font-size: 10pt; }
QLabel { background: transparent; }
QLabel#h1 { font-size: 20pt; font-weight: bold; }
QLabel#h2 { font-size: 13pt; font-weight: bold; }
QLabel#muted { color: $MUTED; }
QFrame#sidebar { background: $PANEL; border-right: 1px solid $BORDER; }
QFrame#card { background: $CARD; border: 1px solid $BORDER; border-radius: 14px; }
QFrame#card QLabel { background: transparent; }
QPushButton { background: $CARD; border: 1px solid $BORDER; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { border-color: $ACCENT2; }
QPushButton:disabled { color: $MUTED; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $ACCENT2, stop:1 $DEEP);
  color: $ONACC; font-weight: bold; border: none; }
QPushButton#primary:hover { background: $ACCENT2; }
QPushButton#primary:disabled { background: $BORDER; color: $MUTED; }
QPushButton#danger { border-color: $DANGER; color: $DANGER; }
QPushButton#nav { text-align: left; padding: 11px 14px; border: none; border-radius: 0; background: transparent; }
QPushButton#nav:hover { background: $CARD; }
QPushButton#nav:checked { background: $CARD; color: $ACCENT; border-left: 3px solid $ACCENT; }
QTableWidget { background: $PANEL; alternate-background-color: $BG; border: 1px solid $BORDER;
  border-radius: 8px; selection-background-color: $DEEP; selection-color: white; }
QHeaderView::section { background: $CARD; color: $MUTED; border: none; padding: 6px; font-weight: bold; }
QGroupBox { border: 1px solid $BORDER; border-radius: 10px; margin-top: 14px; padding: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: $ACCENT; }
QComboBox, QSpinBox, QLineEdit { background: $PANEL; border: 1px solid $BORDER; border-radius: 6px; padding: 5px 8px; min-height: 26px; }
QComboBox QAbstractItemView { background: $PANEL; color: $TEXT; selection-background-color: $DEEP;
  border: 1px solid $BORDER; }
QTextBrowser { background: $PANEL; border: 1px solid $BORDER; border-radius: 10px; padding: 6px; }
QScrollArea { border: none; }
QRadioButton, QCheckBox { spacing: 8px; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $BORDER; border-radius: 6px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $ACCENT2; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: $BORDER; border-radius: 6px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: $ACCENT2; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QPushButton#nav[collapsed="true"] { padding: 11px 0px; text-align: center; }
QMessageBox, QDialog { background: $BG; }
QWidget#plain, QFrame#plain { background: transparent; }
QLabel#cardtitle { color: $MUTED; font-size: 9pt; font-weight: bold; }
QLabel#big { font-size: 20pt; font-weight: bold; }
QPushButton#small { padding: 4px 12px; font-size: 9pt; }
QPushButton#link { border: none; background: transparent; color: $ACCENT; padding: 0 2px; font-size: 9pt; }
QPushButton#link:hover { text-decoration: underline; }
QPushButton::menu-indicator { width: 0; }
QProgressBar { background: $BORDER; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk { background: $ACCENT; border-radius: 3px; }
QStatusBar { background: $PANEL; color: $MUTED; border-top: 1px solid $BORDER; }
QSplitter::handle { background: transparent; width: 8px; }
QMenu { background: $PANEL; color: $TEXT; border: 1px solid $BORDER; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $DEEP; color: white; }
""").substitute(FONT=FONT, **T)


def pick_font():
    try:
        fams = set(QtGui.QFontDatabase.families())
    except TypeError:
        fams = set(QtGui.QFontDatabase().families())
    for f in ("Inter", "Noto Sans", "Ubuntu", "Open Sans", "Cantarell", "Segoe UI", "DejaVu Sans"):
        if f in fams:
            return f
    return "sans-serif"


def pick_display_font():
    """Tipo de letra de destaque (diferente do da interface) para o popup de informações."""
    try:
        fams = set(QtGui.QFontDatabase.families())
    except TypeError:
        fams = set(QtGui.QFontDatabase().families())
    for f in ("Lato", "Poppins", "Montserrat", "Raleway", "Ubuntu", "Noto Sans Display",
              "Noto Serif", "DejaVu Serif"):
        if f in fams and f != FONT:
            return f
    return FONT


def qt_is_dark():
    try:
        cs = QtGui.QGuiApplication.styleHints().colorScheme()
        if cs == Qt.ColorScheme.Dark:
            return True
        if cs == Qt.ColorScheme.Light:
            return False
    except (AttributeError, TypeError):
        pass
    return QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128


def detect_dark():
    d = core.system_is_dark()
    return qt_is_dark() if d is None else d


LOGO_PATHS = ["/usr/share/icons/hicolor/256x256/apps/mainuan-otimizador.png",
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")]


def logo_pixmap(size):
    for p in LOGO_PATHS:
        if os.path.exists(p):
            pm = QtGui.QPixmap(p)
            return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return QtGui.QPixmap()


def draw_pixmap(kind, color, size=22):
    """Ícone desenhado em código (canvas 44x44, escalado)."""
    px = size * 2
    pm = QtGui.QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.scale(px / 44.0, px / 44.0)
    pen = QtGui.QPen(QtGui.QColor(color), 3.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    P, R = QtCore.QPointF, QtCore.QRectF
    s, c = 44.0, 22.0
    if kind == "gauge":
        p.drawArc(R(5, 5, s - 10, s - 10), 225 * 16, -270 * 16)
        p.drawLine(P(c, c), P(s * 0.70, s * 0.34))
    elif kind == "ram":
        p.drawRoundedRect(R(4, 9, s - 8, s - 22), 3, 3)
        for x in (9, 18, 27):
            p.drawRect(R(x, 15, 8, 8))
        for x in range(10, 36, 7):
            p.drawLine(P(x, s - 13), P(x, s - 7))
    elif kind == "cpu":
        p.drawRoundedRect(R(11, 11, s - 22, s - 22), 4, 4)
        p.drawRect(R(17, 17, s - 34, s - 34))
        for v in (17, 22, 27):
            p.drawLine(P(v, 4), P(v, 11)); p.drawLine(P(v, s - 11), P(v, s - 4))
            p.drawLine(P(4, v), P(11, v)); p.drawLine(P(s - 11, v), P(s - 4, v))
    elif kind == "globe":
        p.drawEllipse(R(5, 5, s - 10, s - 10))
        p.drawEllipse(R(c - 8, 5, 16, s - 10))
        p.drawLine(P(5, c), P(s - 5, c))
        p.drawArc(R(9, 11, s - 18, 14), 0, 180 * 16)
        p.drawArc(R(9, 19, s - 18, 14), 0, -180 * 16)
    elif kind == "menu":
        for y in (12, 22, 32):
            p.drawLine(P(8, y), P(s - 8, y))
    elif kind == "check":
        p.drawEllipse(R(5, 5, s - 10, s - 10))
        p.drawPolyline(QtGui.QPolygonF([P(13, 23), P(20, 30), P(32, 15)]))
    elif kind == "bolt":
        p.drawPolyline(QtGui.QPolygonF([P(c + 4, 4), P(12, c + 3), P(c, c + 3), P(c - 4, s - 4),
                                        P(s - 12, c - 3), P(c, c - 3), P(c + 4, 4)]))
    elif kind == "power":
        p.drawArc(R(8, 9, s - 16, s - 16), 120 * 16, 300 * 16)
        p.drawLine(P(c, 5), P(c, c))
    elif kind == "list":
        for y in (11, 22, 33):
            p.drawPoint(P(10, y)); p.drawLine(P(18, y), P(s - 8, y))
    elif kind == "overview":
        p.drawRoundedRect(R(6, 6, 14, 18), 3, 3)
        p.drawRoundedRect(R(24, 6, 14, 10), 3, 3)
        p.drawRoundedRect(R(24, 20, 14, 18), 3, 3)
        p.drawRoundedRect(R(6, 28, 14, 10), 3, 3)
    elif kind == "services":
        p.drawEllipse(R(c - 11, c - 11, 22, 22))
        p.drawEllipse(R(c - 4.5, c - 4.5, 9, 9))
        for k in range(8):
            a = math.radians(k * 45)
            p.drawLine(P(c + 11 * math.cos(a), c + 11 * math.sin(a)), P(c + 17 * math.cos(a), c + 17 * math.sin(a)))
    elif kind == "diagnosis":
        p.drawRoundedRect(R(4, 8, s - 8, s - 18), 5, 5)
        p.drawPolyline(QtGui.QPolygonF([P(9, 22), P(16, 22), P(19.5, 14), P(24.5, 30), P(28, 20), P(30.5, 22), P(35, 22)]))
        p.drawLine(P(16, s - 6), P(s - 16, s - 6))
    elif kind == "optimize":
        body = QtGui.QPainterPath()
        body.moveTo(c, 4)
        body.quadTo(33, 11, 31, 28)
        body.lineTo(13, 28)
        body.quadTo(11, 11, c, 4)
        body.closeSubpath()
        p.drawPath(body)
        p.drawEllipse(R(c - 4, 14, 8, 8))
        p.drawPolyline(QtGui.QPolygonF([P(14, 22), P(7, 32), P(14, 31)]))
        p.drawPolyline(QtGui.QPolygonF([P(30, 22), P(37, 32), P(30, 31)]))
        p.drawLine(P(c, 33), P(c, 40))
    elif kind == "boot":
        p.drawEllipse(R(7, 10, s - 14, s - 14))
        p.drawLine(P(c, 10), P(c, 5))
        p.drawLine(P(17, 5), P(27, 5))
        p.drawLine(P(c, 27), P(30, 19))
        p.drawPoint(P(c, 27))
    elif kind == "history":
        p.drawArc(R(6, 6, s - 12, s - 12), 120 * 16, 300 * 16)
        p.drawPolyline(QtGui.QPolygonF([P(7, 9), P(13.5, 8), P(14.5, 15)]))
        p.drawPolyline(QtGui.QPolygonF([P(c, 13), P(c, c), P(29, 26)]))
    elif kind == "refresh":
        p.drawArc(R(8, 8, s - 16, s - 16), 40 * 16, 280 * 16)
        p.drawPolyline(QtGui.QPolygonF([P(36, 22), P(32.5, 31), P(25, 27)]))
    else:  # info
        p.drawEllipse(R(6, 6, s - 12, s - 12))
        p.drawPoint(P(c, 15)); p.drawLine(P(c, 21), P(c, 31))
    p.end()
    return pm


def make_icon(kind):
    """Ícone de navegação: cor normal e cor de destaque quando selecionado."""
    ic = QtGui.QIcon()
    ic.addPixmap(draw_pixmap(kind, T["TEXT"]), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
    ic.addPixmap(draw_pixmap(kind, T["ACCENT"]), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
    return ic


def label(text, name=None, wrap=False):
    l = QtWidgets.QLabel(text)
    if name:
        l.setObjectName(name)
    l.setWordWrap(wrap)
    return l


def card():
    f = QtWidgets.QFrame()
    f.setObjectName("card")
    return f


def make_table(headers, multi=True):
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection if multi
                       else QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def titem(text, num=None):
    it = QtWidgets.QTableWidgetItem()
    if num is not None:
        it.setData(Qt.ItemDataRole.DisplayRole, num)
    else:
        it.setText(str(text))
    return it


def ask(parent, title, text):
    mb = QtWidgets.QMessageBox(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    yes = mb.addButton(_("Sim"), QtWidgets.QMessageBox.ButtonRole.YesRole)
    mb.addButton(_("Não"), QtWidgets.QMessageBox.ButtonRole.NoRole)
    mb.exec()
    return mb.clickedButton() == yes


def warn(parent, title, text):
    mb = QtWidgets.QMessageBox(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    mb.addButton(_("OK"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    mb.exec()


def fit_dialog(dlg, w, h):
    """Dimensiona o diálogo para caber na área útil do ecrã (fora de painéis)."""
    a = QtWidgets.QApplication.primaryScreen().availableGeometry()
    dlg.resize(max(360, min(w, a.width() - 60)), max(300, min(h, a.height() - 110)))


def scroll_wrap(page, min_h=0, min_w=700):
    """Coloca uma página dentro de uma área com barra de deslocamento."""
    page.setMinimumSize(min_w, min_h)
    sa = QtWidgets.QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    sa.setWidget(page)
    return sa


def notify(parent, title, message, ok=True):
    """Janela de resultado com botão Fechar."""
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    fit_dialog(dlg, 540, 340)
    lay = QtWidgets.QVBoxLayout(dlg)
    lay.setContentsMargins(30, 26, 30, 22)
    lay.setSpacing(12)
    ic = QtWidgets.QLabel()
    ic.setPixmap(draw_pixmap("check" if ok else "info", T["OK"] if ok else T["WARN"], 56))
    ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(ic)
    h = label(title.upper(), "h2")
    h.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(h)
    m = label(message, None, True)
    m.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(m)
    lay.addStretch(1)
    b = QtWidgets.QPushButton(_("Fechar"))
    b.setObjectName("primary")
    b.setMinimumWidth(170)
    b.clicked.connect(dlg.accept)
    lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
    dlg.exec()


# ------------------------------------------------------------ HTML organizado
def esc(s):
    return html.escape(str(s))


def kv_table(rows):
    """Tabela chave/valor com linhas alternadas."""
    out = ['<table width="100%" cellspacing="0" cellpadding="6">']
    for i, (k, v) in enumerate(rows):
        bg = T["CARD"] if i % 2 == 0 else T["PANEL"]
        out.append(f'<tr bgcolor="{bg}"><td width="42%" style="color:{T["MUTED"]}">{esc(k)}</td>'
                   f'<td style="color:{T["TEXT"]}"><b>{esc(v)}</b></td></tr>')
    out.append("</table>")
    return "".join(out)


def section(title):
    return (f'<div style="margin-top:14px;margin-bottom:5px;color:{T["ACCENT"]};'
            f'font-size:9pt;font-weight:600">{esc(title.upper())}</div>')


def page_html(body):
    return (f'<html><body style="font-family:\'{FONT}\';font-size:10pt;color:{T["TEXT"]};'
            f'background:{T["PANEL"]}">{body}</body></html>')


def plan_html(hw, plan):
    head = _("Para {ram} de RAM e {disk}:").format(ram=C.fmt_mb(hw["ram_mb"]), disk=C.storage_label(hw))
    body = (f'<div style="font-size:11pt;font-weight:600;color:{T["ACCENT"]};margin-bottom:6px">{esc(head)}</div>'
            + kv_table(C.plan_rows(plan, hw)))
    if plan.get("notes"):
        body += "".join(f'<div style="color:{T["MUTED"]};font-size:9pt;margin-top:6px">• {esc(n)}</div>'
                        for n in plan["notes"])
    return body


def status_html():
    sw = C.swaps()
    b = [section(_("Swap ativa"))]
    if not sw:
        b.append(f'<div style="color:{T["MUTED"]}">{esc(_("Nenhuma swap ativa"))}</div>')
    else:
        b.append('<table width="100%" cellspacing="0" cellpadding="5">'
                 f'<tr style="color:{T["MUTED"]};font-size:9pt"><td>{esc(_("Dispositivo"))}</td>'
                 f'<td align="right">{esc(_("Tamanho"))}</td><td align="right">{esc(_("Usado"))}</td>'
                 f'<td align="right">{esc(_("Prioridade"))}</td></tr>')
        for i, s in enumerate(sw):
            bg = T["CARD"] if i % 2 == 0 else T["PANEL"]
            tot, used = s["size_kb"] // 1024, s["used_kb"] // 1024
            pct = int(100 * used / tot) if tot else 0
            b.append(f'<tr bgcolor="{bg}"><td><b>{esc(s["name"])}</b></td>'
                     f'<td align="right">{esc(C.fmt_mb(tot))}</td><td align="right">{esc(C.fmt_mb(used))}</td>'
                     f'<td align="right">{s["prio"]}</td></tr>')
            if 0 < pct < 100:
                bar = (f'<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                       f'<td width="{pct}%" bgcolor="{T["ACCENT2"]}" style="font-size:3pt">&nbsp;</td>'
                       f'<td bgcolor="{T["BORDER"]}" style="font-size:3pt">&nbsp;</td></tr></table>')
                b.append(f'<tr bgcolor="{bg}"><td colspan="4">{bar}</td></tr>')
        b.append("</table>")
    for d in sorted(glob.glob("/sys/block/zram[0-9]*")):
        if C.read(d + "/disksize", "0") == "0":
            continue
        algo = C.read(d + "/comp_algorithm")
        cur = algo[algo.find("[") + 1:algo.find("]")] if "[" in algo else algo
        mm = C.read(d + "/mm_stat").split()
        rows = [(_("Compressão"), cur), (_("Tamanho"), C.fmt_mb(int(C.read(d + "/disksize", "0")) // C.MIB))]
        if len(mm) >= 3 and int(mm[1]) > 0:
            rows.append((_("Dados guardados"), f"{C.fmt_mb(int(mm[0]) // C.MIB)} → {C.fmt_mb(int(mm[1]) // C.MIB)}"))
            rows.append((_("Rácio de compressão"), f"{int(mm[0]) / int(mm[1]):.1f}x"))
        b.append(section(os.path.basename(d)))
        b.append(kv_table(rows))
    zp = "/sys/module/zswap/parameters/"
    b.append(section(_("zswap")))
    if os.path.isdir(zp):
        on = C.read(zp + "enabled") in ("Y", "1")
        b.append(kv_table([(_("Estado"), _("ativo") if on else _("inativo")),
                           (_("Compressão"), C.read(zp + "compressor")),
                           (_("Cache máxima"), _("{p}% da RAM").format(p=C.read(zp + "max_pool_percent")))]))
    else:
        b.append(f'<div style="color:{T["MUTED"]}">{esc(_("não disponível neste kernel"))}</div>')
    b.append(section(_("Parâmetros do kernel")))
    b.append(kv_table([("swappiness", C.read("/proc/sys/vm/swappiness")),
                       ("page-cluster", C.read("/proc/sys/vm/page-cluster"))]))
    return page_html("".join(b))


class LogView(QtWidgets.QTextBrowser):
    """Registo com hora, cores por tipo e tipo de letra legível."""

    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.entries = []
        self.render()

    def add(self, text, kind="info"):
        self.entries.append((time.strftime("%H:%M:%S"), kind, text))
        self.entries = self.entries[-300:]
        self.render()

    def add_many(self, items):
        for k, t in items:
            self.entries.append((time.strftime("%H:%M:%S"), k, t))
        self.entries = self.entries[-300:]
        self.render()

    def add_output(self, text):
        for line in text.splitlines():
            line = line.rstrip()
            if not line.strip() or line.strip() == "OK":
                continue
            bad = line.strip().startswith(("!", "Erro", "Error"))
            self.entries.append((time.strftime("%H:%M:%S"), "err" if bad else "info", line.strip()))
        self.entries = self.entries[-300:]
        self.render()

    def render(self):
        col = {"info": T["TEXT"], "ok": T["OK"], "err": T["DANGER"], "cmd": T["MUTED"]}
        rows = []
        for ts, k, txt in self.entries:
            t = esc(txt).replace("\n", "<br>")
            if k == "head":
                rows.append(f'<tr><td colspan="2" style="padding-top:8px"><b style="color:{T["ACCENT"]}">{t}</b></td></tr>')
            else:
                fam = "font-family:monospace;" if k == "cmd" else ""
                rows.append(f'<tr><td valign="top" style="color:{T["MUTED"]};font-size:8pt">{ts}&nbsp;&nbsp;</td>'
                            f'<td style="color:{col.get(k, T["TEXT"])};{fam}">{t}</td></tr>')
        if not rows:
            rows.append(f'<tr><td style="color:{T["MUTED"]}">{esc(_("Sem atividade ainda."))}</td></tr>')
        self.setHtml(page_html('<table cellspacing="0" cellpadding="2">' + "".join(rows) + "</table>"))
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())


# ==================================================================== Tarefas
class Task(QtCore.QThread):
    done = Signal(object, object)

    def __init__(self, fn, args, cb, parent=None):
        super().__init__(parent)
        self.fn, self.args, self.cb = fn, args, cb

    def run(self):
        try:
            res = self.fn(*self.args)
        except Exception as ex:  # noqa: BLE001
            res = ex
        self.done.emit(self, res)


class InfoDialog(QtWidgets.QDialog):
    """Explicação de swap, zram, zswap e modo automático (quatro cartões centrados)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("Mais informações"))
        fit_dialog(self, 940, 680)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(14)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        inner = QtWidgets.QWidget()
        il = QtWidgets.QVBoxLayout(inner)
        il.setContentsMargins(4, 4, 4, 4)
        il.setSpacing(16)
        logo = QtWidgets.QLabel()
        logo.setPixmap(logo_pixmap(84))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(logo)
        t = QtWidgets.QLabel(_("Memória: swap, zram e zswap"))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setWordWrap(True)
        t.setStyleSheet('font-family:"%s"; font-size:24pt; font-weight:700; color:%s;'
                        % (DISPLAY_FONT, T["TEXT"]))
        il.addWidget(t)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        items = (
            ("💾", _("O que é Swap?"),
             _("A swap é como uma extensão da memória do computador. Quando a RAM está cheia, os dados "
               "menos usados vão para a swap, evitando bloqueios.")),
            ("🔄", _("O que é Zswap?"),
             _("O zswap interceta as tentativas de swap e comprime as páginas numa cache na RAM antes de "
               "chegarem ao disco, reduzindo as operações de leitura e escrita.")),
            ("⚡", _("O que é Zram?"),
             _("O zram cria um dispositivo de blocos comprimido na RAM. É mais rápido do que a swap em "
               "disco e ideal para sistemas com disco lento.")),
            ("🎯", _("Modo Automático"),
             _("Recomendado: o modo automático deteta o seu hardware (RAM + armazenamento) e aplica a "
               "configuração ideal automaticamente.")),
        )
        for i, (emo, title, desc) in enumerate(items):
            c = card()
            c.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(22, 18, 22, 18)
            cl.setSpacing(8)
            cl.addStretch(1)
            e = QtWidgets.QLabel(emo)
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            e.setStyleSheet("font-size:30pt; background:transparent;")
            cl.addWidget(e)
            h = QtWidgets.QLabel(title)
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h.setWordWrap(True)
            h.setStyleSheet('font-family:"%s"; font-size:16pt; font-weight:700; color:%s; background:transparent;'
                            % (DISPLAY_FONT, T["ACCENT"]))
            cl.addWidget(h)
            d = QtWidgets.QLabel(desc)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setWordWrap(True)
            d.setStyleSheet('font-family:"%s"; font-size:12pt; color:%s; background:transparent;'
                            % (DISPLAY_FONT, T["TEXT"]))
            cl.addWidget(d)
            cl.addStretch(1)
            grid.addWidget(c, i // 2, i % 2)
        for k in (0, 1):
            grid.setRowStretch(k, 1)
            grid.setColumnStretch(k, 1)
        il.addLayout(grid, 1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        b = QtWidgets.QPushButton(_("Fechar"))
        b.setObjectName("primary")
        b.setMinimumWidth(220)
        b.setMinimumHeight(38)
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)


class MemoryPage(QtWidgets.QWidget):
    KINDS = ("zram", "zswap", "swap")

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._last_status = ""
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        self._mode = "apply"
        top = QtWidgets.QHBoxLayout()
        self.b_info = QtWidgets.QPushButton(_("Mais informações"))
        self.b_info.setIconSize(QtCore.QSize(20, 20))
        self.b_info.clicked.connect(lambda _c=False: InfoDialog(self).exec())
        top.addWidget(label(_("Memória: swap, zram e zswap"), "h1"))
        top.addStretch(1)
        top.addWidget(self.b_info)
        lay.addLayout(top)
        lay.addWidget(label(_("Configure como o sistema usa a memória virtual. O modo automático "
                              "escolhe a melhor configuração para o seu hardware."), "muted", True))
        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(18)
        lay.addLayout(cols, 1)

        left = QtWidgets.QVBoxLayout()
        cols.addLayout(left, 1)
        self.rb_auto = QtWidgets.QRadioButton(_("Automático (recomendado)"))
        self.rb_manual = QtWidgets.QRadioButton(_("Manual"))
        self.rb_auto.setChecked(True)
        f = self.rb_auto.font()
        f.setBold(True)
        self.rb_auto.setFont(f)
        self.rb_manual.setFont(f)
        left.addWidget(self.rb_auto)
        self.auto_card = card()
        al = QtWidgets.QVBoxLayout(self.auto_card)
        al.setContentsMargins(14, 12, 14, 12)
        self.plan_lbl = QtWidgets.QLabel()
        self.plan_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.plan_lbl.setWordWrap(True)
        al.addWidget(self.plan_lbl)
        left.addWidget(self.auto_card)
        left.addWidget(self.rb_manual)

        self.manual = QtWidgets.QGroupBox(_("Definições manuais"))
        form = QtWidgets.QFormLayout(self.manual)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(10)
        form.setContentsMargins(10, 14, 10, 10)
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems([_("zram (recomendado)"), _("zswap + swap em disco"), _("Swap tradicional (ficheiro)")])
        self.zpct = QtWidgets.QSpinBox(); self.zpct.setRange(10, 200); self.zpct.setSingleStep(5)
        self.zpct.setSuffix(" " + _("% da RAM")); self.zpct.setValue(50)
        self.zalgo = QtWidgets.QComboBox(); self.zalgo.addItems(list(C.ZRAM_ALGOS))
        self.zcomp = QtWidgets.QComboBox(); self.zcomp.addItems(list(C.ZSWAP_COMPRESSORS))
        self.zpool = QtWidgets.QSpinBox(); self.zpool.setRange(5, 50); self.zpool.setSuffix(" " + _("% da RAM"))
        self.zpool.setValue(20)
        self.sfile = QtWidgets.QSpinBox(); self.sfile.setRange(0, 131072); self.sfile.setSingleStep(512)
        self.sfile.setSuffix(" MiB"); self.sfile.setValue(2048)
        self.swp = QtWidgets.QSpinBox(); self.swp.setRange(0, 200); self.swp.setValue(60)
        form.addRow(_("Tipo:"), self.kind)
        form.addRow(_("Tamanho do zram:"), self.zpct)
        form.addRow(_("Compressão zram:"), self.zalgo)
        form.addRow(_("Compressão zswap:"), self.zcomp)
        form.addRow(_("Cache máx. zswap:"), self.zpool)
        form.addRow(_("Swap em ficheiro (0 = nenhuma):"), self.sfile)
        form.addRow(_("Swappiness:"), self.swp)
        left.addWidget(self.manual)

        btns = QtWidgets.QHBoxLayout()
        self.b_apply = QtWidgets.QPushButton(_("Aplicar configuração"))
        self.b_apply.setObjectName("primary")
        self.b_restore = QtWidgets.QPushButton(_("Restaurar predefinições"))
        btns.addWidget(self.b_apply)
        btns.addWidget(self.b_restore)
        left.addLayout(btns)
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout()
        cols.addLayout(right, 1)
        right.addWidget(label(_("Estado atual"), "h2"))
        self.status = QtWidgets.QTextBrowser()
        self.status.setOpenLinks(False)
        right.addWidget(self.status, 3)
        right.addWidget(label(_("Registo"), "h2"))
        self.log = LogView()
        right.addWidget(self.log, 2)

        for w in (self.rb_auto, self.rb_manual):
            w.toggled.connect(self.refresh_ui)
        self.kind.currentIndexChanged.connect(self.refresh_ui)
        self.b_apply.clicked.connect(self.apply)
        self.b_restore.clicked.connect(self.restore)
        self.load_saved()
        self.refresh_ui()
        self.refresh_status()

    def on_theme(self):
        self.b_info.setIcon(make_icon("info"))
        self.refresh_ui()
        self._last_status = ""
        self.refresh_status()
        self.log.render()

    def load_saved(self):
        try:
            cfg = C.validate_config(json.loads(C.read(C.CONFIG_FILE)))
        except (ValueError, TypeError):
            return
        if cfg["mode"] == "manual":
            self.rb_manual.setChecked(True)
            self.kind.setCurrentIndex(self.KINDS.index(cfg["kind"]))
            self.zpct.setValue(cfg["zram_percent"])
            self.zalgo.setCurrentText(cfg["zram_algo"])
            self.zcomp.setCurrentText(cfg["zswap_compressor"])
            self.zpool.setValue(cfg["zswap_pool_percent"])
            self.sfile.setValue(cfg["swapfile_mb"])
            self.swp.setValue(cfg["swappiness"])

    def cfg(self):
        if self.rb_auto.isChecked():
            return {"mode": "auto"}
        return {"mode": "manual", "kind": self.KINDS[self.kind.currentIndex()],
                "zram_percent": self.zpct.value(), "zram_algo": self.zalgo.currentText(),
                "zswap_compressor": self.zcomp.currentText(), "zswap_pool_percent": self.zpool.value(),
                "swapfile_mb": self.sfile.value(), "swappiness": self.swp.value()}

    def refresh_ui(self, *_a):
        manual = self.rb_manual.isChecked()
        self.manual.setEnabled(manual)
        self.auto_card.setVisible(not manual)
        k = self.KINDS[self.kind.currentIndex()]
        self.zpct.setEnabled(manual and k == "zram")
        self.zalgo.setEnabled(manual and k == "zram")
        self.zcomp.setEnabled(manual and k == "zswap")
        self.zpool.setEnabled(manual and k == "zswap")
        if not manual:
            hw = self.win.hw
            self.plan_lbl.setText(plan_html(hw, C.auto_plan(hw)))

    def refresh_status(self):
        new = status_html()
        if new == self._last_status:
            return
        self._last_status = new
        sb = self.status.verticalScrollBar()
        pos = sb.value()
        self.status.setHtml(new)
        sb.setValue(pos)

    def _busy(self, busy):
        self.b_apply.setEnabled(not busy)
        self.b_restore.setEnabled(not busy)

    def apply(self):
        self._mode = "apply"
        self._busy(True)
        self.log.add(_("A pedir autorização e a aplicar…"), "cmd")
        self.win.run_task(core.run_helper, ("set-memory", json.dumps(self.cfg())), self._done)

    def restore(self):
        if not ask(self, _("Restaurar predefinições"),
                   _("Remover a configuração desta aplicação e repor os valores originais "
                     "(zram, swap em ficheiro e swappiness)?")):
            return
        self._mode = "restore"
        self._busy(True)
        self.win.run_task(core.run_helper, ("restore",), self._done)

    def _done(self, res):
        self._busy(False)
        if isinstance(res, Exception):
            self.log.add(_("Erro:") + f" {res}", "err")
            return
        rc, out = res
        if out:
            self.log.add_output(out)
        self.log.add(_("Concluído.") if rc == 0 else _("Falhou (código {c}).").format(c=rc),
                     "ok" if rc == 0 else "err")
        self.win.refresh_hw()
        self._last_status = ""
        self.refresh_status()
        if rc != 0:
            warn(self, _("Não foi possível aplicar"), out or _("Operação cancelada."))
        elif self._mode == "apply":
            notify(self, _("Configurações aplicadas"),
                   _("A nova configuração de memória foi aplicada com sucesso. "
                     "Recomendamos reiniciar o sistema para garantir que tudo fica ativo."))


class AboutPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = QtWidgets.QLabel()
        logo.setPixmap(logo_pixmap(128))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)
        t = label(C.APP_NAME, "h1")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        for txt in (_("Versão {v}").format(v=C.VERSION), _("Autor: {a}").format(a=C.AUTHOR),
                    _("Gestão de swap, zram e zswap, serviços do sistema, diagnóstico,"),
                    _("otimização e análise de arranque, com histórico de alterações.")):
            l = label(txt, "muted")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(l)


# ============================================================ Janela principal
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dark):
        super().__init__()
        self.setWindowTitle(C.APP_NAME)
        self.dark = dark
        self.tasks = set()
        self.tick_n = 0
        self.hw = C.hardware()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        h = QtWidgets.QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.collapsed = True
        self.side = QtWidgets.QFrame()
        self.side.setObjectName("sidebar")
        sl = QtWidgets.QVBoxLayout(self.side)
        sl.setContentsMargins(0, 10, 0, 12)
        sl.setSpacing(2)
        self.b_toggle = QtWidgets.QPushButton()
        self.b_toggle.setObjectName("nav")
        self.b_toggle.setIconSize(QtCore.QSize(22, 22))
        self.b_toggle.clicked.connect(lambda _c=False: self.set_sidebar(not self.collapsed))
        sl.addWidget(self.b_toggle)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(12, 8, 8, 12)
        lg = QtWidgets.QLabel()
        lg.setPixmap(logo_pixmap(40))
        head.addWidget(lg)
        self.brand = label("", None)
        head.addWidget(self.brand)
        head.addStretch(1)
        sl.addLayout(head)

        self.stack = QtWidgets.QStackedWidget()
        syspages.bind(sys.modules[__name__])
        self.p_over = syspages.OverviewPage(self)
        self.p_svc = syspages.ServicesPage(self)
        self.p_diag = syspages.DiagnosisPage(self)
        self.p_opt = syspages.OptimizationPage(self)
        self.p_mem = MemoryPage(self)
        self.p_boot = syspages.BootPage(self)
        self.p_hist = syspages.HistoryPage(self)
        self.sys_pages = [self.p_over, self.p_svc, self.p_diag, self.p_opt, self.p_boot, self.p_hist]
        pages = [("overview", _("Resumo"), "overview", self.p_over, 640),
                 ("services", _("Serviços"), "services", self.p_svc, 540),
                 ("diagnosis", _("Diagnóstico"), "diagnosis", self.p_diag, 480),
                 ("optimization", _("Otimização"), "optimize", self.p_opt, 540),
                 ("mem", _("Memória"), "ram", self.p_mem, 800),
                 ("boot", _("Análise de arranque"), "boot", self.p_boot, 540),
                 ("history", _("Histórico"), "history", self.p_hist, 420),
                 ("about", _("Acerca"), "info", AboutPage(), 0)]
        self.idx = {}
        self.pages_by_index = []
        self.nav = []
        for i, (key, txt, ic, page, min_h) in enumerate(pages):
            self.idx[key] = i
            self.pages_by_index.append(page)
            b = QtWidgets.QPushButton("  " + txt)
            b.setObjectName("nav")
            b.setProperty("kind", ic)
            b.setProperty("label", txt)
            b.setIconSize(QtCore.QSize(22, 22))
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.clicked.connect(lambda _c=False, n=i: self.goto(n))
            sl.addWidget(b)
            self.nav.append(b)
            self.stack.addWidget(scroll_wrap(page, min_h, 640 if key != "mem" else 700))
        sl.addStretch(1)
        self.ver = label(f"v{C.VERSION}", "muted")
        sl.addWidget(self.ver, 0, Qt.AlignmentFlag.AlignHCenter)
        h.addWidget(self.side)
        h.addWidget(self.stack, 1)
        self.set_sidebar(True)
        self.restyle()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.goto(0)
        self.tick()

        self.initial_size()

    # ---- barra lateral recolhível
    def set_sidebar(self, collapsed):
        self.collapsed = collapsed
        self.side.setFixedWidth(64 if collapsed else 220)
        self.brand.setVisible(not collapsed)
        self.ver.setVisible(not collapsed)
        for b in self.nav + [self.b_toggle]:
            b.setProperty("collapsed", collapsed)
            b.style().unpolish(b)
            b.style().polish(b)
        for b in self.nav:
            b.setText("" if collapsed else "  " + b.property("label"))
            b.setToolTip(b.property("label"))
        self.b_toggle.setIcon(make_icon("menu"))
        self.b_toggle.setText("" if collapsed else "  " + _("Recolher menu"))
        self.b_toggle.setToolTip(_("Expandir menu") if collapsed else _("Recolher menu"))

    # ---- tamanho e posição dentro da área útil do ecrã
    def _avail(self):
        scr = self.screen() or QtWidgets.QApplication.primaryScreen()
        return scr.availableGeometry()

    @staticmethod
    def _margins():
        wayland = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        return 60, (140 if wayland else 100)  # inclui barra de título e painel

    def initial_size(self):
        a = self._avail()
        mw, mh = self._margins()
        self.setMinimumSize(min(760, a.width() - mw), min(480, a.height() - mh))
        self.resize(min(1180, a.width() - mw), min(780, a.height() - mh))
        self.move(a.left() + (a.width() - self.width()) // 2, a.top() + (a.height() - self.height()) // 2)

    def fit_to_screen(self):
        """Depois de visível (com moldura conhecida): garante que a janela não fica sob o painel nem fora do ecrã."""
        a = self._avail()
        fg = self.frameGeometry()
        extra_w, extra_h = fg.width() - self.width(), fg.height() - self.height()
        w = min(self.width(), a.width() - 20 - extra_w)
        h = min(self.height(), a.height() - 20 - extra_h)
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
            fg = self.frameGeometry()
        x = max(a.left() + 10, min(fg.x(), a.right() - fg.width() - 9))
        y = max(a.top() + 10, min(fg.y(), a.bottom() - fg.height() - 9))
        if (x, y) != (fg.x(), fg.y()):
            self.move(x, y)

    def restyle(self):
        """Reaplica cores (tema claro/escuro) a tudo o que não depende só da folha de estilos."""
        QtWidgets.QApplication.instance().setStyleSheet(build_qss())
        self.brand.setText("<b>MAINUAN</b><br><span style='color:%s'>OTIMIZADOR</span>" % T["ACCENT"])
        for b in self.nav:
            b.setIcon(make_icon(b.property("kind")))
        self.b_toggle.setIcon(make_icon("menu"))
        self.p_mem.on_theme()
        for pg in self.sys_pages:
            pg.on_theme()

    def check_theme(self):
        dark = detect_dark()
        if dark != self.dark:
            self.dark = dark
            set_theme(dark)
            self.restyle()

    def goto(self, n):
        self.nav[n].setChecked(True)
        self.stack.setCurrentIndex(n)
        pg = self.pages_by_index[n]
        if pg is self.p_mem:
            self.p_mem.refresh_ui()
            self.p_mem.refresh_status()
        elif hasattr(pg, "activate"):
            pg.activate()

    def goto_name(self, key):
        self.goto(self.idx[key])

    def open_service(self, name, scope="system"):
        """Abre a página Serviços com o serviço indicado selecionado."""
        self.p_svc.pending = (scope, name)
        self.p_svc.search.setText("")
        self.goto_name("services")
        self.p_svc.reload(True)

    def invalidate(self, key):
        """Marca uma página como desatualizada: volta a ler os dados quando for aberta."""
        self.pages_by_index[self.idx[key]].loaded_at = 0

    def refresh_hw(self):
        self.hw = C.hardware()
        self.p_mem.refresh_ui()

    def run_task(self, fn, args, cb):
        t = Task(fn, args, cb, self)
        self.tasks.add(t)
        t.done.connect(self._task_done)
        t.finished.connect(self._task_finished)
        t.start()

    def _task_done(self, task, res):
        task.cb(res)

    def _task_finished(self):
        self.tasks.discard(self.sender())

    def tick(self):
        self.tick_n += 1
        if self.tick_n % 3 == 0:
            self.check_theme()
            if self.stack.currentIndex() == self.idx["mem"]:
                self.p_mem.refresh_status()
        if self.tick_n % 5 == 0 and self.stack.currentIndex() == self.idx["overview"]:
            self.p_over.refresh_memory()


def main():
    global FONT, DISPLAY_FONT
    QtWidgets.QApplication.setApplicationName("mainuan-otimizador")
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationDisplayName(C.APP_NAME)
    app.setDesktopFileName("mainuan-otimizador")
    FONT = pick_font()
    DISPLAY_FONT = pick_display_font()
    dark = detect_dark()
    set_theme(dark)
    app.setStyleSheet(build_qss())
    app.setWindowIcon(QtGui.QIcon(logo_pixmap(256)))
    w = MainWindow(dark)
    w.show()
    QtCore.QTimer.singleShot(80, w.fit_to_screen)
    QtCore.QTimer.singleShot(400, w.fit_to_screen)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
