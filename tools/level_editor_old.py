#!/usr/bin/env python3
import sys
import os
import glob
import re
import struct
import subprocess
import math
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QImage, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QMessageBox, QTabWidget, QGroupBox
)

MAP_W = 16
MAP_H = 16

TOOL_EMPTY = 0
TOOL_WALL_CONCRETE = 1
TOOL_WALL_RUST = 2
TOOL_WALL_TECH = 3
TOOL_DOOR = 4
TOOL_EXIT = 5
TOOL_PLAYER = 10
TOOL_GUARD = 11
TOOL_MEDKIT = 12
TOOL_AMMO = 13
TOOL_BARREL = 14


def natural_key(path):
    name = os.path.basename(path)
    nums = re.findall(r"\d+", name)
    return (int(nums[0]) if nums else 9999, name)


class MapCanvas(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMinimumSize(512, 512)
        self.cell_size = 32
        self.hover_x = -1
        self.hover_y = -1
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            x = int(event.position().x() // self.cell_size)
            y = int(event.position().y() // self.cell_size)
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                self.editor.entities = [e for e in self.editor.entities if not (e[1] == x and e[2] == y)]
                self.editor.map_grid[y * MAP_W + x] = 0
                self.editor.mark_dirty()
                self.update()
            return
        self.handle_mouse(event, is_click=True)

    def mouseMoveEvent(self, event):
        self.hover_x = int(event.position().x() // self.cell_size)
        self.hover_y = int(event.position().y() // self.cell_size)
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.handle_mouse(event, is_click=False)
        self.update()

    def leaveEvent(self, event):
        self.hover_x = -1
        self.hover_y = -1
        self.update()

    def handle_mouse(self, event, is_click=False):
        x = int(event.position().x() // self.cell_size)
        y = int(event.position().y() // self.cell_size)
        if 0 <= x < MAP_W and 0 <= y < MAP_H:
            tool = self.editor.current_tool
            idx = y * MAP_W + x
            if tool <= 5:
                self.editor.map_grid[idx] = tool
                if tool > 0:
                    self.editor.entities = [e for e in self.editor.entities if not (e[1] == x and e[2] == y)]
            elif tool == TOOL_PLAYER:
                self.editor.map_grid[idx] = 0
                if is_click and self.editor.player_start[0] == x and self.editor.player_start[1] == y:
                    self.editor.player_start[2] = (self.editor.player_start[2] + 256) % 1024
                else:
                    self.editor.player_start[0] = x
                    self.editor.player_start[1] = y
            elif tool >= TOOL_GUARD:
                self.editor.map_grid[idx] = 0
                self.editor.entities = [e for e in self.editor.entities if not (e[1] == x and e[2] == y)]
                ent_type = {TOOL_GUARD: 1, TOOL_MEDKIT: 2, TOOL_AMMO: 3, TOOL_BARREL: 4}[tool]
                self.editor.entities.append([ent_type, x, y])

            self.editor.mark_dirty()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 24, 28))

        for y in range(MAP_H):
            for x in range(MAP_W):
                idx = y * MAP_W + x
                cell = self.editor.map_grid[idx]
                rx, ry = x * self.cell_size, y * self.cell_size

                if cell == 0:
                    color = QColor(32, 38, 44)
                elif cell == 1:
                    color = QColor(80, 95, 80)
                elif cell == 2:
                    color = QColor(120, 82, 58)
                elif cell == 3:
                    color = QColor(62, 86, 118)
                elif cell == 4:
                    color = QColor(38, 175, 78)
                elif cell == 5:
                    color = QColor(215, 55, 55)
                else:
                    color = QColor(50, 50, 50)

                painter.fillRect(rx, ry, self.cell_size, self.cell_size, color)
                painter.setPen(QPen(QColor(45, 55, 62), 1))
                painter.drawRect(rx, ry, self.cell_size, self.cell_size)

                if cell == 4:
                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.drawText(rx + 10, ry + 21, "D")
                elif cell == 5:
                    painter.setPen(QPen(QColor(255, 240, 150), 2))
                    painter.drawText(rx + 3, ry + 21, "EXIT")

        for etype, ex, ey in self.editor.entities:
            cx = ex * self.cell_size + self.cell_size // 2
            cy = ey * self.cell_size + self.cell_size // 2
            painter.setPen(QPen(QColor(20, 20, 20), 1))
            if etype == 1:
                painter.setBrush(QBrush(QColor(225, 55, 55)))
                painter.drawEllipse(cx - 9, cy - 9, 18, 18)
            elif etype == 2:
                painter.setBrush(QBrush(QColor(240, 240, 240)))
                painter.drawRect(cx - 8, cy - 8, 16, 16)
                painter.setPen(QPen(QColor(220, 30, 30), 2))
                painter.drawLine(cx, cy - 5, cx, cy + 5)
                painter.drawLine(cx - 5, cy, cx + 5, cy)
            elif etype == 3:
                painter.setBrush(QBrush(QColor(220, 180, 40)))
                painter.drawRect(cx - 7, cy - 7, 14, 14)
            elif etype == 4:
                painter.setBrush(QBrush(QColor(180, 70, 30)))
                painter.drawEllipse(cx - 9, cy - 9, 18, 18)

        px, py, pang = self.editor.player_start
        pcx = px * self.cell_size + self.cell_size // 2
        pcy = py * self.cell_size + self.cell_size // 2
        rad = (pang * 2.0 * math.pi) / 1024.0
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.setBrush(QBrush(QColor(255, 210, 0)))
        painter.drawEllipse(pcx - 10, pcy - 10, 20, 20)
        painter.drawLine(pcx, pcy, pcx + int(14 * math.cos(rad)), pcy + int(14 * math.sin(rad)))

        if 0 <= self.hover_x < MAP_W and 0 <= self.hover_y < MAP_H:
            painter.setPen(QPen(QColor(255, 255, 255, 190), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.hover_x * self.cell_size, self.hover_y * self.cell_size, self.cell_size, self.cell_size)


class Preview3DWidget(QWidget):
    """Інтерактивний 3D-рейкастер із підтримкою PNG-текстур стін і спрайтів з assets/"""
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMinimumSize(480, 512)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.px = 2.5
        self.py = 2.5
        self.pa = 0.0
        self.keys_pressed = set()
        self.open_doors = set()

        self.sky_pixmaps = {}
        self.wall_images = {}
        self.sprite_images = {}
        self.reload_assets()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def reload_assets(self):
        sky_files = {
            1: "assets/skies/sky_night.png",
            2: "assets/skies/sky_sunset.png",
            3: "assets/skies/sky_industrial.png",
        }
        for sid, path in sky_files.items():
            if os.path.exists(path):
                self.sky_pixmaps[sid] = QPixmap(path)

        wall_files = {
            1: "assets/walls/wall_concrete.png",
            2: "assets/walls/wall_rust.png",
            3: "assets/walls/wall_hazard.png",
            4: "assets/walls/wall_door.png",
            5: "assets/walls/wall_exit.png",
        }
        for wid, path in wall_files.items():
            if os.path.exists(path):
                self.wall_images[wid] = QImage(path).convertToFormat(QImage.Format.Format_RGBA8888)

        sprite_files = {
            1: "assets/sprites/guard_idle.png",
            2: "assets/sprites/medkit.png",
            3: "assets/sprites/ammo.png",
            4: "assets/sprites/barrel.png",
        }
        for sid, path in sprite_files.items():
            if os.path.exists(path):
                self.sprite_images[sid] = QImage(path).convertToFormat(QImage.Format.Format_RGBA8888)

    def reset_camera_from_level(self):
        self.reload_assets()
        sx, sy, sang = self.editor.player_start
        self.px = sx + 0.5
        self.py = sy + 0.5
        self.pa = (sang * 2.0 * math.pi) / 1024.0
        self.open_doors.clear()
        self.update()

    def keyPressEvent(self, event):
        k = event.key()
        self.keys_pressed.add(k)
        if k in (Qt.Key.Key_Space, Qt.Key.Key_E):
            tx = int(self.px + math.cos(self.pa) * 0.9)
            ty = int(self.py + math.sin(self.pa) * 0.9)
            if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
                tile = self.editor.map_grid[ty * MAP_W + tx]
                if tile == 4:
                    if (tx, ty) in self.open_doors:
                        self.open_doors.remove((tx, ty))
                    else:
                        self.open_doors.add((tx, ty))

    def keyReleaseEvent(self, event):
        self.keys_pressed.discard(event.key())

    def is_free(self, x, y):
        cx, cy = int(x), int(y)
        if not (0 <= cx < MAP_W and 0 <= cy < MAP_H):
            return False
        tile = self.editor.map_grid[cy * MAP_W + cx]
        if tile == 0:
            return True
        if tile == 4 and (cx, cy) in self.open_doors:
            return True
        return False

    def tick(self):
        if not self.isVisible():
            return
        rot_speed = 0.065
        move_speed = 0.085

        if Qt.Key.Key_Left in self.keys_pressed or Qt.Key.Key_A in self.keys_pressed:
            self.pa -= rot_speed
        if Qt.Key.Key_Right in self.keys_pressed or Qt.Key.Key_D in self.keys_pressed:
            self.pa += rot_speed

        dx = dy = 0.0
        if Qt.Key.Key_Up in self.keys_pressed or Qt.Key.Key_W in self.keys_pressed:
            dx += math.cos(self.pa) * move_speed
            dy += math.sin(self.pa) * move_speed
        if Qt.Key.Key_Down in self.keys_pressed or Qt.Key.Key_S in self.keys_pressed:
            dx -= math.cos(self.pa) * move_speed
            dy -= math.sin(self.pa) * move_speed

        if dx != 0.0 and self.is_free(self.px + dx * 2.0, self.py):
            self.px += dx
        if dy != 0.0 and self.is_free(self.px, self.py + dy * 2.0):
            self.py += dy

        self.update()

    def draw_skybox(self, painter, w, half_h):
        sky_id = self.editor.sky_id
        if sky_id == 0:
            bands = 16
            band_h = max(1, half_h // bands + 1)
            for i in range(bands):
                shade = 16 + (bands - i) * 2
                painter.fillRect(0, i * band_h, w, band_h, QColor(shade, shade + 4, shade + 8))
            return

        pix = self.sky_pixmaps.get(sky_id)
        if pix and not pix.isNull():
            pw, ph = pix.width(), pix.height()
            u_offset = int(((self.pa % (2.0 * math.pi)) / (2.0 * math.pi)) * pw) % pw
            fov_tex_w = int(pw * 0.45)

            if u_offset + fov_tex_w <= pw:
                painter.drawPixmap(QRect(0, 0, w, half_h), pix, QRect(u_offset, 0, fov_tex_w, ph))
            else:
                first_tex_w = pw - u_offset
                second_tex_w = fov_tex_w - first_tex_w
                first_scr_w = int(w * (first_tex_w / float(fov_tex_w)))
                painter.drawPixmap(QRect(0, 0, first_scr_w, half_h), pix, QRect(u_offset, 0, first_tex_w, ph))
                painter.drawPixmap(QRect(first_scr_w, 0, w - first_scr_w, half_h), pix, QRect(0, 0, second_tex_w, ph))
        else:
            fallback_colors = {1: QColor(14, 24, 48), 2: QColor(125, 38, 28), 3: QColor(52, 68, 58)}
            painter.fillRect(0, 0, w, half_h, fallback_colors.get(sky_id, QColor(24, 30, 36)))

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        half_h = h // 2

        self.draw_skybox(painter, w, half_h)

        bands = 16
        band_h = max(1, half_h // bands + 1)
        for i in range(bands):
            shade = 22 + i * 2
            painter.fillRect(0, half_h + i * band_h, w, band_h, QColor(shade, shade, shade))

        num_rays = 140
        col_w = max(1, w // num_rays)
        dir_x = math.cos(self.pa)
        dir_y = math.sin(self.pa)
        plane_x = -dir_y * 0.66
        plane_y = dir_x * 0.66
        z_buf = [999.0] * num_rays

        for r in range(num_rays):
            cam_x = 2.0 * r / num_rays - 1.0
            ray_x = dir_x + plane_x * cam_x
            ray_y = dir_y + plane_y * cam_x

            map_x = int(self.px)
            map_y = int(self.py)

            delta_x = abs(1.0 / ray_x) if abs(ray_x) > 1e-5 else 1e30
            delta_y = abs(1.0 / ray_y) if abs(ray_y) > 1e-5 else 1e30

            if ray_x < 0:
                step_x = -1
                side_x = (self.px - map_x) * delta_x
            else:
                step_x = 1
                side_x = (map_x + 1.0 - self.px) * delta_x

            if ray_y < 0:
                step_y = -1
                side_y = (self.py - map_y) * delta_y
            else:
                step_y = 1
                side_y = (map_y + 1.0 - self.py) * delta_y

            hit_tile = 1
            side = 0
            for _ in range(28):
                if side_x < side_y:
                    side_x += delta_x
                    map_x += step_x
                    side = 0
                else:
                    side_y += delta_y
                    map_y += step_y
                    side = 1

                if not (0 <= map_x < MAP_W and 0 <= map_y < MAP_H):
                    hit_tile = 1
                    break
                tile = self.editor.map_grid[map_y * MAP_W + map_x]
                if tile > 0:
                    if tile == 4 and (map_x, map_y) in self.open_doors:
                        continue
                    hit_tile = tile
                    break

            dist = (side_x - delta_x) if side == 0 else (side_y - delta_y)
            if dist < 0.1:
                dist = 0.1
            z_buf[r] = dist

            line_h = int(h / dist)
            y0 = max(0, half_h - line_h // 2)
            y1 = min(h, half_h + line_h // 2)

            # Вираховуємо текстурну координату texX (0..63)
            wall_x = (self.py + dist * ray_y) if side == 0 else (self.px + dist * ray_x)
            wall_x -= math.floor(wall_x)
            tex_x = int(wall_x * 64)
            if (side == 0 and ray_x > 0) or (side == 1 and ray_y < 0):
                tex_x = 63 - tex_x

            img = self.wall_images.get(hit_tile)
            if img and not img.isNull():
                # Рендеримо справжню PNG-текстуру стіни вертикальною смугою
                stripe_img = img.copy(tex_x, 0, 1, 64)
                painter.drawImage(QRect(r * col_w, y0, col_w + 1, y1 - y0), stripe_img)
                # Затемнення бічною стороною (side == 1)
                if side == 1:
                    painter.fillRect(r * col_w, y0, col_w + 1, y1 - y0, QColor(0, 0, 0, 90))
            else:
                # Фолбек на кольоровий блок
                col = QColor(80, 95, 80) if hit_tile == 1 else QColor(45, 195, 90)
                painter.fillRect(r * col_w, y0, col_w + 1, y1 - y0, col)

        # Рендер спрайтів із PNG
        sorted_ents = []
        for etype, ex, ey in self.editor.entities:
            rx = (ex + 0.5) - self.px
            ry = (ey + 0.5) - self.py
            ty = rx * dir_x + ry * dir_y
            if ty > 0.2:
                sorted_ents.append((ty, rx, ry, etype))
        sorted_ents.sort(reverse=True)

        for ty, rx, ry, etype in sorted_ents:
            tx = -rx * dir_y + ry * dir_x
            scr_x = int((w / 2) * (1.0 + tx / (ty * 0.66)))
            spr_size = int(h / ty * 0.55)
            ray_idx = int(scr_x / max(1, col_w))
            if 0 <= ray_idx < num_rays and ty < z_buf[ray_idx]:
                simg = self.sprite_images.get(etype)
                if simg and not simg.isNull():
                    painter.drawImage(
                        QRect(scr_x - spr_size // 2, half_h - spr_size // 3, spr_size, spr_size),
                        simg
                    )
                else:
                    painter.setBrush(QBrush(QColor(235, 60, 60)))
                    painter.drawEllipse(scr_x - spr_size // 2, half_h - spr_size // 3, spr_size, spr_size)

        sky_names = ["Стеля бункера", "Нічне небо", "Захід сонця", "Індустріальний туман"]
        cur_sky_name = sky_names[self.editor.sky_id] if 0 <= self.editor.sky_id < len(sky_names) else "Небо"

        painter.fillRect(6, 6, 680, 24, QColor(0, 0, 0, 160))
        painter.setPen(QColor(130, 240, 150))
        painter.setFont(QFont("Monospace", 9, QFont.Weight.Bold))
        painter.drawText(
            12, 22,
            f"TEXTURED 3D | SKY: {cur_sky_name} | WASD: Рух | Space: Двері | Pos: ({self.px:.1f}, {self.py:.1f})"
        )


class LevelEditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bunker 3D Multi-Level Studio (Linux)")
        self.resize(1040, 680)

        os.makedirs("res", exist_ok=True)
        if not glob.glob("res/level*.b3d") or not os.path.exists("assets/skies/sky_night.png"):
            subprocess.run([sys.executable, "tools/build_resources.py"], check=False)

        self.map_grid = [0] * (MAP_W * MAP_H)
        self.player_start = [2, 2, 0]
        self.sky_id = 0
        self.entities = []
        self.current_tool = TOOL_WALL_CONCRETE
        self.current_level_path = "res/level1.b3d"

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_panel = QVBoxLayout()

        lvl_group = QGroupBox("КАМПАНІЯ / РІВНІ (.B3D)")
        lvl_layout = QVBoxLayout(lvl_group)

        self.level_combo = QComboBox()
        self.level_combo.currentIndexChanged.connect(self.on_level_selected)
        lvl_layout.addWidget(self.level_combo)

        lvl_btns = QHBoxLayout()
        btn_new_lvl = QPushButton("+ Новий")
        btn_new_lvl.clicked.connect(self.create_new_level)
        btn_clone_lvl = QPushButton("Клонувати")
        btn_clone_lvl.clicked.connect(self.clone_current_level)
        btn_del_lvl = QPushButton("Видалити")
        btn_del_lvl.clicked.connect(self.delete_current_level)
        lvl_btns.addWidget(btn_new_lvl)
        lvl_btns.addWidget(btn_clone_lvl)
        lvl_btns.addWidget(btn_del_lvl)
        lvl_layout.addLayout(lvl_btns)

        lvl_layout.addWidget(QLabel("Фон локації (Skybox):"))
        self.sky_combo = QComboBox()
        self.sky_combo.addItems([
            "0: Закритий бункер (Стеля)",
            "1: Нічне небо та гори (Outdoor)",
            "2: Багряний захід сонця (Doom)",
            "3: Індустріальний туман"
        ])
        self.sky_combo.currentIndexChanged.connect(self.on_sky_changed)
        lvl_layout.addWidget(self.sky_combo)

        left_panel.addWidget(lvl_group)

        tools_group = QGroupBox("ПАЛІТРА ІНСТРУМЕНТІВ (ЛКМ / ПКМ — стерти)")
        tools_layout = QVBoxLayout(tools_group)

        self.tool_buttons = {}
        tool_names = [
            ("Порожньо / Стерти (0)", TOOL_EMPTY),
            ("Бетон бункера (1)", TOOL_WALL_CONCRETE),
            ("Іржавий метал (2)", TOOL_WALL_RUST),
            ("Технічна стіна (3)", TOOL_WALL_TECH),
            ("Гермодвері (4)", TOOL_DOOR),
            ("Вихід на наст. рівень (5)", TOOL_EXIT),
            ("Спавн гравця (клік = поворот)", TOOL_PLAYER),
            ("Охоронець (Ворог)", TOOL_GUARD),
            ("Аптечка (+25 HP)", TOOL_MEDKIT),
            ("Набої (+15 AMMO)", TOOL_AMMO),
            ("Вибухова бочка", TOOL_BARREL),
        ]

        for name, tid in tool_names:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, t=tid: self.select_tool(t))
            tools_layout.addWidget(btn)
            self.tool_buttons[tid] = btn

        self.tool_buttons[TOOL_WALL_CONCRETE].setChecked(True)
        left_panel.addWidget(tools_group)
        left_panel.addStretch()

        self.status_label = QLabel("Готово")
        left_panel.addWidget(self.status_label)

        btn_save = QPushButton("💾 Зберегти всі рівні + індекс")
        btn_save.clicked.connect(self.save_all)
        left_panel.addWidget(btn_save)

        btn_build = QPushButton("🚀 Компілювати .JAR та Запустити")
        btn_build.setStyleSheet("background-color: #1E7E3E; color: white; font-weight: bold; padding: 8px;")
        btn_build.clicked.connect(self.compile_jar)
        left_panel.addWidget(btn_build)

        main_layout.addLayout(left_panel, stretch=1)

        self.tabs = QTabWidget()
        self.canvas = MapCanvas(self)
        self.tabs.addTab(self.canvas, "2D Редактор сітки")

        self.preview_3d = Preview3DWidget(self)
        self.tabs.addTab(self.preview_3d, "3D Live-Прев'ю (WASD)")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        main_layout.addWidget(self.tabs, stretch=3)

        self.refresh_level_list(select_path="res/level1.b3d")

    def on_tab_changed(self, idx):
        if idx == 1:
            self.preview_3d.reset_camera_from_level()
            self.preview_3d.setFocus()

    def on_sky_changed(self, idx):
        if idx < 0:
            return
        self.sky_id = idx
        self.mark_dirty()
        self.preview_3d.update()

    def select_tool(self, tid):
        self.current_tool = tid
        for t, btn in self.tool_buttons.items():
            btn.setChecked(t == tid)

    def mark_dirty(self):
        self.save_level(self.current_level_path)
        self.status_label.setText(f"Автозбережено: {os.path.basename(self.current_level_path)} (Sky={self.sky_id})")

    def get_sorted_level_files(self):
        return sorted(glob.glob("res/level*.b3d"), key=natural_key)

    def refresh_level_list(self, select_path=None):
        files = self.get_sorted_level_files()
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        for f in files:
            self.level_combo.addItem(os.path.basename(f), f)
        if select_path and select_path in files:
            idx = files.index(select_path)
            self.level_combo.setCurrentIndex(idx)
            self.current_level_path = select_path
        elif files:
            self.level_combo.setCurrentIndex(0)
            self.current_level_path = files[0]
        self.level_combo.blockSignals(False)
        self.load_level(self.current_level_path)

    def on_level_selected(self, idx):
        if idx < 0:
            return
        if self.current_level_path:
            self.save_level(self.current_level_path)
        new_path = self.level_combo.itemData(idx)
        self.current_level_path = new_path
        self.load_level(new_path)
        self.preview_3d.reset_camera_from_level()
        self.canvas.update()
        self.status_label.setText(f"Відкрито: {os.path.basename(new_path)}")

    def next_available_level_path(self):
        files = self.get_sorted_level_files()
        used_nums = set()
        for f in files:
            m = re.findall(r"\d+", os.path.basename(f))
            if m:
                used_nums.add(int(m[0]))
        n = 1
        while n in used_nums:
            n += 1
        return f"res/level{n}.b3d"

    def create_new_level(self):
        self.save_level(self.current_level_path)
        new_path = self.next_available_level_path()
        self.map_grid = [0] * (MAP_W * MAP_H)
        for y in range(MAP_H):
            for x in range(MAP_W):
                if x == 0 or y == 0 or x == MAP_W - 1 or y == MAP_H - 1:
                    self.map_grid[y * MAP_W + x] = 1
        self.map_grid[14 * MAP_W + 14] = 5
        self.player_start = [2, 2, 0]
        self.sky_id = 1
        self.entities = []
        self.save_level(new_path)
        self.rebuild_index()
        self.refresh_level_list(select_path=new_path)
        self.canvas.update()

    def clone_current_level(self):
        self.save_level(self.current_level_path)
        new_path = self.next_available_level_path()
        self.save_level(new_path)
        self.rebuild_index()
        self.refresh_level_list(select_path=new_path)
        self.canvas.update()

    def delete_current_level(self):
        files = self.get_sorted_level_files()
        if len(files) <= 1:
            QMessageBox.warning(self, "Увага", "У проєкті має залишатися щонайменше один рівень!")
            return
        ans = QMessageBox.question(
            self, "Видалення рівня",
            f"Видалити рівень {os.path.basename(self.current_level_path)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            os.remove(self.current_level_path)
            self.current_level_path = None
            self.rebuild_index()
            self.refresh_level_list()
            self.canvas.update()

    def load_level(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "rb") as f:
                magic = f.read(4)
                if magic.startswith(b"B3D"):
                    w = f.read(1)[0]
                    h = f.read(1)[0]
                    sx = f.read(1)[0]
                    sy = f.read(1)[0]
                    sangle = struct.unpack(">H", f.read(2))[0]
                    self.sky_id = f.read(1)[0] if magic == b"B3D3" else 0
                    self.player_start = [sx, sy, sangle]
                    self.map_grid = list(f.read(w * h))
                    self.entities = []
                    if magic in (b"B3D2", b"B3D3"):
                        b_count = f.read(1)
                        if b_count:
                            for _ in range(b_count[0]):
                                etype = f.read(1)[0]
                                ex = f.read(1)[0]
                                ey = f.read(1)[0]
                                self.entities.append([etype, ex, ey])
                    if hasattr(self, "sky_combo"):
                        self.sky_combo.blockSignals(True)
                        self.sky_combo.setCurrentIndex(self.sky_id)
                        self.sky_combo.blockSignals(False)
        except Exception as e:
            print(f"[!] Помилка читання {path}: {e}")

    def save_level(self, path):
        if not path:
            return
        with open(path, "wb") as f:
            f.write(b"B3D3")
            f.write(struct.pack(">BBBBHB", MAP_W, MAP_H, self.player_start[0], self.player_start[1], self.player_start[2], self.sky_id))
            f.write(bytes(self.map_grid))
            f.write(struct.pack(">B", len(self.entities)))
            for etype, ex, ey in self.entities:
                f.write(struct.pack(">BBB", etype, ex, ey))

    def rebuild_index(self):
        files = self.get_sorted_level_files()
        with open("res/levels.idx", "wb") as f:
            f.write(b"BIDX")
            f.write(struct.pack(">B", len(files)))
            for p in files:
                res_name = ("/" + os.path.basename(p)).encode("ascii")
                f.write(struct.pack(">B", len(res_name)))
                f.write(res_name)

    def save_all(self):
        self.save_level(self.current_level_path)
        self.rebuild_index()
        files = [os.path.basename(p) for p in self.get_sorted_level_files()]
        QMessageBox.information(self, "Збережено", f"Усі рівні збережено!\nКампанія ({len(files)}): {', '.join(files)}")

    def compile_jar(self):
        self.save_level(self.current_level_path)
        self.rebuild_index()
        try:
            subprocess.Popen(["./build.sh", "--run"])
            self.status_label.setText("Збірка .JAR та запуск емулятора...")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося запустити ./build.sh: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LevelEditorWindow()
    window.show()
    sys.exit(app.exec())
