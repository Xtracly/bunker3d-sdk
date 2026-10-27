#!/usr/bin/env python3
import os
import glob
import re
import math
import shutil
import struct
import wave
import zlib

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TRANSPARENT_RGB565 = 0xF81F

WALL_FILES = [
    "wall_concrete.png",       # ID 1: Бетон бункера
    "wall_rust.png",           # ID 2: Іржавий метал
    "wall_hazard.png",         # ID 3: Технічна панель
    "wall_door.png",           # ID 4: Гермодвері
    "wall_exit.png",           # ID 5: Рубильник виходу
    "flat_floor_tile.png",     # ID 6: Плитка підлоги бункера
    "flat_ceiling_lights.png", # ID 7: Стеля з тех-плафонами
    "flat_grate.png",          # ID 8: Металева решітка
]


def write_rgba_png(path, width, height, rgba_bytes):
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba_bytes[y * stride : (y + 1) * stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(make_chunk(b"IHDR", ihdr))
        f.write(make_chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(make_chunk(b"IEND", b""))


def read_png_rgba(path, target_w=64, target_h=64):
    if HAS_PIL:
        img = Image.open(path).convert("RGBA")
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.NEAREST)
        return list(img.getdata())

    with open(path, "rb") as f:
        data = f.read()
    pos = 8
    idat = bytearray()
    w = h = 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h = struct.unpack(">II", chunk_data[:8])
        elif ctype == b"IDAT":
            idat.extend(chunk_data)
    raw = zlib.decompress(bytes(idat))
    pixels = []
    stride = w * 4 + 1
    for y in range(h):
        row = raw[y * stride + 1 : (y + 1) * stride]
        for x in range(w):
            i = x * 4
            pixels.append((row[i], row[i + 1], row[i + 2], row[i + 3]))
    return pixels


def rgba_to_rgb565(r, g, b, a):
    if a < 128 or (r > 240 and g < 16 and b > 240):
        return TRANSPARENT_RGB565
    val = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    if val == TRANSPARENT_RGB565:
        val ^= 0x0020
    return val


def ensure_default_pngs():
    os.makedirs("assets/walls", exist_ok=True)
    os.makedirs("assets/sprites", exist_ok=True)
    os.makedirs("assets/weapons", exist_ok=True)

    for idx, fname in enumerate(WALL_FILES):
        p = os.path.join("assets/walls", fname)
        if os.path.exists(p):
            continue
        buf = bytearray(64 * 64 * 4)
        for y in range(64):
            for x in range(64):
                noise = ((x * 37 ^ y * 13) & 15) - 8
                border = x in (0, 63) or y in (0, 63)
                if idx == 0:  # Бетон
                    brick = ((y & 15) == 0) or (((x + ((y >> 4) & 1) * 16) & 31) == 0)
                    r, g, b = (34, 42, 34) if brick else (62 + noise, 74 + noise, 62 + noise)
                elif idx == 1:  # Іржавий метал
                    rivet = ((x in (4, 59)) and (y % 16 == 4)) or ((y in (4, 59)) and (x % 16 == 4))
                    r, g, b = (30, 24, 20) if border else ((122, 104, 85) if rivet else (78 + noise, 54 + noise, 40 + noise))
                elif idx == 2:  # Тех-панель
                    if 26 < y < 38:
                        stripe = (((x + y) >> 3) & 1) == 0
                        r, g, b = (188, 148, 22) if stripe else (26, 26, 26)
                    else:
                        r, g, b = (24, 34, 44) if border else (48 + noise, 64 + noise, 80 + noise)
                elif idx == 3:  # Гермодвері
                    frame = x < 4 or x > 59 or y < 3 or y > 60 or x in (31, 32)
                    light = 24 <= x <= 28 and 28 <= y <= 34
                    r, g, b = (32, 210, 64) if light else ((22, 27, 30) if frame else (60 + noise, 70 + noise, 75 + noise))
                elif idx == 4:  # Вихід
                    panel = 18 <= x <= 45 and 16 <= y <= 47
                    lever_slot = 29 <= x <= 34 and 22 <= y <= 41
                    lever_handle = 25 <= x <= 38 and 24 <= y <= 29
                    led = 29 <= x <= 34 and 18 <= y <= 20
                    if led:
                        r, g, b = (40, 245, 90)
                    elif lever_handle:
                        r, g, b = (230, 45, 35)
                    elif lever_slot:
                        r, g, b = (18, 20, 22)
                    elif panel:
                        p_border = x in (18, 45) or y in (16, 47)
                        r, g, b = (30, 35, 40) if p_border else (90 + noise, 98 + noise, 105 + noise)
                    else:
                        r, g, b = (24, 34, 44) if border else (48 + noise, 64 + noise, 80 + noise)
                elif idx == 5:  # Плитка підлоги (flat_floor_tile.png)
                    grid_seam = (x % 32 == 0) or (y % 32 == 0)
                    diag = ((x + y) % 16 == 0)
                    r, g, b = (28, 32, 34) if grid_seam else ((44, 50, 52) if diag else (52 + noise // 2, 58 + noise // 2, 60 + noise // 2))
                elif idx == 6:  # Стеля з плафонами (flat_ceiling_lights.png)
                    lamp = (22 <= x <= 41 and 22 <= y <= 41)
                    lamp_frame = (20 <= x <= 43 and 20 <= y <= 43)
                    beam = (x % 32 == 0) or (y % 32 == 0)
                    if lamp:
                        r, g, b = (210, 235, 220)
                    elif lamp_frame or beam:
                        r, g, b = (24, 28, 32)
                    else:
                        r, g, b = (42 + noise // 2, 48 + noise // 2, 54 + noise // 2)
                else:  # Металева решітка (flat_grate.png)
                    hole = (x % 8 in (2, 3, 4, 5)) and (y % 8 in (2, 3, 4, 5))
                    bar = (x % 16 == 0) or (y % 16 == 0)
                    if hole:
                        r, g, b = (14, 18, 16)
                    elif bar:
                        r, g, b = (82, 90, 86)
                    else:
                        r, g, b = (58 + noise // 2, 64 + noise // 2, 62 + noise // 2)

                i = (y * 64 + x) * 4
                buf[i : i + 4] = bytes((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), 255))
        write_rgba_png(p, 64, 64, buf)

    sprite_files = [
        "guard_idle.png", "guard_chase.png", "guard_shoot.png", "guard_pain.png", "guard_dead.png",
        "medkit.png", "ammo.png", "barrel.png", "barrel_dead.png",
    ]
    for s_idx, fname in enumerate(sprite_files):
        p = os.path.join("assets/sprites", fname)
        if os.path.exists(p):
            continue
        buf = bytearray(64 * 64 * 4)
        for y in range(64):
            for x in range(64):
                r = g = b = a = 0
                if s_idx in (0, 1, 2, 3):
                    step = 2 if (s_idx == 1 and x < 32) else 0
                    if 10 <= y <= 16 and 24 <= x <= 39:
                        r, g, b, a = 45, 62, 48, 255
                    elif 17 <= y <= 23 and 26 <= x <= 37:
                        if 18 <= y <= 20 and (28 <= x <= 30 or 33 <= x <= 35):
                            r, g, b, a = 220, 40, 30, 255
                        else:
                            r, g, b, a = 195, 155, 125, 255
                    elif 24 <= y <= 43 and 20 <= x <= 43:
                        r, g, b, a = (60, 78, 62, 255) if (x + y) % 7 != 0 else (42, 55, 44, 255)
                        if s_idx == 3 and (x + y) % 3 == 0:
                            r, g, b = 200, 30, 30
                    elif 28 <= y <= 35 and 15 <= x <= 48:
                        if s_idx == 2 and 27 <= x <= 36 and 26 <= y <= 34:
                            r, g, b, a = (255, 230, 70, 255) if (x + y) % 2 == 0 else (255, 130, 20, 255)
                        else:
                            r, g, b, a = 35, 38, 40, 255
                    elif 44 <= y <= 61 - step and (22 <= x <= 29 or 34 <= x <= 41):
                        r, g, b, a = (32, 36, 32, 255) if y > 55 else (50, 62, 50, 255)
                elif s_idx == 4:
                    if 48 <= y <= 61 and 12 <= x <= 52:
                        r, g, b, a = (150, 25, 25, 255) if (x * y) % 5 == 0 else (48, 60, 48, 255)
                elif s_idx == 5:
                    if 42 <= y <= 61 and 18 <= x <= 45:
                        cross = (29 <= x <= 34 and 46 <= y <= 57) or (24 <= x <= 39 and 50 <= y <= 53)
                        border = x in (18, 45) or y in (42, 61)
                        r, g, b, a = (210, 30, 30, 255) if cross else ((140, 145, 150, 255) if border else (225, 230, 235, 255))
                elif s_idx == 6:
                    if 44 <= y <= 61 and 18 <= x <= 45:
                        border = x in (18, 45) or y in (44, 61) or y == 49
                        brass = 24 <= x <= 39 and 52 <= y <= 56 and (x % 3 != 0)
                        r, g, b, a = (220, 180, 40, 255) if brass else ((40, 50, 35, 255) if border else (68, 84, 58, 255))
                elif s_idx == 7:
                    if 24 <= y <= 61 and 18 <= x <= 45:
                        rib = y in (26, 38, 50, 60)
                        toxic = 30 <= x <= 35 and 41 <= y <= 47
                        r, g, b, a = (50, 220, 40, 255) if toxic else ((95, 35, 20, 255) if rib else (165, 55, 28, 255))
                elif s_idx == 8:
                    if 50 <= y <= 61 and 16 <= x <= 48:
                        r, g, b, a = (220, 110, 20, 255) if (x + y) % 4 == 0 else (55, 45, 42, 255)

                i = (y * 64 + x) * 4
                buf[i : i + 4] = bytes((r, g, b, a))
        write_rgba_png(p, 64, 64, buf)

    weapon_files = ["pistol_idle.png", "pistol_fire.png"]
    for w_idx, fname in enumerate(weapon_files):
        p = os.path.join("assets/weapons", fname)
        if os.path.exists(p):
            continue
        buf = bytearray(64 * 64 * 4)
        for y in range(64):
            for x in range(64):
                r = g = b = a = 0
                recoil = -3 if w_idx == 1 else 0
                wy = y - recoil
                if w_idx == 1 and 14 <= y <= 32 and 22 <= x <= 42:
                    dist = abs(x - 32) + abs(y - 24)
                    if dist < 11:
                        r, g, b, a = (255, 245, 130, 255) if dist < 5 else (255, 140, 25, 255)
                if 28 <= wy <= 48 and 27 <= x <= 37:
                    sight = (wy <= 30 and 31 <= x <= 33)
                    r, g, b = (40, 220, 60) if sight else ((85, 92, 98) if x < 32 else (52, 58, 64))
                    a = 255
                elif 48 < wy <= 63 and 22 <= x <= 42:
                    r, g, b = (45, 38, 32) if wy < 55 else (70, 58, 46)
                    a = 255
                i = (y * 64 + x) * 4
                buf[i : i + 4] = bytes((r, g, b, a))
        write_rgba_png(p, 64, 64, buf)


def ensure_default_skies():
    os.makedirs("assets/skies", exist_ok=True)
    sky_files = ["sky_night.png", "sky_sunset.png", "sky_industrial.png"]

    for s_idx, fname in enumerate(sky_files):
        p = os.path.join("assets/skies", fname)
        if os.path.exists(p):
            continue
        w, h = 256, 128
        buf = bytearray(w * h * 4)
        for y in range(h):
            for x in range(w):
                mountain_h = int(92 + 14 * math.sin(x * 0.049) + 8 * math.cos(x * 0.12) + 4 * math.sin(x * 0.28))
                if s_idx == 2:
                    tower = ((x // 16) * 37) % 22
                    mountain_h = 88 + (tower if (x % 16) < 11 else 16)

                if y >= mountain_h:
                    shade = max(0, 28 - (y - mountain_h))
                    if s_idx == 0:
                        r, g, b = shade, shade + 6, shade + 14
                    elif s_idx == 1:
                        r, g, b = shade + 18, shade + 4, shade + 4
                    else:
                        r, g, b = shade + 6, shade + 8, shade + 8
                        if (x % 4 == 1) and (y % 5 == 2) and ((x * y) % 9 == 0):
                            r, g, b = 210, 175, 60
                else:
                    t = y / float(h)
                    if s_idx == 0:
                        r, g, b = int(8 + 14 * t), int(12 + 28 * t), int(28 + 48 * t)
                        if (x - 200) ** 2 + (y - 28) ** 2 <= 64:
                            r, g, b = 235, 240, 210
                        elif ((x * 73 ^ y * 151) & 255) == 0 and y < 75:
                            r, g, b = 200, 220, 255
                    elif s_idx == 1:
                        r = max(0, min(255, int(70 + 150 * t) + int(18 * math.sin(x * 0.07 + y * 0.15))))
                        g = int(18 + 75 * (t ** 1.5))
                        b = int(25 + 20 * (1.0 - t))
                    else:
                        r, g, b = int(35 + 45 * t), int(48 + 65 * t), int(42 + 50 * t)

                i = (y * w + x) * 4
                buf[i : i + 4] = bytes((r, g, b, 255))
        write_rgba_png(p, w, h, buf)
    print("[OK] Prepared 3 panoramic skyboxes (256x128) in assets/skies/")


def ensure_default_sfx():
    os.makedirs("assets/sfx", exist_ok=True)
    os.makedirs("res", exist_ok=True)
    sample_rate = 8000
    sfx_defs = {"shoot.wav": 0.16, "door.wav": 0.30, "pickup.wav": 0.18, "hurt.wav": 0.20, "boom.wav": 0.38}
    rng = 0x5A17C3
    for fname, duration in sfx_defs.items():
        src_path = os.path.join("assets/sfx", fname)
        if not os.path.exists(src_path):
            n_samples = int(sample_rate * duration)
            samples = bytearray(n_samples)
            for i in range(n_samples):
                t = i / sample_rate
                env = max(0.0, 1.0 - (i / n_samples))
                rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
                noise = ((rng >> 16) & 0xFF) / 128.0 - 1.0
                if fname == "shoot.wav":
                    freq = 260.0 * math.exp(-t * 22.0)
                    val = (0.65 * noise + 0.35 * math.sin(2.0 * math.pi * freq * t)) * (env ** 1.4)
                elif fname == "door.wav":
                    freq = 95.0 + 25.0 * math.sin(t * 35.0)
                    val = (0.75 * math.sin(2.0 * math.pi * freq * t) + 0.25 * noise) * 0.7
                elif fname == "pickup.wav":
                    freq = 520.0 if t < duration * 0.5 else 780.0
                    val = math.sin(2.0 * math.pi * freq * t) * env * 0.8
                elif fname == "hurt.wav":
                    freq = 190.0 - 90.0 * (i / n_samples)
                    val = (0.5 * math.sin(2.0 * math.pi * freq * t) + 0.5 * noise) * env
                else:
                    freq = 80.0 * math.exp(-t * 8.0)
                    val = (0.8 * noise + 0.2 * math.sin(2.0 * math.pi * freq * t)) * (env ** 1.2)
                samples[i] = max(0, min(255, int(128 + val * 115)))
            with wave.open(src_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(1)
                wf.setframerate(sample_rate)
                wf.writeframes(bytes(samples))
        shutil.copyfile(src_path, os.path.join("res", fname))
    print("[OK] Prepared 5 WAV sound effects in res/")


def pack_assets(out_pak="res/assets.pak"):
    os.makedirs(os.path.dirname(out_pak), exist_ok=True)
    sprites = [
        "guard_idle.png", "guard_chase.png", "guard_shoot.png", "guard_pain.png", "guard_dead.png",
        "medkit.png", "ammo.png", "barrel.png", "barrel_dead.png",
    ]
    weapons = ["pistol_idle.png", "pistol_fire.png"]
    skies = ["sky_night.png", "sky_sunset.png", "sky_industrial.png"]

    with open(out_pak, "wb") as f:
        f.write(b"BPAK")
        f.write(struct.pack(">BBBB", len(WALL_FILES), len(sprites), len(weapons), len(skies)))

        for wname in WALL_FILES:
            pixels = read_png_rgba(os.path.join("assets/walls", wname), 64, 64)
            for r, g, b, a in pixels:
                f.write(struct.pack(">H", rgba_to_rgb565(r, g, b, 255)))

        for sname in sprites:
            pixels = read_png_rgba(os.path.join("assets/sprites", sname), 64, 64)
            for r, g, b, a in pixels:
                f.write(struct.pack(">H", rgba_to_rgb565(r, g, b, a)))

        for wpname in weapons:
            pixels = read_png_rgba(os.path.join("assets/weapons", wpname), 64, 64)
            for r, g, b, a in pixels:
                f.write(struct.pack(">H", rgba_to_rgb565(r, g, b, a)))

        for skname in skies:
            pixels = read_png_rgba(os.path.join("assets/skies", skname), 256, 128)
            for r, g, b, a in pixels:
                f.write(struct.pack(">H", rgba_to_rgb565(r, g, b, 255)))

    print(f"[OK] Packed {len(WALL_FILES)} textures + sprites + skies into {out_pak} ({os.path.getsize(out_pak)} bytes)")


def write_b3d_file(path, wall_grid, start_pos, entities, sky_id=0, floor_grid=None, ceil_grid=None, light_grid=None):
    h = len(wall_grid)
    w = len(wall_grid[0])
    if floor_grid is None:
        floor_grid = [[6 for _ in range(w)] for _ in range(h)]
    if ceil_grid is None:
        default_c = 0 if sky_id > 0 else 7
        ceil_grid = [[default_c for _ in range(w)] for _ in range(h)]
    if light_grid is None:
        light_grid = [[8 for _ in range(w)] for _ in range(h)]

    with open(path, "wb") as f:
        f.write(b"B3D4")
        f.write(struct.pack(">BBBBHB", w, h, start_pos[0], start_pos[1], start_pos[2], sky_id))
        for row in wall_grid:
            f.write(bytes(row))
        for row in floor_grid:
            f.write(bytes(row))
        for row in ceil_grid:
            f.write(bytes(row))
        for row in light_grid:
            f.write(bytes(row))
        f.write(struct.pack(">B", len(entities)))
        for etype, ex, ey in entities:
            f.write(struct.pack(">BBB", etype, ex, ey))


def ensure_default_levels():
    os.makedirs("res", exist_ok=True)
    lvl1_path = "res/level1.b3d"
    if not os.path.exists(lvl1_path):
        grid1 = [
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            [1,0,0,0,0,1,0,0,0,0,2,0,0,0,0,1],
            [1,0,0,0,0,4,0,0,0,0,2,0,3,3,0,1],
            [1,0,0,0,0,1,0,0,0,0,4,0,0,0,0,1],
            [1,1,4,1,1,1,1,1,4,1,2,1,1,4,1,1],
            [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
            [1,0,2,0,0,2,0,0,0,0,3,0,0,3,0,1],
            [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
            [1,0,2,0,0,2,0,0,0,0,3,0,0,3,0,1],
            [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
            [1,2,2,4,2,2,1,1,4,1,1,3,3,3,3,1],
            [1,2,0,0,0,2,1,0,0,0,1,3,0,0,3,1],
            [1,2,0,0,0,4,0,0,0,0,4,0,0,0,5,1],
            [1,2,0,0,0,2,1,0,0,0,1,3,0,0,3,1],
            [1,2,2,2,2,2,1,0,0,0,1,3,3,3,3,1],
            [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        ]
        # Робимо центральний зал (рядки 5..9) відкритим подвір'ям зі скайбоксом (ceil = 0), а кімнати — під дахом (ceil = 7)
        ceil1 = [[7 for _ in range(16)] for _ in range(16)]
        floor1 = [[6 for _ in range(16)] for _ in range(16)]
        light1 = [[8 for _ in range(16)] for _ in range(16)]
        for y in range(5, 10):
            for x in range(1, 15):
                ceil1[y][x] = 0   # Відкрите небо у внутрішньому дворі!
                floor1[y][x] = 8  # Металева решітка під ногами у дворі
                light1[y][x] = 0  # Яскраве денне/нічне світло надворі

        ents1 = [
            (4, 4, 1), (3, 1, 3), (1, 8, 2), (4, 7, 2), (2, 9, 1),
            (1, 4, 7), (1, 9, 7), (4, 7, 7), (3, 1, 9), (2, 14, 5),
            (1, 13, 3), (1, 3, 12), (1, 8, 13), (4, 8, 12), (1, 13, 12), (2, 13, 13)
        ]
        write_b3d_file(lvl1_path, grid1, (2, 2, 0), ents1, sky_id=1, floor_grid=floor1, ceil_grid=ceil1, light_grid=light1)

    lvl2_path = "res/level2.b3d"
    if not os.path.exists(lvl2_path):
        grid2 = [
            [3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3],
            [3,0,0,0,3,0,0,0,0,0,0,3,0,0,0,3],
            [3,0,0,0,4,0,2,2,2,2,0,4,0,0,0,3],
            [3,0,0,0,3,0,2,0,0,2,0,3,0,0,0,3],
            [3,3,4,3,3,0,4,0,0,4,0,3,3,4,3,3],
            [3,0,0,0,0,0,2,2,2,2,0,0,0,0,0,3],
            [3,0,3,3,0,0,0,0,0,0,0,0,3,3,0,3],
            [3,0,3,3,0,0,1,4,4,1,0,0,3,3,0,3],
            [3,0,0,0,0,0,1,0,0,1,0,0,0,0,0,3],
            [3,2,2,4,2,2,1,0,0,1,2,2,4,2,2,3],
            [3,2,0,0,0,2,1,1,4,1,2,0,0,0,2,3],
            [3,2,0,0,0,2,0,0,0,0,2,0,0,0,2,3],
            [3,2,0,0,0,4,0,0,0,0,4,0,0,0,2,3],
            [3,2,0,0,0,2,0,3,3,0,2,0,0,0,2,3],
            [3,2,2,2,2,2,0,3,5,0,2,2,2,2,2,3],
            [3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3],
        ]
        ents2 = [
            (3, 2, 3), (1, 7, 1), (4, 8, 1), (1, 13, 2), (2, 14, 1),
            (1, 7, 3), (4, 8, 3), (1, 5, 6), (1, 10, 6), (4, 7, 8),
            (2, 8, 8), (1, 3, 12), (4, 3, 11), (3, 2, 13), (1, 13, 12),
            (1, 8, 11), (4, 7, 12), (4, 9, 12), (2, 13, 13)
        ]
        write_b3d_file(lvl2_path, grid2, (2, 2, 0), ents2, sky_id=2)


def natural_key(path):
    name = os.path.basename(path)
    nums = re.findall(r"\d+", name)
    return (int(nums[0]) if nums else 9999, name)


def build_levels_index(idx_path="res/levels.idx"):
    level_files = sorted(glob.glob("res/level*.b3d"), key=natural_key)
    with open(idx_path, "wb") as f:
        f.write(b"BIDX")
        f.write(struct.pack(">B", len(level_files)))
        for p in level_files:
            res_name = ("/" + os.path.basename(p)).encode("ascii")
            f.write(struct.pack(">B", len(res_name)))
            f.write(res_name)
    names = [os.path.basename(p) for p in level_files]
    print(f"[OK] Built {idx_path} with {len(names)} levels: {', '.join(names)}")


if __name__ == "__main__":
    ensure_default_pngs()
    ensure_default_skies()
    ensure_default_sfx()
    pack_assets()
    ensure_default_levels()
    build_levels_index()
