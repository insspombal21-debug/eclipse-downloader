from PIL import Image, ImageDraw

S = 256
image = Image.new("RGBA", (S, S), "#0b0d17")
draw = ImageDraw.Draw(image)

# Neon eclipse: blue outer glow, purple ring and pink highlight.
for box, color, width in (
    ((24, 24, 232, 232), "#2563eb", 14),
    ((38, 38, 218, 218), "#7c3aed", 18),
    ((52, 52, 204, 204), "#ec4899", 12),
):
    draw.ellipse(box, outline=color, width=width)

# Dark moon overlap produces the eclipse crescent.
draw.ellipse((92, 35, 226, 169), fill="#0b0d17")

# White download arrow at the center.
draw.rounded_rectangle((116, 75, 140, 159), radius=10, fill="white")
draw.polygon(((79, 137), (177, 137), (128, 194)), fill="white")

image.save("app.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
