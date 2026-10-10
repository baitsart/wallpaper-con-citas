#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

def obtener_directorio_imagenes():
    try:
        res = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, check=True)
        base = Path(res.stdout.strip())
        if base.exists():
            return base
    except Exception:
        pass
    return Path.home() / "Imágenes"

# 1. Definimos correctamente la carpeta de imágenes del usuario (~/Imágenes)
PICTURES_DIR = obtener_directorio_imagenes()

# 2. Rutas dinámicas universales basadas en el sistema del usuario
SAVE_DIR = PICTURES_DIR / "wallpaper manager_citas"
AUTO_DIR = SAVE_DIR / "Generadas"

# Asegurar que existan
SAVE_DIR.mkdir(parents=True, exist_ok=True)
AUTO_DIR.mkdir(parents=True, exist_ok=True)

# 3. Directorios base internos para configs y fuentes
BASE_DIR = Path("/usr/share/wallpaper_manager")
IMAGENES_QUOTES_DIR = BASE_DIR / "Buenas_imágenes_citas"

CONFIG_CICLAR_PATH = IMAGENES_QUOTES_DIR / "ciclar_render.config"
FONTE_DEFAULT_FALLBACK = IMAGENES_QUOTES_DIR / "fonts" / "C059-BdIta.t1"
TEXT_SHADOW = True

def cargar_parametros_render():
    params = {
        "font_path": str(FONTE_DEFAULT_FALLBACK),
        "font_size": 42,
        "offset_x": 0,
        "offset_y": 0,
        "width_ratio": 0.7,
        "align_mode": "center",
        "draw_background": True
    }
    
    if CONFIG_CICLAR_PATH.exists():
        try:
            for linea in CONFIG_CICLAR_PATH.read_text(encoding="utf-8").splitlines():
                if "=" in linea:
                    k, v = linea.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip().strip('"').strip("'")
                    
                    if k == "font_path" and os.path.exists(v):
                        params["font_path"] = v
                    elif k == "font_size":
                        params["font_size"] = int(v)
                    elif k == "offset_x":
                        params["offset_x"] = int(v)
                    elif k == "offset_y":
                        params["offset_y"] = int(v)
                    elif k == "width_ratio":
                        params["width_ratio"] = float(v)
                    elif k == "align_mode":
                        params["align_mode"] = v
                    elif k == "draw_background":
                        params["draw_background"] = v.lower() in ["true", "1", "si", "sí"]
        except Exception as e:
            print(f"Error leyendo parámetros de render en config: {e}")
            
    return params

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def generate_composite_image(bg_path, quote_text, author_text, config):
    bg_image = Image.open(bg_path).convert("RGB")
    orig_w, orig_h = bg_image.size
    
    # Calcular la nueva altura manteniendo estrictamente la relación de aspecto original basada en un ancho de 1920
    target_width = 1920
    target_height = int(orig_h * (target_width / orig_w))
    
    # Redimensionar la imagen de forma proporcional
    bg_image = bg_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    canvas_w, canvas_h = bg_image.size

    font_path = config.get("font_path", str(FONTE_DEFAULT_FALLBACK))
    font_size = config.get("font_size", 42)
    offset_x = config.get("offset_x", 0)
    offset_y = config.get("offset_y", 0)
    align_mode = config.get("align_mode", "center")
    width_ratio = config.get("width_ratio", 0.7)
    draw_background = config.get("draw_background", True)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path and os.path.exists(font_path) else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    dummy = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy)

    box_w = int(canvas_w * width_ratio)
    max_text_w = box_w - 40

    if quote_text and quote_text.strip():
        clean_quote = quote_text.strip("“”).")
        if not clean_quote.endswith(('.', '!', '?')):
            clean_quote = clean_quote + "."
        lines_quote = wrap_text(f"“{clean_quote}”", font, max_text_w, draw_dummy)
    else:
        lines_quote = []

    author_line = f"— {author_text}" if author_text and author_text.strip() else ""
    author_lines_wrapped = []
    if author_line:
        author_lines_wrapped = wrap_text(author_line, font, max_text_w, draw_dummy)

    all_lines = lines_quote + author_lines_wrapped

    if all_lines:
        bbox = draw_dummy.textbbox((0, 0), "Ag", font=font)
        line_h = bbox[3] - bbox[1] + 8
        total_lines_count = len(lines_quote) + len(author_lines_wrapped)
        box_h = (total_lines_count * line_h) + 50

        margin = 20
        hpos = max(margin, min(margin + offset_x, canvas_w - box_w - margin))
        vpos = max(margin, min(margin + offset_y, canvas_h - box_h - margin))

        if draw_background:
            small = bg_image.resize((1, 1), Image.Resampling.LANCZOS).convert("RGB")
            pixel = small.getpixel((0, 0))
            draw_overlay.rectangle([hpos, vpos, hpos + box_w, vpos + box_h], fill=(pixel[0], pixel[1], pixel[2], 150))
    else:
        hpos, vpos, box_h, line_h = 0, 0, 0, 0

    result = Image.alpha_composite(bg_image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(result)

    def calcular_x(line_text, align_type):
        line_box = draw.textbbox((0, 0), line_text, font=font)
        line_w = line_box[2] - line_box[0]
        if align_type == "left":
            return hpos + 20
        elif align_type == "right":
            return hpos + box_w - line_w - 20
        else:
            return hpos + (box_w - line_w) // 2

    if align_mode == "left":
        q_align, a_align = "left", "left"
    elif align_mode == "right":
        q_align, a_align = "right", "right"
    elif align_mode == "q_left_a_right":
        q_align, a_align = "left", "right"
    elif align_mode == "q_right_a_left":
        q_align, a_align = "right", "left"
    else:
        q_align, a_align = "center", "center"

    text_y = vpos + 25
    min_top_y = vpos + 20
    if text_y < min_top_y:
        text_y = min_top_y

    for line in lines_quote:
        text_x = calcular_x(line, q_align)
        if TEXT_SHADOW:  
            draw.text((text_x + 2, text_y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))
        text_y += line_h

    if author_line:
        for author_l in author_lines_wrapped:
            author_w = draw_dummy.textbbox((0, 0), author_l, font=font)[2] - draw_dummy.textbbox((0, 0), author_l, font=font)[0]
            
            if a_align == "right":
                author_draw_x = hpos + box_w - author_w - 20
            elif a_align == "left":
                author_draw_x = hpos + 20
            else: 
                author_draw_x = hpos + (box_w - author_w) // 2

            if TEXT_SHADOW:
                draw.text((int(author_draw_x + 2), int(text_y + 2)), author_l, font=font, fill=(0, 0, 0, 180))
            draw.text((int(author_draw_x), int(text_y)), author_l, font=font, fill=(255, 255, 255, 255))
            text_y += line_h

    img_final = result.convert("RGB")
    
    metadata_texto = f"Cita: {quote_text}\nAutor: {author_text}\n"
    exif = img_final.getexif()
    exif[270] = metadata_texto
    img_final.info["exif"] = exif.tobytes()

    return img_final

def main():
    valores_path = IMAGENES_QUOTES_DIR / "valores_del_render"
    if not valores_path.exists():
        print("No se encontró el archivo valores_del_render.")
        return

    cita = ""
    autor = ""
    imagen_path = ""

    for linea in valores_path.read_text(encoding="utf-8").splitlines():
        if linea.startswith("Cita:"):
            cita = linea.replace("Cita:", "", 1).strip()
        elif linea.startswith("Autor:"):
            autor = linea.replace("Autor:", "", 1).strip()
        elif linea.startswith("Imagen:"):
            imagen_path = linea.replace("Imagen:", "", 1).strip()

    if not imagen_path or not os.path.exists(imagen_path):
        print(f"Imagen no válida: {imagen_path}")
        return

    render_config = cargar_parametros_render()
    
    img_compuesta = generate_composite_image(
        bg_path=imagen_path,
        quote_text=cita,
        author_text=autor,
        config=render_config
    )

    # Directorio de guardado automático usando AUTO_DIR (en ~/Imágenes/wallpaper manager_citas/Generadas)
    AUTO_DIR.mkdir(parents=True, exist_ok=True)
    nombre_salida = AUTO_DIR / f"render_quote_{Path(imagen_path).name}"
    
    if "exif" in img_compuesta.info:
        img_compuesta.save(nombre_salida, quality=100, exif=img_compuesta.info["exif"])
    else:
        img_compuesta.save(nombre_salida, quality=100)
    print(f"Imagen renderizada y guardada en: {nombre_salida}")

if __name__ == "__main__":
    main()
