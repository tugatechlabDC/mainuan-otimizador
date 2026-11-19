#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - interface gráfica (Qt)."""
import os
import sys
import json
import time
import glob
import html
import signal
import collections
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402
from i18n import _  # noqa: E402

i18n.set_lang(i18n.detect_lang())  # idioma do sistema, detetado automaticamente

import common as C  # noqa: E402
import core  # noqa: E402
import tweaks  # noqa: E402

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


# =================================================================== Gauge
class Gauge(QtWidgets.QWidget):
    def __init__(self, title, alert=True):
        super().__init__()
        self.title, self.alert, self.value, self.sub = title, alert, None, ""
        self.hist = collections.deque(maxlen=60)
        self.setMinimumSize(190, 250)

    def set_value(self, v, sub):
        self.value, self.sub = v, sub
        if v is not None:
            self.hist.append(v)
        self.update()

    def _color(self):
        v = self.value or 0
        if self.alert and v >= 90:
            return QtGui.QColor(T["DANGER"])
        if self.alert and v >= 70:
            return QtGui.QColor(T["WARN"])
        return QtGui.QColor(T["ACCENT"])

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        R, P = QtCore.QRectF, QtCore.QPointF
        r = R(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QtGui.QPen(QtGui.QColor(T["BORDER"]), 1))
        p.setBrush(QtGui.QColor(T["CARD"]))
        p.drawRoundedRect(r, 16, 16)
        f = p.font()
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QtGui.QColor(T["MUTED"]))
        p.drawText(R(r.left() + 16, r.top() + 10, r.width() - 32, 22), self.title.upper(),
                   QtGui.QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        side = max(60.0, min(r.width() - 44, r.height() - 125))
        arc = R(r.center().x() - side / 2, r.top() + 40, side, side)
        w = max(9.0, side * 0.09)
        pen = QtGui.QPen(QtGui.QColor(T["BORDER"]), w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inner = arc.adjusted(w, w, -w, -w)
        p.drawArc(inner, 225 * 16, -270 * 16)
        if self.value is not None:
            pen.setColor(self._color())
            p.setPen(pen)
            p.drawArc(inner, 225 * 16, int(-270 * 16 * min(100.0, self.value) / 100.0))
        f.setPointSize(max(14, int(side / 7)))
        p.setFont(f)
        p.setPen(QtGui.QColor(T["TEXT"]))
        txt = "N/D" if self.value is None else f"{self.value:.0f}%"
        p.drawText(arc, txt, QtGui.QTextOption(Qt.AlignmentFlag.AlignCenter))
        f.setPointSize(9)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QtGui.QColor(T["MUTED"]))
        opt = QtGui.QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        opt.setWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
        p.drawText(R(r.left() + 10, arc.bottom() + 2, r.width() - 20, 34), self.sub, opt)
        h = R(r.left() + 14, r.bottom() - 44, r.width() - 28, 32)
        if len(self.hist) > 1:
            path = QtGui.QPainterPath()
            for i, v in enumerate(self.hist):
                pt = P(h.left() + h.width() * i / (self.hist.maxlen - 1),
                       h.bottom() - h.height() * min(100.0, v) / 100.0)
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            lp = QtGui.QPen(self._color(), 2)
            lp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(lp)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.end()


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


# ================================================================ Diálogo lista
class PickDialog(QtWidgets.QDialog):
    """Lista de processos + ajustes opcionais (caixas, listas) + escolha de ação."""

    def __init__(self, parent, title, intro, rows, headers, action_text, options=(), choices=(),
                 revert_text=None, tall=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        fit_dialog(self, 880, 780 if options and len(options) > 3 else 560)
        self.rows, self.mode = rows, "apply"
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(label(intro, "muted", True))
        self.table = make_table(["", _("Processo"), "PID"] + list(headers))
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if r.get("checked") else Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, chk)
            self.table.setItem(i, 1, titem(r["name"]))
            self.table.setItem(i, 2, titem(r["pid"]))
            self.table.setItem(i, 3, titem(r["c1"]))
            self.table.setItem(i, 4, titem(r["c2"]))
            self.table.item(i, 1).setToolTip(r.get("cmd", ""))
        self.table.setColumnWidth(0, 34)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 110)
        self.table.setMinimumHeight(110)
        if not tall:
            self.table.setMaximumHeight(200)
        if rows:
            lay.addWidget(self.table, 1 if tall else 0)
        else:
            self.table.hide()
            lay.addWidget(label(_("Não foram encontrados processos adequados."), "muted"))

        self.radios = []
        for i, c in enumerate(choices):
            rb = QtWidgets.QRadioButton(c)
            rb.setChecked(i == 0)
            self.radios.append(rb)
            lay.addWidget(rb)

        self.opts = []  # (dict, checkbox, combo)
        if options:
            head = QtWidgets.QHBoxLayout()
            head.addWidget(label(_("Ajustes adicionais"), "h2"))
            head.addStretch(1)
            b_all = QtWidgets.QPushButton(_("Marcar todos"))
            b_none = QtWidgets.QPushButton(_("Desmarcar todos"))
            b_all.clicked.connect(lambda: self._mark(True))
            b_none.clicked.connect(lambda: self._mark(False))
            head.addWidget(b_all)
            head.addWidget(b_none)
            lay.addLayout(head)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            inner = QtWidgets.QWidget()
            il = QtWidgets.QVBoxLayout(inner)
            il.setSpacing(2)
            for o in options:
                row = QtWidgets.QHBoxLayout()
                cb = QtWidgets.QCheckBox(o["label"])
                cb.setChecked(bool(o.get("default")) and o.get("enabled", True))
                cb.setEnabled(o.get("enabled", True))
                row.addWidget(cb, 1)
                combo = None
                if o.get("combo"):
                    combo = QtWidgets.QComboBox()
                    for val, txt in o["combo"]:
                        combo.addItem(txt, val)
                    combo.setEnabled(o.get("enabled", True))
                    row.addWidget(combo)
                il.addLayout(row)
                d = label(o.get("desc", ""), "muted", True)
                d.setContentsMargins(26, 0, 0, 8)
                il.addWidget(d)
                self.opts.append((o, cb, combo))
            il.addStretch(1)
            scroll.setWidget(inner)
            lay.addWidget(scroll, 1)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        cancel = QtWidgets.QPushButton(_("Cancelar"))
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        if revert_text:
            rv = QtWidgets.QPushButton(revert_text)
            rv.clicked.connect(self._revert)
            row.addWidget(rv)
        ok = QtWidgets.QPushButton(action_text)
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def _mark(self, on):
        for o, cb, _combo in self.opts:
            if cb.isEnabled():
                cb.setChecked(on)

    def _revert(self):
        self.mode = "revert"
        self.accept()

    def selected(self):
        return [self.rows[i] for i in range(len(self.rows))
                if self.table.item(i, 0).checkState() == Qt.CheckState.Checked]

    def option_values(self):
        res = []
        for o, cb, combo in self.opts:
            res.append({"id": o["id"], "checked": cb.isChecked(),
                        "param": combo.currentData() if combo is not None else None})
        return res

    def choice(self):
        for i, rb in enumerate(self.radios):
            if rb.isChecked():
                return i
        return 0


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


# =================================================================== Páginas
class DashboardPage(QtWidgets.QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(label(_("Painel"), "h1"))
        lay.addWidget(label(_("Consumo em tempo real do seu sistema."), "muted"))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(14)
        self.g = {"cpu": Gauge(_("CPU")), "ram": Gauge(_("Memória")),
                  "cache": Gauge(_("Cache"), alert=False), "swap": Gauge(_("Swap"))}
        for i, k in enumerate(("cpu", "ram", "cache", "swap")):
            grid.addWidget(self.g[k], 0, i)
        lay.addLayout(grid, 1)
        box = card()
        bl = QtWidgets.QVBoxLayout(box)
        self.info = label("", None, True)
        bl.addWidget(self.info)
        lay.addWidget(box)
        row = QtWidgets.QHBoxLayout()
        b1 = QtWidgets.QPushButton(_("Otimizar RAM"))
        b2 = QtWidgets.QPushButton(_("Otimizar CPU"))
        for b in (b1, b2):
            b.setObjectName("primary")
            row.addWidget(b)
        row.addStretch(1)
        b1.clicked.connect(lambda: (win.goto(2), win.p_opt.optimize_ram()))
        b2.clicked.connect(lambda: (win.goto(2), win.p_opt.optimize_cpu()))
        lay.addLayout(row)

    def update_data(self, d):
        for k in ("cpu", "ram", "cache", "swap"):
            self.g[k].set_value(d[k], d[k + "_sub"])

    def update_info(self):
        hw = self.win.hw
        sw = [f"{s['name']} ({C.fmt_mb(s['size_kb'] // 1024)})" for s in C.swaps()]
        self.info.setText(
            "<b>" + esc(_("Hardware detetado:")) + "</b> RAM " + esc(C.fmt_mb(hw["ram_mb"])) + " · "
            + esc(_("{n} CPU(s)").format(n=hw["cpus"])) + " · " + esc(C.storage_label(hw))
            + "<br><b>" + esc(_("Swap ativa:")) + "</b> " + (esc(", ".join(sw)) if sw else esc(_("nenhuma"))))


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


class OptimizePage(QtWidgets.QWidget):
    WARN_MSG = property(lambda self: _("A operação terminou, mas alguns passos falharam ou foram cancelados. "
                                        "Consulte o Registo para ver os detalhes."))

    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(label(_("Otimizar"), "h1"))
        lay.addWidget(label(_("Reduza o consumo de RAM e CPU. Nada é fechado sem lhe mostrar primeiro a lista."),
                            "muted", True))
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(14)
        self.buttons, self.icons = [], []
        for kind, title, desc, fn in (
                ("ram", _("Otimizar RAM"),
                 _("Fecha processos inativos que ocupam memória e aplica ajustes extra à sua escolha."),
                 self.optimize_ram),
                ("cpu", _("Otimizar CPU"),
                 _("Baixa a prioridade (ou fecha) processos que consomem muito CPU."), self.optimize_cpu),
                ("globe", _("Otimizar navegador"),
                 _("Reduz o uso de memória e a atividade em segundo plano nos navegadores instalados."),
                 self.optimize_browser)):
            c = card()
            cl = QtWidgets.QVBoxLayout(c)
            cl.setContentsMargins(18, 20, 18, 18)
            cl.setSpacing(10)
            ic = QtWidgets.QLabel()
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icons.append((ic, kind))
            cl.addWidget(ic)
            t = label(title, "h2")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(t)
            d = label(desc, "muted", True)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(d)
            cl.addStretch(1)
            b = QtWidgets.QPushButton(title)
            b.setObjectName("primary")
            b.clicked.connect(fn)
            cl.addWidget(b)
            self.buttons.append(b)
            row.addWidget(c, 1)
        lay.addLayout(row)
        self.status = label("", "muted")
        lay.addWidget(self.status)
        lay.addWidget(label(_("Registo"), "h2"))
        self.log = LogView()
        lay.addWidget(self.log, 1)
        self.on_theme()

    def on_theme(self):
        for ic, kind in self.icons:
            ic.setPixmap(draw_pixmap(kind, T["ACCENT"], 52))
        self.log.render()

    def busy(self, on, text=""):
        for b in self.buttons:
            b.setEnabled(not on)
        self.status.setText(text)

    def say(self, msg, kind="info"):
        self.log.add(msg, kind)

    # ----- RAM
    def optimize_ram(self):
        self.busy(True, _("A analisar processos (3 segundos)…"))
        self.win.run_task(self._analyse_ram, (), self._ram_ready)

    @staticmethod
    def _analyse_ram():
        s = core.ProcSampler()
        s.sample()
        time.sleep(3)
        procs = s.sample()
        win = core.window_pids()
        return {"cands": core.ram_candidates(procs, win), "win_ok": win is not None}

    def _ram_ready(self, res):
        self.busy(False)
        if isinstance(res, Exception):
            self.say(_("Erro:") + f" {res}", "err")
            return
        rows = [{"pid": p["pid"], "name": p["name"], "c1": f"{p['rss_kb'] // 1024} MiB",
                 "c2": f"{p['cpu']:.1f}%", "cmd": p["cmd"], "checked": p["checked"]} for p in res["cands"]]
        if res["win_ok"]:
            intro = _("Processos seus, sem janela aberta, inativos e com muita RAM. "
                      "Foram pré-selecionados; desmarque o que quiser manter.")
        else:
            intro = _("Não é possível saber que processos têm janela aberta (sessão Wayland ou sem 'wmctrl'). "
                      "Por segurança nenhum está pré-selecionado: marque só o que sabe que não precisa. "
                      "Trabalho não guardado nesses programas pode perder-se.")
        tweaks.HW = self.win.hw
        options = []
        for t in tweaks.TWEAKS:
            ok, reason = t.avail()
            options.append({"id": t.id, "label": _(t.label), "desc": _(t.desc) if ok else _(reason),
                            "default": t.default, "enabled": ok,
                            "combo": [(v, _(l)) for v, l in t.combo] if t.combo else None})
        dlg = PickDialog(self, _("Otimizar RAM"), intro, rows, (_("RAM"), _("CPU")), _("Aplicar"),
                         options=options, revert_text=_("Reverter ajustes selecionados"))
        if not dlg.exec():
            return
        opts = [(o["id"], o["param"]) for o in dlg.option_values() if o["checked"]]
        if dlg.mode == "revert":
            opts = [(i, p) for i, p in opts if tweaks.BY_ID[i].revert is not None]
            if not opts:
                notify(self, _("Nada selecionado"), _("Nada foi selecionado para otimizar."), ok=False)
                return
            self._ram_mode = "revert"
            self.busy(True, _("A reverter ajustes…"))
            self.win.run_task(self._do_ram, ([], opts, "revert"), self._ram_done)
            return
        sel = dlg.selected()
        if not sel and not opts:
            notify(self, _("Nada selecionado"), _("Nada foi selecionado para otimizar."), ok=False)
            return
        self._ram_mode = "apply"
        self.busy(True, _("A otimizar a RAM…"))
        self.win.run_task(self._do_ram, (sel, opts, "apply"), self._ram_done)

    @staticmethod
    def _do_ram(sel, opts, mode):
        before = C.meminfo().get("MemAvailable", 0)
        log = []
        if sel:
            log.append(("head", _("Fechar processos inativos")))
        for p in sel:
            if not core.same_process(p["pid"], p["name"]):
                continue
            try:
                os.kill(p["pid"], signal.SIGTERM)
                log.append(("cmd", f"$ kill -TERM {p['pid']}  ({p['name']})"))
                log.append(("ok", _("Pedido de fecho enviado a {n} (PID {p})").format(n=p["name"], p=p["pid"])))
            except OSError as e:
                log.append(("err", _("Não foi possível fechar {n}: {e}").format(n=p["name"], e=e.strerror)))
        if sel:
            time.sleep(2.5)
        if opts:
            log += tweaks.run_selected(opts, mode)
        after = C.meminfo().get("MemAvailable", 0)
        return log, before, after

    def _ram_done(self, res):
        self.busy(False)
        if isinstance(res, Exception):
            self.say(_("Erro:") + f" {res}", "err")
            return
        log, before, after = res
        self.log.add_many(log)
        self.say(_("Memória disponível: {a} MiB → {b} MiB ({d:+d} MiB)").format(
            a=before // 1024, b=after // 1024, d=(after - before) // 1024), "head")
        self.win.refresh_hw()
        if any(k == "err" for k, _t in log):
            notify(self, _("Concluído com avisos"), self.WARN_MSG, ok=False)
        elif getattr(self, "_ram_mode", "apply") == "revert":
            notify(self, _("Ajustes revertidos"),
                   _("Os ajustes selecionados foram revertidos. Recomendamos reiniciar o sistema."))
        else:
            notify(self, _("RAM otimizada"),
                   _("A otimização da RAM foi concluída. Memória disponível: {a} MiB → {b} MiB. "
                     "Recomendamos reiniciar o sistema.").format(a=before // 1024, b=after // 1024))

    # ----- CPU
    def optimize_cpu(self):
        self.busy(True, _("A medir o consumo de CPU (3 segundos)…"))
        self.win.run_task(self._analyse_cpu, (), self._cpu_ready)

    @staticmethod
    def _analyse_cpu():
        s = core.ProcSampler()
        s.sample()
        time.sleep(3)
        return core.cpu_candidates(s.sample())

    def _cpu_ready(self, res):
        self.busy(False)
        if isinstance(res, Exception):
            self.say(_("Erro:") + f" {res}", "err")
            return
        rows = [{"pid": p["pid"], "name": p["name"], "c1": f"{p['cpu']:.0f}%",
                 "c2": f"{p['rss_kb'] // 1024} MiB", "cmd": p["cmd"], "checked": True} for p in res]
        intro = _("Processos seus com consumo de CPU elevado. Baixar a prioridade não fecha nada: "
                  "apenas dá preferência ao resto do sistema.")
        has_gov = bool(glob.glob("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"))
        opts = [{"id": "gov", "label": _("Ativar modo de poupança de CPU (governor powersave, pede palavra-passe)"),
                 "desc": "", "default": False, "enabled": True}] if has_gov else []
        dlg = PickDialog(self, _("Otimizar CPU"), intro, rows, (_("CPU"), _("RAM")), _("Aplicar"),
                         options=opts, tall=True,
                         choices=(_("Baixar a prioridade (recomendado)"), _("Fechar os processos")))
        if not dlg.exec():
            return
        sel, close = dlg.selected(), dlg.choice() == 1
        gov = bool(opts) and dlg.option_values()[0]["checked"]
        if not sel and not gov:
            if not rows:
                self.say(_("Otimização de CPU concluída."), "head")
                notify(self, _("CPU otimizado"),
                       _("Não há processos com consumo de CPU elevado neste momento; o CPU já está equilibrado. "
                         "Recomendamos reiniciar o sistema para aplicar totalmente os ajustes."))
            else:
                notify(self, _("Nada selecionado"), _("Nada foi selecionado para otimizar."), ok=False)
            return
        self.busy(True, _("A otimizar o CPU…"))
        self.win.run_task(self._do_cpu, (sel, close, gov), self._cpu_done)

    @staticmethod
    def _do_cpu(sel, close, gov):
        log = []
        for p in sel:
            if not core.same_process(p["pid"], p["name"]):
                continue
            if close:
                try:
                    os.kill(p["pid"], signal.SIGTERM)
                    log.append(("ok", _("Pedido de fecho enviado a {n} (PID {p})").format(n=p["name"], p=p["pid"])))
                except OSError as e:
                    log.append(("err", _("Não foi possível fechar {n}: {e}").format(n=p["name"], e=e.strerror)))
            else:
                n = core.lower_priority(p["pid"])
                log.append(("ok", _("Prioridade baixada: {n} (PID {p}, {t} threads)").format(
                    n=p["name"], p=p["pid"], t=n)))
        if gov:
            rc, out = core.run_helper("governor", "powersave")
            log.append(("ok" if rc == 0 else "err", out or _("Governor alterado.")))
        return log

    def _cpu_done(self, res):
        self.busy(False)
        if isinstance(res, Exception):
            self.say(_("Erro:") + f" {res}", "err")
            return
        self.log.add_many(res)
        self.say(_("Otimização de CPU concluída."), "head")
        if any(k == "err" for k, _t in res):
            notify(self, _("Concluído com avisos"), self.WARN_MSG, ok=False)
        else:
            notify(self, _("CPU otimizado"),
                   _("A otimização do CPU foi concluída. Recomendamos reiniciar o sistema "
                     "para aplicar totalmente os ajustes."))

    # ----- Navegador
    def optimize_browser(self):
        BrowserDialog(self).exec()


class BrowserDialog(QtWidgets.QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setWindowTitle(_("Otimizar navegador"))
        fit_dialog(self, 680, 560)
        lay = QtWidgets.QVBoxLayout(self)
        self.ff = core.firefox_profiles()
        self.has_ch = bool(C.chromium_installed())
        found = core.detect_browsers()
        ram = core.browser_ram_kb()
        lay.addWidget(label(_("Memória usada agora pelos navegadores: <b>{x}</b>").format(x=core.size_kb(ram)),
                            None, True))
        lay.addWidget(label(_("Navegadores instalados:"), "h2"))
        if found:
            txt = "<br>".join(("✔ " if ok else "✖ ") + esc(n) + ("" if ok else " — " + esc(_("sem suporte")))
                              for n, ok in found)
        else:
            txt = esc(_("nenhum encontrado"))
        lay.addWidget(label(txt, None, True))
        self.cb_mem = QtWidgets.QCheckBox(_("Ativar a poupança de memória em todos os navegadores instalados"))
        self.cb_mem.setChecked(True)
        f = self.cb_mem.font()
        f.setBold(True)
        self.cb_mem.setFont(f)
        lay.addWidget(self.cb_mem)
        d = label(_("Aplicado automaticamente a todos: descarrega separadores inativos, limita processos e cache "
                    "(Firefox) e ativa o «Modo de poupança de memória» (Chrome, Chromium, Brave, Edge)."),
                  "muted", True)
        d.setContentsMargins(26, 0, 0, 6)
        lay.addWidget(d)
        self.cb_gen = QtWidgets.QCheckBox(_("Reduzir atividade em segundo plano e telemetria"))
        self.cb_gen.setChecked(True)
        lay.addWidget(self.cb_gen)
        d2 = label(_("Desliga pré-carregamento de páginas, execução em segundo plano e envio de estatísticas. "
                     "O navegador pode mostrar «gerido pela sua organização»."), "muted", True)
        d2.setContentsMargins(26, 0, 0, 6)
        lay.addWidget(d2)
        lay.addWidget(label(_("Feche e volte a abrir o navegador para as alterações terem efeito."), "muted", True))
        self.log = LogView()
        lay.addWidget(self.log, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.b_rev = QtWidgets.QPushButton(_("Reverter"))
        self.b_ok = QtWidgets.QPushButton(_("Aplicar"))
        self.b_ok.setObjectName("primary")
        b_close = QtWidgets.QPushButton(_("Fechar"))
        self.b_rev.clicked.connect(lambda: self.go(False))
        self.b_ok.clicked.connect(lambda: self.go(True))
        b_close.clicked.connect(self.accept)
        for b in (self.b_rev, self.b_ok, b_close):
            row.addWidget(b)
        lay.addLayout(row)

    def go(self, apply):
        parts = []
        if self.cb_mem.isChecked():
            parts.append("memory")
        if self.cb_gen.isChecked():
            parts.append("general")
        if apply and not parts:
            self.log.add(_("Selecione pelo menos uma opção."), "err")
            return
        self._apply = apply
        self.b_ok.setEnabled(False)
        self.b_rev.setEnabled(False)
        self.page.win.run_task(self._do, (apply, parts, list(self.ff), self.has_ch), self._done)

    @staticmethod
    def _do(apply, parts, ff, has_ch):
        log = []
        for p in ff:
            try:
                if apply:
                    core.firefox_apply(p, parts)
                    log.append(("ok", _("Firefox otimizado: {p}").format(p=p)))
                else:
                    core.firefox_remove(p)
                    log.append(("ok", _("Firefox revertido: {p}").format(p=p)))
            except OSError as e:
                log.append(("err", _("Erro:") + f" {p}: {e.strerror}"))
        if (apply and has_ch) or (not apply and any(
                os.path.exists(os.path.join(d, C.POLICY_FILE)) for _n, _b, ds in C.CHROMIUM_TARGETS for d in ds)):
            log.append(("cmd", _("A pedir autorização para as políticas dos navegadores…")))
            if apply:
                rc, out = core.run_helper("browser-policy", "apply", ",".join(parts))
            else:
                rc, out = core.run_helper("browser-policy", "remove")
            for line in (out or "").splitlines():
                if line.strip() and line.strip() != "OK":
                    log.append(("err" if line.strip().startswith(("!", "Erro", "Error")) else "info", line.strip()))
            log.append(("ok" if rc == 0 else "err", _("Concluído.") if rc == 0 else _("Cancelado ou sem autorização.")))
        elif not log:
            log.append(("info", _("Nada para alterar.")))
        return log

    def _done(self, res):
        self.b_ok.setEnabled(True)
        self.b_rev.setEnabled(True)
        if isinstance(res, Exception):
            self.log.add(_("Erro:") + f" {res}", "err")
        else:
            self.log.add_many(res)
            if getattr(self, "_apply", False):
                if any(k == "err" for k, _t in res):
                    notify(self, _("Concluído com avisos"), self.page.WARN_MSG, ok=False)
                else:
                    notify(self, _("Navegador otimizado"),
                           _("A otimização do navegador foi concluída. Se o navegador estiver aberto, "
                             "feche-o e abra-o novamente para aplicar as alterações."))


class StartupPage(QtWidgets.QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.items = []
        self.shown = []
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(label(_("Arranque do sistema"), "h1"))
        lay.addWidget(label(_("Programas e serviços que iniciam sozinhos. Desative ou elimine o que não utiliza. "
                              "Tudo o que desativar pode ser reativado."), "muted", True))
        top = QtWidgets.QHBoxLayout()
        self.flt = QtWidgets.QComboBox()
        self.flt.addItems([_("Todos"), _("Aplicações da sessão"), _("Serviços do utilizador"),
                           _("Serviços do sistema")])
        self.cb_prot = QtWidgets.QCheckBox(_("Mostrar serviços essenciais (protegidos)"))
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Pesquisar…"))
        top.addWidget(self.flt)
        top.addWidget(self.search, 1)
        top.addWidget(self.cb_prot)
        lay.addLayout(top)
        self.table = make_table([_("Nome"), _("Tipo"), _("Estado"), _("Descrição / comando")])
        self.table.setColumnWidth(0, 230)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 150)
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        self.b_dis = QtWidgets.QPushButton(_("Desativar"))
        self.b_dis.setObjectName("primary")
        self.b_en = QtWidgets.QPushButton(_("Reativar"))
        self.b_del = QtWidgets.QPushButton(_("Eliminar"))
        self.b_del.setObjectName("danger")
        b_ref = QtWidgets.QPushButton(_("Atualizar"))
        for b in (self.b_dis, self.b_en, self.b_del):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_ref)
        lay.addLayout(row)
        self.msg = label("", "muted", True)
        lay.addWidget(self.msg)
        self.flt.currentIndexChanged.connect(self.fill)
        self.cb_prot.toggled.connect(self.fill)
        self.search.textChanged.connect(self.fill)
        self.b_dis.clicked.connect(lambda: self.act("disable"))
        self.b_en.clicked.connect(lambda: self.act("enable"))
        self.b_del.clicked.connect(lambda: self.act("delete"))
        b_ref.clicked.connect(self.reload)

    def kind_name(self, k):
        return {"xdg": _("Aplicação da sessão"), "usr": _("Serviço do utilizador"),
                "sys": _("Serviço do sistema")}[k]

    def reload(self):
        self.msg.setText(_("A carregar…"))
        self.win.run_task(core.list_startup, (), self._loaded)

    def _loaded(self, res):
        if isinstance(res, Exception):
            self.msg.setText(_("Erro:") + f" {res}")
            return
        self.items = res
        self.msg.setText("")
        self.fill()

    def fill(self, *_a):
        want = ["", "xdg", "usr", "sys"][self.flt.currentIndex()]
        q = self.search.text().lower().strip()
        self.shown = [i for i in self.items
                      if (not want or i["kind"] == want) and (self.cb_prot.isChecked() or not i["protected"])
                      and (not q or q in (i["name"] + " " + i["desc"]).lower())]
        self.table.setRowCount(len(self.shown))
        for r, i in enumerate(self.shown):
            self.table.setItem(r, 0, titem(i["name"] + ("  🔒" if i["protected"] else "")))
            self.table.setItem(r, 1, titem(self.kind_name(i["kind"])))
            st = titem(i["state"])
            st.setForeground(QtGui.QColor(T["OK"] if i["enabled"] else T["MUTED"]))
            self.table.setItem(r, 2, st)
            self.table.setItem(r, 3, titem(i["desc"]))

    def selection(self):
        rows = sorted({ix.row() for ix in self.table.selectionModel().selectedRows()})
        return [self.shown[r] for r in rows if r < len(self.shown)]

    def act(self, what):
        sel = self.selection()
        if not sel:
            self.msg.setText(_("Selecione primeiro uma ou mais linhas."))
            return
        sel = [i for i in sel if not i["protected"]]
        if not sel:
            self.msg.setText(_("Os serviços essenciais estão protegidos e não podem ser alterados."))
            return
        if what == "delete":
            nomes = "\n".join("• " + i["name"] for i in sel[:12])
            if not ask(self, _("Eliminar"),
                       _("Eliminar do arranque?") + f"\n\n{nomes}\n\n"
                       + _("Aplicações da sessão do utilizador são apagadas; serviços são desativados e "
                           "mascarados (reversível com «Reativar»).")):
                return
        self.msg.setText(_("A aplicar…"))
        self.win.run_task(self._do, (what, sel), self._done)

    @staticmethod
    def _do(what, sel):
        msgs = []
        state = core._load_state()
        for i in sel:
            k, u = i["kind"], i["id"]
            try:
                if k == "xdg":
                    if what == "disable":
                        core.xdg_disable(i)
                    elif what == "enable":
                        core.xdg_enable(i)
                    else:
                        msgs.append(core.xdg_delete(i))
                elif k == "usr":
                    rec = state.setdefault("usr", {})
                    if what == "disable":
                        C.run(["systemctl", "--user", "disable", "--now", u])
                        rec[u] = "disabled"
                    elif what == "enable":
                        C.run(["systemctl", "--user", "unmask", u])
                        C.run(["systemctl", "--user", "enable", "--now", u])
                        rec.pop(u, None)
                    else:
                        rec[u] = core.user_unit_delete(u)
                        if rec[u] == "eliminado":
                            rec.pop(u)
                else:
                    rec = state.setdefault("sys", {})
                    act = {"disable": "disable", "enable": "enable", "delete": "mask"}[what]
                    rc, out = core.run_helper("service", act, u)
                    if rc != 0:
                        msgs.append(f"{u}: {out}")
                        continue
                    if what == "enable":
                        rec.pop(u, None)
                    else:
                        rec[u] = "masked" if what == "delete" else "disabled"
            except OSError as e:
                msgs.append(f"{i['name']}: {e.strerror}")
        core.save_state(state)
        return msgs

    def _done(self, res):
        if isinstance(res, Exception):
            self.msg.setText(_("Erro:") + f" {res}")
        else:
            self.msg.setText(" ".join(res) if res else _("Concluído."))
        self.reload()


class ProcessPage(QtWidgets.QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.sampler = core.ProcSampler()
        self.procs = []
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(label(_("Processos em curso"), "h1"))
        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Pesquisar por nome ou comando…"))
        self.only_me = QtWidgets.QCheckBox(_("Só os meus"))
        self.only_me.setChecked(True)
        top.addWidget(self.search, 1)
        top.addWidget(self.only_me)
        lay.addLayout(top)
        self.table = make_table([_("Nome"), "PID", _("Utilizador"), _("CPU %"), _("RAM (MiB)"), _("Comando")])
        for c, w in enumerate((200, 70, 100, 80, 100)):
            self.table.setColumnWidth(c, w)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        b1 = QtWidgets.QPushButton(_("Terminar"))
        b1.setObjectName("primary")
        b2 = QtWidgets.QPushButton(_("Forçar fecho"))
        b2.setObjectName("danger")
        b3 = QtWidgets.QPushButton(_("Baixar prioridade"))
        for b in (b1, b3, b2):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.msg = label("", "muted", True)
        lay.addWidget(self.msg)
        b1.clicked.connect(lambda: self.kill("TERM"))
        b2.clicked.connect(lambda: self.kill("KILL"))
        b3.clicked.connect(self.renice)

    def refresh(self):
        self.procs = self.sampler.sample()
        q = self.search.text().lower().strip()
        me = os.getuid()
        rows = [p for p in self.procs if (not self.only_me.isChecked() or p["uid"] == me)
                and (not q or q in (p["name"] + " " + p["cmd"]).lower())]
        keep = {ix.sibling(ix.row(), 1).data() for ix in self.table.selectionModel().selectedRows()}
        hs = self.table.horizontalHeader()
        sc, so = hs.sortIndicatorSection(), hs.sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            self.table.setItem(r, 0, titem(p["name"]))
            self.table.setItem(r, 1, titem("", p["pid"]))
            self.table.setItem(r, 2, titem(core.uname(p["uid"])))
            self.table.setItem(r, 3, titem("", round(p["cpu"], 1)))
            self.table.setItem(r, 4, titem("", p["rss_kb"] // 1024))
            self.table.setItem(r, 5, titem(p["cmd"][:200]))
        self.table.setSortingEnabled(True)
        self.table.sortItems(sc if sc >= 0 else 3, so if sc >= 0 else Qt.SortOrder.DescendingOrder)
        if keep:
            last = self.table.columnCount() - 1
            for r in range(self.table.rowCount()):
                if self.table.item(r, 1).data(Qt.ItemDataRole.DisplayRole) in keep:
                    self.table.setRangeSelected(QtWidgets.QTableWidgetSelectionRange(r, 0, r, last), True)

    def selected(self):
        res = []
        for ix in self.table.selectionModel().selectedRows():
            pid = self.table.item(ix.row(), 1).data(Qt.ItemDataRole.DisplayRole)
            name = self.table.item(ix.row(), 0).text()
            res.append((int(pid), name))
        return res

    def kill(self, sig):
        sel = self.selected()
        if not sel:
            self.msg.setText(_("Selecione um processo."))
            return
        bad = [n for _p, n in sel if C.is_protected_name(n)]
        if bad:
            self.msg.setText(_("Processo(s) essenciais protegidos:") + " " + ", ".join(bad))
            return
        txt = "\n".join(f"• {n} (PID {p})" for p, n in sel[:10])
        head = _("Forçar o fecho de:") if sig == "KILL" else _("Terminar:")
        if not ask(self, _("Confirmar"), f"{head}\n\n{txt}"):
            return
        msgs = []
        for pid, name in sel:
            try:
                if not core.same_process(pid, name):
                    continue
                os.kill(pid, signal.SIGTERM if sig == "TERM" else signal.SIGKILL)
            except PermissionError:
                rc, out = core.run_helper("terminate", pid, sig)
                if rc != 0:
                    msgs.append(f"{name}: {out}")
            except OSError as e:
                msgs.append(f"{name}: {e.strerror}")
        self.msg.setText(" ".join(msgs) if msgs else _("Pedido enviado."))

    def renice(self):
        n = 0
        for pid, name in self.selected():
            if core.same_process(pid, name):
                n += core.lower_priority(pid)
        self.msg.setText(_("Prioridade baixada ({n} threads).").format(n=n) if n else
                         _("Só é possível baixar a prioridade dos seus próprios processos."))


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
                    _("Gestão de swap, zram e zswap, otimização de RAM, CPU e navegador,"),
                    _("monitorização em tempo real e controlo do arranque do sistema.")):
            l = label(txt, "muted")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(l)


# ============================================================ Janela principal
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dark):
        super().__init__()
        self.setWindowTitle(C.APP_NAME)
        self.dark = dark
        self.monitor = core.Monitor()
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
        self.p_dash = DashboardPage(self)
        self.p_mem = MemoryPage(self)
        self.p_opt = OptimizePage(self)
        self.p_start = StartupPage(self)
        self.p_proc = ProcessPage(self)
        pages = [(_("Painel"), "gauge", self.p_dash, 560), (_("Memória"), "ram", self.p_mem, 800),
                 (_("Otimizar"), "bolt", self.p_opt, 640), (_("Arranque"), "power", self.p_start, 540),
                 (_("Processos"), "list", self.p_proc, 540), (_("Acerca"), "info", AboutPage(), 0)]
        self.nav = []
        for i, (txt, ic, page, min_h) in enumerate(pages):
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
            self.stack.addWidget(scroll_wrap(page, min_h))
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
        self.p_dash.update_info()
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
        self.p_opt.on_theme()
        self.p_start.fill()
        for g in self.p_dash.g.values():
            g.update()

    def check_theme(self):
        dark = detect_dark()
        if dark != self.dark:
            self.dark = dark
            set_theme(dark)
            self.restyle()

    def goto(self, n):
        self.nav[n].setChecked(True)
        self.stack.setCurrentIndex(n)
        if n == 3 and not self.p_start.items:
            self.p_start.reload()
        if n == 4:
            self.p_proc.refresh()
        if n == 1:
            self.p_mem.refresh_ui()
            self.p_mem.refresh_status()

    def refresh_hw(self):
        self.hw = C.hardware()
        self.p_dash.update_info()
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
        self.p_dash.update_data(self.monitor.snapshot())
        if self.tick_n % 3 == 0:
            self.check_theme()
        i = self.stack.currentIndex()
        if i == 0 and self.tick_n % 5 == 0:
            self.p_dash.update_info()
        elif i == 1 and self.tick_n % 3 == 0:
            self.p_mem.refresh_status()
        elif i == 4 and self.tick_n % 3 == 0:
            self.p_proc.refresh()


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
