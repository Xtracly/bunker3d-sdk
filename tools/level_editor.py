#!/usr/bin/env python3
"""bunkeredit - level editor for Bunker 3D J2ME SDK (PyQt6).

Left: palettes (Walls, Floors, Ceil, Things, Flags, Light).
Centre: interactive map (zoom/pan, view modes: map, light, flags, ceiling).
Right: Level / Thing properties + smooth 30 FPS 3D preview (textured walls, floors, ceilings, sky, light).
Bottom: Log console. Supports instant UA / EN localization switching."""

import os
import sys
import re
import glob
import copy
import math
import struct
import subprocess
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QPointF, QRect, QRectF, QTimer

KIND_COLOR = {
    'monster': '#dc3c3c',
    'pickup': '#f0dc5a',
    'decor': '#ff7832',
}

FLAG_COLOR = {
    'door': '#d2a03c',
    'exit': '#00e060',
}

THINGS_DEF = {
    'guard':  {'id': 1, 'kind': 'monster', 'sprite': 'guard_idle.png'},
    'medkit': {'id': 2, 'kind': 'pickup',  'sprite': 'medkit.png'},
    'ammo':   {'id': 3, 'kind': 'pickup',  'sprite': 'ammo.png'},
    'barrel': {'id': 4, 'kind': 'decor',   'sprite': 'barrel.png'},
}
ID_TO_THING = {v['id']: k for k, v in THINGS_DEF.items()}

TEX_DEFS = [
    (1, 'wall_concrete',       'wall_concrete.png'),
    (2, 'wall_rust',           'wall_rust.png'),
    (3, 'wall_hazard',         'wall_hazard.png'),
    (4, 'wall_door',           'wall_door.png'),
    (5, 'wall_exit',           'wall_exit.png'),
    (6, 'flat_floor_tile',     'flat_floor_tile.png'),
    (7, 'flat_ceiling_lights', 'flat_ceiling_lights.png'),
    (8, 'flat_grate',          'flat_grate.png'),
]

SKY_DEFS = [
    (0, 'sky_none',       None),
    (1, 'sky_night',      'sky_night.png'),
    (2, 'sky_sunset',     'sky_sunset.png'),
    (3, 'sky_industrial', 'sky_industrial.png'),
]

TR = {
    'ua': {
        'menu_file': '&Файл',
        'menu_edit': '&Правка',
        'menu_build': '&Збірка',
        'menu_view': '&Вигляд',
        'act_new': 'Новий рівень…',
        'act_save': 'Зберегти рівень',
        'act_reload': 'Оновити PNG-ресурси',
        'act_undo': 'Скасувати (Undo)',
        'act_redo': 'Повторити (Redo)',
        'act_check': 'Перевірити рівень',
        'act_pack': 'Запакувати ресурси',
        'act_build_run': 'Зібрати JAR + Запустити емулятор',
        'lbl_level': ' Рівень: ',
        'lbl_view': ' Режим: ',
        'lbl_lang': ' Мова: ',
        'view_map': 'Карта (Стіни+Підлога)',
        'view_light': 'Освітлення',
        'view_flags': 'Тригери',
        'view_ceil': 'Стеля / Небо',
        'btn_check': 'Перевірка (F7)',
        'btn_pack': 'Пакувати (F6)',
        'btn_run': '▶ Запуск (F5)',
        'tool_brush': 'Пензель',
        'tool_rect': 'Прямокутник',
        'tool_fill': 'Заливка',
        'tool_pick': 'Піпетка',
        'tool_thing': 'Об\'єкт',
        'tool_select': 'Вибір/Рух',
        'tool_start': 'Старт гравця',
        'tool_camera': 'Камера 3D',
        'dock_palette': 'Палітра шарів',
        'tab_walls': 'Стіни',
        'tab_floors': 'Підлога',
        'tab_ceil': 'Стеля',
        'tab_things': 'Об\'єкти',
        'tab_flags': 'Тригери',
        'tab_light': 'Світло',
        'light_fmt': 'Затемнення: {v}   (0 = яскраво, 40 = темрява)',
        'dock_props': 'Властивості',
        'tab_prop_level': 'Рівень',
        'tab_prop_thing': 'Об\'єкт',
        'prop_name': 'Назва',
        'prop_sub': 'Підзаголовок',
        'prop_sky': 'Текстура неба (Skybox)',
        'prop_size': 'Розмір сітки',
        'btn_resize': 'Змінити',
        'prop_start': 'Старт X, Y, Кут (0-1023)',
        'prop_type': 'Тип об\'єкта',
        'dock_prev': '3D Прев\'ю — клікни сюди для керування: WASD / Стрілки (рух), Q/E (стрейф), Space (двері)',
        'dock_log': 'Лог збірки та перевірки',
        'wall_empty': '∅ Порожньо (Коридор)',
        'ceil_sky': '☁ ВІДКРИТЕ НЕБО (SKY)',
        'wall_concrete': 'Бетон бункера',
        'wall_rust': 'Іржавий метал',
        'wall_hazard': 'Тех-панель',
        'wall_door': 'Гермодвері',
        'wall_exit': 'Рубильник виходу',
        'flat_floor_tile': 'Плитка підлоги',
        'flat_ceiling_lights': 'Стеля з лампами',
        'flat_grate': 'Металева решітка',
        'thing_guard': 'Охоронець [ворог]',
        'thing_medkit': 'Аптечка [+25 HP]',
        'thing_ammo': 'Набої [+15 AMMO]',
        'thing_barrel': 'Вибухова бочка [декор]',
        'flag_door': 'Гермодвері (ID 4)',
        'flag_exit': 'Вихід з рівня (ID 5)',
        'sky_none': '0: Без скайбоксу (Темне небо)',
        'sky_night': '1: Нічне небо та гори',
        'sky_sunset': '2: Багряний захід сонця',
        'sky_industrial': '3: Індустріальний туман',
        'hud_active': '3D АКТИВНЕ | WASD/Стрілки: Рух | Q/E: Стрейф | Space: Двері',
        'hud_inactive': 'Клікни мишкою по 3D-вікну для керування WASD',
        'status_fmt': 'клітинка {x},{y} | шар: {l} | масштаб {z:.0f}% | інструмент: {t}',
        'dlg_unsaved_title': 'Незбережені зміни',
        'dlg_unsaved_msg': 'Зберегти зміни у файлі level{n}.b3d?',
        'dlg_new_title': 'Створення нового рівня',
        'dlg_new_num': 'Номер рівня (level<N>.b3d)',
        'dlg_new_exists': 'Рівень із таким номером вже існує.',
        'msg_saved': 'Збережено level{n}.b3d (формат B3D4) та оновлено levels.idx',
        'msg_reloaded': 'PNG-текстури та спрайти оновлено з папки assets/',
        'msg_packed': 'Ресурси запаковано у res/assets.pak та res/levels.idx',
        'msg_building': 'Пакування ресурсів, компіляція Bunker3D.jar та запуск емулятора...',
        'msg_build_ok': 'Збірку та роботу емулятора завершено успішно.',
        'msg_build_fail': 'Помилка збірки (код {c})',
        'chk_ok': 'Перевірка level{n}.b3d: ОК, проблем не виявлено',
        'chk_issues': 'Перевірка level{n}.b3d виявила зауваження:',
    },
    'en': {
        'menu_file': '&File',
        'menu_edit': '&Edit',
        'menu_build': '&Build',
        'menu_view': '&View',
        'act_new': 'New level…',
        'act_save': 'Save level',
        'act_reload': 'Reload PNG assets',
        'act_undo': 'Undo',
        'act_redo': 'Redo',
        'act_check': 'Check level',
        'act_pack': 'Pack resources',
        'act_build_run': 'Pack + build JAR + run emulator',
        'lbl_level': ' Level: ',
        'lbl_view': ' View: ',
        'lbl_lang': ' Lang: ',
        'view_map': 'Map (Walls+Floor)',
        'view_light': 'Light',
        'view_flags': 'Flags',
        'view_ceil': 'Ceiling / Sky',
        'btn_check': 'Check (F7)',
        'btn_pack': 'Pack (F6)',
        'btn_run': '▶ Run (F5)',
        'tool_brush': 'Brush',
        'tool_rect': 'Rect',
        'tool_fill': 'Fill',
        'tool_pick': 'Pick',
        'tool_thing': 'Place thing',
        'tool_select': 'Select/move',
        'tool_start': 'Start pos',
        'tool_camera': '3D Camera',
        'dock_palette': 'Layer Palettes',
        'tab_walls': 'Walls',
        'tab_floors': 'Floors',
        'tab_ceil': 'Ceil',
        'tab_things': 'Things',
        'tab_flags': 'Flags',
        'tab_light': 'Light',
        'light_fmt': 'Light level: {v}   (0 = brightest, 40 = darkest)',
        'dock_props': 'Properties',
        'tab_prop_level': 'Level',
        'tab_prop_thing': 'Thing',
        'prop_name': 'Name',
        'prop_sub': 'Subtitle',
        'prop_sky': 'Skybox texture',
        'prop_size': 'Grid size',
        'btn_resize': 'Resize',
        'prop_start': 'Start X, Y, Angle (0-1023)',
        'prop_type': 'Thing type',
        'dock_prev': '3D Preview — click here to control: WASD / Arrows (move), Q/E (strafe), Space (doors)',
        'dock_log': 'Build & Check Log',
        'wall_empty': '∅ Empty (Corridor)',
        'ceil_sky': '☁ OPEN SKY (SKYBOX)',
        'wall_concrete': 'Concrete Wall',
        'wall_rust': 'Rusty Metal',
        'wall_hazard': 'Tech Hazard Wall',
        'wall_door': 'Sliding Door',
        'wall_exit': 'Exit Switch',
        'flat_floor_tile': 'Bunker Floor Tile',
        'flat_ceiling_lights': 'Ceiling w/ Lights',
        'flat_grate': 'Metal Grate',
        'thing_guard': 'Guard [monster]',
        'thing_medkit': 'Medkit [+25 HP]',
        'thing_ammo': 'Ammo Crate [+15]',
        'thing_barrel': 'Explosive Barrel [decor]',
        'flag_door': 'Sliding Door (ID 4)',
        'flag_exit': 'Level Exit (ID 5)',
        'sky_none': '0: No Skybox (Dark Sky)',
        'sky_night': '1: Night Sky & Mountains',
        'sky_sunset': '2: Crimson Sunset (Doom)',
        'sky_industrial': '3: Industrial Fog',
        'hud_active': '3D ACTIVE | WASD/Arrows: Move | Q/E: Strafe | Space: Door',
        'hud_inactive': 'Click inside 3D view to control with WASD',
        'status_fmt': 'cell {x},{y} | layer: {l} | zoom {z:.0f}% | tool: {t}',
        'dlg_unsaved_title': 'Unsaved changes',
        'dlg_unsaved_msg': 'Save changes to level{n}.b3d?',
        'dlg_new_title': 'New level',
        'dlg_new_num': 'Level number (level<N>.b3d)',
        'dlg_new_exists': 'That level number already exists.',
        'msg_saved': 'Saved level{n}.b3d (B3D4 format) and updated levels.idx',
        'msg_reloaded': 'PNG textures & sprites reloaded from assets/',
        'msg_packed': 'Resources packed into res/assets.pak & res/levels.idx',
        'msg_building': 'Packing resources, building Bunker3D.jar & launching emulator...',
        'msg_build_ok': 'Build & emulator finished.',
        'msg_build_fail': 'Build failed (exit code {c})',
        'chk_ok': 'Check level{n}.b3d: OK, no problems found',
        'chk_issues': 'Check level{n}.b3d found issues:',
    }
}


def natural_key(path):
    name = os.path.basename(path)
    nums = re.findall(r'\d+', name)
    return (int(nums[0]) if nums else 9999, name)


# ------------------------------------------------------------------------------------------------ document
class Doc:
    def __init__(self, path, number):
        self.path = path
        self.number = number
        self.w = 16
        self.h = 16
        self.wall = [[0 for _ in range(self.w)] for _ in range(self.h)]
        self.flr = [[6 for _ in range(self.w)] for _ in range(self.h)]
        self.ceil = [[7 for _ in range(self.w)] for _ in range(self.h)]
        self.light = [[8 for _ in range(self.w)] for _ in range(self.h)]
        self.things = []
        self.start = {'x': 2.5, 'y': 2.5, 'angle': 0}
        self.meta = {
            'name': f'SECTOR {number}',
            'subtitle': 'Bunker 3D Zone',
            'sky': 1,
        }
        self.undo = []
        self.redo = []
        self.dirty = False
        self.load_from_b3d(path)

    def load_from_b3d(self, path):
        if not os.path.exists(path):
            for y in range(self.h):
                for x in range(self.w):
                    if x in (0, self.w - 1) or y in (0, self.h - 1):
                        self.wall[y][x] = 1
            self.wall[self.h - 2][self.w - 2] = 5
            return

        with open(path, 'rb') as f:
            magic = f.read(4)
            if not magic.startswith(b'B3D'):
                return
            ver = magic[3:4]
            self.w = f.read(1)[0]
            self.h = f.read(1)[0]
            sx = f.read(1)[0]
            sy = f.read(1)[0]
            sangle = struct.unpack('>H', f.read(2))[0]
            sky_id = f.read(1)[0] if ver in (b'3', b'4') else 1

            self.start = {'x': sx + 0.5, 'y': sy + 0.5, 'angle': sangle & 1023}
            self.meta['sky'] = sky_id

            total = self.w * self.h
            raw_wall = list(f.read(total))
            self.wall = [raw_wall[y * self.w : (y + 1) * self.w] for y in range(self.h)]

            if ver == b'4':
                raw_flr = list(f.read(total))
                raw_ceil = list(f.read(total))
                raw_light = list(f.read(total))
                self.flr = [raw_flr[y * self.w : (y + 1) * self.w] for y in range(self.h)]
                self.ceil = [raw_ceil[y * self.w : (y + 1) * self.w] for y in range(self.h)]
                self.light = [raw_light[y * self.w : (y + 1) * self.w] for y in range(self.h)]
            else:
                def_c = 0 if sky_id > 0 else 7
                self.flr = [[6 for _ in range(self.w)] for _ in range(self.h)]
                self.ceil = [[def_c for _ in range(self.w)] for _ in range(self.h)]
                self.light = [[8 for _ in range(self.w)] for _ in range(self.h)]

            self.things = []
            if ver in (b'2', b'3', b'4'):
                b_cnt = f.read(1)
                if b_cnt:
                    for _ in range(b_cnt[0]):
                        etype, ex, ey = struct.unpack('>BBB', f.read(3))
                        tname = ID_TO_THING.get(etype, 'guard')
                        self.things.append({
                            'type': tname,
                            'x': ex + 0.5,
                            'y': ey + 0.5,
                        })

    def save_to_b3d(self, out_path=None):
        target = out_path or self.path
        os.makedirs(os.path.dirname(target), exist_ok=True)
        sx = max(0, min(self.w - 1, int(self.start['x'])))
        sy = max(0, min(self.h - 1, int(self.start['y'])))
        sang = int(self.start['angle']) & 1023
        sky_id = int(self.meta.get('sky', 1))

        with open(target, 'wb') as f:
            f.write(b'B3D4')
            f.write(struct.pack('>BBBBHB', self.w, self.h, sx, sy, sang, sky_id))
            for row in self.wall:
                f.write(bytes(row))
            for row in self.flr:
                f.write(bytes(row))
            for row in self.ceil:
                f.write(bytes(row))
            for row in self.light:
                f.write(bytes(row))
            valid_things = [
                t for t in self.things
                if 0 <= int(t['x']) < self.w and 0 <= int(t['y']) < self.h
            ][:128]
            f.write(struct.pack('>B', len(valid_things)))
            for t in valid_things:
                tid = THINGS_DEF.get(t['type'], THINGS_DEF['guard'])['id']
                f.write(struct.pack('>BBB', tid, int(t['x']), int(t['y'])))

    def snap(self):
        return (
            copy.deepcopy(self.wall),
            copy.deepcopy(self.flr),
            copy.deepcopy(self.ceil),
            copy.deepcopy(self.light),
            copy.deepcopy(self.things),
            dict(self.start),
            copy.deepcopy(self.meta),
            self.w,
            self.h,
        )

    def restore(self, s):
        self.wall = copy.deepcopy(s[0])
        self.flr = copy.deepcopy(s[1])
        self.ceil = copy.deepcopy(s[2])
        self.light = copy.deepcopy(s[3])
        self.things = copy.deepcopy(s[4])
        self.start = dict(s[5])
        self.meta = copy.deepcopy(s[6])
        self.w, self.h = s[7], s[8]

    def push(self):
        self.undo.append(self.snap())
        self.undo = self.undo[-100:]
        self.redo = []
        self.dirty = True

    def do_undo(self):
        if self.undo:
            self.redo.append(self.snap())
            self.restore(self.undo.pop())
            self.dirty = True

    def do_redo(self):
        if self.redo:
            self.undo.append(self.snap())
            self.restore(self.redo.pop())
            self.dirty = True

    def resize(self, new_w, new_h):
        def fit_grid(grid, fill_val):
            ng = [[fill_val for _ in range(new_w)] for _ in range(new_h)]
            for y in range(min(self.h, new_h)):
                for x in range(min(self.w, new_w)):
                    ng[y][x] = grid[y][x]
            return ng

        self.wall = fit_grid(self.wall, 0)
        self.flr = fit_grid(self.flr, 6)
        self.ceil = fit_grid(self.ceil, 7)
        self.light = fit_grid(self.light, 8)
        self.things = [t for t in self.things if t['x'] < new_w and t['y'] < new_h]
        self.w, self.h = new_w, new_h

    def check(self, lang='ua'):
        out = []
        if self.w > 64 or self.h > 64:
            out.append(
                f'Розмір карти {self.w}x{self.h} перевищує ліміт 64x64'
                if lang == 'ua' else
                f'Map size {self.w}x{self.h} exceeds 64x64 limit'
            )
        sx, sy = int(self.start['x']), int(self.start['y'])
        if not (0 <= sx < self.w and 0 <= sy < self.h) or self.wall[sy][sx] != 0:
            out.append(
                'Точка старту гравця знаходиться всередині стіни або за межами карти'
                if lang == 'ua' else
                'Player start is inside a wall or outside the map'
            )
        has_exit = any(cell == 5 for row in self.wall for cell in row)
        if not has_exit:
            out.append(
                'Немає клітинки виходу з рівня (ID 5) — рівень неможливо завершити'
                if lang == 'ua' else
                'No exit switch cell (ID 5) — the level cannot be finished'
            )
        if len(self.things) > 128:
            out.append(
                f'Розміщено {len(self.things)} об\'єктів (ліміт рушія MAX_ENTITIES = 128)'
                if lang == 'ua' else
                f'{len(self.things)} things placed (engine MAX_ENTITIES limit is 128)'
            )
        for t in self.things:
            cx, cy = int(t['x']), int(t['y'])
            if not (0 <= cx < self.w and 0 <= cy < self.h):
                out.append(f"Об'єкт {t['type']} за межами карти ({cx}, {cy})" if lang == 'ua' else f"Thing {t['type']} outside map at ({cx}, {cy})")
            elif self.wall[cy][cx] != 0:
                out.append(f"Об'єкт {t['type']} всередині стіни ({cx}, {cy})" if lang == 'ua' else f"Thing {t['type']} inside wall at ({cx}, {cy})")
        return out


# ------------------------------------------------------------------------------------------------ map canvas (2D)
class Canvas(QtWidgets.QWidget):
    changed = QtCore.pyqtSignal()
    selected = QtCore.pyqtSignal(int)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.zoom = 28.0
        self.off = QPointF(32, 32)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.mode = 'map'
        self.tool = 'brush'
        self.sel = -1
        self.drag = False
        self.erase = False
        self.rect0 = None
        self.cursor_cell = None
        self.pan0 = None
        self.cam = None

    def world(self, p):
        return QPointF((p.x() - self.off.x()) / self.zoom, (p.y() - self.off.y()) / self.zoom)

    def cell(self, p):
        w = self.world(p)
        return int(math.floor(w.x())), int(math.floor(w.y()))

    def inside(self, c):
        d = self.win.doc
        return d is not None and 0 <= c[0] < d.w and 0 <= c[1] < d.h

    def paintEvent(self, ev):
        d = self.win.doc
        qp = QtGui.QPainter(self)
        qp.fillRect(self.rect(), QtGui.QColor('#1b1b1f'))
        if d is None:
            return

        z, o = self.zoom, self.off
        tp = self.win.tex_pm
        x0, y0 = max(0, int(-o.x() / z)), max(0, int(-o.y() / z))
        x1 = min(d.w, int((self.width() - o.x()) / z) + 1)
        y1 = min(d.h, int((self.height() - o.y()) / z) + 1)
        qp.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, z < 40)

        for cy in range(y0, y1):
            for cx in range(x0, x1):
                r = QRectF(o.x() + cx * z, o.y() + cy * z, z + 0.5, z + 0.5)
                wv = d.wall[cy][cx]
                fv = d.flr[cy][cx]
                cv = d.ceil[cy][cx]
                lv = d.light[cy][cx]

                if self.mode == 'light':
                    g = int(max(0, min(255, 255 * (1.0 - lv / 40.0))))
                    qp.fillRect(r, QtGui.QColor(g, g, g))
                    if wv > 0:
                        qp.fillRect(r, QtGui.QColor(90, 60, 30, 120))
                elif self.mode == 'ceiling':
                    if cv == 0:
                        qp.fillRect(r, QtGui.QColor('#4a74b5'))  # SKY
                    elif cv in tp:
                        qp.drawPixmap(r, tp[cv], QRectF(tp[cv].rect()))
                    else:
                        qp.fillRect(r, QtGui.QColor('#384048'))
                    if wv > 0:
                        qp.fillRect(r, QtGui.QColor(0, 0, 0, 150))
                else:
                    # Стандартний режим Map: стіни яскраві, підлога притемнена (як у bgedit)
                    if wv > 0 and wv in tp:
                        qp.drawPixmap(r, tp[wv], QRectF(tp[wv].rect()))
                    elif wv > 0:
                        qp.fillRect(r, QtGui.QColor('#ff00ff'))
                    elif fv in tp:
                        qp.drawPixmap(r, tp[fv], QRectF(tp[fv].rect()))
                        qp.fillRect(r, QtGui.QColor(0, 0, 0, 95))
                    else:
                        qp.fillRect(r, QtGui.QColor('#252830'))

                if wv in (4, 5):
                    fl_name = 'door' if wv == 4 else 'exit'
                    c = QtGui.QColor(FLAG_COLOR[fl_name])
                    qp.setPen(QtGui.QPen(c, 2))
                    qp.setBrush(Qt.BrushStyle.NoBrush)
                    if self.mode == 'flags':
                        c.setAlpha(130)
                        qp.fillRect(r, c)
                    else:
                        qp.drawRect(r.adjusted(1, 1, -1, -1))

        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 28), 1))
        if z >= 10:
            for cx in range(x0, x1 + 1):
                qp.drawLine(QPointF(o.x() + cx * z, o.y() + y0 * z), QPointF(o.x() + cx * z, o.y() + y1 * z))
            for cy in range(y0, y1 + 1):
                qp.drawLine(QPointF(o.x() + x0 * z, o.y() + cy * z), QPointF(o.x() + x1 * z, o.y() + cy * z))

        for i, t in enumerate(d.things):
            tinfo = THINGS_DEF.get(t['type'], THINGS_DEF['guard'])
            c = QtGui.QColor(KIND_COLOR.get(tinfo['kind'], '#ffffff'))
            rad = z * 0.34
            ctr = QPointF(o.x() + t['x'] * z, o.y() + t['y'] * z)
            qp.setPen(QtGui.QPen(QtGui.QColor('#ffffff' if i == self.sel else '#000000'), 2 if i == self.sel else 1))
            qp.setBrush(c)
            qp.drawEllipse(ctr, rad, rad)
            if z >= 18:
                qp.setPen(QtGui.QColor('#000000'))
                qp.drawText(
                    QRectF(ctr.x() - rad, ctr.y() - rad, rad * 2, rad * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    t['type'][:1].upper()
                )

        s = d.start
        a = s['angle'] * 2.0 * math.pi / 1024.0
        ctr = QPointF(o.x() + s['x'] * z, o.y() + s['y'] * z)
        poly = QtGui.QPolygonF([
            ctr + QPointF(math.cos(a), math.sin(a)) * z * 0.55,
            ctr + QPointF(math.cos(a + 2.5), math.sin(a + 2.5)) * z * 0.38,
            ctr + QPointF(math.cos(a - 2.5), math.sin(a - 2.5)) * z * 0.38,
        ])
        qp.setPen(QtGui.QPen(QtGui.QColor('#ffffff'), 1))
        qp.setBrush(QtGui.QColor('#20e060'))
        qp.drawPolygon(poly)

        if self.cam:
            cx_, cy_, ca = self.cam
            a = math.radians(ca)
            ctr = QPointF(o.x() + cx_ * z, o.y() + cy_ * z)
            qp.setPen(QtGui.QPen(QtGui.QColor('#30e0ff'), 2))
            qp.setBrush(QtGui.QColor(48, 224, 255, 55))
            qp.drawPolygon(QtGui.QPolygonF([
                ctr,
                ctr + QPointF(math.cos(a - 0.58), math.sin(a - 0.58)) * z * 2.2,
                ctr + QPointF(math.cos(a + 0.58), math.sin(a + 0.58)) * z * 2.2,
            ]))

        qp.setPen(QtGui.QPen(QtGui.QColor('#ffff00'), 1, Qt.PenStyle.DashLine))
        qp.setBrush(Qt.BrushStyle.NoBrush)
        if self.rect0 and self.cursor_cell:
            ax, ay = self.rect0
            bx, by = self.cursor_cell
            qp.drawRect(QRectF(
                o.x() + min(ax, bx) * z,
                o.y() + min(ay, by) * z,
                (abs(ax - bx) + 1) * z,
                (abs(ay - by) + 1) * z
            ))
        elif self.cursor_cell and self.tool in ('brush', 'fill', 'pick'):
            cx, cy = self.cursor_cell
            qp.drawRect(QRectF(o.x() + cx * z, o.y() + cy * z, z, z))

    def mousePressEvent(self, ev):
        d = self.win.doc
        if d is None:
            return
        self.setFocus()
        if ev.button() == Qt.MouseButton.MiddleButton or (
            ev.button() == Qt.MouseButton.LeftButton and (ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            self.pan0 = (ev.position(), QPointF(self.off))
            return

        c = self.cell(ev.position())
        w = self.world(ev.position())
        erase = (ev.button() == Qt.MouseButton.RightButton)

        if self.tool == 'camera':
            if self.inside(c):
                self.cam = (w.x(), w.y(), self.cam[2] if self.cam else 0.0)
                self.win.prev.sync_from_canvas_cam()
                self.update()
                self.win.prev.setFocus()
            return

        if self.tool == 'start':
            if self.inside(c):
                d.push()
                if int(d.start['x']) == c[0] and int(d.start['y']) == c[1]:
                    d.start['angle'] = (d.start['angle'] + 256) % 1024
                else:
                    d.start['x'] = c[0] + 0.5
                    d.start['y'] = c[1] + 0.5
                self.win.sync_meta()
                self.after_edit()
            return

        if self.tool in ('thing', 'select'):
            near = self.nearest(w)
            if erase:
                if near >= 0:
                    d.push()
                    d.things.pop(near)
                    self.sel = -1
                    self.after_edit()
                return
            if self.tool == 'select' or (near >= 0 and self.win.thing_type is None):
                self.sel = near
                self.drag = (near >= 0)
                if self.drag:
                    d.push()
                self.selected.emit(self.sel)
                self.update()
                return
            if self.win.thing_type and self.inside(c):
                d.push()
                d.things = [t for t in d.things if not (int(t['x']) == c[0] and int(t['y']) == c[1])]
                d.things.append({
                    'type': self.win.thing_type,
                    'x': c[0] + 0.5,
                    'y': c[1] + 0.5,
                })
                self.sel = len(d.things) - 1
                self.selected.emit(self.sel)
                self.after_edit()
            return

        if not self.inside(c):
            return
        if self.tool == 'pick':
            self.win.pick(c)
            return

        d.push()
        if self.tool == 'rect':
            self.rect0 = c
            self.cursor_cell = c
            return
        if self.tool == 'fill':
            self.win.flood(c, erase)
        else:
            self.win.paint(c, erase)
        self.drag = True
        self.erase = erase
        self.after_edit()

    def mouseMoveEvent(self, ev):
        d = self.win.doc
        if d is None:
            return
        if self.pan0:
            self.off = self.pan0[1] + (ev.position() - self.pan0[0])
            self.update()
            return
        c = self.cell(ev.position())
        self.cursor_cell = c
        t_dict = TR[self.win.lang]
        self.win.status.setText(
            t_dict['status_fmt'].format(x=c[0], y=c[1], l=self.win.layer, z=self.zoom / 28.0 * 100, t=self.tool)
        )
        if self.drag and self.tool == 'brush' and self.inside(c):
            self.win.paint(c, self.erase)
            self.after_edit(False)
        elif self.drag and self.tool in ('thing', 'select') and self.sel >= 0 and self.inside(c):
            t = d.things[self.sel]
            t['x'], t['y'] = c[0] + 0.5, c[1] + 0.5
            self.win.show_thing(self.sel)
            self.after_edit(False)
        self.update()

    def mouseReleaseEvent(self, ev):
        self.pan0 = None
        if self.tool == 'rect' and self.rect0 and self.cursor_cell and self.win.doc:
            ax, ay = self.rect0
            bx, by = self.cursor_cell
            erase = (ev.button() == Qt.MouseButton.RightButton)
            for y in range(max(0, min(ay, by)), min(self.win.doc.h, max(ay, by) + 1)):
                for x in range(max(0, min(ax, bx)), min(self.win.doc.w, max(ax, bx) + 1)):
                    self.win.paint((x, y), erase)
            self.rect0 = None
            self.after_edit()
        if self.drag:
            self.drag = False
            self.after_edit()

    def nearest(self, w):
        best, bd = -1, 0.55
        if not self.win.doc:
            return -1
        for i, t in enumerate(self.win.doc.things):
            dd = math.hypot(t['x'] - w.x(), t['y'] - w.y())
            if dd < bd:
                best, bd = i, dd
        return best

    def wheelEvent(self, ev):
        k = 1.15 if ev.angleDelta().y() > 0 else 1.0 / 1.15
        p = ev.position()
        w = self.world(p)
        self.zoom = max(8.0, min(96.0, self.zoom * k))
        self.off = QPointF(p.x() - w.x() * self.zoom, p.y() - w.y() * self.zoom)
        self.update()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Delete and self.sel >= 0 and self.win.doc:
            self.win.doc.push()
            self.win.doc.things.pop(self.sel)
            self.sel = -1
            self.after_edit()
        else:
            super().keyPressEvent(ev)

    def after_edit(self, signal=True):
        self.update()
        self.changed.emit()


# ------------------------------------------------------------------------------------------------ Smooth 3D Preview Dock Widget
class Preview3DDockWidget(QtWidgets.QWidget):
    """Інтерактивний 30 FPS 3D-рейкастер із рендером текстурованої підлоги, стелі, скайбоксу та світла"""
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMinimumSize(420, 290)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.px = 2.5
        self.py = 2.5
        self.pa = 0.0
        self.keys_pressed = set()
        self.open_doors = set()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def sync_from_canvas_cam(self):
        if self.win.canvas.cam:
            cx, cy, cdeg = self.win.canvas.cam
            self.px = cx
            self.py = cy
            self.pa = math.radians(cdeg)
            self.update()

    def sync_to_canvas_cam(self):
        deg = math.degrees(self.pa) % 360.0
        self.win.canvas.cam = (self.px, self.py, deg)
        self.win.canvas.update()

    def mousePressEvent(self, ev):
        self.setFocus()
        self.update()

    def focusInEvent(self, ev):
        self.update()
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        self.keys_pressed.clear()
        self.update()
        super().focusOutEvent(ev)

    def keyPressEvent(self, ev):
        if ev.isAutoRepeat():
            return
        k = ev.key()
        self.keys_pressed.add(k)
        if k == Qt.Key.Key_Space:
            d = self.win.doc
            if d:
                tx = int(self.px + math.cos(self.pa) * 0.9)
                ty = int(self.py + math.sin(self.pa) * 0.9)
                if 0 <= tx < d.w and 0 <= ty < d.h and d.wall[ty][tx] == 4:
                    if (tx, ty) in self.open_doors:
                        self.open_doors.remove((tx, ty))
                    else:
                        self.open_doors.add((tx, ty))
                    self.update()

    def keyReleaseEvent(self, ev):
        if ev.isAutoRepeat():
            return
        self.keys_pressed.discard(ev.key())

    def is_free(self, x, y):
        d = self.win.doc
        if not d:
            return False
        cx, cy = int(x), int(y)
        if not (0 <= cx < d.w and 0 <= cy < d.h):
            return False
        tile = d.wall[cy][cx]
        if tile == 0:
            return True
        if tile == 4 and (cx, cy) in self.open_doors:
            return True
        return False

    def tick(self):
        if not self.keys_pressed or not self.win.doc:
            return

        rot_speed = 0.065
        move_speed = 0.085
        moved = False

        if Qt.Key.Key_Left in self.keys_pressed or Qt.Key.Key_A in self.keys_pressed:
            self.pa -= rot_speed
            moved = True
        if Qt.Key.Key_Right in self.keys_pressed or Qt.Key.Key_D in self.keys_pressed:
            self.pa += rot_speed
            moved = True

        dx = dy = 0.0
        if Qt.Key.Key_Up in self.keys_pressed or Qt.Key.Key_W in self.keys_pressed:
            dx += math.cos(self.pa) * move_speed
            dy += math.sin(self.pa) * move_speed
        if Qt.Key.Key_Down in self.keys_pressed or Qt.Key.Key_S in self.keys_pressed:
            dx -= math.cos(self.pa) * move_speed
            dy -= math.sin(self.pa) * move_speed
        if Qt.Key.Key_Q in self.keys_pressed:
            dx += math.sin(self.pa) * move_speed
            dy -= math.cos(self.pa) * move_speed
        if Qt.Key.Key_E in self.keys_pressed:
            dx -= math.sin(self.pa) * move_speed
            dy += math.cos(self.pa) * move_speed

        if dx != 0.0 and self.is_free(self.px + dx * 2.0, self.py):
            self.px += dx
            moved = True
        if dy != 0.0 and self.is_free(self.px, self.py + dy * 2.0):
            self.py += dy
            moved = True

        if moved:
            self.sync_to_canvas_cam()
            self.update()

    def render_software_buffer(self, d, buf_w=160, buf_h=120):
        """Швидкий програмний рендер 3D-буфера зі стінами, текстурованою підлогою, стелею, небом та світлом"""
        half_h = buf_h // 2
        fb = bytearray(buf_w * buf_h * 4)

        dir_x, dir_y = math.cos(self.pa), math.sin(self.pa)
        plane_x, plane_y = -dir_y * 0.66, dir_x * 0.66
        sky_id = int(d.meta.get('sky', 1))
        sky_lut = self.win.sky_rgb.get(sky_id)
        tex_lut = self.win.tex_rgb
        default_tex = tex_lut.get(1)
        angle_sky_off = int(((self.pa % (2.0 * math.pi)) / (2.0 * math.pi)) * 256) & 255

        row_dists = [float(buf_h) * 0.5 / max(1, abs(y - half_h)) for y in range(buf_h)]
        z_buf = [999.0] * buf_w

        for x in range(buf_w):
            cam_x = 2.0 * x / buf_w - 1.0
            ray_x = dir_x + plane_x * cam_x
            ray_y = dir_y + plane_y * cam_x

            mx, my = int(self.px), int(self.py)
            delta_x = abs(1.0 / ray_x) if abs(ray_x) > 1e-5 else 1e30
            delta_y = abs(1.0 / ray_y) if abs(ray_y) > 1e-5 else 1e30

            if ray_x < 0:
                step_x, side_x = -1, (self.px - mx) * delta_x
            else:
                step_x, side_x = 1, (mx + 1.0 - self.px) * delta_x

            if ray_y < 0:
                step_y, side_y = -1, (self.py - my) * delta_y
            else:
                step_y, side_y = 1, (my + 1.0 - self.py) * delta_y

            hit_tile, side = 1, 0
            for _ in range(64):
                if side_x < side_y:
                    side_x += delta_x
                    mx += step_x
                    side = 0
                else:
                    side_y += delta_y
                    my += step_y
                    side = 1
                if not (0 <= mx < d.w and 0 <= my < d.h):
                    hit_tile = 1
                    break
                tval = d.wall[my][mx]
                if tval > 0:
                    if tval == 4 and (mx, my) in self.open_doors:
                        continue
                    hit_tile = tval
                    break

            dist = (side_x - delta_x) if side == 0 else (side_y - delta_y)
            if dist < 0.1:
                dist = 0.1
            z_buf[x] = dist

            line_h = int(buf_h / dist)
            draw_start = max(0, half_h - line_h // 2)
            draw_end = min(buf_h - 1, half_h + line_h // 2)

            sky_u = (angle_sky_off + x) & 255

            # 1. Стеля [0 .. draw_start - 1]
            for y in range(0, draw_start):
                rdist = row_dists[y]
                wx = self.px + rdist * ray_x
                wy = self.py + rdist * ray_y
                cx, cy = int(wx), int(wy)
                if 0 <= cx < d.w and 0 <= cy < d.h:
                    cid = d.ceil[cy][cx]
                    if cid == 0:
                        if sky_lut:
                            sky_v = (y * 128) // half_h
                            r, g, b = sky_lut[(sky_v << 8) + sky_u]
                        else:
                            r, g, b = 22, 32, 48
                    else:
                        ctex = tex_lut.get(cid, default_tex)
                        tx = int(wx * 64) & 63
                        ty = int(wy * 64) & 63
                        r, g, b = ctex[(ty << 6) + tx]
                        lv = d.light[cy][cx]
                        shade = max(0.15, (1.0 - lv / 44.0) / (1.0 + rdist * 0.14))
                        r, g, b = int(r * shade), int(g * shade), int(b * shade)
                elif sky_lut:
                    sky_v = (y * 128) // half_h
                    r, g, b = sky_lut[(sky_v << 8) + sky_u]
                else:
                    r, g, b = 20, 26, 32

                idx = (y * buf_w + x) * 4
                fb[idx] = b
                fb[idx + 1] = g
                fb[idx + 2] = r
                fb[idx + 3] = 255

            # 2. Стіна [draw_start .. draw_end]
            wtex = tex_lut.get(hit_tile, default_tex)
            wall_x = (self.py + dist * ray_y) if side == 0 else (self.px + dist * ray_x)
            wall_x -= math.floor(wall_x)
            tex_x = int(wall_x * 64) & 63
            if hit_tile != 4 and ((side == 0 and ray_x > 0) or (side == 1 and ray_y < 0)):
                tex_x = 63 - tex_x

            adj_x = mx - (step_x if side == 0 else 0)
            adj_y = my - (step_y if side == 1 else 0)
            cell_l = d.light[adj_y][adj_x] if (0 <= adj_x < d.w and 0 <= adj_y < d.h) else 8
            w_shade = max(0.15, (1.0 - cell_l / 44.0) / (1.0 + dist * 0.14))
            if side == 1:
                w_shade *= 0.78

            if wtex and line_h > 0:
                step_v = 64.0 / line_h
                tex_pos = (draw_start - half_h + line_h // 2) * step_v
                for y in range(draw_start, draw_end + 1):
                    ty = int(tex_pos) & 63
                    tex_pos += step_v
                    r, g, b = wtex[(ty << 6) + tex_x]
                    idx = (y * buf_w + x) * 4
                    fb[idx] = int(b * w_shade)
                    fb[idx + 1] = int(g * w_shade)
                    fb[idx + 2] = int(r * w_shade)
                    fb[idx + 3] = 255

            # 3. Підлога [draw_end + 1 .. buf_h - 1]
            for y in range(draw_end + 1, buf_h):
                rdist = row_dists[y]
                wx = self.px + rdist * ray_x
                wy = self.py + rdist * ray_y
                cx, cy = int(wx), int(wy)
                if 0 <= cx < d.w and 0 <= cy < d.h:
                    fid = d.flr[cy][cx]
                    if fid <= 0:
                        fid = 6
                    ftex = tex_lut.get(fid, default_tex)
                    tx = int(wx * 64) & 63
                    ty = int(wy * 64) & 63
                    r, g, b = ftex[(ty << 6) + tx]
                    lv = d.light[cy][cx]
                    shade = max(0.15, (1.0 - lv / 44.0) / (1.0 + rdist * 0.14))
                    r, g, b = int(r * shade), int(g * shade), int(b * shade)
                else:
                    r, g, b = 26, 30, 28

                idx = (y * buf_w + x) * 4
                fb[idx] = b
                fb[idx + 1] = g
                fb[idx + 2] = r
                fb[idx + 3] = 255

        return fb, z_buf, buf_w, buf_h

    def paintEvent(self, ev):
        d = self.win.doc
        painter = QtGui.QPainter(self)
        w, h = self.width(), self.height()

        if not d:
            painter.fillRect(0, 0, w, h, QtGui.QColor(20, 24, 28))
            return

        fb, z_buf, bw, bh = self.render_software_buffer(d, 160, 120)
        qimg = QtGui.QImage(bytes(fb), bw, bh, bw * 4, QtGui.QImage.Format.Format_RGB32)
        painter.drawImage(QRect(0, 0, w, h), qimg)

        # Поверх відмальовуємо PNG-спрайти з відсіканням по z_buf
        half_h = h // 2
        dir_x, dir_y = math.cos(self.pa), math.sin(self.pa)
        sorted_things = []
        for t in d.things:
            rx, ry = t['x'] - self.px, t['y'] - self.py
            ty = rx * dir_x + ry * dir_y
            if ty > 0.2:
                sorted_things.append((ty, rx, ry, t['type']))
        sorted_things.sort(reverse=True)

        for ty, rx, ry, tname in sorted_things:
            tx = -rx * dir_y + ry * dir_x
            scr_x = int((w / 2.0) * (1.0 + tx / (ty * 0.66)))
            spr_sz = int((h / ty) * 0.65)
            ray_i = int((scr_x / float(w)) * bw)
            if 0 <= ray_i < bw and ty < z_buf[ray_i]:
                simg = self.win.sprite_imgs.get(tname)
                if simg and not simg.isNull():
                    painter.drawImage(QRect(scr_x - spr_sz // 2, half_h - spr_sz // 2, spr_sz, spr_sz), simg)

        focused = self.hasFocus()
        t_dict = TR[self.win.lang]
        painter.fillRect(0, 0, w, 24, QtGui.QColor(0, 0, 0, 165))
        painter.setFont(QtGui.QFont('Monospace', 8, QtGui.QFont.Weight.Bold))
        painter.setPen(QtGui.QColor('#50ff78' if focused else '#ffcc40'))
        hud_msg = t_dict['hud_active'] if focused else t_dict['hud_inactive']
        painter.drawText(8, 16, f'{hud_msg} | ({self.px:.1f}, {self.py:.1f})')

        if focused:
            painter.setPen(QtGui.QPen(QtGui.QColor('#30e060'), 2))
            painter.drawRect(1, 1, w - 2, h - 2)


# ------------------------------------------------------------------------------------------------ main window
class Win(QtWidgets.QMainWindow):
    def __init__(self, proj_dir):
        super().__init__()
        self.proj_dir = os.path.abspath(proj_dir)
        self.lang = 'ua'
        self.doc = None
        self.thing_type = 'guard'
        self.cur = {'wall': 1, 'floor': 6, 'ceiling': 7, 'light': 8, 'flag': 'door'}
        self.layer = 'wall'

        self.tex_pm = {}
        self.tex_rgb = {}
        self.sprite_imgs = {}
        self.sky_rgb = {}
        self.proc = None

        self.ensure_project_resources()
        self.load_assets()

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.canvas.changed.connect(self.on_changed)
        self.canvas.selected.connect(self.show_thing)

        self.status = QtWidgets.QLabel()
        self.statusBar().addWidget(self.status)

        self.build_ui()
        self.retranslate_ui()
        self.fill_levels()
        self.resize(1500, 900)

    def ensure_project_resources(self):
        os.makedirs(os.path.join(self.proj_dir, 'res'), exist_ok=True)
        if not glob.glob(os.path.join(self.proj_dir, 'res', 'level*.b3d')) or not os.path.exists(
            os.path.join(self.proj_dir, 'assets', 'walls', 'flat_floor_tile.png')
        ):
            subprocess.run([sys.executable, os.path.join(self.proj_dir, 'tools', 'build_resources.py')], check=False)

    def load_assets(self):
        self.tex_pm.clear()
        self.tex_rgb.clear()
        self.sprite_imgs.clear()
        self.sky_rgb.clear()

        for tid, name, fname in TEX_DEFS:
            p = os.path.join(self.proj_dir, 'assets', 'walls', fname)
            if os.path.exists(p):
                img = QtGui.QImage(p).convertToFormat(QtGui.QImage.Format.Format_RGBA8888).scaled(64, 64)
                self.tex_pm[tid] = QtGui.QPixmap.fromImage(img)
                ptr = img.bits()
                ptr.setsize(64 * 64 * 4)
                raw = bytes(ptr)
                self.tex_rgb[tid] = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4)]

        for tname, info in THINGS_DEF.items():
            p = os.path.join(self.proj_dir, 'assets', 'sprites', info['sprite'])
            if os.path.exists(p):
                self.sprite_imgs[tname] = QtGui.QImage(p).convertToFormat(QtGui.QImage.Format.Format_RGBA8888)

        for sid, name, fname in SKY_DEFS:
            if fname:
                p = os.path.join(self.proj_dir, 'assets', 'skies', fname)
                if os.path.exists(p):
                    simg = QtGui.QImage(p).convertToFormat(QtGui.QImage.Format.Format_RGBA8888).scaled(256, 128)
                    ptr = simg.bits()
                    ptr.setsize(256 * 128 * 4)
                    raw = bytes(ptr)
                    self.sky_rgb[sid] = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4)]

    def populate_palettes(self):
        t = TR[self.lang]

        def fill_tex_widget(lw, extra_first=None, default_row=0):
            cur_r = max(0, lw.currentRow())
            lw.blockSignals(True)
            lw.clear()
            if extra_first:
                it0 = QtWidgets.QListWidgetItem(extra_first[0])
                it0.setData(Qt.ItemDataRole.UserRole, extra_first[1])
                lw.addItem(it0)
            for tid, key, _ in TEX_DEFS:
                pm = self.tex_pm.get(tid)
                icon = QtGui.QIcon(pm) if pm else QtGui.QIcon()
                label = t.get(key, key)
                it = QtWidgets.QListWidgetItem(icon, f'{label} ({tid})')
                it.setToolTip(f'{label} [ID {tid}]')
                it.setData(Qt.ItemDataRole.UserRole, tid)
                lw.addItem(it)
            lw.setCurrentRow(cur_r if cur_r < lw.count() else default_row)
            lw.blockSignals(False)

        fill_tex_widget(self.lw_wall, (t['wall_empty'], 0), default_row=1)
        fill_tex_widget(self.lw_floor, None, default_row=5)
        fill_tex_widget(self.lw_ceil, (t['ceil_sky'], 0), default_row=7)

        cur_thing_row = max(0, self.lw_things.currentRow())
        self.lw_things.blockSignals(True)
        self.lw_things.clear()
        for name, info in THINGS_DEF.items():
            simg = self.sprite_imgs.get(name)
            icon = QtGui.QIcon(QtGui.QPixmap.fromImage(simg)) if simg else QtGui.QIcon()
            label = t.get(f'thing_{name}', name)
            it = QtWidgets.QListWidgetItem(icon, label)
            it.setData(Qt.ItemDataRole.UserRole, name)
            it.setForeground(QtGui.QColor(KIND_COLOR[info['kind']]))
            self.lw_things.addItem(it)
        self.lw_things.setCurrentRow(cur_thing_row)
        self.lw_things.blockSignals(False)

        cur_flag_row = max(0, self.lw_flags.currentRow())
        self.lw_flags.blockSignals(True)
        self.lw_flags.clear()
        for fname in ('door', 'exit'):
            it = QtWidgets.QListWidgetItem(t[f'flag_{fname}'])
            it.setData(Qt.ItemDataRole.UserRole, fname)
            it.setForeground(QtGui.QColor(FLAG_COLOR[fname]))
            self.lw_flags.addItem(it)
        self.lw_flags.setCurrentRow(cur_flag_row)
        self.lw_flags.blockSignals(False)

        cur_sky_idx = max(0, self.c_sky.currentIndex())
        self.c_sky.blockSignals(True)
        self.c_sky.clear()
        for sid, skey, _ in SKY_DEFS:
            self.c_sky.addItem(t[skey], sid)
        if self.doc:
            self.c_sky.setCurrentIndex(int(self.doc.meta.get('sky', 1)))
        else:
            self.c_sky.setCurrentIndex(cur_sky_idx)
        self.c_sky.blockSignals(False)

    def build_ui(self):
        tb = self.addToolBar('main')
        tb.setMovable(False)

        self.lbl_level = QtWidgets.QLabel()
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.setMinimumWidth(210)
        self.level_combo.activated.connect(self.on_level_chosen)
        tb.addWidget(self.lbl_level)
        tb.addWidget(self.level_combo)

        def make_action(fn, key=None, menu=None, toolbar=False):
            a = QtGui.QAction('', self)
            a.triggered.connect(fn)
            if key:
                a.setShortcut(key)
            if menu:
                menu.addAction(a)
            if toolbar:
                tb.addAction(a)
            return a

        self.fm = self.menuBar().addMenu('')
        self.act_new = make_action(self.new_level, 'Ctrl+N', self.fm)
        self.act_save = make_action(self.save, 'Ctrl+S', self.fm)
        self.fm.addSeparator()
        self.act_reload = make_action(self.reload_assets, 'Ctrl+R', self.fm)

        self.em = self.menuBar().addMenu('')
        self.act_undo = make_action(lambda: self.edit_op('undo'), 'Ctrl+Z', self.em)
        self.act_redo = make_action(lambda: self.edit_op('redo'), 'Ctrl+Y', self.em)
        self.act_check = make_action(self.check, 'F7', self.em)

        self.bm = self.menuBar().addMenu('')
        self.act_pack = make_action(self.pack, 'F6', self.bm)
        self.act_build_run = make_action(self.build_run, 'F5', self.bm)

        self.vm = self.menuBar().addMenu('')
        self.act_lang_ua = make_action(lambda: self.set_language('ua'), None, self.vm)
        self.act_lang_ua.setText('Українська (UA)')
        self.act_lang_en = make_action(lambda: self.set_language('en'), None, self.vm)
        self.act_lang_en.setText('English (EN)')

        tb.addSeparator()
        self.tool_group = QtGui.QActionGroup(self)
        self.tool_actions = {}
        tools_spec = (
            ('brush',  'B'),
            ('rect',   'R'),
            ('fill',   'F'),
            ('pick',   'I'),
            ('thing',  'T'),
            ('select', 'V'),
            ('start',  'P'),
            ('camera', 'C'),
        )
        for name, key in tools_spec:
            a = QtGui.QAction('', self, checkable=True)
            a.setShortcut(key)
            a.triggered.connect(lambda _, n=name: self.set_tool(n))
            self.tool_group.addAction(a)
            tb.addAction(a)
            self.tool_actions[name] = (a, key)
            if name == 'brush':
                a.setChecked(True)

        tb.addSeparator()
        self.lbl_view = QtWidgets.QLabel()
        tb.addWidget(self.lbl_view)
        self.vc = QtWidgets.QComboBox()
        view_modes = ['map', 'light', 'flags', 'ceiling']
        self.vc.currentIndexChanged.connect(
            lambda idx: (setattr(self.canvas, 'mode', view_modes[idx] if 0 <= idx < 4 else 'map'), self.canvas.update())
        )
        tb.addWidget(self.vc)

        tb.addSeparator()
        self.btn_tb_check = make_action(self.check, None, toolbar=True)
        self.btn_tb_pack = make_action(self.pack, None, toolbar=True)
        self.btn_tb_run = make_action(self.build_run, None, toolbar=True)

        tb.addSeparator()
        self.lbl_lang = QtWidgets.QLabel()
        tb.addWidget(self.lbl_lang)
        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItem('🇺🇦 UA', 'ua')
        self.lang_combo.addItem('🇬🇧 EN', 'en')
        self.lang_combo.currentIndexChanged.connect(
            lambda idx: self.set_language(self.lang_combo.itemData(idx))
        )
        tb.addWidget(self.lang_combo)

        # ---- Left Dock: 6 Layer Palettes (Walls, Floors, Ceil, Things, Flags, Light)
        self.tabs = QtWidgets.QTabWidget()

        def make_tex_list(key):
            lw = QtWidgets.QListWidget()
            lw.setIconSize(QtCore.QSize(38, 38))
            lw.setSpacing(2)
            lw.currentItemChanged.connect(
                lambda cur, _, k=key: cur and self.cur.__setitem__(k, cur.data(Qt.ItemDataRole.UserRole))
            )
            return lw

        self.lw_wall = make_tex_list('wall')
        self.lw_floor = make_tex_list('floor')
        self.lw_ceil = make_tex_list('ceiling')

        self.tabs.addTab(self.lw_wall, '')
        self.tabs.addTab(self.lw_floor, '')
        self.tabs.addTab(self.lw_ceil, '')

        self.lw_things = QtWidgets.QListWidget()
        self.lw_things.setIconSize(QtCore.QSize(36, 36))
        self.lw_things.currentItemChanged.connect(
            lambda cur, _: cur and self.set_thing(cur.data(Qt.ItemDataRole.UserRole))
        )
        self.tabs.addTab(self.lw_things, '')

        self.lw_flags = QtWidgets.QListWidget()
        self.lw_flags.currentItemChanged.connect(
            lambda cur, _: cur and self.cur.__setitem__('flag', cur.data(Qt.ItemDataRole.UserRole))
        )
        self.tabs.addTab(self.lw_flags, '')

        lp = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(lp)
        self.light_sl = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.light_sl.setRange(0, 40)
        self.light_sl.setValue(8)
        self.light_lb = QtWidgets.QLabel()
        self.light_sl.valueChanged.connect(self.on_light_slider)
        ll.addWidget(self.light_lb)
        ll.addWidget(self.light_sl)
        ll.addStretch()
        self.tabs.addTab(lp, '')

        self.tabs.currentChanged.connect(self.on_tab)
        self.dock_left = QtWidgets.QDockWidget('', self)
        self.dock_left.setWidget(self.tabs)
        self.dock_left.setMinimumWidth(310)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_left)

        # ---- Right Dock 1: Properties
        self.props = QtWidgets.QTabWidget()
        lvw = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(lvw)

        self.e_name = QtWidgets.QLineEdit()
        self.e_sub = QtWidgets.QLineEdit()
        self.c_sky = QtWidgets.QComboBox()

        self.s_w = QtWidgets.QSpinBox()
        self.s_h = QtWidgets.QSpinBox()
        for s in (self.s_w, self.s_h):
            s.setRange(8, 64)
            s.setValue(24)
        szrow = QtWidgets.QHBoxLayout()
        szrow.addWidget(self.s_w)
        szrow.addWidget(QtWidgets.QLabel('×'))
        szrow.addWidget(self.s_h)
        self.b_resize = QtWidgets.QPushButton()
        self.b_resize.clicked.connect(self.do_resize)
        szrow.addWidget(self.b_resize)

        self.sa = [QtWidgets.QDoubleSpinBox() for _ in range(3)]
        for s in self.sa[:2]:
            s.setDecimals(1)
            s.setRange(0, 64)
            s.setSingleStep(0.5)
        self.sa[2].setDecimals(0)
        self.sa[2].setRange(0, 1023)
        self.sa[2].setSingleStep(64)
        strow = QtWidgets.QHBoxLayout()
        for s in self.sa:
            strow.addWidget(s)

        self.lbl_p_name = QtWidgets.QLabel()
        self.lbl_p_sub = QtWidgets.QLabel()
        self.lbl_p_sky = QtWidgets.QLabel()
        self.lbl_p_size = QtWidgets.QLabel()
        self.lbl_p_start = QtWidgets.QLabel()

        f.addRow(self.lbl_p_name, self.e_name)
        f.addRow(self.lbl_p_sub, self.e_sub)
        f.addRow(self.lbl_p_sky, self.c_sky)
        f.addRow(self.lbl_p_size, szrow)
        f.addRow(self.lbl_p_start, strow)

        for w in (self.e_name, self.e_sub):
            w.editingFinished.connect(self.meta_changed)
        self.c_sky.activated.connect(self.meta_changed)
        for s in self.sa:
            s.editingFinished.connect(self.meta_changed)

        self.props.addTab(lvw, '')

        tw = QtWidgets.QWidget()
        tf = QtWidgets.QFormLayout(tw)
        self.t_type = QtWidgets.QComboBox()
        self.t_type.addItems(list(THINGS_DEF.keys()))
        self.t_x = QtWidgets.QDoubleSpinBox()
        self.t_y = QtWidgets.QDoubleSpinBox()
        for s in (self.t_x, self.t_y):
            s.setRange(0, 64)
            s.setDecimals(1)
            s.setSingleStep(1.0)
        self.lbl_t_type = QtWidgets.QLabel()
        tf.addRow(self.lbl_t_type, self.t_type)
        tf.addRow('X', self.t_x)
        tf.addRow('Y', self.t_y)

        self.t_type.activated.connect(self.thing_changed)
        for w in (self.t_x, self.t_y):
            w.editingFinished.connect(self.thing_changed)

        self.props.addTab(tw, '')

        self.dock_props = QtWidgets.QDockWidget('', self)
        self.dock_props.setWidget(self.props)
        self.dock_props.setMinimumWidth(430)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_props)

        # ---- Right Dock 2: Smooth Live 3D Preview
        self.prev = Preview3DDockWidget(self)
        self.dock_prev = QtWidgets.QDockWidget('', self)
        self.dock_prev.setWidget(self.prev)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_prev)

        # ---- Bottom Dock: Log
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMaximumHeight(150)
        self.dock_log = QtWidgets.QDockWidget('', self)
        self.dock_log.setWidget(self.log)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_log)

    def on_light_slider(self, val):
        self.cur['light'] = val
        self.light_lb.setText(TR[self.lang]['light_fmt'].format(v=val))

    def set_language(self, lang_code):
        if lang_code not in TR:
            return
        self.lang = lang_code
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(0 if lang_code == 'ua' else 1)
        self.lang_combo.blockSignals(False)
        self.retranslate_ui()

    def retranslate_ui(self):
        t = TR[self.lang]
        self.fm.setTitle(t['menu_file'])
        self.em.setTitle(t['menu_edit'])
        self.bm.setTitle(t['menu_build'])
        self.vm.setTitle(t['menu_view'])

        self.act_new.setText(t['act_new'])
        self.act_save.setText(t['act_save'])
        self.act_reload.setText(t['act_reload'])
        self.act_undo.setText(t['act_undo'])
        self.act_redo.setText(t['act_redo'])
        self.act_check.setText(t['act_check'])
        self.act_pack.setText(t['act_pack'])
        self.act_build_run.setText(t['act_build_run'])

        self.lbl_level.setText(t['lbl_level'])
        self.lbl_view.setText(t['lbl_view'])
        self.lbl_lang.setText(t['lbl_lang'])

        cur_v = max(0, self.vc.currentIndex())
        self.vc.blockSignals(True)
        self.vc.clear()
        self.vc.addItems([t['view_map'], t['view_light'], t['view_flags'], t['view_ceil']])
        self.vc.setCurrentIndex(cur_v)
        self.vc.blockSignals(False)

        for name, (act, key) in self.tool_actions.items():
            label = t[f'tool_{name}']
            act.setText(label)
            act.setToolTip(f'{label} ({key})')

        self.btn_tb_check.setText(t['btn_check'])
        self.btn_tb_pack.setText(t['btn_pack'])
        self.btn_tb_run.setText(t['btn_run'])

        self.dock_left.setWindowTitle(t['dock_palette'])
        self.tabs.setTabText(0, t['tab_walls'])
        self.tabs.setTabText(1, t['tab_floors'])
        self.tabs.setTabText(2, t['tab_ceil'])
        self.tabs.setTabText(3, t['tab_things'])
        self.tabs.setTabText(4, t['tab_flags'])
        self.tabs.setTabText(5, t['tab_light'])
        self.light_lb.setText(t['light_fmt'].format(v=self.light_sl.value()))

        self.dock_props.setWindowTitle(t['dock_props'])
        self.props.setTabText(0, t['tab_prop_level'])
        self.props.setTabText(1, t['tab_prop_thing'])

        self.lbl_p_name.setText(t['prop_name'])
        self.lbl_p_sub.setText(t['prop_sub'])
        self.lbl_p_sky.setText(t['prop_sky'])
        self.lbl_p_size.setText(t['prop_size'])
        self.b_resize.setText(t['btn_resize'])
        self.lbl_p_start.setText(t['prop_start'])
        self.lbl_t_type.setText(t['prop_type'])

        self.dock_prev.setWindowTitle(t['dock_prev'])
        self.dock_log.setWindowTitle(t['dock_log'])

        self.populate_palettes()
        self.prev.update()

    # ---- levels management
    def level_files(self):
        res_dir = os.path.join(self.proj_dir, 'res')
        files = glob.glob(os.path.join(res_dir, 'level*.b3d'))
        return [os.path.basename(p) for p in sorted(files, key=natural_key)]

    def fill_levels(self):
        self.level_combo.clear()
        for f in self.level_files():
            nums = re.findall(r'\d+', f)
            num = int(nums[0]) if nums else 1
            self.level_combo.addItem(f'{f[:-4]}  —  SECTOR {num}', f)
        if self.level_combo.count():
            self.open_level(self.level_combo.itemData(0))

    def maybe_save(self):
        if self.doc and self.doc.dirty:
            t = TR[self.lang]
            r = QtWidgets.QMessageBox.question(
                self,
                t['dlg_unsaved_title'],
                t['dlg_unsaved_msg'].format(n=self.doc.number),
                QtWidgets.QMessageBox.StandardButton.Save
                | QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel
            )
            if r == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False
            if r == QtWidgets.QMessageBox.StandardButton.Save:
                self.save()
        return True

    def on_level_chosen(self, idx):
        if self.maybe_save():
            self.open_level(self.level_combo.itemData(idx))
        else:
            cur_f = f'level{self.doc.number}.b3d'
            for i in range(self.level_combo.count()):
                if self.level_combo.itemData(i) == cur_f:
                    self.level_combo.setCurrentIndex(i)

    def open_level(self, fname):
        nums = re.findall(r'\d+', fname)
        num = int(nums[0]) if nums else 1
        full_path = os.path.join(self.proj_dir, 'res', fname)
        self.doc = Doc(full_path, num)
        d = self.doc
        self.canvas.sel = -1
        self.canvas.off = QPointF(32, 32)
        self.canvas.cam = (d.start['x'], d.start['y'], d.start['angle'] * 360.0 / 1024.0)
        self.prev.open_doors.clear()
        self.prev.sync_from_canvas_cam()
        self.sync_meta()
        self.canvas.update()
        self.setWindowTitle(f'bunkeredit — {os.path.basename(self.proj_dir)} — {fname}')
        for i in range(self.level_combo.count()):
            if self.level_combo.itemData(i) == fname:
                self.level_combo.setCurrentIndex(i)

    def sync_meta(self):
        d = self.doc
        if not d:
            return
        m = d.meta
        widgets = (self.e_name, self.e_sub, self.c_sky, self.s_w, self.s_h, *self.sa)
        for w in widgets:
            w.blockSignals(True)
        self.e_name.setText(m['name'])
        self.e_sub.setText(m['subtitle'])
        self.c_sky.setCurrentIndex(max(0, min(self.c_sky.count() - 1, int(m['sky']))))
        self.s_w.setValue(d.w)
        self.s_h.setValue(d.h)
        self.sa[0].setValue(d.start['x'])
        self.sa[1].setValue(d.start['y'])
        self.sa[2].setValue(d.start['angle'])
        for w in widgets:
            w.blockSignals(False)

    def meta_changed(self):
        d = self.doc
        if not d:
            return
        d.push()
        m = d.meta
        m['name'] = self.e_name.text()
        m['subtitle'] = self.e_sub.text()
        m['sky'] = self.c_sky.currentIndex()
        d.start.update(
            x=self.sa[0].value(),
            y=self.sa[1].value(),
            angle=int(self.sa[2].value()) & 1023,
        )
        self.canvas.update()
        self.on_changed()

    def do_resize(self):
        if self.doc:
            self.doc.push()
            self.doc.resize(self.s_w.value(), self.s_h.value())
            self.canvas.update()
            self.on_changed()

    def new_level(self):
        if not self.maybe_save():
            return
        t = TR[self.lang]
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(t['dlg_new_title'])
        f = QtWidgets.QFormLayout(dlg)
        nums = [int(re.findall(r'\d+', x)[0]) for x in self.level_files() if re.findall(r'\d+', x)]
        num = QtWidgets.QSpinBox()
        num.setRange(1, 99)
        num.setValue(max(nums + [0]) + 1)
        name = QtWidgets.QLineEdit(f'SECTOR {num.value()}')
        sky_cb = QtWidgets.QComboBox()
        for sid, skey, _ in SKY_DEFS:
            sky_cb.addItem(t[skey], sid)
        sky_cb.setCurrentIndex(1)

        w_spin = QtWidgets.QSpinBox(); w_spin.setRange(8, 64); w_spin.setValue(24)
        h_spin = QtWidgets.QSpinBox(); h_spin.setRange(8, 64); h_spin.setValue(24)
        sz_box = QtWidgets.QHBoxLayout()
        sz_box.addWidget(w_spin); sz_box.addWidget(QtWidgets.QLabel('×')); sz_box.addWidget(h_spin)

        f.addRow(t['prop_size'], sz_box)
        f.addRow(t['dlg_new_num'], num)
        f.addRow(t['prop_name'], name)
        f.addRow(t['prop_sky'], sky_cb)

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec():
            return
        if num.value() in nums:
            QtWidgets.QMessageBox.warning(self, t['dlg_new_title'], t['dlg_new_exists'])
            return

        fn = f'level{num.value()}.b3d'
        full_path = os.path.join(self.proj_dir, 'res', fn)
        new_doc = Doc(full_path, num.value())
        new_doc.meta['name'] = name.text()
        new_doc.meta['sky'] = sky_cb.currentIndex()
        new_doc.resize(w_spin.value(), h_spin.value())
        # Робимо рамку стін по новому периметру
        for y in range(new_doc.h):
            for x in range(new_doc.w):
                new_doc.wall[y][x] = 1 if (x in (0, new_doc.w - 1) or y in (0, new_doc.h - 1)) else 0
        new_doc.wall[new_doc.h - 2][new_doc.w - 2] = 5
        new_doc.save_to_b3d()
        self.rebuild_levels_index()
        self.fill_levels()
        self.open_level(fn)
        self.say(f'Created {fn}')

    def rebuild_levels_index(self):
        idx_path = os.path.join(self.proj_dir, 'res', 'levels.idx')
        files = self.level_files()
        with open(idx_path, 'wb') as f:
            f.write(b'BIDX')
            f.write(struct.pack('>B', len(files)))
            for fname in files:
                res_name = ('/' + fname).encode('ascii')
                f.write(struct.pack('>B', len(res_name)))
                f.write(res_name)

    def save(self):
        if not self.doc:
            return
        self.doc.save_to_b3d()
        self.rebuild_levels_index()
        self.doc.dirty = False
        self.on_changed()
        self.say(TR[self.lang]['msg_saved'].format(n=self.doc.number))

    # ---- painting & tools across all 6 layers
    def set_tool(self, n):
        self.canvas.tool = n
        self.canvas.rect0 = None
        if n == 'thing' and not self.thing_type:
            self.tabs.setCurrentIndex(3)

    def on_tab(self, i):
        layers = ['wall', 'floor', 'ceiling', 'thing', 'flags', 'light']
        self.layer = layers[i] if 0 <= i < len(layers) else 'wall'
        if self.layer == 'thing' and self.canvas.tool in ('brush', 'rect', 'fill'):
            self.tool_actions['thing'][0].trigger()
        elif self.layer != 'thing' and self.canvas.tool in ('thing', 'select'):
            self.tool_actions['brush'][0].trigger()

        # Автоматичне перемикання режиму відображення карти при виборі вкладки Стеля / Світло / Тригери
        mode_idx = {'ceiling': 3, 'flags': 2, 'light': 1}.get(self.layer, 0)
        self.vc.setCurrentIndex(mode_idx)

    def set_thing(self, name):
        self.thing_type = name
        if self.canvas.tool != 'thing':
            self.tool_actions['thing'][0].trigger()

    def paint(self, c, erase):
        d, (x, y), L = self.doc, c, self.layer
        if L == 'wall':
            v = self.cur['wall']
            d.wall[y][x] = 0 if (erase or v <= 0) else v
            if d.wall[y][x] != 0:
                d.things = [t for t in d.things if not (int(t['x']) == x and int(t['y']) == y)]
        elif L == 'floor':
            d.flr[y][x] = 6 if erase else self.cur['floor']
        elif L == 'ceiling':
            d.ceil[y][x] = 0 if erase else self.cur['ceiling']
        elif L == 'light':
            d.light[y][x] = 8 if erase else self.cur['light']
        elif L == 'flags':
            fl = self.cur['flag']
            tile_id = 4 if fl == 'door' else 5
            d.wall[y][x] = 0 if erase else tile_id

    def active_grid(self):
        d = self.doc
        if not d:
            return None
        return {
            'wall': d.wall,
            'floor': d.flr,
            'ceiling': d.ceil,
            'light': d.light,
            'flags': d.wall,
        }.get(self.layer)

    def flood(self, c, erase):
        grid = self.active_grid()
        d = self.doc
        if not grid or not d:
            return
        old = grid[c[1]][c[0]]
        todo = [c]
        seen = set()
        while todo:
            x, y = todo.pop()
            if (x, y) in seen or not (0 <= x < d.w and 0 <= y < d.h) or grid[y][x] != old:
                continue
            seen.add((x, y))
            self.paint((x, y), erase)
            todo.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
            if len(seen) > 2048:
                break

    def pick(self, c):
        d, (x, y), L = self.doc, c, self.layer
        if L == 'light':
            self.light_sl.setValue(int(d.light[y][x]))
            return
        lw = {'wall': self.lw_wall, 'floor': self.lw_floor, 'ceiling': self.lw_ceil}.get(L)
        grid = {'wall': d.wall, 'floor': d.flr, 'ceiling': d.ceil}.get(L)
        if lw and grid:
            val = grid[y][x]
            for i in range(lw.count()):
                if lw.item(i).data(Qt.ItemDataRole.UserRole) == val:
                    lw.setCurrentRow(i)
                    break

    # ---- things panel
    def show_thing(self, i):
        d = self.doc
        if not d or i < 0 or i >= len(d.things):
            return
        t = d.things[i]
        self.props.setCurrentIndex(1)
        for w in (self.t_type, self.t_x, self.t_y):
            w.blockSignals(True)
        self.t_type.setCurrentText(t['type'])
        self.t_x.setValue(t['x'])
        self.t_y.setValue(t['y'])
        for w in (self.t_type, self.t_x, self.t_y):
            w.blockSignals(False)

    def thing_changed(self):
        d, i = self.doc, self.canvas.sel
        if not d or i < 0 or i >= len(d.things):
            return
        d.push()
        t = d.things[i]
        t.update(
            type=self.t_type.currentText(),
            x=self.t_x.value(),
            y=self.t_y.value(),
        )
        self.canvas.update()
        self.on_changed()

    def on_changed(self):
        base = self.windowTitle().rstrip(' *')
        self.setWindowTitle(base + (' *' if self.doc and self.doc.dirty else ''))
        self.prev.update()

    # ---- actions: undo/redo, check, reload, pack, build+run
    def edit_op(self, op):
        if not self.doc:
            return
        getattr(self.doc, 'do_' + op)()
        self.sync_meta()
        self.canvas.update()
        self.on_changed()

    def say(self, s):
        self.log.appendPlainText(s)
        self.statusBar().showMessage(s, 4000)

    def check(self):
        if not self.doc:
            return
        t = TR[self.lang]
        issues = self.doc.check(self.lang)
        self.say(
            t['chk_ok'].format(n=self.doc.number)
            if not issues else
            t['chk_issues'].format(n=self.doc.number)
        )
        for s in issues:
            self.say('  ! ' + s)

    def reload_assets(self):
        self.load_assets()
        self.populate_palettes()
        self.canvas.update()
        self.prev.update()
        self.say(TR[self.lang]['msg_reloaded'])

    def pack(self):
        if self.doc and self.doc.dirty:
            self.save()
        res = subprocess.run(
            [sys.executable, os.path.join(self.proj_dir, 'tools', 'build_resources.py')],
            cwd=self.proj_dir,
            capture_output=True,
            text=True
        )
        if res.stdout:
            self.log.appendPlainText(res.stdout.strip())
        if res.stderr:
            self.log.appendPlainText(res.stderr.strip())
        self.say(TR[self.lang]['msg_packed'])

    def build_run(self):
        if self.doc and self.doc.dirty:
            self.save()
        t = TR[self.lang]
        self.say(t['msg_building'])
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.proc.setWorkingDirectory(self.proj_dir)
        self.proc.readyRead.connect(
            lambda: self.log.appendPlainText(bytes(self.proc.readAll()).decode(errors='replace').rstrip())
        )
        self.proc.finished.connect(
            lambda code, _: self.say(
                t['msg_build_ok'] if code == 0 else t['msg_build_fail'].format(c=code)
            )
        )
        self.proc.start('bash', [os.path.join(self.proj_dir, 'build.sh'), '--run'])

    def closeEvent(self, ev):
        if self.maybe_save():
            ev.accept()
        else:
            ev.ignore()


def main():
    proj = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = QtWidgets.QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    w = Win(proj)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
