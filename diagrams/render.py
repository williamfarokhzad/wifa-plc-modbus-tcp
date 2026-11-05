"""Create original WebP diagrams from the checked-in response fixture."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

here = Path(__file__).resolve().parent
case = json.loads((here.parent / "examples/split.json").read_text())
chunks = [bytes.fromhex(chunk) for chunk in case["response_chunks"]]
wire = b"".join(chunks)
navy, teal, ink, pale, muted = "#112b45", "#006a69", "#172e49", "#edf5f5", "#3b5468"


def canvas(title, subtitle):
    im = Image.new("RGB", (840, 390), pale)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((14, 14, 826, 376), 18, fill="white")
    label(d, (44, 40), title, 38, navy)
    label(d, (44, 91), subtitle, 22, muted)
    return im, d


def label(draw, pos, text, size, color="white"):
    draw.text(pos, text, font=ImageFont.load_default(size=size), fill=color)


def box(draw, xy, color):
    draw.rounded_rectangle(xy, radius=9, fill=color)


im, d = canvas("Read a Modbus TCP response", "Synthetic example: two holding registers, function 03")
for title, start, end, x, color in (
    ("Transaction", 0, 2, 44, navy), ("Protocol", 2, 4, 231, navy),
    ("Length", 4, 6, 418, navy), ("Unit", 6, 7, 605, teal),
):
    box(d, (x, 139, x + 170, 225), color)
    label(d, (x + 12, 150), title, 22)
    label(d, (x + 12, 184), wire[start:end].hex(" ").upper(), 28)
for title, start, end, x in (("Function", 7, 8, 44), ("Byte count", 8, 9, 231),
                             ("Register 10", 9, 11, 418), ("Register 11", 11, 13, 605)):
    box(d, (x, 236, x + 170, 322), teal)
    label(d, (x + 12, 247), title, 22)
    label(d, (x + 12, 281), wire[start:end].hex(" ").upper(), 28)
label(d, (44, 337), "Length 7 covers the seven bytes in teal, starting with the Unit field.", 20, ink)
im.save(here / "modbus-tcp-response-fields.webp", quality=84, method=6)

im, d = canvas("Three chunks, one frame", "The parser waits for the full response before reading values.")
for index, chunk in enumerate(chunks):
    x = 44 + 252 * index
    box(d, (x, 146, x + 229, 236), navy if index < 2 else teal)
    label(d, (x + 12, 158), f"Chunk {index + 1}  |  {len(chunk)} bytes", 22)
    label(d, (x + 12, 195), chunk.hex(" ").upper(), 24)
    label(d, (x, 252), "Wait" if index < 2 else "Decode two registers", 22, ink)
label(d, (44, 325), f"{' + '.join(map(str, map(len, chunks)))} = {len(wire)} bytes; the length field itself is 7.", 23, muted)
im.save(here / "modbus-tcp-stream-chunks.webp", quality=84, method=6)
