# -*- coding: utf-8 -*-
"""MAINUAN OTIMIZADOR - páginas de gestão do sistema (Resumo, Serviços, Diagnóstico,
Otimização, Análise de arranque, Histórico). Usa o tema, as cores e os ícones da app principal."""
import os
import time

import i18n
from i18n import _
import sysmgr as S

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:  # alternativa: PyQt5
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt

A = None  # módulo da app principal (tema, widgets base); ligado por bind()


def bind(app_module):
    global A
    A = app_module


def col(key):
    return A.T[key]


def rgba(hexcol, alpha):
    c = QtGui.QColor(hexcol)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


# ------------------------------------------------------------------ formatação
def fmt_bytes(b):
    if b is None:
        return "—"
    if b >= 1 << 30:
        return f"{b / (1 << 30):.1f} GiB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.0f} MiB"
    return f"{b / 1024:.0f} KiB"


def fmt_ms(ms):
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{int(ms)} ms"
    if ms < 60000:
        return f"{ms / 1000:.1f} s"
    m = int(ms // 60000)
    return f"{m} min {(ms - m * 60000) / 1000:.0f} s"


def fmt_uptime(sec):
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    if d:
        return f"{d} d {h} h"
    if h:
        return f"{h} h {m} min"
    return f"{m} min"


def fmt_time(ts):
    t = time.localtime(ts)
    now = time.localtime()
    hm = time.strftime("%H:%M", t)
    if t[:3] == now[:3]:
        return _("hoje") + " " + hm
    if t[:3] == time.localtime(time.time() - 86400)[:3]:
        return _("ontem") + " " + hm
    return time.strftime("%d/%m %H:%M", t)


def fmt_interval(secs):
    if secs is None:
        return ""
    if secs < 90:
        return f"{int(secs)} s"
    if secs < 5400:
        return f"{round(secs / 60)} min"
    return f"{secs / 3600:.1f} h"


def share_tone(frac):
    return "DANGER" if frac >= 0.5 else ("WARN" if frac >= 0.25 else "OK")


def action_label(a):
    return {"start": _("Iniciar"), "stop": _("Parar"), "restart": _("Reiniciar"),
            "enable": _("Ativar no arranque"), "disable": _("Desativar no arranque"),
            "enable-now": _("Ativar e iniciar"), "disable-now": _("Parar e desativar"),
            "package-reinstall": _("Reinstalar o pacote"), "package-install": _("Instalar o pacote"),
            "dpkg-configure": _("Terminar a configuração dos pacotes"),
            "apt-fix-broken": _("Reparar dependências em falta"), "remove-link": _("Remover ligação quebrada"),
            "remove-autostart": _("Remover serviço órfão"),
            "add-journal-group": _("Permitir ler o histórico de arranques")}.get(a, a)


def state_label(s):
    return {"active": _("Ativo"), "inactive": _("Inativo"), "failed": _("Falhou"), "activating": _("A iniciar"),
            "deactivating": _("A parar"), "reloading": _("A recarregar"),
            "maintenance": _("Manutenção")}.get(s, s)


def boot_label(s):
    return {"enabled": _("Ativado"), "enabled-runtime": _("Ativado"), "disabled": _("Desativado"),
            "static": _("Estático"), "masked": _("Mascarado"), "indirect": _("Indireto"),
            "generated": _("Gerado"), "alias": _("Alias"), "transient": _("Transitório")}.get(s, s)


def step_err(msg):
    return _("Cancelado") if msg == "cancelled" else msg


# ------------------------------------------------------------------ widgets comuns
def plain(layout_cls=None):
    w = QtWidgets.QWidget()
    w.setObjectName("plain")
    if layout_cls:
        lay = layout_cls(w)
        lay.setContentsMargins(0, 0, 0, 0)
        return w, lay
    return w


def clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear(it.layout())


def lbl(text="", name=None, wrap=False, rich=False):
    l = A.label(text, name, wrap)
    if rich:
        l.setTextFormat(Qt.TextFormat.RichText)
    return l


def chip(text, tone="MUTED"):
    l = QtWidgets.QLabel(text)
    c = col(tone)
    l.setStyleSheet(f"QLabel {{ background: {rgba(c, 0.16)}; color: {c}; border-radius: 9px; "
                    f"padding: 1px 9px; font-size: 8pt; font-weight: bold; }}")
    l.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
    return l


def small_btn(text, name=None):
    b = QtWidgets.QPushButton(text)
    b.setObjectName(name or "small")
    return b


def link_btn(text, cb):
    b = QtWidgets.QPushButton(text)
    b.setObjectName("link")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(lambda _c=False: cb())
    return b


def tcard(title=None, link=None, cb=None):
    """Cartão com título em maiúsculas e ligação opcional. Devolve (frame, layout do corpo)."""
    f = A.card()
    v = QtWidgets.QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(8)
    if title:
        row = QtWidgets.QHBoxLayout()
        row.addWidget(lbl(title.upper(), "cardtitle"))
        row.addStretch(1)
        if link:
            row.addWidget(link_btn(link, cb))
        v.addLayout(row)
    return f, v


class Bar(QtWidgets.QWidget):
    def __init__(self, frac=0.0, tone="ACCENT", height=8):
        super().__init__()
        self.frac, self.tone = frac, tone
        self.setFixedHeight(height)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def set(self, frac, tone=None):
        self.frac = max(0.0, min(1.0, frac))
        if tone:
            self.tone = tone
        self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect())
        rad = r.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(col("BORDER")))
        p.drawRoundedRect(r, rad, rad)
        if self.frac > 0:
            w = max(r.height(), r.width() * self.frac)
            p.setBrush(QtGui.QColor(col(self.tone)))
            p.drawRoundedRect(QtCore.QRectF(r.left(), r.top(), w, r.height()), rad, rad)
        p.end()


class StackBar(QtWidgets.QWidget):
    """Barra dividida em partes (fases do arranque)."""

    def __init__(self, parts, total):
        super().__init__()
        self.parts, self.total = parts, max(1, total)
        self.setFixedHeight(12)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect())
        path = QtGui.QPainterPath()
        path.addRoundedRect(r, 6, 6)
        p.setClipPath(path)
        p.fillRect(r, QtGui.QColor(col("BORDER")))
        x = r.left()
        for ms in self.parts:
            w = r.width() * ms / self.total
            p.fillRect(QtCore.QRectF(x, r.top(), max(1.0, w - 1), r.height()), QtGui.QColor(col(share_tone(ms / self.total))))
            x += w
        p.end()


class Donut(QtWidgets.QWidget):
    def __init__(self, value=100.0):
        super().__init__()
        self.value = value
        self.setFixedSize(96, 96)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(9, 9, -9, -9)
        pen = QtGui.QPen(QtGui.QColor(col("BORDER")), 9)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(r, 90 * 16, -360 * 16)
        tone = "OK" if self.value >= 90 else ("WARN" if self.value >= 60 else "DANGER")
        pen.setColor(QtGui.QColor(col(tone)))
        p.setPen(pen)
        p.drawArc(r, 90 * 16, int(-360 * 16 * self.value / 100.0))
        f = p.font()
        f.setPointSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QtGui.QColor(col("TEXT")))
        p.drawText(QtCore.QRectF(self.rect()), f"{self.value:.0f}", QtGui.QTextOption(Qt.AlignmentFlag.AlignCenter))
        p.end()


def bar_row(name, frac, right, tone="ACCENT", name_w=130, right_w=70):
    w, h = plain(QtWidgets.QHBoxLayout)
    h.setSpacing(10)
    n = lbl(name)
    n.setFixedWidth(name_w)
    n.setToolTip(name)
    n.setText(QtGui.QFontMetrics(n.font()).elidedText(name, Qt.TextElideMode.ElideRight, name_w))
    h.addWidget(n)
    h.addWidget(Bar(frac, tone), 1)
    r = lbl(right, "muted")
    r.setFixedWidth(right_w)
    r.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    h.addWidget(r)
    return w


def kv_rows(layout, rows):
    g = QtWidgets.QGridLayout()
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(6)
    for i, (k, v) in enumerate(rows):
        g.addWidget(lbl(k, "muted"), i, 0, Qt.AlignmentFlag.AlignTop)
        val = lbl(str(v), None, True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        g.addWidget(val, i, 1)
    g.setColumnStretch(1, 1)
    layout.addLayout(g)


def empty_note(text):
    l = lbl(text, "muted", True)
    l.setAlignment(Qt.AlignmentFlag.AlignCenter)
    l.setContentsMargins(0, 18, 0, 18)
    return l


def fit_combo(cb):
    """Largura suficiente para mostrar o texto completo de todas as opções (caixa e lista)."""
    fm = cb.fontMetrics()
    w = max([fm.horizontalAdvance(cb.itemText(i)) for i in range(cb.count())] + [60])
    cb.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
    cb.setMinimumWidth(w + 64)
    cb.view().setMinimumWidth(w + 40)
    return cb


class WaitBanner(QtWidgets.QFrame):
    """Aviso «Por favor aguarde» com barra de progresso, mostrado enquanto a página lê o sistema."""

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(6)
        self.title = lbl(_("Por favor aguarde…").upper(), "h2")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail = lbl("", "muted", True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        v.addWidget(self.title)
        v.addWidget(self.detail)
        v.addWidget(self.bar)
        self.hide()

    def start(self, text):
        self.detail.setText(text)
        self.show()

    def stop(self):
        self.hide()


class NotesDialog(QtWidgets.QDialog):
    """Notas da página: o que é, como usar e o que convém saber (antigo painel de notas)."""

    def __init__(self, parent, title, what, steps, know):
        super().__init__(parent)
        self.setWindowTitle(title)
        A.fit_dialog(self, 640, 560)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        head = QtWidgets.QHBoxLayout()
        ic = QtWidgets.QLabel()
        ic.setPixmap(A.draw_pixmap("info", col("ACCENT"), 34))
        head.addWidget(ic)
        head.addWidget(lbl(title.upper(), "h2"))
        head.addStretch(1)
        lay.addLayout(head)
        tb = QtWidgets.QTextBrowser()
        body = [A.section(_("O que é")), f"<div>{A.esc(what)}</div>", A.section(_("Como usar"))]
        body.append("".join(f'<div style="margin-bottom:4px"><b style="color:{col("ACCENT")}">{i}.</b> {A.esc(s)}</div>'
                            for i, s in enumerate(steps, 1)))
        body += [A.section(_("Convém saber")), f"<div>{A.esc(know)}</div>"]
        tb.setHtml(A.page_html("".join(body)))
        lay.addWidget(tb, 1)
        b = QtWidgets.QPushButton(_("Fechar"))
        b.setObjectName("primary")
        b.setMinimumWidth(150)
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)


class SysPage(QtWidgets.QWidget):
    """Base: barra de ferramentas (sem faixa de título), carregamento em segundo plano e notas."""
    STALE_SECS = 60

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.loaded_at = 0
        self.busy = False
        self.lay = QtWidgets.QVBoxLayout(self)
        self.lay.setContentsMargins(24, 20, 24, 20)
        self.lay.setSpacing(12)
        self.tool = QtWidgets.QHBoxLayout()
        self.tool.setSpacing(8)
        self.lay.addLayout(self.tool)
        self.wait = WaitBanner()
        self.lay.addWidget(self.wait)
        self.keep_wait = False
        self.b_reload = QtWidgets.QPushButton(_("Atualizar"))
        self.b_reload.clicked.connect(lambda _c=False: self.reload(True))
        self.b_info = QtWidgets.QPushButton(_("Mais informações"))
        self.b_info.setIconSize(QtCore.QSize(20, 20))
        self.b_info.clicked.connect(lambda _c=False: self.show_notes())

    def finish_toolbar(self):
        self.tool.addStretch(1)
        self.tool.addWidget(self.b_reload)
        self.tool.addWidget(self.b_info)

    def notes(self):
        return None

    def show_notes(self):
        n = self.notes()
        if n:
            NotesDialog(self, *n).exec()

    def on_theme(self):
        self.b_info.setIcon(A.make_icon("info"))
        self.b_reload.setIcon(A.make_icon("refresh"))
        self.render_all()

    def render_all(self):
        pass

    def activate(self):
        if time.time() - self.loaded_at > self.STALE_SECS:
            self.reload()

    def reload(self, force=False):
        pass

    def wait_text(self):
        return _("A ler o sistema…")

    def spawn(self, fn, args, cb):
        self.busy = True
        self.wait.start(self.wait_text())
        self.win.run_task(fn, args, lambda res: self._done(res, cb))

    def _done(self, res, cb):
        self.busy = False
        self.loaded_at = time.time()
        try:
            cb(res)
        finally:
            if not self.keep_wait:
                self.wait.stop()

    def toast(self, text, ok=True):
        self.win.statusBar().showMessage(text, 6000)


class LogDialog(QtWidgets.QDialog):
    """Registos do diário de uma unidade (ou de todo o sistema)."""

    def __init__(self, parent, unit="", scope="system"):
        super().__init__(parent)
        self.setWindowTitle(_("Registos") + (f" · {unit}" if unit else ""))
        A.fit_dialog(self, 920, 620)
        self.unit, self.scope, self.rows = unit, scope, []
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        top = QtWidgets.QHBoxLayout()
        self.ed_unit = QtWidgets.QLineEdit(unit)
        self.ed_unit.setPlaceholderText(_("Todo o sistema, ou um serviço (cups.service)"))
        self.cb_prio = QtWidgets.QComboBox()
        for txt, val in ((_("Emergência"), 0), (_("Erro"), 3), (_("Aviso+"), 4), (_("Info"), 6), (_("Depuração"), 7)):
            self.cb_prio.addItem(txt, val)
        self.cb_prio.setCurrentIndex(1)
        self.cb_range = QtWidgets.QComboBox()
        for txt, val in ((_("Esta sessão"), "boot"), (_("24 h"), "day"), (_("7 d"), "week")):
            self.cb_range.addItem(txt, val)
        self.cb_range.setCurrentIndex(1)
        fit_combo(self.cb_prio)
        fit_combo(self.cb_range)
        self.ed_text = QtWidgets.QLineEdit()
        self.ed_text.setPlaceholderText(_("Filtrar texto…"))
        top.addWidget(self.ed_unit, 2)
        top.addWidget(self.cb_prio)
        top.addWidget(self.cb_range)
        top.addWidget(self.ed_text, 2)
        lay.addLayout(top)
        row = QtWidgets.QHBoxLayout()
        self.live = QtWidgets.QCheckBox(_("Seguir em direto"))
        self.count = lbl("", "muted")
        b_ref = QtWidgets.QPushButton(_("Atualizar"))
        b_exp = QtWidgets.QPushButton(_("Exportar"))
        row.addWidget(self.live)
        row.addWidget(self.count)
        row.addStretch(1)
        row.addWidget(b_ref)
        row.addWidget(b_exp)
        lay.addLayout(row)
        self.view = QtWidgets.QTextBrowser()
        lay.addWidget(self.view, 1)
        b = QtWidgets.QPushButton(_("Fechar"))
        b.setObjectName("primary")
        b.setMinimumWidth(150)
        b.clicked.connect(self.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.live.toggled.connect(lambda on: self.timer.start(4000) if on else self.timer.stop())
        b_ref.clicked.connect(lambda _c=False: self.refresh())
        b_exp.clicked.connect(lambda _c=False: self.export())
        self.cb_prio.currentIndexChanged.connect(lambda _i: self.refresh())
        self.cb_range.currentIndexChanged.connect(lambda _i: self.refresh())
        self.ed_unit.editingFinished.connect(self.refresh)
        self.ed_text.editingFinished.connect(self.refresh)
        self.refresh()

    def _scope(self, unit):
        if not unit:
            return "system"
        name = unit if "." in unit else unit + ".service"
        return "user" if self.scope == "user" and name == self.unit else "system"

    def refresh(self):
        unit = self.ed_unit.text().strip()
        if unit and "." not in unit:
            unit += ".service"
        rows, ok = S.query_logs(unit or None, self._scope(unit), self.cb_prio.currentData(),
                                self.cb_range.currentData(), self.ed_text.text().strip() or None)
        self.rows = rows
        self.render(ok)

    def render(self, ok=True):
        tones = {0: "DANGER", 1: "DANGER", 2: "DANGER", 3: "DANGER", 4: "WARN", 5: "MUTED", 6: "TEXT", 7: "MUTED"}
        out = []
        for r in self.rows:
            c = col(tones.get(r["priority"], "TEXT"))
            out.append(f'<tr><td valign="top" style="color:{col("MUTED")};font-size:8pt">{A.esc(time.strftime("%d/%m %H:%M:%S", time.localtime(r["ts"])))}&nbsp;&nbsp;</td>'
                       f'<td valign="top" style="color:{col("ACCENT")}">{A.esc(r["source"])}&nbsp;&nbsp;</td>'
                       f'<td style="color:{c}">{A.esc(r["message"])}</td></tr>')
        if not out:
            msg = _("O diário não pôde ser lido") if not ok else _("Sem entradas com estes filtros")
            out = [f'<tr><td style="color:{col("MUTED")}">{A.esc(msg)}</td></tr>']
        self.count.setText(_("{n} linhas").format(n=len(self.rows)))
        self.view.setHtml(A.page_html('<table cellspacing="0" cellpadding="2">' + "".join(out) + "</table>"))
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def export(self):
        name = (self.ed_unit.text().strip() or "system") + ".log"
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, _("Exportar"), os.path.expanduser("~/" + name))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for r in self.rows:
                    f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"]))} [{r["priority"]}] '
                            f'{r["source"]}: {r["message"]}\n')
            A.notify(self, _("Exportar"), _("Registo exportado"))
        except OSError:
            A.warn(self, _("Exportar"), _("Não foi possível exportar o registo"))


# ================================================================= RESUMO
class OverviewPage(SysPage):
    def __init__(self, win):
        super().__init__(win)
        self.d = None
        self.finish_toolbar()
        self.status = lbl(_("A ler o sistema…"), "muted")
        self.lay.addWidget(self.status)
        cols = QtWidgets.QHBoxLayout()
        cols.setSpacing(16)
        self.lay.addLayout(cols, 1)
        lw, self.left = plain(QtWidgets.QVBoxLayout)
        rw, self.right = plain(QtWidgets.QVBoxLayout)
        self.left.setSpacing(14)
        self.right.setSpacing(14)
        cols.addWidget(lw, 3, Qt.AlignmentFlag.AlignTop)
        cols.addWidget(rw, 2, Qt.AlignmentFlag.AlignTop)
        self.mem_view = None

    def wait_text(self):
        return _("A ler o sistema…")

    def notes(self):
        return (_("Resumo"),
                _("Uma vista rápida do estado do sistema: serviços ativos e falhados, saúde geral, tempo de arranque, "
                  "serviços que mais memória usam, atividade recente e o estado da memória (swap, zram e zswap)."),
                [_("A saúde desce quando há serviços que falharam; use «Reiniciar» ou «Ver» para tratar deles."),
                 _("Os cartões com ligação levam à página completa (Serviços, Análise de arranque, Histórico, Memória)."),
                 _("«Atualizar» volta a ler tudo; os dados também se atualizam ao regressar a esta página.")],
                _("Os valores de arranque pertencem ao arranque atual e só mudam depois de reiniciar o computador."))

    def reload(self, force=False):
        if self.busy:
            return
        self.status.setVisible(False)
        self.spawn(self._gather, (), self._loaded)

    @staticmethod
    def _gather():
        return dict(overview=S.overview(), system=S.system_info(), boot=S.boot_analysis(),
                    boots=S.boot_history(), history=S.history_load())

    def _loaded(self, res):
        if isinstance(res, Exception):
            self.status.setText(_("Não foi possível ler o sistema"))
            self.status.setVisible(True)
            return
        self.d = res
        self.status.setVisible(False)
        self.render_all()

    def refresh_memory(self):
        if self.mem_view is not None and self.win.stack.currentIndex() == self.win.idx["overview"]:
            self.fill_memory()

    def render_all(self):
        if not self.d:
            return
        d = self.d
        ov, sy = d["overview"], d["system"]
        clear(self.left)
        clear(self.right)
        # contadores
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)
        for title, n, tone in ((_("Ativos"), ov["active"], "OK"), (_("Inativos"), ov["inactive"], "TEXT"),
                               (_("Falhados"), ov["failed"], "DANGER" if ov["failed"] else "TEXT"),
                               (_("Ativos no arranque"), ov["enabled"], "TEXT")):
            f, v = tcard(None)
            v.setSpacing(2)
            v.addWidget(lbl(title, "muted"))
            big = lbl(str(n), "big")
            big.setStyleSheet(f"color: {col(tone)};")
            v.addWidget(big)
            row.addWidget(f)
        wrap = QtWidgets.QWidget()
        wrap.setObjectName("plain")
        wrap.setLayout(row)
        self.left.addWidget(wrap)
        # saúde e atenção
        f, v = tcard(_("Precisa de atenção"))
        total = ov["active"] + ov["inactive"] + ov["failed"]
        health = 100.0 if not total else (total - ov["failed"]) / total * 100.0
        hrow = QtWidgets.QHBoxLayout()
        hrow.setSpacing(16)
        hrow.addWidget(Donut(health))
        hv = QtWidgets.QVBoxLayout()
        hv.addWidget(lbl(_("Saúde"), "h2"))
        hv.addWidget(lbl(_("100 = nenhum serviço falhou"), "muted"))
        hv.addStretch(1)
        hrow.addLayout(hv, 1)
        v.addLayout(hrow)
        if not ov["failed_units"]:
            ok = lbl("✓  " + _("Tudo em ordem: nenhum serviço falhou"))
            ok.setStyleSheet(f"color: {col('OK')}; font-weight: bold;")
            v.addWidget(ok)
        for s in ov["failed_units"][:6]:
            w, h = plain(QtWidgets.QHBoxLayout)
            h.setSpacing(8)
            h.addWidget(chip(_("Falhou"), "DANGER"))
            tv = QtWidgets.QVBoxLayout()
            tv.setSpacing(0)
            tv.addWidget(lbl(s["name"]))
            tv.addWidget(lbl(s["description"], "muted"))
            h.addLayout(tv, 1)
            if not s["protected"]:
                b = small_btn(_("Reiniciar"))
                b.clicked.connect(lambda _c=False, s=s: self.restart(s))
                h.addWidget(b)
            b2 = small_btn(_("Ver"))
            b2.clicked.connect(lambda _c=False, s=s: self.win.open_service(s["name"], s["scope"]))
            h.addWidget(b2)
            v.addWidget(w)
        self.left.addWidget(f)
        # arranque
        f, v = tcard(_("Arranque"), _("Ver análise") + " →", lambda: self.win.goto_name("boot"))
        bt = d["boot"]["boot"]
        if not bt:
            v.addWidget(empty_note(_("O tempo de arranque não está disponível: o systemd-analyze não devolveu dados")))
        else:
            big = lbl(fmt_ms(bt["total"]), "big")
            v.addWidget(big)
            boots = d["boots"]["boots"]
            if len(boots) > 1:
                tt = [b["total"] for b in boots]
                v.addWidget(lbl(_("Média {avg} · melhor {best} · últimos {n}").format(
                    avg=fmt_ms(sum(tt) / len(tt)), best=fmt_ms(min(tt)), n=len(tt)), "muted"))
            parts = [(k, bt["parts"][k]) for k in ("firmware", "loader", "kernel", "initrd", "userspace") if k in bt["parts"]]
            v.addWidget(StackBar([p[1] for p in parts], bt["total"]))
            names = {"firmware": _("Firmware"), "loader": _("Carregador"), "kernel": _("Kernel"),
                     "initrd": _("Initrd"), "userspace": _("Sistema")}
            leg = " &nbsp; ".join(f'<span style="color:{col(share_tone(ms / max(1, bt["total"])))}">■</span> '
                                  f'{A.esc(names[k])} {A.esc(fmt_ms(ms))}' for k, ms in parts)
            v.addWidget(lbl(leg, "muted", True, True))
            sl = d["boot"]["slowest"][:5]
            if sl:
                v.addWidget(lbl(_("Serviços mais lentos no arranque"), "muted"))
                mx = max(1, sl[0]["ms"])
                for s in sl:
                    v.addWidget(bar_row(s["name"], s["ms"] / mx, fmt_ms(s["ms"]), "ACCENT", 190, 70))
        self.left.addWidget(f)
        # mais memória
        f, v = tcard(_("Mais memória"), _("Serviços") + " →", lambda: self.win.goto_name("services"))
        top = sorted([s for s in ov["services"] if s["memory"]], key=lambda s: -s["memory"])[:8]
        if not top:
            v.addWidget(empty_note(_("Sem dados de memória")))
        else:
            mx = max(1, top[0]["memory"])
            for s in top:
                v.addWidget(bar_row(s["name"], s["memory"] / mx, fmt_bytes(s["memory"]), "ACCENT", 190, 80))
        self.left.addWidget(f)
        # atividade recente
        f, v = tcard(_("Atividade recente"), _("Histórico") + " →", lambda: self.win.goto_name("history"))
        hist = list(reversed(d["history"]))[:4]
        if not hist:
            v.addWidget(empty_note(_("Ainda não fez alterações")))
        for r in hist:
            w, h = plain(QtWidgets.QHBoxLayout)
            tone = {"ok": "OK", "partial": "WARN", "failed": "DANGER"}.get(r["result"], "MUTED")
            dot = lbl("●")
            dot.setStyleSheet(f"color: {col(tone)};")
            h.addWidget(dot)
            h.addWidget(lbl(history_title(r)), 1)
            h.addWidget(lbl(fmt_time(r["at"]), "muted"))
            v.addWidget(w)
        self.left.addWidget(f)
        # --- coluna direita: sistema + memória
        f, v = tcard(_("Sistema"))
        kv_rows(v, [(_("Distribuição"), sy["distro"]), (_("Kernel"), sy["kernel"]),
                    (_("Sessão"), sy["session"] or "—"), (_("Tempo ligado"), fmt_uptime(sy["uptime"])),
                    (_("CPU"), sy["cpu"] or "—"), (_("Threads"), str(sy["threads"]))])
        v.addWidget(bar_row(_("Uso da CPU"), sy["cpu_use"] / 100.0, f"{sy['cpu_use']:.0f}%", "ACCENT", 110, 50))
        self.right.addWidget(f)
        f, v = tcard(_("Memória"), _("Configurar") + " →", lambda: self.win.goto_name("mem"))
        used = sy["mem_total"] - sy["mem_avail"]
        v.addWidget(bar_row(_("Memória"), used / max(1, sy["mem_total"]),
                            f"{fmt_bytes(used)} / {fmt_bytes(sy['mem_total'])}", "ACCENT", 80, 150))
        if sy["swap_total"]:
            su = sy["swap_total"] - sy["swap_free"]
            v.addWidget(bar_row(_("Swap"), su / max(1, sy["swap_total"]),
                                f"{fmt_bytes(su)} / {fmt_bytes(sy['swap_total'])}", "ACCENT2", 80, 150))
        else:
            v.addWidget(bar_row(_("Swap"), 0, _("nenhuma"), "ACCENT2", 80, 150))
        self.mem_view = QtWidgets.QTextBrowser()
        self.mem_view.setOpenLinks(False)
        self.mem_view.setMinimumHeight(340)
        v.addWidget(self.mem_view)
        self.fill_memory()
        self.right.addWidget(f)

    def fill_memory(self):
        sb = self.mem_view.verticalScrollBar()
        pos = sb.value()
        self.mem_view.setHtml(A.status_html())
        sb.setValue(pos)

    def restart(self, s):
        steps = [dict(unit=s["name"], scope=s["scope"], action="restart")]
        self.win.run_task(S.apply_steps, (steps, "services"), lambda res: self._restarted(res))

    def _restarted(self, res):
        if not isinstance(res, Exception) and res and not res[0]["ok"]:
            A.warn(self, _("Reiniciar"), step_err(res[0].get("message", "")))
        self.reload(True)


def history_title(rec):
    if rec.get("source") == "optimization":
        return _("Otimização ({n})").format(n=len(rec["steps"]))
    st = rec["steps"][0]
    return f"{action_label(st['action'])} · {st['unit']}"


# ================================================================= SERVIÇOS
class ServicesPage(SysPage):
    PROTECTED_HINT = property(lambda self: _("O sistema precisa deste serviço: não pode ser parado, reiniciado nem desativado"))

    def __init__(self, win):
        super().__init__(win)
        self.rows, self.cur, self.pending = [], None, None
        self.keep_wait = True  # o aviso só desaparece quando a tabela estiver toda preenchida
        self._gen = 0
        self.sort_key, self.sort_rev = "name", False
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Pesquisar serviços…"))
        self.search.setMinimumWidth(220)
        self.f_state = QtWidgets.QComboBox()
        for txt, val in ((_("Todos"), "all"), (_("Ativos"), "active"), (_("Falhados"), "failed"), (_("Inativos"), "inactive")):
            self.f_state.addItem(txt, val)
        fit_combo(self.f_state)
        self.f_scope = QtWidgets.QComboBox()
        for txt, val in ((_("Todos"), "all"), (_("Sistema"), "system"), (_("Utilizador"), "user")):
            self.f_scope.addItem(txt, val)
        fit_combo(self.f_scope)
        self.count = lbl("", "muted")
        self.tool.addWidget(self.search, 1)
        self.tool.addWidget(self.f_state)
        self.tool.addWidget(self.f_scope)
        self.tool.addWidget(self.count)
        self.finish_toolbar()
        sp = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False)
        self.table = A.make_table([_("Serviço"), _("Estado"), _("Arranque"), _("RAM")], multi=False)
        self.table.setMinimumWidth(380)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setStretchLastSection(False)
        for i, w in ((1, 100), (2, 110), (3, 90)):
            hh.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(i, w)
        vh = self.table.verticalHeader()
        vh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(30)
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self.on_sort)
        sp.addWidget(self.table)
        self.detail = A.card()
        dv = QtWidgets.QVBoxLayout(self.detail)
        dv.setContentsMargins(16, 14, 16, 14)
        dv.setSpacing(8)
        self.d_title = lbl(_("Escolha um serviço para ver os detalhes"), "h2", True)
        self.d_desc = lbl("", "muted", True)
        self.d_chips = QtWidgets.QHBoxLayout()
        self.d_chips.setSpacing(6)
        self.d_info_host, self.d_info = plain(QtWidgets.QVBoxLayout)
        self.d_status = QtWidgets.QTextBrowser()
        self.d_status.setMinimumHeight(110)
        self.d_hint = lbl("", "muted", True)
        dv.addWidget(self.d_title)
        dv.addWidget(self.d_desc)
        dv.addLayout(self.d_chips)
        dv.addWidget(self.d_info_host)
        dv.addWidget(self.d_status, 1)
        dv.addWidget(self.d_hint)
        r1 = QtWidgets.QHBoxLayout()
        self.b_start, self.b_stop, self.b_restart = (QtWidgets.QPushButton(_("Iniciar")), QtWidgets.QPushButton(_("Parar")),
                                                     QtWidgets.QPushButton(_("Reiniciar")))
        for b, a in ((self.b_start, "start"), (self.b_stop, "stop"), (self.b_restart, "restart")):
            b.clicked.connect(lambda _c=False, a=a: self.act(a))
            r1.addWidget(b)
        dv.addLayout(r1)
        r2 = QtWidgets.QHBoxLayout()
        self.b_boot = QtWidgets.QPushButton(_("Ativar no arranque"))
        self.b_boot.setObjectName("primary")
        self.b_boot.clicked.connect(lambda _c=False: self.act(self.b_boot.property("action")))
        self.b_more = QtWidgets.QPushButton(_("Mais…"))
        menu = QtWidgets.QMenu(self.b_more)
        for a in ("enable-now", "disable-now"):
            menu.addAction(action_label(a)).triggered.connect(lambda _c=False, a=a: self.act(a))
        self.b_more.setMenu(menu)
        self.b_logs = QtWidgets.QPushButton(_("Registos") + " →")
        self.b_logs.clicked.connect(lambda _c=False: self.cur and LogDialog(self, self.cur[1], self.cur[0]).exec())
        r2.addWidget(self.b_boot)
        r2.addWidget(self.b_more)
        r2.addWidget(self.b_logs)
        dv.addLayout(r2)
        sp.addWidget(self.detail)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 2)
        self.lay.addWidget(sp, 1)
        self.search.textChanged.connect(lambda _t: self.fill())
        self.f_state.currentIndexChanged.connect(lambda _i: self.fill())
        self.f_scope.currentIndexChanged.connect(lambda _i: self.fill())
        self.table.itemSelectionChanged.connect(self.on_select)
        self.set_buttons(None)

    def wait_text(self):
        return _("A ler os serviços do sistema…")

    def render_all(self):
        if self.rows:
            self.fill()

    def notes(self):
        return (_("Serviços"),
                _("Um serviço é um programa que o sistema mantém a correr em segundo plano: rede, impressão, som, "
                  "Bluetooth… Aqui vê todos os serviços deste computador, quais estão a correr e quais falharam."),
                [_("Pesquise um serviço pelo nome ou descrição, ou filtre por estado: Ativos, Falhados ou Inativos."),
                 _("Clique num para ver os detalhes à direita: desde quando corre, quanta memória usa, de que pacote vem e o estado completo."),
                 _("Use os botões para iniciar, parar ou reiniciar agora, e o botão do arranque para decidir se arranca com o sistema. Ser-lhe-á pedida a palavra-passe.")],
                _("Parar um serviço só dura até reiniciar o computador; o botão do arranque é o que muda de forma permanente. "
                  "Os serviços marcados como protegidos são essenciais e não podem ser parados nem desativados."))

    def reload(self, force=False):
        if self.busy:
            return
        self.spawn(S.list_services, (), self._loaded)

    def _loaded(self, res):
        if isinstance(res, Exception):
            self.wait.stop()
            self.count.setText(_("Não foi possível ler os serviços"))
            return
        self.rows = res
        self.fill()

    def on_sort(self, i):
        key = ("name", "active", "boot", "memory")[i]
        self.sort_rev = (not self.sort_rev) if self.sort_key == key else (key == "memory")
        self.sort_key = key
        self.fill()

    def filtered(self):
        q = self.search.text().strip().lower()
        st, sc = self.f_state.currentData(), self.f_scope.currentData()
        out = []
        for s in self.rows:
            if sc != "all" and s["scope"] != sc:
                continue
            if st == "active" and s["active"] != "active":
                continue
            if st == "failed" and s["active"] != "failed":
                continue
            if st == "inactive" and s["active"] in ("active", "failed"):
                continue
            if q and q not in s["name"].lower() and q not in s["description"].lower():
                continue
            out.append(s)
        k = self.sort_key
        out.sort(key=lambda s: (s[k] is None, s[k] if k == "memory" and s[k] is not None else str(s[k]).lower()),
                 reverse=self.sort_rev)
        return out

    CHUNK = 60

    def fill(self):
        """Preenche a tabela por blocos, para a janela continuar a responder."""
        rows = self.filtered()
        self._gen += 1
        gen = self._gen
        self._rows_shown = rows
        sel = self.cur
        pick = -1
        for i, s in enumerate(rows):
            key = (s["scope"], s["name"])
            if self.pending and key == self.pending:
                pick = i
                break
            if pick < 0 and sel and key == sel:
                pick = i
        total = len(self.rows)
        prot = sum(1 for s in self.rows if s["protected"])
        self.count.setText(_("{shown} de {total}").format(shown=len(rows), total=total) + "  ·  "
                           + _("Protegidos") + f": {prot}")
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        self.table.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        if len(rows) > self.CHUNK:
            self.wait.start(_("A carregar a lista de serviços…"))
        QtCore.QTimer.singleShot(0, lambda: self._fill_step(gen, 0, pick))

    def _fill_step(self, gen, start, pick):
        if gen != self._gen:
            return  # chegou uma lista mais recente
        rows = self._rows_shown
        end = min(len(rows), start + self.CHUNK)
        self.table.setUpdatesEnabled(False)
        for i in range(start, end):
            self._set_row(i, rows[i])
        self.table.setUpdatesEnabled(True)
        if end < len(rows):
            QtCore.QTimer.singleShot(0, lambda: self._fill_step(gen, end, pick))
            return
        self.wait.stop()
        if pick >= 0:
            self.pending = None
            self.table.blockSignals(True)
            self.table.selectRow(pick)
            self.table.blockSignals(False)
            self.on_select()
        elif not rows:
            self.cur = None
            self.set_buttons(None)

    def _set_row(self, i, s):
        name = s["name"] + (" ·" + _("utilizador") if s["scope"] == "user" else "")
        it = A.titem(("🔒 " if s["protected"] else "") + name)
        it.setData(Qt.ItemDataRole.UserRole, (s["scope"], s["name"]))
        if s["description"]:
            it.setToolTip(s["description"])
        st = A.titem(state_label(s["active"]))
        tone = {"active": "OK", "failed": "DANGER"}.get(s["active"])
        if tone:
            st.setForeground(QtGui.QBrush(QtGui.QColor(col(tone))))
        self.table.setItem(i, 0, it)
        self.table.setItem(i, 1, st)
        self.table.setItem(i, 2, A.titem(boot_label(s["boot"])))
        ram = A.titem(fmt_bytes(s["memory"]) if s["memory"] else "—")
        ram.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(i, 3, ram)

    def current_row(self):
        r = self.table.currentRow()
        if r < 0 or self.table.item(r, 0) is None:
            return None
        scope, name = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        return next((s for s in self.rows if s["name"] == name and s["scope"] == scope), None)

    def on_select(self):
        s = self.current_row()
        if not s:
            return
        self.cur = (s["scope"], s["name"])
        self.d_title.setText(s["name"])
        self.d_desc.setText(s["description"])
        clear(self.d_chips)
        self.d_chips.addWidget(chip(state_label(s["active"]), {"active": "OK", "failed": "DANGER"}.get(s["active"], "MUTED")))
        self.d_chips.addWidget(chip(boot_label(s["boot"]), "ACCENT" if s["boot"].startswith("enabled") else "MUTED"))
        if s["protected"]:
            self.d_chips.addWidget(chip(_("Protegido"), "WARN"))
        if s["scope"] == "user":
            self.d_chips.addWidget(chip(_("utilizador"), "ACCENT2"))
        self.d_chips.addStretch(1)
        self.set_buttons(s)
        clear(self.d_info)
        self.d_status.setHtml(A.page_html(f'<span style="color:{col("MUTED")}">{A.esc(_("A ler os detalhes…"))}</span>'))
        key = self.cur
        self.win.run_task(S.service_details, (s["name"], s["scope"]), lambda res: self.detail_loaded(key, res))

    def detail_loaded(self, key, res):
        if key != self.cur:
            return
        clear(self.d_info)
        if isinstance(res, Exception):
            self.d_status.setHtml(A.page_html(A.esc(_("Não foi possível ler os detalhes"))))
            return
        rows = [(_("Ativo desde"), res["since"] or "—"), (_("PID"), res["pid"] or "—"),
                (_("Memória"), fmt_bytes(res["memory"])), (_("Pacote"), res["package"] or "—"),
                (_("Ficheiro"), res["file"] or "—")]
        if res["requires"]:
            rows.append((_("Requer"), ", ".join(res["requires"][:6])))
        if res["wanted_by"]:
            rows.append((_("Pretendido por"), ", ".join(res["wanted_by"][:6])))
        kv_rows(self.d_info, rows)
        self.d_status.setHtml(A.page_html(f'<pre style="font-family:monospace;font-size:8.5pt;margin:0">{A.esc(res["status"])}</pre>'))

    def set_buttons(self, s):
        on = s is not None
        prot = bool(s and s["protected"])
        self.b_start.setEnabled(on and s["active"] != "active")
        self.b_stop.setEnabled(on and not prot and s["active"] in ("active", "activating", "failed"))
        self.b_restart.setEnabled(on and not prot)
        self.b_more.setEnabled(on and not prot)
        self.b_logs.setEnabled(on)
        enabled = bool(s and s["boot"].startswith("enabled"))
        self.b_boot.setText(_("Desativar no arranque") if enabled else _("Ativar no arranque"))
        self.b_boot.setProperty("action", "disable" if enabled else "enable")
        self.b_boot.setEnabled(on and not (prot and enabled) and (not s or s["boot"] in ("enabled", "enabled-runtime", "disabled", "")))
        self.d_hint.setText(self.PROTECTED_HINT if prot else "")
        if not on:
            self.d_title.setText(_("Escolha um serviço para ver os detalhes"))
            self.d_desc.setText("")
            clear(self.d_chips)
            clear(self.d_info)
            self.d_status.clear()

    def act(self, action):
        if not self.cur:
            return
        scope, unit = self.cur
        confirm = {"stop": _("Parar {unit}? Fica parado até o iniciar de novo."),
                   "restart": _("Reiniciar {unit}? Ficará indisponível por instantes."),
                   "disable": _("Desativar {unit}? Deixa de arrancar com o sistema, mas continua a correr até o parar."),
                   "disable-now": _("Parar e desativar {unit}? Fica parado agora e não arranca com o sistema.")}
        if action in confirm and not A.ask(self, _("Confirmar"), confirm[action].format(unit=unit)):
            return
        self.pending = self.cur
        steps = [dict(unit=unit, scope=scope, action=action)]
        self.win.run_task(S.apply_steps, (steps, "services"), lambda res: self.acted(res, action, unit))

    def acted(self, res, action, unit):
        if isinstance(res, Exception):
            A.warn(self, _("Serviços"), str(res))
        elif res and res[0]["ok"]:
            msgs = {"start": _("{unit} iniciado"), "stop": _("{unit} parado"), "restart": _("{unit} reiniciado"),
                    "enable": _("{unit} vai arrancar com o sistema"), "disable": _("{unit} não vai arrancar com o sistema"),
                    "enable-now": _("{unit} ativado e iniciado"), "disable-now": _("{unit} parado e desativado")}
            self.toast(msgs.get(action, "OK").format(unit=unit))
        elif res:
            A.warn(self, _("Serviços"), _("Não foi possível {action} {unit}").format(
                action=action_label(action).lower(), unit=unit) + ": " + step_err(res[0].get("message", "")))
        self.reload(True)
        self.win.invalidate("overview")
        self.win.invalidate("history")


# ================================================================= DIAGNÓSTICO
def reason_text(code, p):
    t = {
        "owner": _("Pacote: {package}."),
        "package_damaged": _("O pacote {package} está danificado: {count} ficheiro(s) em falta ou diferente(s) do pacote original (por exemplo {example})."),
        "package_damaged_unavailable": _("O pacote {package} está danificado ({count} ficheiro(s), por exemplo {example}), mas a versão instalada já não está nos seus repositórios, por isso não pode ser reinstalado."),
        "unit_state": _("A unidade está no estado «{state}» (resultado: {result}, código de saída: {status})."),
        "exec_missing": _("O programa que a unidade inicia, {path}, não existe."),
        "restarts": _("Reiniciou {count} vez(es) desde que arrancou."),
        "repeats": _("Regista erros em {boots} arranques diferentes."),
        "required_by": _("Outras unidades dependem dela ({units}), por isso não se oferece desativá-la."),
        "dpkg_audit": _("Há pacotes semi-instalados ou semi-configurados: {packages}."),
        "apt_broken": _("O apt indica dependências em falta: {detail}"),
        "broken_links": _("{count} ligação(ões) em /etc/systemd/system apontam para nada (por exemplo {example}), por isso não fazem nada."),
        "autostart_flatpak_missing": _("A entrada de arranque automático {file} inicia o Flatpak {app}, que já não está instalado, por isso falha ao iniciar a sessão."),
        "autostart_program_missing": _("A entrada de arranque automático {file} inicia {program}, que não existe neste computador, por isso falha ao iniciar a sessão."),
        "dm_link_missing": _("Falta /etc/systemd/system/display-manager.service: é a ligação que o sistema usa para iniciar o gestor de sessão. Sem ela o arranque gráfico acaba numa consola de texto. O gestor instalado é {unit}."),
        "dm_link_ambiguous": _("Falta /etc/systemd/system/display-manager.service e há vários gestores de sessão instalados ({units}): não é possível saber qual deve arrancar."),
    }
    try:
        return t.get(code, code).format(**p)
    except (KeyError, IndexError):
        return t.get(code, code)


def fix_label(f):
    t = {"reinstall": _("Reinstalar {target}"), "restart": _("Reiniciar {target}"),
         "disable": _("Impedir {target} de arrancar com o sistema"), "configure": _("Terminar a configuração dos pacotes"),
         "fix-broken": _("Reparar as dependências em falta"), "install": _("Instalar {target}"),
         "remove-links": _("Remover as ligações quebradas ({target})"), "enable": _("Ativar {target}"),
         "remove-autostart": _("Remover {target}")}
    return t.get(f["fix"], f["fix"]).format(target=f["target"])


def step_text(st):
    t = {"package-reinstall": _("O pacote {unit} é reinstalado com o apt (precisa dos repositórios). Não pode ser desfeito no Histórico."),
         "package-install": _("O pacote {unit} é instalado com o apt."),
         "restart": _("{unit} é reiniciado."),
         "disable": _("{unit} deixa de arrancar com o sistema. Pode ativá-lo de novo no Histórico."),
         "dpkg-configure": _("É executado «dpkg --configure -a»."),
         "apt-fix-broken": _("É executado «apt-get -f install»."),
         "enable": _("{unit} é ativado para arrancar com o sistema."),
         "remove-link": _("A ligação quebrada {unit} é apagada. Não pode ser desfeito, mas apontava para nada."),
         "remove-autostart": _("{unit} é apagado de ~/.config/autostart. O programa já não existe, por isso não há nada a restaurar.")}
    return t.get(st["action"], st["action"]).format(unit=st["unit"])


SYSTEM_NAMES = lambda: {"dpkg": _("Pacotes semi-configurados"), "apt": _("Dependências de pacotes em falta"),
                        "links": _("Ligações do systemd quebradas"), "display-manager": _("Gestor de sessão sem a sua ligação"),
                        "logcheck-database": _("Lista de mensagens normais do Debian")}


class DiagnosisPage(SysPage):
    def __init__(self, win):
        super().__init__(win)
        self.data = None
        self.range = QtWidgets.QComboBox()
        for txt, val in ((_("Esta sessão"), "boot"), (_("24 h"), "day"), (_("7 d"), "week")):
            self.range.addItem(txt, val)
        self.range.setCurrentIndex(1)
        fit_combo(self.range)
        self.summary = lbl("", "muted")
        self.tool.addWidget(self.range)
        self.tool.addWidget(self.summary)
        self.finish_toolbar()
        self.body_w, self.body = plain(QtWidgets.QVBoxLayout)
        self.body.setSpacing(12)
        self.lay.addWidget(self.body_w)
        self.lay.addStretch(1)
        self.range.currentIndexChanged.connect(lambda _i: self.reload(True))

    def wait_text(self):
        return _("A analisar o sistema…")

    def notes(self):
        return (_("Diagnóstico"),
                _("Agrupa os erros do sistema, explica cada um e repara os que têm reparação possível: serviços que "
                  "falharam, pacotes danificados ou semi-configurados, ligações do systemd quebradas e entradas de arranque órfãs."),
                [_("Escolha o período a analisar: esta sessão, 24 horas ou 7 dias."),
                 _("Cada cartão explica o que foi medido, não só o que o diário diz."),
                 _("Os botões de reparação mostram primeiro o que vai mudar e só aplicam depois de confirmar. Uma só palavra-passe cobre todo o lote.")],
                _("Só se oferece uma reparação quando algo foi medido e pode ser corrigido a partir daqui. As mensagens de registo sem efeito "
                  "medido apenas são contadas, não mostradas."))

    def reload(self, force=False):
        if self.busy:
            return
        clear(self.body)
        self.body.addWidget(empty_note(_("A analisar o sistema…")))
        self.summary.setText("")
        self.spawn(S.diagnose, (self.range.currentData(),), self._loaded)

    def _loaded(self, res):
        clear(self.body)
        if isinstance(res, Exception):
            self.body.addWidget(empty_note(_("Não foi possível analisar o sistema")))
            return
        self.data = res
        self.render_all()

    def render_all(self):
        d = self.data
        if d is None:
            return
        clear(self.body)
        items = d["items"]
        rep = sum(1 for i in items if i["fixes"])
        self.summary.setText(_("{a} precisam de atenção · {r} podem ser reparados").format(a=len(items), r=rep) if items else "")
        if not items:
            f, v = tcard()
            v.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            ic = QtWidgets.QLabel()
            ic.setPixmap(A.draw_pixmap("check", col("OK"), 48))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(ic)
            h = lbl(_("O sistema está a funcionar corretamente"), "h2")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            t = lbl(_("Não há serviços falhados (do sistema ou do utilizador), ligações do systemd quebradas, "
                      "pacotes semi-instalados nem dependências em falta."), "muted", True)
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(t)
            self.body.addWidget(f)
        for it in items:
            self.body.addWidget(self.item_card(it))
        if d["quiet"]:
            f, v = tcard()
            v.addWidget(lbl(_("Mensagens de registo sem efeito medido: {n}").format(n=d["quiet"]), "h2"))
            v.addWidget(lbl(_("Aparecem no registo, mas por trás delas não há nenhuma unidade falhada nem pacote danificado. "
                              "São contadas, não mostradas."), "muted", True))
            self.body.addWidget(f)

    def item_card(self, it):
        f, v = tcard()
        name = SYSTEM_NAMES().get(it["name"], it["name"]) if it["subject"] == "system" else it["name"]
        head = QtWidgets.QHBoxLayout()
        head.addWidget(lbl(name, "h2"), 0)
        head.addWidget(chip(_("Reparável") if it["fixes"] else _("A falhar agora"),
                            "OK" if it["fixes"] else "DANGER"))
        if it["count"] > 1 or it["last"]:
            head.addWidget(chip(_("{n} vezes").format(n=it["count"]), "WARN"))
        head.addWidget(chip(_("Acontece neste arranque") if it["this_boot"] else _("Só em arranques anteriores"), "MUTED"))
        head.addStretch(1)
        v.addLayout(head)
        for code, p in it["reasons"]:
            r = lbl("• " + reason_text(code, p), None, True)
            v.addWidget(r)
        if it["samples"]:
            v.addWidget(lbl(_("Registado mesmo antes"), "muted"))
            tb = QtWidgets.QLabel("<br>".join(A.esc(s)[:240] for s in it["samples"]))
            tb.setWordWrap(True)
            tb.setTextFormat(Qt.TextFormat.RichText)
            tb.setStyleSheet(f"color:{col('MUTED')}; font-family: monospace; font-size: 8.5pt;")
            v.addWidget(tb)
        row = QtWidgets.QHBoxLayout()
        for fx in it["fixes"]:
            b = QtWidgets.QPushButton(fix_label(fx))
            b.setObjectName("primary")
            b.clicked.connect(lambda _c=False, fx=fx: self.fix(fx))
            row.addWidget(b)
        if not it["fixes"]:
            row.addWidget(lbl(_("Sem reparação disponível: não foi medido nada que se possa corrigir a partir daqui."), "muted", True), 1)
        row.addStretch(1)
        if it["subject"] == "unit" and it["name"].endswith(".service"):
            b = QtWidgets.QPushButton(_("Registos") + " →")
            b.clicked.connect(lambda _c=False, it=it: LogDialog(self, it["name"], it["scope"]).exec())
            row.addWidget(b)
        bc = QtWidgets.QPushButton(_("Copiar"))
        bc.clicked.connect(lambda _c=False, it=it, name=name: self.copy(it, name))
        row.addWidget(bc)
        v.addLayout(row)
        return f

    def copy(self, it, name):
        text = name + "\n" + "\n".join("- " + reason_text(c, p) for c, p in it["reasons"]) + "\n" + "\n".join(it["samples"])
        QtWidgets.QApplication.clipboard().setText(text)
        self.toast(_("Copiado"))

    def fix(self, fx):
        txt = _("Isto vai ser feito:") + "\n\n" + "\n".join("• " + step_text(s) for s in fx["steps"][:8])
        if len(fx["steps"]) > 8:
            txt += "\n• …"
        if not A.ask(self, _("Aplicar esta reparação?"), txt):
            return
        self.win.run_task(S.apply_steps, (fx["steps"], "diagnosis"), self.fixed)

    def fixed(self, res):
        if isinstance(res, Exception):
            A.warn(self, _("Diagnóstico"), str(res))
        elif res and all(r["ok"] for r in res):
            self.toast(_("Reparação aplicada"))
        else:
            bad = next((r for r in res if not r["ok"]), None)
            A.warn(self, _("Diagnóstico"), _("Não foi possível aplicar a reparação") +
                   (": " + step_err(bad.get("message", "")) if bad else ""))
        self.reload(True)
        self.win.invalidate("overview")
        self.win.invalidate("history")


# ================================================================= OTIMIZAÇÃO
def opt_texts():
    return {
        "printing": (_("Serviço de impressão (CUPS)"), _("Não há nenhuma impressora configurada nem ligada, por isso o serviço de impressão não tem nada a gerir.")),
        "bluetooth": (_("Bluetooth"), _("Não foi encontrado nenhum adaptador Bluetooth.")),
        "wifi": (_("Wi-Fi (wpa_supplicant)"), _("Não foi encontrado nenhum adaptador Wi-Fi. As redes com fios que usam autenticação 802.1X precisam deste serviço.")),
        "modem": (_("Banda larga móvel (ModemManager)"), _("Não foi encontrado nenhum modem de banda larga móvel. Este serviço também pode interferir com placas série USB como o Arduino.")),
        "thunderbolt": (_("Gestor Thunderbolt"), _("Não foi encontrado nenhum controlador Thunderbolt.")),
        "hybrid_gpu": (_("Alternância de gráficos"), _("Há só uma placa gráfica, por isso não há nada entre que alternar.")),
        "battery": (_("Otimização da bateria do portátil"), _("Não foi encontrada nenhuma bateria: é um computador de secretária, por isso as ferramentas de energia de portáteis não fazem nada.")),
        "thermald": (_("Daemon térmico da Intel"), _("Este processador não é Intel ({vendor}) e este serviço só funciona com processadores Intel.")),
        "vm_tools_physical": (_("Ferramentas de máquinas virtuais"), _("Este é um computador físico, não uma máquina virtual, por isso as ferramentas de convidado não fazem nada.")),
        "vm_tools_other": (_("Ferramentas de outras máquinas virtuais"), _("Esta é uma máquina virtual {platform}: as ferramentas de convidado de outras plataformas não fazem nada aqui.")),
        "smart_in_vm": (_("Monitorização da saúde dos discos (SMART)"), _("Esta é uma máquina virtual: os seus discos são virtuais e não têm dados SMART para monitorizar.")),
        "lvm": (_("Monitorização LVM"), _("Não há volumes LVM em uso neste computador.")),
        "mdraid": (_("Monitorização RAID (mdadm)"), _("Não foram encontrados conjuntos RAID por software.")),
        "nfs": (_("Partilha de ficheiros em rede (NFS)"), _("Não há partilhas NFS montadas nem exportadas neste computador.")),
        "snap": (_("Serviço de pacotes Snap"), _("Não há pacotes snap instalados, por isso o serviço não tem nada a executar.")),
        "wait_online": (_("Esperar pela rede no arranque"), _("Faz o arranque esperar {seconds} s até a rede estar pronta. A rede continua a ligar-se sozinha; só algo que precise dela no instante em que arranca poderia ser afetado.")),
        "fstrim": (_("TRIM periódico do SSD"), _("Foi encontrado um disco de estado sólido ({device}) e o TRIM periódico não está ativo. Ativá-lo mantém o disco rápido e duradouro.")),
    }


class OptimizationPage(SysPage):
    def __init__(self, win):
        super().__init__(win)
        self.data, self.sel, self.cat = None, set(), "all"
        self.stats = QtWidgets.QHBoxLayout()
        self.stats.setSpacing(12)
        sw = QtWidgets.QWidget()
        sw.setObjectName("plain")
        sw.setLayout(self.stats)
        self.finish_toolbar()
        self.lay.addWidget(sw)
        fr = QtWidgets.QHBoxLayout()
        self.cb_cat = QtWidgets.QComboBox()
        self.cb_cat.currentIndexChanged.connect(lambda _i: self.on_cat())
        fr.addWidget(lbl(_("Filtrar:"), "muted"))
        fr.addWidget(self.cb_cat)
        fr.addStretch(1)
        self.lay.addLayout(fr)
        self.body_w, self.body = plain(QtWidgets.QVBoxLayout)
        self.body.setSpacing(10)
        self.lay.addWidget(self.body_w)
        self.lay.addStretch(1)
        bar = QtWidgets.QHBoxLayout()
        self.sel_lbl = lbl("", "muted")
        self.b_apply = QtWidgets.QPushButton(_("Aplicar seleção"))
        self.b_apply.setObjectName("primary")
        self.b_apply.clicked.connect(lambda _c=False: self.apply())
        bar.addWidget(self.sel_lbl)
        bar.addWidget(lbl(_("Uma palavra-passe para todo o lote"), "muted"))
        bar.addStretch(1)
        bar.addWidget(self.b_apply)
        self.lay.addLayout(bar)
        self.b_reload.setText(_("Analisar de novo"))

    def wait_text(self):
        return _("A analisar este computador…")

    def notes(self):
        return (_("Otimização"),
                _("A análise olha para o hardware e a configuração deste computador e encontra serviços que correm mas não têm nada com que trabalhar aqui "
                  "(por exemplo, o serviço de impressão quando não há impressora)."),
                [_("Leia cada resultado: diz o que a análise encontrou neste computador e quanta memória e tempo de arranque devolveria."),
                 _("Marque os que quer (os seguros vêm marcados) e carregue em Aplicar. Uma só palavra-passe cobre todo o lote."),
                 _("Cada serviço é parado de imediato e desativado, para não voltar após reiniciar.")],
                _("Os resultados vêm do que existe neste computador agora. Se mais tarde ligar uma impressora ou um adaptador, volte a ativar o serviço em Serviços. "
                  "Os marcados como «Rever» pedem que confirme que não os usa. Os candidatos são diferentes dos resultados verificados: a análise só mostra que "
                  "mais nada no sistema depende deles, não que sejam inúteis."))

    def reload(self, force=False):
        if self.busy:
            return
        clear(self.body)
        self.body.addWidget(empty_note(_("A analisar este computador…")))
        self.spawn(S.scan_optimization, (), self._loaded)

    def _loaded(self, res):
        clear(self.body)
        if isinstance(res, Exception):
            self.body.addWidget(empty_note(_("Não foi possível concluir a análise")))
            return
        self.data = res
        self.sel = {f["id"] for f in res["findings"] if f["risk"] == "safe"}
        self.fill_cats()
        self.render_all()

    def cat_names(self):
        return {"hardware": _("Hardware que não existe"), "unused": _("Não usado aqui"),
                "boot": _("Atrasa o arranque"), "maintenance": _("Manutenção")}

    def fill_cats(self):
        self.cb_cat.blockSignals(True)
        self.cb_cat.clear()
        self.cb_cat.addItem(_("Todos"), "all")
        cats = []
        for f in self.data["findings"]:
            if f["category"] not in cats:
                cats.append(f["category"])
        for c in cats:
            self.cb_cat.addItem(self.cat_names()[c], c)
        fit_combo(self.cb_cat)
        self.cb_cat.blockSignals(False)
        self.cat = "all"

    def on_cat(self):
        self.cat = self.cb_cat.currentData() or "all"
        self.render_all()

    @staticmethod
    def title_row(cb, title):
        """Caixa de seleção + título completo (com quebra de linha); clicar no título também seleciona."""
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
        t = lbl(title, None, True)
        f = t.font()
        f.setBold(True)
        t.setFont(f)
        t.setCursor(Qt.CursorShape.PointingHandCursor)
        t.mousePressEvent = lambda _e, cb=cb: cb.toggle()
        row.addWidget(t, 1)
        return row

    def toggle(self, key, on):
        (self.sel.add if on else self.sel.discard)(key)
        self.update_sel()

    def render_all(self):
        d = self.data
        clear(self.stats)
        clear(self.body)
        if d is None:
            return
        fnd = d["findings"]
        for title, val in ((_("Resultados"), str(len(fnd))), (_("RAM que libertaria"), fmt_bytes(sum(f["ram"] for f in fnd))),
                           (_("Arranque mais rápido"), fmt_ms(sum(f["boot_ms"] for f in fnd)))):
            f, v = tcard()
            v.setSpacing(2)
            v.addWidget(lbl(title, "muted"))
            v.addWidget(lbl(val, "big"))
            self.stats.addWidget(f)
        texts = opt_texts()
        shown = [f for f in fnd if self.cat in ("all", f["category"])]
        if not fnd:
            f, v = tcard()
            ic = QtWidgets.QLabel()
            ic.setPixmap(A.draw_pixmap("check", col("OK"), 48))
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(ic)
            h = lbl(_("Tudo em ordem"), "h2")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            t = lbl(_("A análise não encontrou nada de que este computador não precise."), "muted", True)
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(t)
            self.body.addWidget(f)
        if shown:
            self.body.addWidget(lbl(_("Verificado neste computador").upper(), "cardtitle"))
        for fi in shown:
            title, text = texts[fi["id"]]
            f, v = tcard()
            cb = QtWidgets.QCheckBox()
            cb.setChecked(fi["id"] in self.sel)
            cb.toggled.connect(lambda on, k=fi["id"]: self.toggle(k, on))
            v.addLayout(self.title_row(cb, title))
            chips = QtWidgets.QHBoxLayout()
            chips.setContentsMargins(30, 0, 0, 0)
            chips.addWidget(chip(self.cat_names()[fi["category"]], "ACCENT2"))
            chips.addWidget(chip(_("Seguro") if fi["risk"] == "safe" else _("Rever"), "OK" if fi["risk"] == "safe" else "WARN"))
            if fi["ram"]:
                chips.addWidget(chip("RAM " + fmt_bytes(fi["ram"]), "MUTED"))
            if fi["boot_ms"]:
                chips.addWidget(chip(_("Arranque") + " " + fmt_ms(fi["boot_ms"]), "MUTED"))
            chips.addStretch(1)
            v.addLayout(chips)
            try:
                text = text.format(**fi["params"])
            except (KeyError, IndexError):
                pass
            tl = lbl(text, None, True)
            tl.setContentsMargins(30, 0, 0, 0)
            v.addWidget(tl)
            hint = (_("A análise mostrou que nada neste computador a usa") if fi["risk"] == "safe"
                    else _("Confirme que não a usa antes de aplicar"))
            eff = (_("Para agora e não volta a arrancar. Pode ativá-la de novo em Serviços.") if fi["action"] == "disable-now"
                   else _("Arranca agora e passa a arrancar em cada arranque."))
            hl = lbl(hint + " · " + eff + "  (" + ", ".join(fi["units"]) + ")", "muted", True)
            hl.setContentsMargins(30, 0, 0, 0)
            v.addWidget(hl)
            self.body.addWidget(f)
        cands = d["candidates"] if self.cat == "all" else []
        if cands:
            self.body.addWidget(lbl(_("Candidatos: mais nada no sistema depende deles").upper(), "cardtitle"))
            cov = d["coverage"]
            self.body.addWidget(lbl(_("Foram analisados {total} serviços: {system} fazem parte do sistema, {needed} são necessários a algo em execução, "
                                      "{cheap} custam quase nada e {idle} não estão a correr nem ativados.").format(**cov), "muted", True))
            for c in cands:
                f, v = tcard()
                key = "unit:" + c["name"]
                cb = QtWidgets.QCheckBox()
                cb.setChecked(key in self.sel)
                cb.toggled.connect(lambda on, k=key: self.toggle(k, on))
                v.addLayout(self.title_row(cb, c["name"]))
                chips = QtWidgets.QHBoxLayout()
                chips.setContentsMargins(30, 0, 0, 0)
                chips.addWidget(chip(_("Rever"), "WARN"))
                chips.addWidget(chip("RAM " + fmt_bytes(c["ram"]), "MUTED"))
                if c["boot_ms"]:
                    chips.addWidget(chip(_("Arranque") + " " + fmt_ms(c["boot_ms"]), "MUTED"))
                chips.addStretch(1)
                v.addLayout(chips)
                extra = [c["description"], _("Nenhum serviço depende dele")]
                if c["on_demand"]:
                    extra.append(_("Arranca a pedido"))
                if c["package"]:
                    extra.append(_("Pacote: {name}").format(name=c["package"]))
                el = lbl(" · ".join(x for x in extra if x), None, True)
                el.setContentsMargins(30, 0, 0, 0)
                v.addWidget(el)
                self.body.addWidget(f)
            self.body.addWidget(lbl(_("Não há prova de que seja desnecessário, só de que nenhuma unidade em execução depende dele. "
                                      "Confirme que não o usa antes de aplicar."), "muted", True))
        self.update_sel()

    def selected_steps(self):
        steps = []
        for fi in self.data["findings"]:
            if fi["id"] in self.sel:
                steps += [dict(unit=u, scope="system", action=fi["action"]) for u in fi["units"]]
        for c in self.data["candidates"]:
            if "unit:" + c["name"] in self.sel:
                steps.append(dict(unit=c["name"], scope="system", action="disable-now"))
        return steps

    def update_sel(self):
        n = len(self.sel)
        self.sel_lbl.setText(_("{n} selecionados").format(n=n))
        self.b_apply.setEnabled(n > 0 and not self.busy)

    def apply(self):
        steps = self.selected_steps()
        if not steps:
            return
        txt = _("Agora, isto vai ser alterado:") + "\n\n" + "\n".join(
            f"• {action_label(s['action'])}: {s['unit']}" for s in steps[:14])
        if len(steps) > 14:
            txt += "\n• …"
        if not A.ask(self, _("Aplicar a seleção?"), txt):
            return
        self.b_apply.setEnabled(False)
        self.b_apply.setText(_("A aplicar…"))
        self.win.run_task(S.apply_steps, (steps, "optimization"), self.applied)

    def applied(self, res):
        self.b_apply.setText(_("Aplicar seleção"))
        if isinstance(res, Exception):
            A.warn(self, _("Otimização"), str(res))
        else:
            ok = sum(1 for r in res if r["ok"])
            bad = next((r for r in res if not r["ok"]), None)
            msg = _("{ok} de {total} alterações aplicadas").format(ok=ok, total=len(res))
            if bad and bad.get("message"):
                msg += ": " + step_err(bad["message"])
            A.notify(self, _("Otimização"), msg, ok=bad is None)
        self.reload(True)
        self.win.invalidate("overview")
        self.win.invalidate("services")
        self.win.invalidate("history")


# ================================================================= ARRANQUE
class BootPage(SysPage):
    def __init__(self, win):
        super().__init__(win)
        self.data = None
        self.finish_toolbar()
        self.body_w, self.body = plain(QtWidgets.QVBoxLayout)
        self.body.setSpacing(14)
        self.lay.addWidget(self.body_w)
        self.lay.addStretch(1)

    def wait_text(self):
        return _("A ler o arranque…")

    def notes(self):
        return (_("Análise de arranque"),
                _("Mostra quanto tempo demorou o último arranque, como esse tempo se dividiu (firmware, kernel, arranque do sistema) e que unidades o tornaram mais lento."),
                [_("Os primeiros valores são as fases do arranque: quanto maior a parte, mais pesa. As cores vão do verde (pequeno) ao vermelho (metade ou mais)."),
                 _("«Unidades mais lentas» lista o que demorou mais a arrancar. Um tempo longo nem sempre atrasou o arranque: outras unidades arrancavam ao mesmo tempo."),
                 _("A cadeia crítica mostra as unidades que o arranque realmente teve de esperar, por ordem. Só estas encurtam o arranque se forem aceleradas ou desativadas.")],
                _("Estes valores pertencem ao arranque em curso e não mudam até reiniciar. Os temporizadores frequentes não afetam o arranque, mas mantêm o sistema acordado."))

    def reload(self, force=False):
        if self.busy:
            return
        clear(self.body)
        self.body.addWidget(empty_note(_("A ler o arranque…")))
        self.spawn(self._gather, (), self._loaded)

    @staticmethod
    def _gather():
        return dict(boot=S.boot_analysis(), hist=S.boot_history(), timers=S.frequent_timers())

    def _loaded(self, res):
        clear(self.body)
        if isinstance(res, Exception):
            self.body.addWidget(empty_note(_("Não foi possível ler o arranque")))
            return
        self.data = res
        self.render_all()

    def render_all(self):
        d = self.data
        if d is None:
            return
        clear(self.body)
        bt = d["boot"]["boot"]
        f, v = tcard(_("Total"))
        if not bt:
            v.addWidget(empty_note(_("O tempo de arranque não está disponível: o systemd-analyze não devolveu dados.")))
        else:
            v.addWidget(lbl(fmt_ms(bt["total"]), "big"))
            names = {"firmware": _("Firmware"), "loader": _("Carregador"), "kernel": _("Kernel"),
                     "initrd": _("Initrd"), "userspace": _("Sistema")}
            parts = [(k, bt["parts"][k]) for k in ("firmware", "loader", "kernel", "initrd", "userspace") if k in bt["parts"]]
            v.addWidget(StackBar([p[1] for p in parts], bt["total"]))
            grid = QtWidgets.QHBoxLayout()
            for k, ms in parts:
                cell = QtWidgets.QVBoxLayout()
                cell.setSpacing(0)
                cell.addWidget(lbl(names[k], "muted"))
                val = lbl(fmt_ms(ms), "h2")
                val.setStyleSheet(f"color: {col(share_tone(ms / max(1, bt['total'])))};")
                cell.addWidget(val)
                grid.addLayout(cell)
            v.addLayout(grid)
        self.body.addWidget(f)
        sl = d["boot"]["slowest"]
        if sl:
            f, v = tcard(_("Unidades mais lentas no arranque"))
            mx = max(1, sl[0]["ms"])
            for s in sl:
                v.addWidget(bar_row(s["name"], s["ms"] / mx, fmt_ms(s["ms"]), share_tone(s["ms"] / max(1, bt["total"] if bt else mx)), 230, 80))
            self.body.addWidget(f)
        ch = d["boot"]["chain"]
        if ch:
            f, v = tcard(_("Cadeia crítica"))
            v.addWidget(lbl(_("O que realmente decidiu quanto durou o arranque, pela ordem em que aconteceu. O arranque esperou por cada passo antes de avançar."), "muted", True))
            for c in ch:
                w, h = plain(QtWidgets.QHBoxLayout)
                a = lbl("@" + fmt_ms(c["at"]), "muted")
                a.setFixedWidth(80)
                h.addWidget(a)
                h.addWidget(lbl(c["name"]), 1)
                if c["took"]:
                    h.addWidget(chip("+" + fmt_ms(c["took"]), "WARN" if c["took"] > 3000 else "MUTED"))
                v.addWidget(w)
            self.body.addWidget(f)
        f, v = tcard(_("Temporizadores frequentes"))
        if not d["timers"]:
            v.addWidget(lbl(_("Nenhum temporizador corre com demasiada frequência."), "muted"))
        for t in d["timers"]:
            w, h = plain(QtWidgets.QHBoxLayout)
            h.addWidget(lbl(t["name"]), 1)
            h.addWidget(chip(_("a cada {i}").format(i=fmt_interval(t["period"])), "WARN"))
            v.addWidget(w)
        v.addWidget(lbl(_("Os temporizadores com um intervalo curto acordam o sistema e gastam mais bateria."), "muted", True))
        self.body.addWidget(f)
        f, v = tcard(_("Últimos arranques"))
        acc = d["hist"]["access"]
        boots = d["hist"]["boots"]
        if not acc["can_read"]:
            if acc["pending"]:
                v.addWidget(lbl(_("O seu utilizador já está no grupo systemd-journal. Reinicie a sessão ou o computador para ver o histórico de arranques."), None, True))
            else:
                v.addWidget(lbl(_("O seu utilizador não pode ler o diário do sistema, onde estão os arranques anteriores. Adicioná-lo ao grupo systemd-journal mostra-os."), None, True))
                b = QtWidgets.QPushButton(_("Adicionar aos grupos"))
                b.setObjectName("primary")
                b.clicked.connect(lambda _c=False: self.grant())
                v.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        elif len(boots) <= 1:
            v.addWidget(lbl(_("Só este arranque tem dados: o diário não guarda os anteriores."), "muted", True))
        if boots:
            tt = [b["total"] for b in boots]
            if len(boots) > 1:
                v.addWidget(lbl(_("Média {avg} · melhor {best} · pior {worst}").format(
                    avg=fmt_ms(sum(tt) / len(tt)), best=fmt_ms(min(tt)), worst=fmt_ms(max(tt))), "muted"))
            mx = max(tt)
            for i, b in enumerate(boots):
                name = fmt_time(b["at"]) + (" · " + _("Este arranque") if i == 0 else "")
                v.addWidget(bar_row(name, b["total"] / mx, fmt_ms(b["total"]), "ACCENT", 200, 80))
        self.body.addWidget(f)

    def grant(self):
        self.win.run_task(S.grant_journal_access, (), self.granted)

    def granted(self, res):
        if isinstance(res, Exception) or not res[0]:
            A.warn(self, _("Arranque"), _("Não foi possível adicionar o utilizador: {reason}").format(
                reason=step_err(res[1]) if not isinstance(res, Exception) else str(res)))
        else:
            A.notify(self, _("Arranque"), _("Utilizador adicionado ao systemd-journal. Reinicie a sessão ou o computador para ver o histórico de arranques."))
        self.reload(True)


# ================================================================= HISTÓRICO
class HistoryPage(SysPage):
    STALE_SECS = 5

    def __init__(self, win):
        super().__init__(win)
        self.items = []
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Pesquisar no histórico…"))
        self.count = lbl("", "muted")
        self.tool.addWidget(self.search, 1)
        self.tool.addWidget(self.count)
        self.finish_toolbar()
        self.lay.addWidget(lbl(_("Cada alteração feita a partir desta aplicação fica registada e pode ser desfeita."), "muted", True))
        self.table = A.make_table([_("Data"), _("Ação"), _("Unidade"), _("Resultado"), ""], multi=False)
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for i in (0, 1, 3, 4):
            hh.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.lay.addWidget(self.table, 1)
        self.empty = empty_note(_("Ainda não alterou nada a partir desta aplicação."))
        self.lay.addWidget(self.empty)
        self.search.textChanged.connect(lambda _t: self.fill())

    def render_all(self):
        self.fill()

    def notes(self):
        return (_("Histórico"),
                _("O registo das alterações feitas a partir desta aplicação: serviços iniciados, parados ou ativados, otimizações e reparações."),
                [_("Pesquise por data, ação ou unidade."),
                 _("Carregue em «Desfazer» para aplicar o contrário do que foi feito; mostra primeiro o que vai mudar."),
                 _("As otimizações aparecem agrupadas numa só linha.")],
                _("Só se podem desfazer alterações de arranque e de estado dos serviços. Reinstalações de pacotes e remoções de ligações quebradas ficam registadas, mas não se desfazem."))

    def reload(self, force=False):
        self.items = list(reversed(S.history_load()))
        self.loaded_at = time.time()
        self.fill()

    def fill(self):
        q = self.search.text().strip().lower()
        rows = []
        for r in self.items:
            blob = " ".join([history_title(r)] + [s["unit"] for s in r["steps"]]).lower()
            if not q or q in blob:
                rows.append(r)
        self.table.setRowCount(len(rows))
        res_names = {"ok": _("feito"), "partial": _("parcial"), "failed": _("falhou"), "cancelled": _("cancelado")}
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, A.titem(fmt_time(r["at"])))
            if r["source"] == "optimization":
                act, unit = _("Otimização ({n})").format(n=len(r["steps"])), ", ".join(s["unit"] for s in r["steps"][:3]) + ("…" if len(r["steps"]) > 3 else "")
            else:
                act, unit = action_label(r["steps"][0]["action"]), r["steps"][0]["unit"]
            self.table.setItem(i, 1, A.titem(act))
            self.table.setItem(i, 2, A.titem(unit))
            txt = res_names.get(r["result"], r["result"]) + (" · " + _("desfeito") if r.get("undone") else "")
            it = A.titem(txt)
            tone = {"ok": "OK", "partial": "WARN", "failed": "DANGER"}.get(r["result"])
            if tone:
                it.setForeground(QtGui.QBrush(QtGui.QColor(col(tone))))
            self.table.setItem(i, 3, it)
            if S.can_undo(r):
                b = small_btn(_("Desfazer"))
                b.clicked.connect(lambda _c=False, r=r: self.undo(r))
                self.table.setCellWidget(i, 4, b)
            else:
                self.table.removeCellWidget(i, 4)
                self.table.setItem(i, 4, A.titem(""))
        self.count.setText(_("{shown} de {total}").format(shown=len(rows), total=len(self.items)))
        self.empty.setVisible(not self.items)
        self.table.setVisible(bool(self.items))

    def undo(self, rec):
        steps = S.undo_steps(rec)
        txt = _("Vai ser aplicado o contrário do que foi feito:") + "\n\n" + "\n".join(
            f"• {action_label(s['action'])}: {s['unit']}" for s in steps[:12])
        if not A.ask(self, _("Desfazer esta alteração?"), txt):
            return
        self.win.run_task(S.apply_steps, (steps, "undo", False), lambda res: self.undone(rec, res))

    def undone(self, rec, res):
        if isinstance(res, Exception) or not all(r["ok"] for r in res):
            bad = next((r for r in res if not r["ok"]), {}) if not isinstance(res, Exception) else {}
            A.warn(self, _("Histórico"), _("Não foi possível desfazer") + (": " + step_err(bad.get("message", "")) if bad else ""))
        else:
            S.history_mark_undone(rec["id"])
            self.toast(_("Alteração desfeita"))
        self.reload(True)
        self.win.invalidate("services")
        self.win.invalidate("overview")
