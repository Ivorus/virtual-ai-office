# -*- coding: utf-8 -*-
"""
Virtual AI Office v4 — Windows 11 Desktop App
Complete: Quick commands editor, EXE builder, furniture drag, floors, design panel
"""
import sys, json, sqlite3, threading, requests
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QScrollArea, QFrame, QSplitter,
    QComboBox, QProgressBar, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolBar, QSizePolicy, QLineEdit, QListWidget, QListWidgetItem,
    QColorDialog, QInputDialog, QGroupBox, QSpacerItem
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPalette

from office_scene import OfficeScene, THEMES, AGENT_CFG, FloorData

BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "office.db"
CLOUD_DIR  = BASE_DIR / "office_cloud"
QUICK_FILE = BASE_DIR / "quick_commands.json"
CLOUD_DIR.mkdir(exist_ok=True)

# ── Color palette ─────────────────────────────────────────────────────────────
S = dict(
    bg="#0A0E1A", panel="#111827", card="#1A2235", input="#1E2D42",
    blue="#3B82F6", cyan="#06B6D4", green="#10B981", amber="#F59E0B",
    red="#EF4444", purp="#8B5CF6", text="#F1F5F9", muted="#64748B",
    border="#1E3A5F", dim="#334155",
)

AGENT_DEFS = {
    "programmer": {"name":"Алекс","role":"Программист","emoji":"💻","color":"#3B82F6",
        "system":"Ты Алекс — опытный программист. Пишешь код на Python, JavaScript, TypeScript и других языках. Создаёшь боты, API, веб-приложения, скрипты автоматизации. Отвечай на русском. Давай конкретный рабочий код с комментариями и объяснением."},
    "designer":   {"name":"Майя","role":"Дизайнер","emoji":"🎨","color":"#8B5CF6",
        "system":"Ты Майя — UI/UX дизайнер. Создаёшь макеты, концепции интерфейсов, брендинг, wireframes. Отвечай на русском. Описывай детально: цвета, шрифты, компоненты, UX-паттерны, accessibility. При необходимости — HTML/CSS код."},
    "sales":      {"name":"Давид","role":"Менеджер продаж","emoji":"💼","color":"#10B981",
        "system":"Ты Давид — опытный менеджер продаж. Составляешь скрипты продаж, коммерческие предложения, письма и сообщения клиентам. Отвечай на русском. Будь убедительным, профессиональным и дружелюбным. ВАЖНО: предлагай варианты, окончательное решение за пользователем."},
    "accountant": {"name":"Рита","role":"Финансовый аналитик","emoji":"📊","color":"#F59E0B",
        "system":"Ты Рита — финансовый аналитик. Помогаешь с учётом затрат, ROI-анализом, бюджетированием, финансовыми отчётами и расчётами. Отвечай на русском. Давай чёткие цифры, таблицы в markdown, формулы и конкретные рекомендации."},
    "devops":     {"name":"Макс","role":"DevOps инженер","emoji":"🔧","color":"#06B6D4",
        "system":"Ты Макс — DevOps инженер. Разбираешься в Docker, Kubernetes, CI/CD (GitHub Actions, GitLab CI), Linux, bash-скриптах, Nginx, облачных сервисах (AWS/GCP/Azure/DigitalOcean), мониторинге (Prometheus, Grafana). Отвечай на русском. Давай конкретные команды, конфиги и пошаговые инструкции."},
    "researcher": {"name":"Ана","role":"Аналитик и Автор","emoji":"🔍","color":"#EC4899",
        "system":"Ты Ана — исследователь и автор контента. Помогаешь с анализом данных, написанием статей, SEO-контентом, презентациями, переводами, маркетинговыми текстами. Отвечай на русском. Пиши структурировано, с заголовками и списками, убедительно и интересно."},
}

# Agent context memory (last 6 messages = 3 exchanges per agent)
AGENT_MEMORY: dict[str, list] = {k: [] for k in AGENT_DEFS}
MAX_MEMORY_MSGS = 6

MODELS = {
    "claude-sonnet-4-6":         {"label":"⚡ Sonnet 4.6 (Рекомендуется)", "cost_in":3.0,  "cost_out":15.0},
    "claude-haiku-4-5-20251001": {"label":"🚀 Haiku 4.5 (Быстрый/Дешёвый)","cost_in":0.8,  "cost_out":4.0},
    "claude-opus-4-6":           {"label":"🏆 Opus 4.6 (Максимум качества)","cost_in":15.0, "cost_out":75.0},
}
DEFAULT_MODEL = "claude-sonnet-4-6"

DEFAULT_COMMANDS = [
    {"emoji":"💻","text":"Напиши Python скрипт для автоматизации [опиши задачу]"},
    {"emoji":"🤖","text":"Создай Telegram бота на Python с aiogram с командами /start и /help"},
    {"emoji":"🎨","text":"Создай концепцию UI/UX для [опиши приложение]: цвета, шрифты, компоненты"},
    {"emoji":"📋","text":"Составь профессиональное письмо клиенту о [тема] для WhatsApp/Email"},
    {"emoji":"📊","text":"Создай таблицу учёта расходов и ROI-анализ для проекта"},
    {"emoji":"🔧","text":"Напиши Docker Compose файл для [опиши стек: Python/Node/PostgreSQL]"},
    {"emoji":"🔍","text":"Исследуй тему [тема] и напиши структурированный отчёт с выводами"},
    {"emoji":"📝","text":"Напиши SEO-статью на тему [тема]: заголовки, структура, ключевые слова"},
]

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._l = threading.Lock()
        self.conn.cursor().executescript("""
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_key TEXT, task_text TEXT, response TEXT,
                status TEXT DEFAULT 'pending',
                tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0,
                created_at TEXT, completed_at TEXT, approved INTEGER DEFAULT 0
            );""")
        self.conn.commit()

    def add_task(self, ak, tt):
        with self._l:
            c = self.conn.cursor()
            c.execute("INSERT INTO tasks(agent_key,task_text,status,created_at)VALUES(?,?,?,?)",
                      (ak, tt, "working", datetime.now().isoformat()))
            self.conn.commit(); return c.lastrowid

    def update_task(self, tid, r, ti, to, cost):
        with self._l:
            self.conn.cursor().execute(
                "UPDATE tasks SET response=?,status='awaiting_approval',"
                "tokens_in=?,tokens_out=?,cost_usd=?,completed_at=? WHERE id=?",
                (r, ti, to, cost, datetime.now().isoformat(), tid))
            self.conn.commit()

    def approve_task(self, tid):
        with self._l:
            self.conn.cursor().execute(
                "UPDATE tasks SET status='approved',approved=1 WHERE id=?", (tid,))
            self.conn.commit()

    def reject_task(self, tid):
        with self._l:
            self.conn.cursor().execute(
                "UPDATE tasks SET status='rejected' WHERE id=?", (tid,))
            self.conn.commit()

    def get_stats(self):
        with self._l:
            r = self.conn.cursor().execute(
                "SELECT COUNT(*),SUM(cost_usd),SUM(tokens_in+tokens_out) "
                "FROM tasks WHERE status='approved'").fetchone()
            return {"tasks": r[0] or 0, "cost": r[1] or 0.0, "tokens": r[2] or 0}

    def get_all_tasks(self):
        with self._l:
            return self.conn.cursor().execute(
                "SELECT id,agent_key,task_text,status,cost_usd,created_at "
                "FROM tasks ORDER BY id DESC LIMIT 60").fetchall()

DB = Database()

# ─────────────────────────────────────────────────────────────────────────────
# API WORKER
# ─────────────────────────────────────────────────────────────────────────────
class AgentWorker(QThread):
    finished = Signal(int, str, int, int, float)
    error    = Signal(int, str)

    def __init__(self, tid, ak, tt, key, model=DEFAULT_MODEL):
        super().__init__()
        self.tid, self.ak, self.tt, self.key, self.model = tid, ak, tt, key, model

    def run(self):
        try:
            # Build messages with agent memory context
            messages = list(AGENT_MEMORY.get(self.ak, [])[-MAX_MEMORY_MSGS:])
            messages.append({"role":"user","content":self.tt})

            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type":"application/json",
                         "x-api-key": self.key,
                         "anthropic-version":"2023-06-01"},
                json={"model": self.model, "max_tokens":4096,
                      "system": AGENT_DEFS[self.ak]["system"],
                      "messages": messages},
                timeout=120)
            d = r.json()
            if r.status_code != 200:
                self.error.emit(self.tid, d.get("error",{}).get("message","API Error"))
                return
            text = d["content"][0]["text"]
            ti   = d.get("usage",{}).get("input_tokens",0)
            to_  = d.get("usage",{}).get("output_tokens",0)
            pricing = MODELS.get(self.model, MODELS[DEFAULT_MODEL])
            cost = (ti * pricing["cost_in"] + to_ * pricing["cost_out"]) / 1_000_000
            DB.update_task(self.tid, text, ti, to_, cost)
            # Update agent memory
            AGENT_MEMORY[self.ak].append({"role":"user","content":self.tt})
            AGENT_MEMORY[self.ak].append({"role":"assistant","content":text})
            if len(AGENT_MEMORY[self.ak]) > MAX_MEMORY_MSGS:
                AGENT_MEMORY[self.ak] = AGENT_MEMORY[self.ak][-MAX_MEMORY_MSGS:]
            (CLOUD_DIR/f"task_{self.tid}_{self.ak}.txt").write_text(
                f"Агент: {AGENT_DEFS[self.ak]['name']}\nМодель: {self.model}\nЗадача: {self.tt}\n\n{text}",
                encoding="utf-8")
            self.finished.emit(self.tid, text, ti, to_, cost)
        except Exception as e:
            self.error.emit(self.tid, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# TASK CARD
# ─────────────────────────────────────────────────────────────────────────────
class TaskCard(QFrame):
    approved = Signal(int)
    rejected = Signal(int)

    def __init__(self, tid, ak, tt, resp, cost, tokens):
        super().__init__()
        cfg = AGENT_DEFS[ak]; self.tid = tid; self._done = False
        self.setObjectName("TC")
        self.setStyleSheet(
            f"QFrame#TC{{background:{S['card']};border:1px solid {S['border']};"
            f"border-left:3px solid {cfg['color']};border-radius:8px;}}")
        lay = QVBoxLayout(self); lay.setContentsMargins(12,10,12,10); lay.setSpacing(6)

        hdr = QHBoxLayout()
        ic  = QLabel(cfg["emoji"]); ic.setFont(QFont("Segoe UI Emoji",14))
        nm  = QLabel(f"<b>{cfg['name']}</b> · {cfg['role']}")
        nm.setStyleSheet(f"color:{cfg['color']};font-size:12px;")
        mt  = QLabel(f"${cost:.4f} | {tokens} tok")
        mt.setStyleSheet(f"color:{S['muted']};font-size:11px;")
        hdr.addWidget(ic); hdr.addWidget(nm); hdr.addStretch(); hdr.addWidget(mt)
        lay.addLayout(hdr)

        tl = QLabel(f"📌 {tt[:110]}{'...' if len(tt)>110 else ''}")
        tl.setStyleSheet(f"color:{S['muted']};font-size:11px;"); tl.setWordWrap(True)
        lay.addWidget(tl)

        rt = QTextEdit(); rt.setPlainText(resp); rt.setReadOnly(True); rt.setMaximumHeight(110)
        rt.setStyleSheet(
            f"QTextEdit{{background:{S['input']};color:{S['text']};"
            f"border:1px solid {S['border']};border-radius:4px;"
            f"font-size:12px;font-family:Consolas;padding:6px;}}")
        lay.addWidget(rt)

        self._resp_text = resp
        self._br = QHBoxLayout()
        w = QLabel("⚠️  Ожидает вашего разрешения")
        w.setStyleSheet(f"color:{S['amber']};font-size:11px;font-weight:bold;")
        self._br.addWidget(w); self._br.addStretch()
        self._br.addWidget(self._btn("📋  Копировать", S['dim'],   self._copy))
        self._br.addWidget(self._btn("❌  Отклонить",  S['red'],   self._reject))
        self._br.addWidget(self._btn("✅  Разрешить",  S['green'], self._approve))
        lay.addLayout(self._br)

    def _btn(self, t, c, fn):
        b = QPushButton(t); b.setFixedHeight(28)
        b.setStyleSheet(
            f"QPushButton{{background:{c};color:white;border:none;"
            f"border-radius:5px;font-size:12px;font-weight:bold;padding:0 14px;}}"
            f"QPushButton:hover{{opacity:.85;}}")
        b.clicked.connect(fn); return b

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._resp_text)

    def _approve(self):
        if self._done: return
        self._done = True; self._clr("✅  Выполнено и одобрено", S['green'])
        DB.approve_task(self.tid); self.approved.emit(self.tid)

    def _reject(self):
        if self._done: return
        self._done = True; self._clr("❌  Отклонено", S['red'])
        DB.reject_task(self.tid); self.rejected.emit(self.tid)

    def _clr(self, msg, col):
        while self._br.count():
            it = self._br.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        l = QLabel(msg); l.setStyleSheet(f"color:{col};font-size:12px;font-weight:bold;")
        self._br.addWidget(l)

# ─────────────────────────────────────────────────────────────────────────────
# DIALOGS
# ─────────────────────────────────────────────────────────────────────────────
DIALOG_STYLE = (
    f"QDialog{{background:{S['panel']};color:{S['text']};}}"
    f"QLabel{{color:{S['text']};font-size:12px;}}"
    f"QLineEdit,QTextEdit{{background:{S['input']};color:{S['text']};"
    f"border:1px solid {S['border']};border-radius:5px;padding:6px;font-size:12px;}}"
    f"QPushButton{{background:{S['input']};color:{S['text']};"
    f"border:1px solid {S['border']};border-radius:5px;padding:5px 12px;font-size:12px;}}"
    f"QPushButton:hover{{border-color:{S['blue']};}}"
    f"QListWidget{{background:{S['card']};color:{S['text']};"
    f"border:1px solid {S['border']};border-radius:6px;font-size:12px;}}"
    f"QListWidget::item{{padding:8px;border-bottom:1px solid {S['border']};}}"
    f"QListWidget::item:selected{{background:{S['blue']};border-radius:4px;}}"
    f"QComboBox{{background:{S['input']};color:{S['text']};"
    f"border:1px solid {S['border']};border-radius:5px;padding:6px;font-size:12px;}}"
    f"QGroupBox{{color:{S['muted']};border:1px solid {S['border']};"
    f"border-radius:6px;padding:10px;margin-top:14px;font-size:11px;font-weight:bold;}}"
    f"QGroupBox::title{{subcontrol-origin:margin;left:8px;padding:0 4px;}}"
)

def accent_btn(text, color, parent=None):
    b = QPushButton(text, parent); b.setFixedHeight(30)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:white;border:none;"
        f"border-radius:5px;font-size:12px;font-weight:bold;padding:0 14px;}}"
        f"QPushButton:hover{{opacity:.85;}}")
    return b


# ── Quick Commands Editor ─────────────────────────────────────────────────────
class QuickCommandsDialog(QDialog):
    def __init__(self, commands, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Быстрые команды — Редактор")
        self.setMinimumSize(580, 500); self.setStyleSheet(DIALOG_STYLE)
        self.commands = [dict(c) for c in commands]

        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        t = QLabel("📋  Управление быстрыми командами")
        t.setStyleSheet(f"color:{S['cyan']};font-size:14px;font-weight:bold;"); lay.addWidget(t)

        self.lst = QListWidget()
        self.lst.itemClicked.connect(self._load)
        lay.addWidget(self.lst, stretch=2)

        # Edit form
        fb = QFrame(); fb.setStyleSheet(
            f"QFrame{{background:{S['card']};border:1px solid {S['border']};border-radius:8px;}}")
        fl = QFormLayout(fb); fl.setContentsMargins(14,12,14,12); fl.setSpacing(8)
        self.e_emoji = QLineEdit(); self.e_emoji.setFixedWidth(64); self.e_emoji.setPlaceholderText("📌")
        self.e_text  = QLineEdit(); self.e_text.setPlaceholderText("Текст команды...")
        fl.addRow("Emoji:", self.e_emoji); fl.addRow("Команда:", self.e_text)

        row = QHBoxLayout()
        b_add  = accent_btn("➕ Добавить",  S['green']); b_add.clicked.connect(self._add)
        b_save = accent_btn("✏️ Сохранить", S['blue']);  b_save.clicked.connect(self._save)
        b_del  = accent_btn("🗑 Удалить",   S['red']);   b_del.clicked.connect(self._delete)
        row.addWidget(b_add); row.addWidget(b_save); row.addWidget(b_del); row.addStretch()
        fl.addRow(row); lay.addWidget(fb)

        cb = accent_btn("Закрыть", S['dim']); cb.clicked.connect(self.accept); 
        cb.setStyleSheet(f"QPushButton{{background:{S['dim']};color:{S['text']};border:none;border-radius:5px;font-size:12px;padding:5px 20px;}}")
        lay.addWidget(cb, alignment=Qt.AlignRight)
        self._refresh()

    def _refresh(self):
        self.lst.clear()
        for c in self.commands: self.lst.addItem(f"  {c['emoji']}  {c['text']}")

    def _load(self, _):
        i = self.lst.currentRow()
        if 0 <= i < len(self.commands):
            self.e_emoji.setText(self.commands[i]["emoji"])
            self.e_text.setText(self.commands[i]["text"])

    def _add(self):
        text = self.e_text.text().strip()
        if not text: QMessageBox.warning(self,"","Введите текст команды."); return
        self.commands.append({"emoji": self.e_emoji.text().strip() or "📌", "text": text})
        self._refresh(); self.e_emoji.clear(); self.e_text.clear()

    def _save(self):
        i = self.lst.currentRow()
        if i < 0: QMessageBox.warning(self,"","Выберите команду в списке."); return
        text = self.e_text.text().strip()
        if not text: return
        self.commands[i] = {"emoji": self.e_emoji.text().strip() or "📌", "text": text}
        self._refresh(); self.lst.setCurrentRow(i)

    def _delete(self):
        i = self.lst.currentRow()
        if i < 0: return
        self.commands.pop(i); self._refresh(); self.e_emoji.clear(); self.e_text.clear()


# ── Design Panel ─────────────────────────────────────────────────────────────
class DesignPanel(QDialog):
    def __init__(self, office: OfficeScene, parent=None):
        super().__init__(parent)
        self.office = office
        self.setWindowTitle("🎨  Дизайн офиса")
        self.setMinimumSize(560, 640); self.setStyleSheet(DIALOG_STYLE)

        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        lay.addWidget(self._heading("🎨  Редактор дизайна офиса"))

        # Theme picker
        tg = QGroupBox("Тема оформления")
        tl = QVBoxLayout(tg); tl.setSpacing(5)
        cur = self.office.floors[self.office.current_floor].theme
        for name, colors in THEMES.items():
            b = QPushButton(f"  {name}")
            b.setCheckable(True); b.setChecked(name == cur)
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton{{background:{colors['fa']};color:{colors['tx']};"
                f"border:2px solid {colors['accent']};border-radius:5px;"
                f"text-align:left;padding:0 10px;font-size:12px;font-weight:bold;}}"
                f"QPushButton:checked{{border:3px solid #FBBF24;}}"
                f"QPushButton:hover{{opacity:.85;}}")
            b.clicked.connect(lambda _, n=name: self._theme(n))
            tl.addWidget(b)
        lay.addWidget(tg)

        # Furniture
        fg = QGroupBox("Добавить мебель")
        fl2 = QHBoxLayout(fg); fl2.setSpacing(6); fl2.setContentsMargins(6,10,6,6)
        fl2.setFlexibleDirections = None
        furn_left  = QVBoxLayout(); furn_right = QVBoxLayout()
        items = [
            ("🖥  Рабочий стол","desk"),("🛋  Диван","sofa"),
            ("☕  Кофемашина","coffee_machine"),("🌿  Растение","plant"),
            ("📋  Стол переговоров","meeting_table"),("🚽  Туалет","toilet"),
            ("🚿  Раковина","sink"),("📚  Стеллаж","bookshelf"),
            ("📌  Доска","whiteboard"),("🖥  Серверная стойка","server_rack"),
        ]
        for i,(label,ftype) in enumerate(items):
            b = QPushButton(label); b.setFixedHeight(28)
            b.clicked.connect(lambda _,ft=ftype: self._add_furn(ft))
            (furn_left if i%2==0 else furn_right).addWidget(b)
        fl2.addLayout(furn_left); fl2.addLayout(furn_right)
        lay.addWidget(fg)

        # Edit tools
        eg = QGroupBox("Инструменты редактирования")
        el = QHBoxLayout(eg); el.setSpacing(6)
        self._edit_btn = QPushButton("✏️  Включить перемещение мебели")
        self._edit_btn.setCheckable(True); self._edit_btn.setFixedHeight(30)
        self._edit_btn.setStyleSheet(
            f"QPushButton{{background:{S['input']};color:{S['text']};"
            f"border:1px solid {S['border']};border-radius:5px;padding:0 12px;font-size:12px;}}"
            f"QPushButton:checked{{background:{S['amber']};color:#111;border:none;font-weight:bold;}}")
        self._edit_btn.toggled.connect(self._toggle_edit)

        b_del = accent_btn("🗑  Удалить выбранное", S['red'])
        b_del.clicked.connect(lambda: self.office.delete_selected())
        b_col = accent_btn("🎨  Перекрасить", S['purp'])
        b_col.clicked.connect(self._recolor)

        el.addWidget(self._edit_btn); el.addWidget(b_del); el.addWidget(b_col)
        lay.addWidget(eg)

        # Floor name
        ng = QGroupBox("Переименовать текущий этаж")
        nl = QHBoxLayout(ng); nl.setSpacing(6)
        self.name_edit = QLineEdit(self.office.floors[self.office.current_floor].name)
        b_ren = accent_btn("Сохранить", S['blue']); b_ren.setFixedWidth(90)
        b_ren.clicked.connect(self._rename)
        nl.addWidget(self.name_edit); nl.addWidget(b_ren)
        lay.addWidget(ng)

        lay.addStretch()
        close_btn = accent_btn("Закрыть", S['dim'])
        close_btn.setStyleSheet(f"QPushButton{{background:{S['dim']};color:{S['text']};border:none;border-radius:5px;font-size:12px;padding:5px 20px;}}")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignRight)

    def _heading(self, text):
        l = QLabel(text); l.setStyleSheet(f"color:{S['cyan']};font-size:14px;font-weight:bold;"); return l

    def _theme(self, name):
        self.office.set_floor_theme(name)

    def _add_furn(self, ftype):
        self.office.add_furniture(ftype)

    def _toggle_edit(self, on):
        self.office.set_edit_mode(on)
        self._edit_btn.setText("✏️  Выключить перемещение" if on else "✏️  Включить перемещение мебели")

    def _recolor(self):
        col = QColorDialog.getColor(QColor("#3B82F6"), self, "Выберите цвет")
        if col.isValid(): self.office.recolor_selected(col.name())

    def _rename(self):
        n = self.name_edit.text().strip()
        if n: self.office.rename_floor(n)


# ── Floor Manager ─────────────────────────────────────────────────────────────
class FloorManager(QDialog):
    switched = Signal(int)
    def __init__(self, office: OfficeScene, parent=None):
        super().__init__(parent)
        self.office = office
        self.setWindowTitle("🏢  Небоскрёб — Управление этажами")
        self.setMinimumSize(520, 460); self.setStyleSheet(DIALOG_STYLE)
        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)

        t = QLabel("🏢  Твой небоскрёб")
        t.setStyleSheet(f"color:{S['cyan']};font-size:14px;font-weight:bold;"); lay.addWidget(t)
        note = QLabel("Двойной клик — перейти на этаж")
        note.setStyleSheet(f"color:{S['muted']};font-size:11px;"); lay.addWidget(note)

        self.lst = QListWidget(); self.lst.setMinimumHeight(180)
        self.lst.itemDoubleClicked.connect(lambda: self._switch(self.lst.currentRow()))
        lay.addWidget(self.lst)

        br = QHBoxLayout()
        b_add  = accent_btn("➕  Добавить этаж", S['green']); b_add.clicked.connect(self._add)
        b_go   = accent_btn("🔀  Перейти",      S['blue']);  b_go.clicked.connect(lambda: self._switch(self.lst.currentRow()))
        b_del  = accent_btn("🗑  Удалить",       S['red']);   b_del.clicked.connect(self._delete)
        br.addWidget(b_add); br.addWidget(b_go); br.addWidget(b_del); br.addStretch()
        lay.addLayout(br)

        # Send agent
        sg = QGroupBox("Отправить агента на другой этаж")
        sl = QHBoxLayout(sg); sl.setSpacing(8)
        self._ac = QComboBox()
        for k,d in AGENT_DEFS.items(): self._ac.addItem(f"{d['emoji']} {d['name']}",k)
        self._fc = QComboBox()
        b_send = accent_btn("🚀  Отправить", S['blue'])
        b_send.clicked.connect(self._send_agent)
        sl.addWidget(QLabel("Агент:")); sl.addWidget(self._ac)
        sl.addWidget(QLabel("на:")); sl.addWidget(self._fc)
        sl.addWidget(b_send)
        lay.addWidget(sg)

        cb = QPushButton("Закрыть"); cb.setFixedHeight(30)
        cb.setStyleSheet(f"QPushButton{{background:{S['dim']};color:{S['text']};border:none;border-radius:5px;font-size:12px;padding:0 20px;}}")
        cb.clicked.connect(self.accept); lay.addWidget(cb, alignment=Qt.AlignRight)
        self._refresh()

    def _refresh(self):
        self.lst.clear(); self._fc.clear()
        for fl in self.office.floors:
            agents_str = ", ".join(AGENT_CFG.get(a,{}).get("name","?") for a in fl.agents)
            marker = "➤ " if fl.idx == self.office.current_floor else "    "
            self.lst.addItem(f"{marker}🏢  {fl.name}  [{agents_str or '—'}]")
            self._fc.addItem(f"Этаж {fl.idx+1} — {fl.name}", fl.idx)

    def _add(self):
        name, ok = QInputDialog.getText(self,"Новый этаж","Название этажа:")
        if ok and name.strip(): self.office.add_floor(name.strip()); self._refresh()

    def _switch(self, idx):
        if 0 <= idx < len(self.office.floors):
            self.office.switch_floor(idx); self.switched.emit(idx); self._refresh()

    def _delete(self):
        idx = self.lst.currentRow()
        if idx <= 0: QMessageBox.warning(self,"","Нельзя удалить первый этаж."); return
        if QMessageBox.question(self,"Удалить?",
                f"Удалить «{self.office.floors[idx].name}»?") == QMessageBox.Yes:
            self.office.delete_floor(idx); self._refresh()
            self.switched.emit(self.office.current_floor)

    def _send_agent(self):
        ak   = self._ac.currentData()
        fidx = self._fc.currentData()
        self.office.send_agent_to_floor(ak, fidx)
        self._refresh(); self.switched.emit(fidx)


# ── Settings ──────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, key="", model=DEFAULT_MODEL, parent=None):
        super().__init__(parent); self.setWindowTitle("⚙️  Настройки")
        self.setFixedSize(520, 260); self.setStyleSheet(DIALOG_STYLE)
        lay = QFormLayout(self); lay.setSpacing(14); lay.setContentsMargins(24,24,24,24)
        self.api = QLineEdit(key); self.api.setEchoMode(QLineEdit.Password)
        self.api.setPlaceholderText("sk-ant-api03-...")
        lay.addRow("Anthropic API Key:", self.api)
        lay.addRow(QLabel("  Ключ хранится локально. Получите на console.anthropic.com"))

        self.model_cb = QComboBox()
        for mid, minfo in MODELS.items():
            self.model_cb.addItem(minfo["label"], mid)
        cur_idx = list(MODELS.keys()).index(model) if model in MODELS else 0
        self.model_cb.setCurrentIndex(cur_idx)
        lay.addRow("Модель AI:", self.model_cb)

        pricing = MODELS.get(model, MODELS[DEFAULT_MODEL])
        self._price_lbl = QLabel(
            f"  Цена: ${pricing['cost_in']}/M вход · ${pricing['cost_out']}/M выход")
        self._price_lbl.setStyleSheet(f"color:{S['muted']};font-size:11px;")
        lay.addRow(self._price_lbl)
        self.model_cb.currentIndexChanged.connect(self._update_price)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"QPushButton{{background:{S['blue']};color:white;border:none;border-radius:5px;padding:6px 20px;font-size:12px;}}")
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def _update_price(self):
        mid = self.model_cb.currentData()
        pricing = MODELS.get(mid, MODELS[DEFAULT_MODEL])
        self._price_lbl.setText(
            f"  Цена: ${pricing['cost_in']}/M вход · ${pricing['cost_out']}/M выход")

    def get_key(self):   return self.api.text().strip()
    def get_model(self): return self.model_cb.currentData() or DEFAULT_MODEL


# ── Reports Tab ───────────────────────────────────────────────────────────────
class ReportsTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(14,14,14,14); lay.setSpacing(10)
        sr = QHBoxLayout()
        self._ct = self._card("Задач выполнено", "0",      S['blue'])
        self._cc = self._card("Потрачено API",  "$0.0000", S['amber'])
        self._ck = self._card("Токенов",         "0",      S['purp'])
        for c in (self._ct, self._cc, self._ck): sr.addWidget(c)
        lay.addLayout(sr)

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["ID","Агент","Задача","Статус","Стоимость","Дата"])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.setStyleSheet(
            f"QTableWidget{{background:{S['card']};color:{S['text']};"
            f"gridline-color:{S['border']};border:1px solid {S['border']};border-radius:6px;font-size:12px;}}"
            f"QHeaderView::section{{background:{S['input']};color:{S['muted']};"
            f"border:none;padding:6px;font-size:11px;font-weight:bold;}}"
            f"QTableWidget::item{{padding:4px 8px;}}"
            f"QTableWidget::item:selected{{background:{S['blue']};}}")
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.tbl)

        rb = QPushButton("🔄  Обновить отчёт"); rb.setFixedHeight(30)
        rb.setStyleSheet(f"QPushButton{{background:{S['input']};color:{S['text']};"
                         f"border:1px solid {S['border']};border-radius:5px;font-size:12px;padding:0 16px;}}"
                         f"QPushButton:hover{{background:{S['border']};}}")
        rb.clicked.connect(self.refresh); lay.addWidget(rb)
        self.refresh()

    def _card(self, label, val, col):
        f = QFrame(); f.setFixedHeight(68)
        f.setStyleSheet(f"QFrame{{background:{S['card']};border:1px solid {S['border']};"
                        f"border-top:3px solid {col};border-radius:8px;}}")
        l = QVBoxLayout(f); l.setContentsMargins(14,8,14,8)
        lb = QLabel(label); lb.setStyleSheet(f"color:{S['muted']};font-size:11px;border:none;")
        vl = QLabel(val); vl.setStyleSheet(f"color:{col};font-size:18px;font-weight:bold;border:none;")
        vl.setObjectName("val"); l.addWidget(lb); l.addWidget(vl); return f

    def refresh(self):
        s = DB.get_stats()
        self._ct.findChild(QLabel,"val").setText(str(s["tasks"]))
        self._cc.findChild(QLabel,"val").setText(f"${s['cost']:.4f}")
        self._ck.findChild(QLabel,"val").setText(f"{s['tokens']:,}")
        sm = {"working":("⚙️ Работает",S['amber']),"awaiting_approval":("⏳ Ждёт",S['cyan']),
              "approved":("✅ Одобрено",S['green']),"rejected":("❌ Отклонено",S['red'])}
        rows = DB.get_all_tasks(); self.tbl.setRowCount(len(rows))
        for ri,(tid,ak,task,status,cost,created) in enumerate(rows):
            cfg = AGENT_DEFS.get(ak,{"emoji":"🤖","name":ak})
            vals = [str(tid), f"{cfg['emoji']} {cfg['name']}",
                    task[:55]+("..." if len(task)>55 else ""),
                    sm.get(status,(status,S['text']))[0],
                    f"${cost:.4f}" if cost else "$0.0000",
                    (created or "")[:16]]
            for ci,v in enumerate(vals):
                it = QTableWidgetItem(v)
                if ci==3: it.setForeground(QColor(sm.get(status,("",S['text']))[1]))
                self.tbl.setItem(ri,ci,it)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual AI Office v5 — AI Агенты для всех 🤖")
        self.setMinimumSize(1360, 900)
        self._api_key = ""
        self._model   = DEFAULT_MODEL
        self._workers: dict = {}
        self._commands = self._load_commands()
        self._load_settings()
        self._build_ui()
        self._apply_style()

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_settings(self):
        p = BASE_DIR/"settings.json"
        if p.exists():
            try:
                d = json.loads(p.read_text())
                self._api_key = d.get("api_key","")
                self._model   = d.get("model", DEFAULT_MODEL)
            except: pass

    def _save_settings(self):
        (BASE_DIR/"settings.json").write_text(
            json.dumps({"api_key":self._api_key,"model":self._model}))

    def _load_commands(self):
        if QUICK_FILE.exists():
            try: return json.loads(QUICK_FILE.read_text(encoding="utf-8"))
            except: pass
        return list(DEFAULT_COMMANDS)

    def _save_commands(self):
        QUICK_FILE.write_text(json.dumps(self._commands, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Style ─────────────────────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet(
            f"QMainWindow,QWidget{{background:{S['bg']};color:{S['text']};"
            f"font-family:'Segoe UI',sans-serif;font-size:13px;}}"
            f"QToolBar{{background:{S['panel']};border-bottom:1px solid {S['border']};"
            f"spacing:5px;padding:3px 10px;}}"
            f"QStatusBar{{background:{S['panel']};color:{S['muted']};"
            f"border-top:1px solid {S['border']};font-size:11px;}}"
            f"QTabWidget::pane{{background:{S['bg']};border:1px solid {S['border']};border-radius:6px;}}"
            f"QTabBar::tab{{background:{S['panel']};color:{S['muted']};padding:8px 18px;border:none;font-size:12px;}}"
            f"QTabBar::tab:selected{{background:{S['card']};color:{S['text']};border-bottom:2px solid {S['blue']};}}"
            f"QTabBar::tab:hover{{color:{S['text']};}}"
            f"QScrollBar:vertical{{background:{S['panel']};width:6px;}}"
            f"QScrollBar::handle:vertical{{background:{S['dim']};border-radius:3px;}}")

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Toolbar ──
        tb = self.addToolBar("Main"); tb.setMovable(False); tb.setIconSize(QSize(16,16))
        logo = QLabel("  🏢  VIRTUAL AI OFFICE"); logo.setStyleSheet(f"color:{S['cyan']};font-size:14px;font-weight:bold;"); tb.addWidget(logo)
        sp = QWidget(); sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); tb.addWidget(sp)
        self._bal_lbl = QLabel("💰 $0.0000 | 0 задач"); self._bal_lbl.setStyleSheet(f"color:{S['amber']};font-size:12px;"); tb.addWidget(self._bal_lbl)
        self._floor_lbl = QLabel("  🏢 Этаж 1"); self._floor_lbl.setStyleSheet(f"color:{S['cyan']};font-size:12px;font-weight:bold;"); tb.addWidget(self._floor_lbl)
        tb.addSeparator()

        for txt, col, fn in [
            ("🏢  Этажи",     S['cyan'],  self._open_floors),
            ("🎨  Дизайн",    S['purp'],  self._open_design),
            ("📋  Команды",   S['green'], self._open_commands),
            ("📤  Экспорт",   S['blue'],  self._export_results),
            ("🧠  Память",    S['amber'], self._clear_memory),
            ("⚙️  Настройки", S['input'], self._open_settings),
        ]:
            b = QPushButton(txt); b.setFixedHeight(28)
            b.setStyleSheet(
                f"QPushButton{{background:{col};color:{S['text']};"
                f"border:1px solid {S['border']};border-radius:5px;"
                f"font-size:12px;padding:0 10px;}}"
                f"QPushButton:hover{{border-color:{S['blue']};}}")
            b.clicked.connect(fn); tb.addWidget(b)

        # ── Central ──
        central = QWidget(); self.setCentralWidget(central)
        ml = QVBoxLayout(central); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # Office scene
        self.office = OfficeScene()
        self.office.floor_changed.connect(self._on_floor_changed)
        ml.addWidget(self.office)

        # Splitter
        spl = QSplitter(Qt.Horizontal); spl.setHandleWidth(2)
        spl.setStyleSheet(f"QSplitter::handle{{background:{S['border']};}}"); ml.addWidget(spl)

        # ── Left panel ──
        lp = QFrame(); lp.setFixedWidth(290)
        lp.setStyleSheet(f"QFrame{{background:{S['panel']};border-right:1px solid {S['border']};}}")
        ll = QVBoxLayout(lp); ll.setContentsMargins(12,12,12,12); ll.setSpacing(7)

        ll.addWidget(self._lbl("🎯  КОМАНДОВАНИЕ", S['cyan'], 11, bold=True))
        ll.addWidget(self._lbl("Кому:", S['muted'], 11))
        self._combo = QComboBox(); self._combo.setFixedHeight(32)
        self._combo.setStyleSheet(
            f"QComboBox{{background:{S['input']};color:{S['text']};"
            f"border:1px solid {S['border']};border-radius:5px;padding:0 10px;font-size:12px;}}"
            f"QComboBox::drop-down{{border:none;}}"
            f"QComboBox QAbstractItemView{{background:{S['card']};color:{S['text']};"
            f"border:1px solid {S['border']};selection-background-color:{S['blue']};}}")
        self._combo.addItem("📢  Всем агентам", "all")
        for k,d in AGENT_DEFS.items(): self._combo.addItem(f"{d['emoji']}  {d['name']}", k)
        self._combo.currentIndexChanged.connect(lambda: self._update_memory_label())
        ll.addWidget(self._combo)

        # Quick commands (scrollable list)
        ll.addWidget(self._lbl("Быстрые команды:", S['muted'], 11))
        self._qs = QScrollArea(); self._qs.setWidgetResizable(True); self._qs.setMaximumHeight(155)
        self._qs.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._qw = QWidget(); self._ql = QVBoxLayout(self._qw)
        self._ql.setContentsMargins(0,0,0,0); self._ql.setSpacing(3)
        self._qs.setWidget(self._qw); ll.addWidget(self._qs)
        self._rebuild_quick()

        ll.addWidget(self._lbl("Задание:", S['muted'], 11))
        self._ti = QTextEdit()
        self._ti.setPlaceholderText("Напишите задачу...\n\nAгент выполнит только с вашего разрешения.\n\nCtrl+Enter — отправить")
        self._ti.setMaximumHeight(100)
        self._ti.setStyleSheet(
            f"QTextEdit{{background:{S['input']};color:{S['text']};"
            f"border:1px solid {S['border']};border-radius:6px;padding:8px;font-size:12px;}}"
            f"QTextEdit:focus{{border-color:{S['blue']};}}")
        self._ti.installEventFilter(self)
        ll.addWidget(self._ti)

        # Memory indicator
        self._mem_lbl = QLabel("🧠  Память: 0 сообщ.")
        self._mem_lbl.setStyleSheet(f"color:{S['muted']};font-size:10px;")
        ll.addWidget(self._mem_lbl)

        sb = QPushButton("🚀  Поставить задачу  [Ctrl+Enter]"); sb.setFixedHeight(38)
        sb.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {S['blue']},stop:1 {S['cyan']});color:white;border:none;"
            f"border-radius:6px;font-size:13px;font-weight:bold;}}"
            f"QPushButton:disabled{{background:{S['input']};color:{S['muted']};}}")
        sb.clicked.connect(self._send); ll.addWidget(sb); ll.addStretch()

        # ── Right panel ──
        rp = QWidget(); rl = QVBoxLayout(rp); rl.setContentsMargins(0,0,0,0)
        self._tabs = QTabWidget(); rl.addWidget(self._tabs)
        # Activity tab
        aw = QWidget(); al = QVBoxLayout(aw); al.setContentsMargins(0,0,0,0)
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._fw = QWidget(); self._fw.setStyleSheet(f"background:{S['bg']};")
        self._fl = QVBoxLayout(self._fw); self._fl.setContentsMargins(10,10,10,10); self._fl.setSpacing(8); self._fl.addStretch()
        self._scroll.setWidget(self._fw); al.addWidget(self._scroll)
        self._rep = ReportsTab()
        self._tabs.addTab(aw, "📨  Активность"); self._tabs.addTab(self._rep, "📊  Отчёты")

        spl.addWidget(lp); spl.addWidget(rp); spl.setSizes([290, 1010])

        self.statusBar().showMessage(
            "🏢 Virtual AI Office v5 — 6 AI агентов готовы к работе! "
            "Нажмите ⚙️ Настройки чтобы ввести Anthropic API ключ.")
        t = QTimer(self); t.timeout.connect(self._rb); t.start(5000)

    # ── Event filter (Ctrl+Enter) ─────────────────────────────────────────────
    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if obj is self._ti and event.type() == QEvent.KeyPress:
            ke = event
            if ke.key() == Qt.Key_Return and ke.modifiers() == Qt.ControlModifier:
                self._send(); return True
        return super().eventFilter(obj, event)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, text, col, size, bold=False):
        l = QLabel(text)
        l.setStyleSheet(f"color:{col};font-size:{size}px;" + ("font-weight:bold;letter-spacing:1px;" if bold else ""))
        return l

    def _update_memory_label(self):
        tgt = self._combo.currentData()
        if tgt == "all":
            total = sum(len(v) for v in AGENT_MEMORY.values())
            self._mem_lbl.setText(f"🧠  Память всех агентов: {total} сообщ.")
        else:
            n = len(AGENT_MEMORY.get(tgt, []))
            self._mem_lbl.setText(f"🧠  Память агента: {n} сообщ.")

    def _rebuild_quick(self):
        while self._ql.count():
            it = self._ql.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        for cmd in self._commands:
            text = cmd["text"]; emoji = cmd.get("emoji","📌")
            b = QPushButton(f"{emoji}  {text[:44]}{'...' if len(text)>44 else ''}")
            b.setFixedHeight(26); b.setToolTip(text)
            b.setStyleSheet(
                f"QPushButton{{background:{S['input']};color:{S['muted']};"
                f"border:1px solid {S['border']};border-radius:4px;"
                f"text-align:left;padding:0 8px;font-size:11px;}}"
                f"QPushButton:hover{{color:{S['text']};border-color:{S['blue']};}}")
            b.clicked.connect(lambda _,t=text: self._ti.setPlainText(t))
            self._ql.addWidget(b)
        self._ql.addStretch()

    def _rb(self):
        s = DB.get_stats(); self._bal_lbl.setText(f"💰 ${s['cost']:.4f}  |  {s['tasks']} задач")

    def _on_floor_changed(self, idx):
        if idx < len(self.office.floors):
            name = self.office.floors[idx].name
            self._floor_lbl.setText(f"  🏢 {name}  ({idx+1}/{len(self.office.floors)})")

    # ── Button handlers ───────────────────────────────────────────────────────
    def _open_floors(self):
        dlg = FloorManager(self.office, self)
        dlg.switched.connect(self._on_floor_changed); dlg.exec()

    def _open_design(self):
        dlg = DesignPanel(self.office, self); dlg.exec()

    def _open_commands(self):
        dlg = QuickCommandsDialog(self._commands, self); dlg.exec()
        self._commands = dlg.commands; self._save_commands(); self._rebuild_quick()

    def _export_results(self):
        files = list(CLOUD_DIR.glob("*.txt"))
        if not files:
            QMessageBox.information(self,"Экспорт","Нет сохранённых результатов."); return
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self,"Выберите папку для экспорта")
        if not folder: return
        import shutil; dest = Path(folder)
        for f in files: shutil.copy(f, dest/f.name)
        QMessageBox.information(self,"Экспорт",f"✅ Экспортировано {len(files)} файлов в:\n{folder}")
        self.statusBar().showMessage(f"✅  Экспортировано {len(files)} результатов.")

    def _clear_memory(self):
        tgt = self._combo.currentData()
        if tgt == "all":
            if QMessageBox.question(self,"Очистить память?",
                    "Очистить память всех агентов?\nАгенты забудут предыдущие разговоры.") == QMessageBox.Yes:
                for k in AGENT_MEMORY: AGENT_MEMORY[k].clear()
                self.statusBar().showMessage("🧠  Память всех агентов очищена.")
        else:
            cfg = AGENT_DEFS.get(tgt, {})
            if QMessageBox.question(self,"Очистить память?",
                    f"Очистить память агента {cfg.get('name','?')}?") == QMessageBox.Yes:
                AGENT_MEMORY[tgt].clear()
                self.statusBar().showMessage(f"🧠  Память {cfg.get('name','?')} очищена.")
        self._update_memory_label()

    def _open_settings(self):
        dlg = SettingsDialog(self._api_key, self._model, self)
        if dlg.exec() == QDialog.Accepted:
            self._api_key = dlg.get_key()
            self._model   = dlg.get_model()
            self._save_settings()
            mname = MODELS.get(self._model,{}).get("label",self._model)
            self.statusBar().showMessage(f"✅  Настройки сохранены. Модель: {mname}")

    # ── Task dispatch ─────────────────────────────────────────────────────────
    def _send(self):
        task = self._ti.toPlainText().strip()
        if not task: QMessageBox.warning(self,"","Введите задачу."); return
        if not self._api_key: self._open_settings()
        if not self._api_key: return
        tgt     = self._combo.currentData()
        targets = list(AGENT_DEFS.keys()) if tgt == "all" else [tgt]
        self._ti.clear()
        for k in targets:
            tid = DB.add_task(k, task); self._launch(tid, k, task)
            self._add_loading(tid, k); self.office.set_working(k)
        mname = MODELS.get(self._model,{}).get("label",self._model).split("(")[0].strip()
        self.statusBar().showMessage(
            f"⚙️  Задача отправлена {len(targets)} агентам [{mname}]...")

    def _launch(self, tid, k, task):
        w = AgentWorker(tid, k, task, self._api_key, self._model)
        w.finished.connect(self._done); w.error.connect(self._err)
        self._workers[tid] = w; w.start()

    def _add_loading(self, tid, k):
        cfg  = AGENT_DEFS[k]
        card = QFrame(); card.setObjectName(f"L_{tid}_{k}"); card.setFixedHeight(66)
        card.setStyleSheet(
            f"QFrame{{background:{S['card']};border:1px solid {S['border']};"
            f"border-left:3px solid {cfg['color']};border-radius:8px;}}")
        row = QHBoxLayout(card); row.setContentsMargins(12,8,12,8)
        ic = QLabel(cfg["emoji"]); ic.setFont(QFont("Segoe UI Emoji",16))
        tl = QVBoxLayout()
        tl.addWidget(self._lbl(f"<b>{cfg['name']}</b> · {cfg['role']}", cfg['color'], 12))
        tl.addWidget(self._lbl("⚙️  Думает над задачей...", S['muted'], 11))
        pb = QProgressBar(); pb.setRange(0,0); pb.setFixedSize(80,8)
        pb.setStyleSheet(
            f"QProgressBar{{background:{S['input']};border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{cfg['color']};border-radius:4px;}}")
        row.addWidget(ic); row.addLayout(tl); row.addStretch(); row.addWidget(pb)
        self._fl.insertWidget(self._fl.count()-1, card); self._tabs.setCurrentIndex(0)
        QTimer.singleShot(100, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _find_remove_loading(self, tid):
        for i in range(self._fl.count()):
            it = self._fl.itemAt(i)
            if it and it.widget():
                w = it.widget(); nm = w.objectName()
                if nm.startswith(f"L_{tid}_"):
                    k = nm.split("_",2)[2]; self._fl.removeWidget(w); w.deleteLater(); return k
        return None

    def _done(self, tid, resp, ti, to_, cost):
        k = self._find_remove_loading(tid)
        if k:
            with DB._l:
                row = DB.conn.cursor().execute("SELECT task_text FROM tasks WHERE id=?",(tid,)).fetchone()
            tt = row[0] if row else ""
            card = TaskCard(tid, k, tt, resp, cost, ti+to_)
            card.approved.connect(lambda _: self._approved(k))
            card.rejected.connect(lambda _: self._rejected(k))
            self._fl.insertWidget(self._fl.count()-1, card)
            self.office.set_awaiting(k)
            QTimer.singleShot(100, lambda: self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()))
        mem_n = len(AGENT_MEMORY.get(k, []))
        self.statusBar().showMessage(
            f"✅  {AGENT_DEFS.get(k,{}).get('name','?')} ответил. "
            f"${cost:.5f} | {ti+to_} токенов | 🧠 память: {mem_n} сообщ.")
        self._rb(); self._update_memory_label()

    def _err(self, tid, msg):
        k = self._find_remove_loading(tid)
        if k: self.office.set_idle(k)
        el = QLabel(f"💥  Ошибка API: {msg}")
        el.setStyleSheet(f"color:{S['red']};background:{S['card']};border:1px solid {S['red']};border-radius:6px;padding:10px;font-size:12px;")
        el.setWordWrap(True)
        self._fl.insertWidget(self._fl.count()-1, el)
        self.statusBar().showMessage(f"Ошибка: {msg}")

    def _approved(self, k): self.office.set_idle(k); self._rb(); self._rep.refresh()
    def _rejected(self, k): self.office.set_idle(k)

    def closeEvent(self, e): self.office.save_floors(); super().closeEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv); app.setApplicationName("Virtual AI Office")
    p = QPalette()
    for role, col in [
        (QPalette.Window,          S['bg']),
        (QPalette.WindowText,      S['text']),
        (QPalette.Base,            S['card']),
        (QPalette.AlternateBase,   S['panel']),
        (QPalette.Text,            S['text']),
        (QPalette.Button,          S['input']),
        (QPalette.ButtonText,      S['text']),
        (QPalette.Highlight,       S['blue']),
        (QPalette.HighlightedText, "#FFFFFF"),
    ]:
        p.setColor(role, QColor(col))
    app.setPalette(p)
    win = MainWindow(); win.show(); sys.exit(app.exec())

if __name__ == "__main__":
    main()
