#!/usr/bin/env python3
import sys
import os
import struct
import random
import math
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QSlider,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox, QSpinBox,
    QCheckBox, QSplitter, QFrame
)

TEX_SIZE = 64

# ========================== ГЕНЕРАТОРИ ТЕКСТУР ==========================

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))

def noise2d(x, y, seed):
    n = int(x * 12.9898 + y * 78.233 + seed * 43.758)  # перетворюємо в int одразу
    n = (n << 13) ^ n
    return (1.0 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7fffffff) / 1073741824.0)

def generate_texture(style: str, seed: int = 0, params: dict = None) -> list:
    """Повертає список з TEX_SIZE*TEX_SIZE кольорів у форматі (r, g, b)"""
    random.seed(seed)
    params = params or {}
    pixels = [(0, 0, 0)] * (TEX_SIZE * TEX_SIZE)

    def set_px(x, y, r, g, b):
        if 0 <= x < TEX_SIZE and 0 <= y < TEX_SIZE:
            pixels[y * TEX_SIZE + x] = (clamp(r), clamp(g), clamp(b))

    # ---------- 1. Цегляна кладка ----------
    if style == "brick":
        bw = params.get("brick_w", 16)
        bh = params.get("brick_h", 8)
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                row = y // bh
                offset = (row % 2) * (bw // 2)
                local_x = (x + offset) % bw
                local_y = y % bh
                if local_x == 0 or local_y == 0:
                    set_px(x, y, 40, 42, 38)
                else:
                    v = ((row * 17 + (x // bw) * 31 + seed) & 15) - 7
                    set_px(x, y, 92 + v, 78 + v, 62 + v)

    # ---------- 2. Брудний бетон ----------
    elif style == "concrete":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                n = int((noise2d(x/4, y/4, seed) * 0.5 + noise2d(x/2, y/2, seed+1) * 0.3 + 0.5) * 40)
                base = 95 + n
                # тріщини
                if abs(noise2d(x/8, y/8, seed+3)) > 0.82:
                    base -= 35
                set_px(x, y, base, base-3, base-8)

    # ---------- 3. Іржавий метал ----------
    elif style == "rusty_metal":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                n = int(noise2d(x/3, y/3, seed) * 50)
                r = 110 + n
                g = 70 + n // 2
                b = 45 + n // 3
                if x % 9 < 1:  # вертикальні шви
                    r, g, b = r//2, g//2, b//2
                # плями іржі
                if noise2d(x/5, y/5, seed+7) > 0.6:
                    r += 40
                    g -= 10
                set_px(x, y, r, g, b)

    # ---------- 4. Гофрований метал ----------
    elif style == "corrugated":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                wave = int(math.sin(x / 3.5) * 18)
                n = int(noise2d(x/6, y/6, seed) * 20)
                base = 85 + wave + n
                set_px(x, y, base+10, base, base-15)

    # ---------- 5. Тех-панель (синя) ----------
    elif style == "tech_blue":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                if x % 16 < 1 or y % 16 < 1:
                    set_px(x, y, 25, 35, 50)
                else:
                    panel = ((x // 16) + (y // 16)) % 2
                    r = 45 + panel * 12
                    g = 70 + panel * 10
                    b = 105 + panel * 15
                    # маленькі індикатори
                    if 4 < x % 16 < 7 and 4 < y % 16 < 7 and random.random() > 0.7:
                        r, g, b = 30, 180, 80
                    set_px(x, y, r, g, b)

    # ---------- 6. Тех-панель (зелена) ----------
    elif style == "tech_green":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                if x % 16 < 1 or y % 16 < 1:
                    set_px(x, y, 20, 40, 25)
                else:
                    n = int(noise2d(x/8, y/8, seed) * 15)
                    set_px(x, y, 40 + n, 85 + n, 55 + n)

    # ---------- 7. Hazard / попередження ----------
    elif style == "hazard":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                diag = (x + y + seed) % 16
                if diag < 8:
                    set_px(x, y, 190, 160, 20)
                else:
                    set_px(x, y, 25, 25, 25)

    # ---------- 8. Гермодвері ----------
    elif style == "door":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                # Рамка
                if x < 5 or x > 58 or y < 4 or y > 59:
                    set_px(x, y, 30, 70, 40)
                else:
                    set_px(x, y, 50, 130, 70)
                    # Центральна смуга
                    if 29 < x < 35:
                        set_px(x, y, 35, 90, 50)
                    # Ручка
                    if 26 < x < 38 and 28 < y < 38:
                        set_px(x, y, 180, 170, 60)
                    # Заклепки
                    if (x in (10, 53) and y in (12, 32, 52)):
                        set_px(x, y, 160, 160, 140)

    # ---------- 9. Вентиляційна решітка ----------
    elif style == "vent":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                if x % 4 < 1 or y % 6 < 1:
                    set_px(x, y, 25, 28, 30)
                else:
                    n = int(noise2d(x/3, y/3, seed) * 20)
                    set_px(x, y, 70 + n, 75 + n, 80 + n)

    # ---------- 10. Пошкоджена стіна ----------
    elif style == "damaged":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                n = int(noise2d(x/3, y/3, seed) * 45)
                base = 80 + n
                # великі пошкодження
                if noise2d(x/7, y/7, seed+4) > 0.7:
                    base -= 40
                    set_px(x, y, base+20, base-10, base-20)  # іржавий відтінок
                else:
                    set_px(x, y, base, base-5, base-12)

    # ---------- 11. Темний бункер ----------
    elif style == "dark_bunker":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                n = int(noise2d(x/5, y/5, seed) * 25)
                set_px(x, y, 38 + n, 42 + n, 40 + n)
                if x % 32 < 1 or y % 32 < 1:
                    set_px(x, y, 25, 28, 26)

    # ---------- 12. Плитка / підлога ----------
    elif style == "tiles":
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                tx, ty = x // 16, y // 16
                local_x, local_y = x % 16, y % 16
                if local_x == 0 or local_y == 0:
                    set_px(x, y, 30, 32, 35)
                else:
                    v = ((tx * 13 + ty * 7 + seed) & 15) - 6
                    set_px(x, y, 70 + v, 75 + v, 80 + v)

    return pixels


# ========================== ГОЛОВНЕ ВІКНО ==========================

STYLES = [
    ("Цегла", "brick"),
    ("Брудний бетон", "concrete"),
    ("Іржавий метал", "rusty_metal"),
    ("Гофрований метал", "corrugated"),
    ("Тех-панель (синя)", "tech_blue"),
    ("Тех-панель (зелена)", "tech_green"),
    ("Hazard-смуги", "hazard"),
    ("Гермодвері", "door"),
    ("Вентиляція", "vent"),
    ("Пошкоджена стіна", "damaged"),
    ("Темний бункер", "dark_bunker"),
    ("Плитка", "tiles"),
]


class TextureGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bunker 3D — Texture Generator")
        self.resize(1000, 700)

        self.current_style = "brick"
        self.current_seed = 42
        self.current_pixels = []

        main = QWidget()
        self.setCentralWidget(main)
        layout = QHBoxLayout(main)

        # ===== Ліва панель =====
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>СТИЛІ ТЕКСТУР</b>"))

        self.style_list = QListWidget()
        for name, key in STYLES:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.style_list.addItem(item)
        self.style_list.setCurrentRow(0)
        self.style_list.currentItemChanged.connect(self.on_style_changed)
        left.addWidget(self.style_list)

        # Кнопки генерації
        btn_vary = QPushButton("🔄  Нова варіація")
        btn_vary.setStyleSheet("background-color: #2a6a3a; color: white; font-weight: bold; padding: 8px;")
        btn_vary.clicked.connect(self.regenerate)
        left.addWidget(btn_vary)

        btn_rand = QPushButton("🎲  Випадковий стиль")
        btn_rand.clicked.connect(self.random_style)
        left.addWidget(btn_rand)

        left.addSpacing(15)

        # Експорт
        exp_group = QGroupBox("Експорт")
        exp_layout = QVBoxLayout(exp_group)

        btn_png = QPushButton("Зберегти PNG (64×64)")
        btn_png.clicked.connect(self.export_png)
        exp_layout.addWidget(btn_png)

        btn_rgb565 = QPushButton("Зберегти RGB565 (.tex)")
        btn_rgb565.clicked.connect(self.export_rgb565)
        exp_layout.addWidget(btn_rgb565)

        btn_pak = QPushButton("📦  Експорт у assets.pak стиль")
        btn_pak.setStyleSheet("background-color: #204080; color: white; font-weight: bold;")
        btn_pak.clicked.connect(self.export_pak_style)
        exp_layout.addWidget(btn_pak)

        left.addWidget(exp_group)
        left.addStretch()

        # ===== Центр — прев'ю =====
        center = QVBoxLayout()
        center.addWidget(QLabel("<b>ПЕРЕГЛЯД 64×64</b>", alignment=Qt.AlignmentFlag.AlignCenter))

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setStyleSheet("background-color: #1a1e22; border: 2px solid #444;")
        center.addWidget(self.preview_label, stretch=1)

        self.info_label = QLabel("Стиль: — | Seed: —")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.info_label)

        # Збираємо
        layout.addLayout(left, stretch=1)
        layout.addLayout(center, stretch=3)

        self.regenerate()

    def on_style_changed(self, current, previous):
        if current:
            self.current_style = current.data(Qt.ItemDataRole.UserRole)
            self.regenerate()

    def regenerate(self):
        self.current_seed = random.randint(0, 999999)
        self.current_pixels = generate_texture(self.current_style, self.current_seed)
        self.update_preview()

    def random_style(self):
        row = random.randint(0, len(STYLES) - 1)
        self.style_list.setCurrentRow(row)

    def update_preview(self):
        img = QImage(TEX_SIZE, TEX_SIZE, QImage.Format.Format_RGB32)
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                r, g, b = self.current_pixels[y * TEX_SIZE + x]
                img.setPixel(x, y, (r << 16) | (g << 8) | b)

        # Масштабуємо найближчим сусідом (щоб було чітко)
        scaled = img.scaled(384, 384, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.preview_label.setPixmap(QPixmap.fromImage(scaled))
        self.info_label.setText(f"Стиль: <b>{self.current_style}</b>  |  Seed: {self.current_seed}")

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти PNG", f"{self.current_style}_{self.current_seed}.png", "PNG (*.png)")
        if not path:
            return
        img = QImage(TEX_SIZE, TEX_SIZE, QImage.Format.Format_RGB32)
        for y in range(TEX_SIZE):
            for x in range(TEX_SIZE):
                r, g, b = self.current_pixels[y * TEX_SIZE + x]
                img.setPixel(x, y, (r << 16) | (g << 8) | b)
        img.save(path)
        QMessageBox.information(self, "Успіх", f"Збережено:\n{path}")

    def export_rgb565(self):
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти RGB565", f"{self.current_style}_{self.current_seed}.tex", "Texture (*.tex)")
        if not path:
            return
        with open(path, "wb") as f:
            for r, g, b in self.current_pixels:
                val = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                f.write(struct.pack(">H", val))
        QMessageBox.information(self, "Успіх", f"RGB565 збережено:\n{path}")

    def export_pak_style(self):
        """Експортує поточну текстуру у вигляді, зручному для додавання в assets.pak"""
        path, _ = QFileDialog.getSaveFileName(self, "Експорт під assets.pak", f"wall_{self.current_style}.bin", "Binary (*.bin)")
        if not path:
            return
        with open(path, "wb") as f:
            for r, g, b in self.current_pixels:
                # RGB565 big-endian — саме так читає твій Java-код
                val = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                f.write(struct.pack(">H", val))
        QMessageBox.information(self, "Готово",
            f"Файл збережено:\n{path}\n\n"
            "Це сирі 8192 байти (64×64×2) у RGB565.\n"
            "Можеш додати їх у свій assets.pak як наступну wall-текстуру.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TextureGenerator()
    window.show()
    sys.exit(app.exec())
