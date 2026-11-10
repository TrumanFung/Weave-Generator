"""Draws the application icon (a 2/2 twill drawdown) into weavegen/assets.

    python tools/make_icon.py

The PNG is the window icon; the ICO is for the Windows executable.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "weavegen" / "assets"
SIZE = 256
CELLS = 8
INK = (70, 110, 215, 255)      # warp up
PAPER = (244, 238, 224, 255)  # weft up
BACK = (36, 36, 46, 255)


def draw() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=40, fill=BACK)
    margin = 20
    cell = (SIZE - 2 * margin) // CELLS
    gap = 3
    for row in range(CELLS):
        for col in range(CELLS):
            up = (col - row) % 4 < 2  # 2/2 twill
            x, y = margin + col * cell, margin + row * cell
            pen.rounded_rectangle((x + gap, y + gap, x + cell - gap, y + cell - gap),
                                  radius=5, fill=(INK if up else PAPER)[:3] + (255,))
    return image


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    icon = draw()
    icon.save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT / "icon.png", "and", OUT / "icon.ico")
