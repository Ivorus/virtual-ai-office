# -*- coding: utf-8 -*-
"""
office_scene.py v4 — Virtual AI Office
Living humans, draggable furniture, themes, multi-floor
"""
import random, math, json
from pathlib import Path
from PySide6.QtWidgets import QGraphicsView, QWidget
from PySide6.QtCore import Qt, QTimer, QRectF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QCursor
)

BASE_DIR    = Path(__file__).parent
FLOORS_FILE = BASE_DIR / "floors.json"

# ── Themes ──────────────────────────────────────────────────────────────────
THEMES = {
    "Ночной офис":   {"fa":"#1A1F2E","fb":"#161B28","wall":"#0D1117","accent":"#3B82F6","tx":"#94A3B8"},
    "Светлый лофт":  {"fa":"#F0EBE0","fb":"#E8E0D2","wall":"#C8BAA0","accent":"#92400E","tx":"#44403C"},
    "Зелёный Bio":   {"fa":"#182818","fb":"#142214","wall":"#0F1F0F","accent":"#22C55E","tx":"#86EFAC"},
    "Корпоратив":    {"fa":"#1E2433","fb":"#1A1F2D","wall":"#151A26","accent":"#2563EB","tx":"#CBD5E1"},
    "Тёмный Luxury": {"fa":"#1C1510","fb":"#17120E","wall":"#100D09","accent":"#D97706","tx":"#FCD34D"},
    "Cyberpunk":     {"fa":"#0D0D1A","fb":"#0A0A14","wall":"#070710","accent":"#EC4899","tx":"#F0ABFC"},
}
DEFAULT_THEME = "Ночной офис"

# ── Agent config ─────────────────────────────────────────────────────────────
AGENT_CFG = {
    "programmer": {"name":"Алекс", "color":"#3B82F6", "hair":"#281E14"},
    "designer":   {"name":"Майя",  "color":"#8B5CF6", "hair":"#B46490"},
    "sales":      {"name":"Давид", "color":"#10B981", "hair":"#5A3C1E"},
    "accountant": {"name":"Рита",  "color":"#F59E0B", "hair":"#3C3229"},
    "devops":     {"name":"Макс",  "color":"#06B6D4", "hair":"#1E3A5F"},
    "researcher": {"name":"Ана",   "color":"#EC4899", "hair":"#4A1942"},
}

ALL_AGENT_KEYS = list(AGENT_CFG.keys())

# ── Furniture piece (plain data + draw) ──────────────────────────────────────
class FurniturePiece:
    """A piece of furniture that lives on a floor."""
    def __init__(self, ftype, x, y, w, h, color, label=""):
        self.ftype  = ftype
        self.x      = float(x)
        self.y      = float(y)
        self.w      = float(w)
        self.h      = float(h)
        self.color  = color      # hex string
        self.label  = label
        self.selected = False

    def rect(self):
        return (self.x, self.y, self.w, self.h)

    def contains(self, px, py):
        return self.x <= px <= self.x+self.w and self.y <= py <= self.y+self.h

    def to_dict(self):
        return {"type":self.ftype,"x":self.x,"y":self.y,
                "w":self.w,"h":self.h,"color":self.color,"label":self.label}

    @staticmethod
    def from_dict(d):
        return FurniturePiece(d["type"],d["x"],d["y"],d["w"],d["h"],d["color"],d.get("label",""))

    def draw(self, p: QPainter):
        col  = QColor(self.color)
        rx, ry, rw, rh = self.x, self.y, self.w, self.h

        # Body
        p.setBrush(QBrush(col.darker(160)))
        border_col = QColor("#FBBF24") if self.selected else col
        p.setPen(QPen(border_col, 2.5 if self.selected else 1.5))
        p.drawRoundedRect(rx, ry, rw, rh, 4, 4)

        # Top highlight
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(col.darker(120)))
        p.drawRoundedRect(rx+2, ry+2, rw-4, rh*0.45, 3, 3)

        cx, cy = rx + rw/2, ry + rh/2

        # Type details
        if self.ftype == "desk":
            # Monitor
            p.setBrush(QBrush(QColor(10,15,28))); p.setPen(QPen(col, 1))
            p.drawRoundedRect(cx-18, ry+4, 36, 24, 2, 2)
            p.setBrush(QBrush(col.darker(280))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(cx-16, ry+6, 32, 20, 2, 2)
            # Screen lines
            p.setPen(QPen(col.lighter(150), 0.8))
            for li in range(3): p.drawLine(cx-12, ry+10+li*5, cx+8, ry+10+li*5)
            p.setPen(Qt.NoPen)
            # Keyboard
            p.setBrush(QBrush(QColor(22,32,50)))
            p.drawRoundedRect(cx-16, ry+30, 32, 10, 2, 2)
            p.setBrush(QBrush(QColor(18,26,42)))
            for ki in range(7): p.drawRoundedRect(cx-14+ki*4.5, ry+32, 3, 3, 1, 1)

        elif self.ftype == "sofa":
            p.setBrush(QBrush(col.darker(110)))
            p.drawRoundedRect(rx+4, ry+4, rw-8, rh-16, 8, 8)
            p.setBrush(QBrush(col.darker(140)))
            p.drawRoundedRect(rx+4, ry+rh-16, rw-8, 12, 3, 3)
            # Cushions
            p.setBrush(QBrush(col.darker(125)))
            p.drawRoundedRect(rx+6, ry+6, rw/2-10, rh-22, 5, 5)
            p.drawRoundedRect(cx+2, ry+6, rw/2-10, rh-22, 5, 5)

        elif self.ftype == "coffee_machine":
            p.setBrush(QBrush(QColor(28,18,10))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(cx-14, ry+4, 28, 36, 5, 5)
            p.setBrush(QBrush(QColor(180,100,30)))
            p.drawEllipse(cx-10, ry+8, 20, 20)
            p.setBrush(QBrush(QColor(10,10,10)))
            p.drawEllipse(cx-7, ry+11, 14, 14)
            p.setBrush(QBrush(QColor(0,210,80)))
            p.drawEllipse(cx+6, ry+5, 5, 5)

        elif self.ftype == "plant":
            p.setBrush(QBrush(QColor(110,70,40))); p.setPen(Qt.NoPen)
            p.drawRect(cx-7, ry+rh-14, 14, 12)
            gc = QColor(self.color)
            p.setBrush(QBrush(gc))
            p.drawEllipse(cx-13, ry+2, 15, 24)
            p.drawEllipse(cx-2,  ry,   15, 24)
            p.drawEllipse(cx-7,  ry+6, 12, 18)

        elif self.ftype == "meeting_table":
            p.setBrush(QBrush(col.darker(115)))
            p.drawEllipse(rx+5, ry+5, rw-10, rh-10)
            p.setBrush(QBrush(col.darker(135)))
            p.drawEllipse(rx+12, ry+12, rw-24, rh-24)

        elif self.ftype == "toilet":
            p.setBrush(QBrush(QColor(218,228,238))); p.setPen(QPen(QColor(160,170,180),1))
            p.drawEllipse(cx-18, cy-10, 36, 28)
            p.setBrush(QBrush(QColor(200,212,222)))
            p.drawRoundedRect(cx-16, ry+4, 32, 20, 2, 2)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(140,152,162),2))
            p.drawEllipse(cx-16, cy-8, 32, 24)

        elif self.ftype == "sink":
            p.setBrush(QBrush(QColor(192,202,214))); p.setPen(QPen(QColor(140,152,164),1))
            p.drawRoundedRect(cx-14, cy-10, 28, 22, 4, 4)
            p.setBrush(QBrush(QColor(100,160,210,140)))
            p.drawEllipse(cx-9, cy-6, 18, 14)
            p.setPen(QPen(QColor(180,188,198),2))
            p.drawLine(cx, cy-12, cx, cy-18)
            p.drawLine(cx, cy-18, cx+6, cy-18)
            p.setPen(Qt.NoPen)

        elif self.ftype == "bookshelf":
            p.setBrush(QBrush(col.darker(130)))
            p.drawRect(rx+3, ry+3, rw-6, rh-6)
            book_colors = ["#EF4444","#3B82F6","#22C55E","#F59E0B","#8B5CF6","#EC4899"]
            bw = (rw-10) / 6
            for i,bc in enumerate(book_colors):
                p.setBrush(QBrush(QColor(bc))); p.setPen(Qt.NoPen)
                p.drawRect(rx+5+i*bw, ry+6, bw-1, rh-12)
            # Shelves
            p.setPen(QPen(col.darker(100),1))
            p.drawLine(rx+3, ry+rh/2, rx+rw-3, ry+rh/2)

        elif self.ftype == "whiteboard":
            p.setBrush(QBrush(QColor(240,244,248)))
            p.setPen(QPen(col, 2)); p.drawRect(rx+2, ry+2, rw-4, rh-4)
            p.setPen(QPen(QColor(50,100,200),1.5))
            p.drawLine(rx+8, ry+rh/3, rx+rw*0.6, ry+rh/3)
            p.drawLine(rx+8, ry+rh/2, rx+rw*0.45, ry+rh/2)
            p.setPen(QPen(QColor(200,50,50),1.5))
            p.drawLine(rx+rw*0.65, ry+rh/4, rx+rw-8, ry+rh*0.7)
            p.drawLine(rx+rw*0.65, ry+rh*0.7, rx+rw-8, ry+rh/4)

        elif self.ftype == "server_rack":
            p.setBrush(QBrush(QColor(20,25,35))); p.setPen(QPen(col,1))
            p.drawRect(rx+3, ry+3, rw-6, rh-6)
            for i in range(5):
                c2 = QColor(0,160,80) if i%2==0 else QColor(0,100,200)
                p.setBrush(QBrush(c2)); p.setPen(Qt.NoPen)
                p.drawRect(rx+6, ry+6+i*(rh-12)/5, rw-12, (rh-12)/5-2)
                p.setBrush(QBrush(QColor(0,255,100) if i%2==0 else QColor(0,180,255)))
                p.drawEllipse(rx+rw-12, ry+8+i*(rh-12)/5, 4, 4)

        # Selection glow
        if self.selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(251,191,36,140), 5))
            p.drawRoundedRect(rx-3, ry-3, rw+6, rh+6, 6, 6)

        # Label
        if self.label:
            p.setPen(QPen(QColor(self.color).lighter(180)))
            p.setFont(QFont("Consolas", 6, QFont.Bold))
            p.drawText(QRectF(rx, ry+rh-16, rw, 14), Qt.AlignCenter, self.label)


# ── Human sprite ─────────────────────────────────────────────────────────────
class Human:
    def __init__(self, key, x, y):
        self.key        = key
        self.x          = float(x)
        self.y          = float(y)
        self.tx         = float(x)
        self.ty         = float(y)
        self.floor_idx  = 0
        self.state      = "working"
        self.speed      = 1.7 + random.uniform(-0.3, 0.3)
        self.anim_tick  = random.randint(0, 80)
        self.think      = ""
        self.think_timer= 0
        self.need_tick  = random.randint(200, 500)
        self.state_timer= 0
        self.walk_phase = 0.0
        self.facing     = 1
        self._mid       = None
        self._cabin     = None
        cfg = AGENT_CFG[key]
        self.color      = QColor(cfg["color"])
        self.hair       = QColor(cfg["hair"])
        self.name       = cfg["name"]

    def at_target(self):
        return abs(self.x-self.tx) < 2.5 and abs(self.y-self.ty) < 2.5

    def move_step(self):
        dx = self.tx - self.x; dy = self.ty - self.y
        dist = math.sqrt(dx*dx+dy*dy)
        if dist > 1.5:
            self.x += dx/dist*self.speed; self.y += dy/dist*self.speed
            self.walk_phase += 0.22
            if abs(dx) > 1: self.facing = 1 if dx > 0 else -1

    def set_target(self, x, y):
        self.tx, self.ty = float(x), float(y)
        if abs(x-self.x) > 2: self.facing = 1 if x > self.x else -1

    def show_thought(self, txt, ticks=90):
        self.think = txt; self.think_timer = ticks

    def draw(self, p: QPainter):
        x, y  = int(self.x), int(self.y)
        col   = self.color
        skin  = QColor(255, 220, 177)
        walk  = not self.at_target()
        tick  = self.anim_tick
        ls    = math.sin(self.walk_phase)*(8 if walk else 0)
        bob   = int(math.sin(tick*0.08))

        p.save(); p.translate(x, y)
        if self.facing == -1: p.scale(-1, 1)

        # Shadow
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(0,0,0,40)))
        p.drawEllipse(-10, 23, 20, 6)

        # Legs
        p.setBrush(QBrush(col.darker(170)))
        p.drawRoundedRect(-6, 12, 5, 12+int(ls), 2, 2)
        p.drawRoundedRect( 1, 12, 5, 12-int(ls), 2, 2)
        p.setBrush(QBrush(QColor(32,22,12)))
        p.drawRoundedRect(-7, 23+int(ls), 7, 3, 1, 1)
        p.drawRoundedRect( 1, 23-int(ls), 7, 3, 1, 1)

        # Body
        p.setBrush(QBrush(col)); p.drawRoundedRect(-8,-2,16,16,4,4)
        p.setBrush(QBrush(QColor(255,255,255,50))); p.drawRoundedRect(-3,-2,6,6,2,2)

        # Arms
        as_ = math.sin(self.walk_phase+math.pi)*(5 if walk else 2)
        p.setBrush(QBrush(col))
        p.drawRoundedRect(-13,-1,5,10,2,2); p.drawRoundedRect(8,-1,5,10,2,2)
        p.setBrush(QBrush(skin))
        p.drawEllipse(-14,8+int(as_),5,5); p.drawEllipse(9,8-int(as_),5,5)

        # Props by state
        if self.state in ("working","task_working","awaiting"):
            p.setBrush(QBrush(QColor(80,160,255,100)))
            p.drawRoundedRect(-6,5,12,7,2,2)
        elif self.state in ("making_coffee","drinking_coffee"):
            p.setBrush(QBrush(QColor(65,38,12)))
            p.drawRoundedRect(8,4,9,10,2,2)
            if tick%20 < 10:
                p.setPen(QPen(QColor(200,200,200,110),1))
                p.drawLine(11,3,10,-2); p.drawLine(14,3,15,-2)
            p.setPen(Qt.NoPen)
        elif self.state == "in_meeting":
            p.setBrush(QBrush(QColor(240,240,200)))
            p.drawRoundedRect(-6,3,10,13,1,1)
            p.setPen(QPen(QColor(100,100,100),0.8))
            for li in range(3): p.drawLine(-4,6+li*3,2,6+li*3)
            p.setPen(Qt.NoPen)

        # Neck + head
        p.setBrush(QBrush(skin)); p.drawRoundedRect(-3,-6,6,6,2,2)
        p.setBrush(QBrush(skin)); p.drawEllipse(-9,-20+bob,18,18)
        # Hair
        p.setBrush(QBrush(self.hair))
        hp = QPainterPath(); hp.addEllipse(QRectF(-9,-20+bob,18,12)); p.drawPath(hp)
        # Eyes
        blink = tick%80 < 4; eh = 1 if blink else 4
        p.setBrush(QBrush(QColor(25,15,8)))
        p.drawEllipse(-5,-12+bob,4,eh); p.drawEllipse(1,-12+bob,4,eh)
        if not blink:
            p.setBrush(QBrush(QColor(255,255,255,200)))
            p.drawEllipse(-4,-12+bob,2,2); p.drawEllipse(2,-12+bob,2,2)
        # Mouth
        mp = QPainterPath()
        p.setPen(QPen(QColor(175,88,68),1.5))
        happy = self.state in ("making_coffee","drinking_coffee","in_meeting","break")
        if happy: mp.moveTo(-3,-5+bob); mp.quadTo(0,-2+bob,3,-5+bob)
        else:     mp.moveTo(-2,-4+bob); mp.lineTo(2,-4+bob)
        p.drawPath(mp); p.setPen(Qt.NoPen)
        p.restore()

        # Name tag
        p.save(); p.setPen(QPen(QColor(255,255,255,185)))
        p.setFont(QFont("Segoe UI",7,QFont.Bold))
        p.drawText(x-20, y+35, 40, 13, Qt.AlignCenter, self.name); p.restore()

        # State badge
        icons = {"working":"💻","task_working":"⚙️","awaiting":"⏳","to_toilet":"🚶",
                 "in_toilet":"🚽","to_kitchen":"🚶","making_coffee":"☕",
                 "drinking_coffee":"☕","to_meeting":"🚶","in_meeting":"📋","break":"😌"}
        icon = icons.get(self.state,"")
        if icon:
            p.save()
            p.setBrush(QBrush(self.color)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(x+9,y-27,18,16,4,4)
            p.setFont(QFont("Segoe UI Emoji",8))
            p.setPen(QPen(QColor("white")))
            p.drawText(x+9,y-27,18,16,Qt.AlignCenter,icon); p.restore()

        # Thought bubble
        if self.think_timer > 0 and self.think:
            a = min(255, self.think_timer*4)
            p.save(); p.setOpacity(a/255)
            bx,by = x-52,y-68
            p.setBrush(QBrush(QColor(14,22,42,210))); p.setPen(QPen(QColor(180,200,255,a),1))
            p.drawRoundedRect(bx,by,104,22,5,5)
            p.drawEllipse(x-5,y-40,5,5); p.drawEllipse(x-3,y-45,4,4)
            p.setFont(QFont("Segoe UI",7)); p.setPen(QPen(QColor(200,220,255,a)))
            p.drawText(bx+4,by+3,96,18,Qt.AlignCenter|Qt.TextSingleLine, self.think)
            p.restore()


# ── Floor data ────────────────────────────────────────────────────────────────
class FloorData:
    def __init__(self, idx, name, theme=DEFAULT_THEME):
        self.idx    = idx
        self.name   = name
        self.theme  = theme
        self.pieces : list[FurniturePiece] = []
        self.agents : list[str] = []
        self._make_default()

    def _make_default(self):
        t = THEMES[self.theme]
        ac = t["accent"]
        if self.idx == 0:
            self.agents = list(ALL_AGENT_KEYS)
            default_furn = [
                ("desk",  35,  90, 88,60, ac,         "ПРОГРАММИСТ"),
                ("desk",  143, 90, 88,60, "#8B5CF6",  "ДИЗАЙНЕР"),
                ("desk",  251, 90, 88,60, "#10B981",  "ПРОДАЖИ"),
                ("desk",  359, 90, 88,60, "#F59E0B",  "БУХГАЛТЕР"),
                ("desk",  467, 90, 88,60, "#06B6D4",  "ДЕВОПС"),
                ("desk",  575, 90, 88,60, "#EC4899",  "ИССЛЕДОВАТЕЛЬ"),
                ("coffee_machine",740,50,50,52,"#92400E","КОФЕ"),
                ("sofa",  40, 340,130,55, "#334155",  "ДИВАН"),
                ("meeting_table",610,260,130,105,"#4B5563","ПЕРЕГОВОРНАЯ"),
                ("plant",  5,  38, 30,42, "#166534",  ""),
                ("plant",  5, 358, 30,42, "#166534",  ""),
                ("plant",870,  38, 30,42, "#166534",  ""),
                ("whiteboard",690,160,80,52,"#1E3A5F","ЗАДАЧИ"),
                ("server_rack",810,160,50,90,"#1E293F","СЕРВЕРЫ"),
                ("toilet",720,360,50,62, "#475569",  "ТУАЛЕТ 1"),
                ("toilet",790,360,50,62, "#475569",  "ТУАЛЕТ 2"),
                ("sink",  720,432,42,36, "#64748B",  ""),
                ("sink",  790,432,42,36, "#64748B",  ""),
            ]
        else:
            self.agents = []
            default_furn = [
                ("desk",  80,  90, 90,60, ac,         "СТОЛ 1"),
                ("desk",  280, 90, 90,60, ac,          "СТОЛ 2"),
                ("meeting_table",500,140,120,100,"#4B5563","СОВЕЩАНИЕ"),
                ("plant",   8, 40, 30,42, "#166534",  ""),
                ("bookshelf",750,80,60,100,"#7C3AED","БИБЛИОТЕКА"),
            ]
        for row in default_furn:
            self.pieces.append(FurniturePiece(*row))

    def to_dict(self):
        return {"idx":self.idx,"name":self.name,"theme":self.theme,
                "pieces":[p.to_dict() for p in self.pieces],
                "agents":self.agents}

    @staticmethod
    def from_dict(d):
        fl = FloorData.__new__(FloorData)
        fl.idx    = d["idx"]; fl.name = d["name"]
        fl.theme  = d.get("theme", DEFAULT_THEME)
        fl.pieces = [FurniturePiece.from_dict(p) for p in d.get("pieces",[])]
        fl.agents = d.get("agents",[])
        return fl


# ── Main scene view ───────────────────────────────────────────────────────────
class OfficeScene(QGraphicsView):
    floor_changed = Signal(int)

    W, H = 920, 430

    def __init__(self):
        super().__init__()
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self.setStyleSheet("QGraphicsView{border:none;background:#0A0E1A;}")

        self.floors: list[FloorData] = []
        self.current_floor = 0
        self._load_floors()

        # Humans dict key→Human
        self.humans: dict[str, Human] = {}
        self._init_humans()

        # Edit / drag
        self.edit_mode    = False
        self._drag_piece  : FurniturePiece | None = None
        self._drag_ox     = 0.0
        self._drag_oy     = 0.0
        self._selected    : FurniturePiece | None = None

        # Toilet occupancy
        self._toilet_occ: set[str] = set()

        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(30)

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_floors(self):
        if FLOORS_FILE.exists():
            try:
                data = json.loads(FLOORS_FILE.read_text(encoding="utf-8"))
                self.floors = [FloorData.from_dict(d) for d in data]
                if self.floors: return
            except: pass
        self.floors = [FloorData(0, "Этаж 1 — Главный")]

    def save_floors(self):
        FLOORS_FILE.write_text(
            json.dumps([f.to_dict() for f in self.floors], ensure_ascii=False, indent=2),
            encoding="utf-8")

    # ── Init humans ──────────────────────────────────────────────────────────
    def _init_humans(self):
        starts = {
            "programmer":(85,155),  "designer":(200,155),
            "sales":(315,155),      "accountant":(430,155),
            "devops":(545,155),     "researcher":(660,155),
        }
        for key,(x,y) in starts.items():
            h = Human(key,x,y); h.floor_idx=0; self.humans[key]=h

    # ── Floor management ──────────────────────────────────────────────────────
    def add_floor(self, name=None):
        idx = len(self.floors)
        fl  = FloorData(idx, name or f"Этаж {idx+1}")
        self.floors.append(fl); self.save_floors(); return idx

    def delete_floor(self, idx):
        if idx == 0 or idx >= len(self.floors): return
        self.floors.pop(idx)
        for i,f in enumerate(self.floors): f.idx = i
        if self.current_floor >= len(self.floors):
            self.current_floor = len(self.floors)-1
        self.save_floors()

    def switch_floor(self, idx):
        if 0 <= idx < len(self.floors):
            self._deselect_all()
            self.current_floor = idx
            self.viewport().update()
            self.floor_changed.emit(idx)

    def rename_floor(self, name):
        self.floors[self.current_floor].name = name; self.save_floors()

    def send_agent_to_floor(self, agent_key, floor_idx):
        for fl in self.floors:
            if agent_key in fl.agents: fl.agents.remove(agent_key)
        self.floors[floor_idx].agents.append(agent_key)
        if agent_key in self.humans: self.humans[agent_key].floor_idx = floor_idx
        self.save_floors()

    # ── Public agent control ──────────────────────────────────────────────────
    def set_working(self, key):
        h = self.humans.get(key)
        if not h: return
        h.state = "task_working"
        pos = self._desk_pos(key)
        if pos: h.set_target(*pos)
        h.show_thought("Работаю...", 120)

    def set_awaiting(self, key):
        h = self.humans.get(key)
        if h: h.state = "awaiting"; h.show_thought("Жду одобрения ⏳", 100)

    def set_idle(self, key):
        h = self.humans.get(key)
        if h and h.state in ("task_working","awaiting"):
            h.state = "working"
            pos = self._desk_pos(key)
            if pos: h.set_target(*pos)
            h.show_thought("Готово ✓", 60)

    def _desk_pos(self, key):
        labels = {"programmer":"ПРОГРАММИСТ","designer":"ДИЗАЙНЕР",
                  "sales":"ПРОДАЖИ","accountant":"БУХГАЛТЕР",
                  "devops":"ДЕВОПС","researcher":"ИССЛЕДОВАТЕЛЬ"}
        lbl = labels.get(key,"")
        fl  = self.floors[self.current_floor]
        for pc in fl.pieces:
            if pc.ftype == "desk" and pc.label == lbl:
                return (pc.x + pc.w/2, pc.y + pc.h/2)
        return None

    # ── Theme / design ────────────────────────────────────────────────────────
    def set_floor_theme(self, theme_name):
        self.floors[self.current_floor].theme = theme_name
        self.save_floors(); self.viewport().update()

    # ── Furniture CRUD ────────────────────────────────────────────────────────
    FURN_SIZES = {
        "desk":(90,60),"sofa":(120,55),"coffee_machine":(50,52),
        "plant":(30,42),"meeting_table":(120,100),"toilet":(50,62),
        "sink":(42,36),"bookshelf":(60,100),"whiteboard":(120,50),
        "server_rack":(50,90),
    }

    def add_furniture(self, ftype, color=None):
        fl  = self.floors[self.current_floor]
        t   = THEMES[fl.theme]
        col = color or t["accent"]
        w,h = self.FURN_SIZES.get(ftype,(60,60))
        pc  = FurniturePiece(ftype, 200, 180, w, h, col,
                             ftype.upper().replace("_"," "))
        fl.pieces.append(pc); self.save_floors(); self.viewport().update()

    def delete_selected(self):
        fl = self.floors[self.current_floor]
        fl.pieces = [p for p in fl.pieces if not p.selected]
        self._selected = None; self.save_floors(); self.viewport().update()

    def recolor_selected(self, color: str):
        for p in self.floors[self.current_floor].pieces:
            if p.selected: p.color = color
        self.save_floors(); self.viewport().update()

    def _deselect_all(self):
        for fl in self.floors:
            for p in fl.pieces: p.selected = False
        self._selected = None

    # ── Edit mode ─────────────────────────────────────────────────────────────
    def set_edit_mode(self, on: bool):
        self.edit_mode = on
        if not on:
            self._deselect_all(); self.save_floors()
        self.setCursor(QCursor(Qt.SizeAllCursor if on else Qt.ArrowCursor))
        self.viewport().update()

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def _scene_pos(self, event):
        vw = self.viewport().width(); vh = self.viewport().height()
        scale = min(vw/self.W, vh/self.H)
        ox = (vw - self.W*scale)/2; oy = (vh - self.H*scale)/2
        sx = (event.position().x() - ox) / scale
        sy = (event.position().y() - oy) / scale
        return sx, sy

    def mousePressEvent(self, event):
        if not self.edit_mode: return
        sx, sy = self._scene_pos(event)
        fl = self.floors[self.current_floor]
        self._deselect_all()
        # Hit test reversed (top items first)
        for pc in reversed(fl.pieces):
            if pc.contains(sx, sy):
                pc.selected = True; self._selected = pc
                self._drag_piece = pc
                self._drag_ox = sx - pc.x; self._drag_oy = sy - pc.y
                break
        self.viewport().update()

    def mouseMoveEvent(self, event):
        if self._drag_piece and self.edit_mode:
            sx, sy = self._scene_pos(event)
            self._drag_piece.x = max(0, min(self.W - self._drag_piece.w, sx - self._drag_ox))
            self._drag_piece.y = max(0, min(self.H - self._drag_piece.h - 28, sy - self._drag_oy))
            self.viewport().update()

    def mouseReleaseEvent(self, event):
        if self._drag_piece:
            self._drag_piece = None; self.save_floors()

    # ── Autonomous AI ─────────────────────────────────────────────────────────
    def _update(self):
        self._tick += 1
        fl = self.floors[self.current_floor]

        for key, h in self.humans.items():
            h.anim_tick += 1
            h.state_timer += 1
            if h.think_timer > 0: h.think_timer -= 1
            if h.floor_idx != self.current_floor: continue

            if h._mid:
                h.move_step()
                if h.at_target(): self._resolve_mid(h)
            else:
                h.move_step()
                self._state_machine(h)

            if h.state in ("working","idle","break") and not h._mid:
                h.need_tick -= 1
                if h.need_tick <= 0: self._trigger_need(h)

        self.viewport().update()

    def _resolve_mid(self, h: Human):
        mid = h._mid; h._mid = None
        if mid == "toilet":
            for lbl in ["ТУАЛЕТ 1","ТУАЛЕТ 2"]:
                if lbl not in self._toilet_occ:
                    self._toilet_occ.add(lbl); h._cabin = lbl
                    pos = self._furn_pos("toilet", lbl)
                    if pos: h.set_target(*pos)
                    h.state = "in_toilet"; h.state_timer = 0
                    h.show_thought("...", 200); return
            pos = self._furn_pos("sink")
            if pos: h.set_target(*pos)
        elif mid == "coffee":
            pos = self._furn_pos("coffee_machine")
            if pos: h.set_target(*pos)
            h.state = "making_coffee"; h.state_timer = 0
        elif mid == "break":
            pos = self._furn_pos("sofa")
            if pos: h.set_target(*pos)

    def _furn_pos(self, ftype, label=None):
        fl = self.floors[self.current_floor]
        for pc in fl.pieces:
            if pc.ftype == ftype and (label is None or pc.label == label):
                return (pc.x + pc.w/2, pc.y + pc.h/2)
        return None

    def _state_machine(self, h: Human):
        if h.state == "in_toilet":
            if h.at_target() and h.state_timer > 80:
                if h._cabin: self._toilet_occ.discard(h._cabin)
                h.state = "working"
                pos = self._desk_pos(h.key)
                if pos: h.set_target(*pos)
                h.show_thought("Освежился 💧", 70)
                h.need_tick = random.randint(500,900)
        elif h.state == "making_coffee":
            if h.at_target() and h.state_timer > 70:
                h.state = "drinking_coffee"; h.state_timer = 0
                h.show_thought("Мммм, вкусно!", 90)
                pos = self._furn_pos("sofa")
                if pos: h.set_target(*pos)
                else: h.set_target(h.x+30, h.y)
        elif h.state == "drinking_coffee":
            if h.at_target() and h.state_timer > 55:
                h.state = "working"
                pos = self._desk_pos(h.key)
                if pos: h.set_target(*pos)
                h.show_thought("Готов к работе! ⚡", 70)
                h.need_tick = random.randint(400,700)
        elif h.state == "break":
            if h.at_target() and h.state_timer > 100:
                h.state = "working"
                pos = self._desk_pos(h.key)
                if pos: h.set_target(*pos)
                h.need_tick = random.randint(350,650)

    def _trigger_need(self, h: Human):
        if h.state in ("task_working","awaiting","in_toilet",
                       "making_coffee","drinking_coffee","to_toilet","to_kitchen"):
            h.need_tick = random.randint(200,400); return
        need = random.choices(["toilet","coffee","break"],[20,45,35])[0]
        mid_pos = self._furn_pos("coffee_machine") or (450, 280)
        if need == "toilet":
            h.state = "to_toilet"; h._mid = "toilet"
            h.set_target(*mid_pos); h.show_thought("Мне нужно выйти 🚶", 80)
        elif need == "coffee":
            h.state = "to_kitchen"; h._mid = "coffee"
            h.set_target(*mid_pos); h.show_thought("Хочу кофе ☕", 80)
        else:
            h.state = "break"; h._mid = "break"
            pos = self._furn_pos("sofa") or (100, 350)
            h.set_target(*pos); h.show_thought("Небольшой перерыв...", 80)
        h.need_tick = random.randint(450,850)

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)
        vw = self.viewport().width(); vh = self.viewport().height()
        scale = min(vw/self.W, vh/self.H)
        ox = (vw - self.W*scale)/2; oy = (vh - self.H*scale)/2
        p.translate(ox, oy); p.scale(scale, scale)
        self._draw_floor(p)
        p.end()

    def _draw_floor(self, p: QPainter):
        fl = self.floors[self.current_floor]
        t  = THEMES.get(fl.theme, THEMES[DEFAULT_THEME])
        fa = QColor(t["fa"]); fb = QColor(t["fb"])
        wc = QColor(t["wall"]); ac = QColor(t["accent"])
        tx = QColor(t["tx"])

        # Floor tiles
        tile = 38
        for row in range(self.H//tile+1):
            for col in range(self.W//tile+1):
                p.setPen(QPen(wc, 0.4))
                p.setBrush(QBrush(fa if (row+col)%2==0 else fb))
                p.drawRect(col*tile, row*tile, tile, tile)

        # Walls (border)
        p.setBrush(Qt.NoBrush); p.setPen(QPen(ac, 2.5))
        p.drawRect(1, 1, self.W-2, self.H-2)

        # Windows
        for wx in range(55, self.W-55, 105):
            p.setBrush(QBrush(QColor(ac.red(),ac.green(),ac.blue(),45)))
            p.setPen(QPen(ac.darker(120), 1.2))
            p.drawRect(wx, 0, 72, 26)
            p.setPen(QPen(ac.darker(160),0.8))
            p.drawLine(wx+36,0,wx+36,26); p.drawLine(wx,13,wx+72,13)

        # Wall plants
        for px_, py_ in [(4,38),(4,180),(4,320),(self.W-34,38),(self.W-34,220)]:
            self._draw_wall_plant(p, px_, py_, ac)

        # Furniture
        p.save()
        for pc in fl.pieces:
            pc.draw(p)
        p.restore()

        # Humans on this floor
        for key, h in self.humans.items():
            if h.floor_idx == self.current_floor:
                h.draw(p)

        # Bottom info bar
        p.setBrush(QBrush(QColor(wc.red(),wc.green(),wc.blue(),210)))
        p.setPen(Qt.NoPen); p.drawRect(0, self.H-26, self.W, 26)
        p.setFont(QFont("Consolas",8,QFont.Bold))
        p.setPen(QPen(ac))
        p.drawText(10, self.H-8, f"🏢  {fl.name}  |  {fl.idx+1}/{len(self.floors)} этаж")
        p.setPen(QPen(tx))
        agents_here = [AGENT_CFG[a]["name"] for a in fl.agents if a in AGENT_CFG]
        p.drawText(self.W-260, self.H-8, "Агенты: " + (", ".join(agents_here) or "—"))

        # Edit banner
        if self.edit_mode:
            p.setBrush(QBrush(QColor(251,191,36,40)))
            p.setPen(QPen(QColor(251,191,36,180),2))
            p.drawRect(2,2,self.W-4,self.H-4)
            p.setFont(QFont("Consolas",9,QFont.Bold))
            p.setPen(QPen(QColor(251,191,36)))
            p.drawText(self.W//2-120, 20, "✏️  РЕЖИМ РЕДАКТИРОВАНИЯ — ПЕРЕТАСКИВАЙ МЕБЕЛЬ")

    def _draw_wall_plant(self, p, x, y, accent):
        col = QColor(accent).darker(130)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(100,58,28)))
        p.drawRect(x, y+24, 14, 10)
        p.setBrush(QBrush(col))
        p.drawEllipse(x-6,y, 14,22); p.drawEllipse(x+6,y-4,14,22); p.drawEllipse(x+1,y+6,12,16)

    def resizeEvent(self, e):
        super().resizeEvent(e); self.viewport().update()
