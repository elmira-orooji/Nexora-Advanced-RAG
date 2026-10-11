"""Create a high-contrast, full-frame Nexora product-tour GIF.

The output retains the editorial browser-window template requested by the
product owner. Every screen is a real Nexora capture, scaled without cropping
so the sidebar and companion panels remain fully visible.
"""
from pathlib import Path
from math import pi, sin

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media"
CAPTURES = MEDIA / "promo-frames"
OUT = MEDIA / "nexora-product-promo.gif"
POSTER = MEDIA / "nexora-promo-poster.png"
SHEET = MEDIA / "nexora-promo-contact-sheet.jpg"

W, H = 1280, 900
WINDOW_X, WINDOW_Y = 60, 156
CONTENT_W, CONTENT_H = 1160, 653  # exact 16:9: no crop from the 1280x720 sources
CHROME_H = 28
FPS = 10
FONT_DIR = Path("C:/Windows/Fonts")
REGULAR = lambda size: ImageFont.truetype(str(FONT_DIR / "segoeui.ttf"), size)
SEMIBOLD = lambda size: ImageFont.truetype(str(FONT_DIR / "segoeuib.ttf"), size)

# Each step is a real interaction: the cursor moves on the current capture,
# clicks a visible control, and only then does the destination capture appear.
# This prevents a pointer from ever implying that a control on the destination
# screen was clicked to get there.
STEPS = [
    ("login", "Your Nexora workspace", "Sign in to manage knowledge, conversations, and your team.", (972, 587), "analytics"),
    ("analytics", "Understand your workspace", "Review activity, answer quality, and knowledge health.", (1080, 50), "notifications"),
    ("notifications", "Keep track of operations", "See document and connector updates in one place.", (1190, 112), "analytics"),
    ("analytics", "Export the details", "Download an Excel workbook, CSV data, or a printable report.", (1168, 50), "export"),
    ("export", "Bring knowledge together", "Organize documents into focused knowledge sets.", (1180, 50), "analytics"),
    ("analytics", "Bring knowledge together", "Organize documents into focused knowledge sets.", (92, 279), "knowledge"),
    ("knowledge", "Connect trusted sources", "Bring external sources into the right collection.", (770, 337), "connectors"),
    ("connectors", "Tune retrieval context", "Control how source documents become answerable context.", (939, 108), "knowledge"),
    ("knowledge", "Tune retrieval context", "Control how source documents become answerable context.", (708, 92), "chunking"),
    ("chunking", "Ask with context", "Start a source-grounded conversation from your knowledge.", (939, 119), "knowledge"),
    ("knowledge", "Ask with context", "Start a source-grounded conversation from your knowledge.", (120, 150), "conversation"),
    ("conversation", "Trace every answer", "Open the exact passage behind each cited response.", (735, 480), "sources"),
    ("sources", "Create focused assistants", "Give each assistant clear instructions and sources.", (1191, 114), "conversation"),
    ("conversation", "Create focused assistants", "Give each assistant clear instructions and sources.", (95, 322), "assistants"),
    ("assistants", "Manage your team", "Keep roles and member access visible in one place.", (95, 365), "team"),
    ("team", "A workspace that fits", "Choose language and appearance without losing consistency.", (95, 406), "settings-light"),
    ("settings-light", "Light or dark", "The same Nexora experience in every viewing mode.", (1100, 342), "settings-dark"),
    ("settings-dark", "A source-grounded conversation", "Ask, verify, and trace answers in one workspace.", (120, 150), "chat-dark-en"),
    ("chat-dark-en", "A source-grounded conversation", "Ask, verify, and trace answers in one workspace.", None, None),
]


def eased(value):
    return 1 - (1 - value) ** 3


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *size), radius=radius, fill=255)
    return mask


def branded_background():
    canvas = Image.new("RGBA", (W, H), "#f8f9fe")
    light = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(light)
    draw.ellipse((-180, -210, 410, 340), fill=(124, 39, 255, 34))
    draw.ellipse((750, -170, 1430, 370), fill=(24, 199, 244, 32))
    draw.ellipse((470, 650, 1040, 1090), fill=(196, 60, 255, 20))
    return Image.alpha_composite(canvas, light.filter(ImageFilter.GaussianBlur(82)))


def screen(name):
    image = Image.open(CAPTURES / f"{name}.png").convert("RGB")
    # Preserve actual project colors, then lift only local contrast for GIF
    # palettes so small text does not disappear against white surfaces.
    image = ImageEnhance.Contrast(image).enhance(1.09)
    image = ImageEnhance.Color(image).enhance(1.04)
    image = ImageEnhance.Sharpness(image).enhance(1.10)
    return image.resize((CONTENT_W, CONTENT_H), Image.Resampling.LANCZOS)


def draw_browser(canvas, product):
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sx, sy = WINDOW_X + 10, WINDOW_Y + 15
    ImageDraw.Draw(shadow).rounded_rectangle((sx, sy, sx + CONTENT_W, sy + CONTENT_H + CHROME_H), radius=22, fill=(27, 39, 71, 54))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(20)))
    browser = Image.new("RGBA", (CONTENT_W, CONTENT_H + CHROME_H), "#ffffff")
    draw = ImageDraw.Draw(browser)
    draw.rounded_rectangle((0, 0, CONTENT_W - 1, CONTENT_H + CHROME_H - 1), radius=18, fill="#ffffff", outline="#d8dfed", width=1)
    for offset, color in ((22, "#a5adbd"), (36, "#a5adbd"), (50, "#a5adbd")):
        draw.ellipse((offset - 4, 11, offset + 4, 19), fill=color)
    browser.paste(product, (0, CHROME_H))
    canvas.paste(browser, (WINDOW_X, WINDOW_Y), rounded_mask(browser.size, 18))


def draw_cursor(canvas, source_point, pulse=0):
    scale = CONTENT_W / 1280
    x = int(WINDOW_X + source_point[0] * scale)
    y = int(WINDOW_Y + CHROME_H + source_point[1] * scale)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if pulse:
        radius = int(10 + pulse * 20)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(124, 39, 255, int(145 * (1 - pulse))), width=3)
    pointer = [(x, y), (x, y + 19), (x + 6, y + 14), (x + 12, y + 25), (x + 17, y + 22), (x + 12, y + 11), (x + 22, y + 11)]
    draw.polygon(pointer, fill="#ffffff", outline="#17233d")
    return Image.alpha_composite(canvas, layer)


def project_logo(width):
    """Use the brand rendered by the actual login screen, not a redrawn mark."""
    capture = Image.open(CAPTURES / "login.png").convert("RGBA")
    # This is the exact horizontal Nexora mark, including the small by-elmira
    # signature, as it is rendered in the project login page.
    mark = capture.crop((872, 164, 1078, 228))
    pixels = mark.load()
    for y in range(mark.height):
        for x in range(mark.width):
            red, green, blue, alpha = pixels[x, y]
            # Remove only the white login surface while preserving antialiasing.
            whiteness = min(red, green, blue)
            if whiteness > 246:
                pixels[x, y] = (red, green, blue, 0)
            elif whiteness > 225:
                pixels[x, y] = (red, green, blue, int((246 - whiteness) * 12))
    height = max(1, round(mark.height * width / mark.width))
    return mark.resize((width, height), Image.Resampling.LANCZOS)


def draw_header(canvas, number, title, subtitle):
    draw = ImageDraw.Draw(canvas)
    mark = project_logo(116)
    canvas.alpha_composite(mark, (42, 27))
    draw.text((1212, 36), f"{number:02d} / {len(STEPS):02d}", font=REGULAR(10), fill="#64748b", anchor="ra")
    draw.text((W // 2, 66), title, font=SEMIBOLD(29), fill="#17284a", anchor="ma")
    draw.text((W // 2, 104), subtitle, font=REGULAR(15), fill="#52627e", anchor="ma")
    draw.rectangle((382, 132, 898, 134), fill="#dde4f0")
    draw.rectangle((382, 132, 382 + int(516 * number / len(STEPS)), 134), fill="#7c27ff")


def compose(product, number, title, subtitle, pointer=None, pulse=0):
    canvas = branded_background()
    draw_header(canvas, number, title, subtitle)
    draw_browser(canvas, product)
    if pointer is not None:
        canvas = draw_cursor(canvas, pointer, pulse)
    draw = ImageDraw.Draw(canvas)
    draw.text((42, 868), "NEXORA  /  PRODUCT TOUR", font=SEMIBOLD(10), fill="#60708b")
    return canvas.convert("RGB")


def compose_intro(opacity=1.0):
    canvas = branded_background()
    mark = project_logo(300)
    mark.putalpha(mark.getchannel("A").point(lambda value: round(value * opacity)))
    canvas.alpha_composite(mark, ((W - mark.width) // 2, 300))
    draw = ImageDraw.Draw(canvas)
    text_alpha = int(255 * opacity)
    draw.text((W // 2, 430), "Knowledge, grounded.", font=SEMIBOLD(31), fill=(23, 40, 74, text_alpha), anchor="ma")
    draw.text((W // 2, 474), "A focused workspace for your team and documents.", font=REGULAR(16), fill=(82, 98, 126, text_alpha), anchor="ma")
    draw.text((W // 2, 830), "NEXORA  /  PRODUCT TOUR", font=SEMIBOLD(10), fill=(96, 112, 139, text_alpha), anchor="ma")
    return canvas.convert("RGB")


def build_frames():
    screen_names = tuple(dict.fromkeys(step[0] for step in STEPS))
    products = {name: screen(name) for name in screen_names}
    frames = []
    for tick in range(8):
        frames.append(compose_intro(eased((tick + 1) / 8)))
    for _ in range(8):
        frames.append(compose_intro())
    previous_pointer = (640, 500)
    for index, (name, title, subtitle, pointer, destination) in enumerate(STEPS, start=1):
        current = products[name]
        if pointer is None:
            for _ in range(16):
                frames.append(compose(current, index, title, subtitle))
            continue
        for tick in range(7):
            progress = eased(tick / 6)
            point = (
                previous_pointer[0] + (pointer[0] - previous_pointer[0]) * progress,
                previous_pointer[1] + (pointer[1] - previous_pointer[1]) * progress,
            )
            frames.append(compose(current, index, title, subtitle, point))
        for tick in range(4):
            frames.append(compose(current, index, title, subtitle, pointer, (tick + 1) / 4))
        for _ in range(5):
            frames.append(compose(current, index, title, subtitle, pointer))
        if destination:
            following = products[destination]
            for tick in range(6):
                progress = eased((tick + 1) / 6)
                blended = Image.blend(current, following, progress)
                # The cursor is intentionally absent while the UI changes.
                # It re-enters on the next screen and targets its own control.
                frames.append(compose(blended, index, title, subtitle))
        previous_pointer = pointer
    return frames


def main():
    rgb_frames = build_frames()
    # Build one compatible palette from every real product state, including the
    # navy dark-mode screen. This is valid in GIF readers while retaining the
    # light neutrals, violet accents, cyan details, and dark surfaces.
    palette_sheet = Image.new("RGB", (1280, 1800), "#f8f9fe")
    for index, step in enumerate(STEPS):
        keyframe = compose(screen(step[0]), index + 1, step[1], step[2], step[3])
        palette_sheet.paste(keyframe.resize((640, 360), Image.Resampling.LANCZOS), ((index % 2) * 640, (index // 2) * 360))
    palette = palette_sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    # Reserve exact product foundations before mapping the rendered frames.
    # This prevents the GIF encoder from approximating Nexora navy as violet.
    required_colors = [
        (9, 19, 42), (11, 19, 35), (12, 20, 38), (15, 28, 52),
        (18, 29, 53), (21, 30, 52), (32, 41, 64), (23, 32, 51),
        (124, 39, 255), (196, 60, 255), (24, 199, 244), (50, 18, 122),
        (255, 255, 255), (248, 249, 254), (82, 97, 122), (104, 115, 138),
    ]
    palette_data = palette.getpalette()
    for index, color in enumerate(required_colors):
        palette_data[index * 3:index * 3 + 3] = color
    palette.putpalette(palette_data)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG) for frame in rgb_frames]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, optimize=False, disposal=1)
    rgb_frames[0].save(POSTER)
    sheet = Image.new("RGB", (960, 540), "#f8f9fe")
    for index, step in enumerate(STEPS[:6]):
        frame = compose(screen(step[0]), index + 1, step[1], step[2], step[3])
        sheet.paste(frame.resize((320, 225), Image.Resampling.LANCZOS), ((index % 3) * 320, (index // 3) * 225))
    sheet.save(SHEET, quality=92)
    print(f"{OUT}\n{len(frames)} frames; {len(frames) / FPS:.1f}s; {W}x{H}; {OUT.stat().st_size / 1048576:.2f} MiB")


if __name__ == "__main__":
    main()
