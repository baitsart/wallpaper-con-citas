#!/usr/bin/env python3

import json
import os
import random
import re
import sys
from html import unescape
from urllib.request import Request, urlopen

# ----------------------------------------------------------------------
# CAPTURA Y CONFIGURACIÓN DE IDIOMA
# ----------------------------------------------------------------------
IDIOMA = sys.argv[1].lower() if len(sys.argv) > 1 else "es"

# Selección de endpoint y prefijo de URL según el idioma recibido
if IDIOMA == "en":
    LANG_CODE = "en-US"
    URL_PREFIX = "en"
else:
    LANG_CODE = "es-ES"
    URL_PREFIX = "es"

HISTORIAL_PATH = os.path.expanduser("~/.citas_prem_rawat.txt")
API_BASE = f"https://api3.timelesstoday.io/v2/cms/products/{LANG_CODE}/group/2/12"
LIMIT = 12
MAX_INTENTOS = 5


def hacer_peticion(offset):
    url = f"{API_BASE}/{offset}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like"
            " Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://timelesstoday.tv/",
        "Origin": "https://timelesstoday.tv",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def procesar_evento(evento):
    raw_cita = evento.get("tt_one_line_quote")
    if not raw_cita:
        return None, None, None

    # 1. Limpieza inicial de HTML y espacios
    texto = unescape(str(raw_cita))
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # 2. Extraer firma integrada si existe
    lugar_fecha = None
    match_firma = re.search(
        r"[\s–\-—]*Prem\s+Rawat(?:,\s*(.+))?$", texto, flags=re.IGNORECASE
    )

    if match_firma:
        texto = texto[: match_firma.start()].strip()
        if match_firma.group(1):
            lugar_fecha = match_firma.group(1).strip()

    # 3. Fallback al nombre del evento
    if not lugar_fecha:
        nombre_evento = evento.get("tt_name")
        if nombre_evento and nombre_evento.strip():
            lugar_fecha = nombre_evento.strip()

    # 4. Limpiar comillas basura
    texto = re.sub(r'^["“”’\']+|["“”’\']+$', "", texto).strip()
    texto = re.sub(r'["”’\']+\s*\.?$', "", texto).strip()

    if texto and not texto.endswith((".", "!", "?", "…")):
        texto += "."

    if not texto:
        return None, None, None

    if lugar_fecha:
        lugar_fecha = re.sub(r'^["“”’\']+|["“”’\']+$', "", lugar_fecha).strip().rstrip(".")

    # 5. Obtener URL real del evento
    uuid = evento.get("tt_media_uuid")
    
    if uuid:
        url_contenido = f"https://timelesstoday.tv/es/events/product/{uuid}"
    else:
        url_contenido = "https://timelesstoday.tv/es"
    
    return texto, lugar_fecha or "Desconocida", url_contenido


def es_duplicado(cita_texto):
    if not os.path.exists(HISTORIAL_PATH):
        return False
    with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
        historial = f.read()
        return cita_texto in historial


def guardar_en_historial(cita_texto, fecha_lugar):
    with open(HISTORIAL_PATH, "a", encoding="utf-8") as f:
        f.write(f"{cita_texto} | Origen: {fecha_lugar}\n")


def main():
    primera_pagina = hacer_peticion(0)
    if not primera_pagina:
        print("Error: No se pudo conectar con la API de TimelessToday.")
        sys.exit(1)

    total_eventos = primera_pagina.get("filter", {}).get("count", 0)
    if total_eventos == 0:
        print("Error: No se encontraron citas.")
        sys.exit(1)

    offsets_posibles = list(range(0, total_eventos, LIMIT))

    for _ in range(MAX_INTENTOS):
        offset_azar = random.choice(offsets_posibles)
        datos = primera_pagina if offset_azar == 0 else hacer_peticion(offset_azar)

        if not datos:
            continue

        eventos = datos.get("data", [])
        if not eventos:
            continue

        random.shuffle(eventos)

        for evento in eventos:
            cita, lugar_fecha, url_video = procesar_evento(evento)
            if cita and not es_duplicado(cita):
                guardar_en_historial(cita, lugar_fecha)

                # Salida formateada
                print(f"Cita: {cita}")
                print("Autor: Prem Rawat")
                print(f"Fecha: {lugar_fecha}")
                print(f"URL: {url_video}")
                sys.exit(0)

    print(f"Error: No se pudo obtener una cita válida tras {MAX_INTENTOS} intentos.")
    sys.exit(1)


if __name__ == "__main__":
    main()
