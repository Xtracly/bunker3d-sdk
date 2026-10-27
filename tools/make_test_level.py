#!/usr/bin/env python3
import struct
import os

# 0 = порожньо, 1 = бетон бункера, 2 = іржавий метал, 3 = тех-стіна, 4 = розсувні двері
MAP_GRID = [
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
    [1,2,0,0,0,4,0,0,0,0,4,0,0,0,3,1],
    [1,2,0,0,0,2,1,0,0,0,1,3,0,0,3,1],
    [1,2,2,2,2,2,1,0,0,0,1,3,3,3,3,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

def build_level(out_path="res/level1.b3d"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    width = 16
    height = 16
    start_x = 2       # Стартова клітинка X
    start_y = 2       # Стартова клітинка Y
    start_angle = 0   # Кут (0..1023)

    with open(out_path, "wb") as f:
        # Заголовок: Magic 'B3D1', width, height, start_x, start_y, start_angle
        f.write(b"B3D1")
        f.write(struct.pack(">BBBBH", width, height, start_x, start_y, start_angle))
        for row in MAP_GRID:
            f.write(bytes(row))
    print(f"[OK] Level packed: {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    build_level()
