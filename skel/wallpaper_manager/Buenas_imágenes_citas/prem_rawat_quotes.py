#!/usr/bin/env python3

import json
import random
import re
import sys
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

# ----------------------------------------------------------------------
# CAPTURA Y CONFIGURACIÓN DE IDIOMA
# ----------------------------------------------------------------------
IDIOMA = sys.argv[1].lower() if len(sys.argv) > 1 else "es"

IDIOMAS_MAP = {
    "es": {"lang_code": "es-ES", "prefix": "es"},
    "en": {"lang_code": "en-US", "prefix": "en"},
    "pt": {"lang_code": "pt-BR", "prefix": "pt"},
    "fr": {"lang_code": "fr-FR", "prefix": "fr"},
    "de": {"lang_code": "de-DE", "prefix": "de"},
    "it": {"lang_code": "it-IT", "prefix": "it"},
    "hi": {"lang_code": "hi-IN", "prefix": "hi"},
    "ja": {"lang_code": "ja-JP", "prefix": "ja"},
}

config_idioma = IDIOMAS_MAP.get(IDIOMA, {"lang_code": "en-US", "prefix": IDIOMA})
LANG_CODE = config_idioma["lang_code"]

BASE_DIR = Path(__file__).parent
BANCO_JSON_PATH = BASE_DIR / "banco.json"
LIMIT = 12
MAX_INTENTOS = 5


def limpiar_texto(raw_cita):
    if not raw_cita:
        return None
    texto = unescape(str(raw_cita))
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    match_firma = re.search(
        r"[\s–\-—]*Prem\s+Rawat(?:,\s*(.+))?$", texto, flags=re.IGNORECASE
    )
    if match_firma:
        texto = texto[: match_firma.start()].strip()

    texto = re.sub(r'^["“”’\']+|["“”’\']+$', "", texto).strip()
    texto = re.sub(r'["”’\']+\s*\.?$', "", texto).strip()
    if texto and not texto.endswith((".", "!", "?", "…")):
        texto += "."
    return texto if texto else None


def hacer_peticion(offset):
    url = f"https://api3.timelesstoday.io/v2/cms/products/{LANG_CODE}/group/2/{LIMIT}/{offset}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like"
            " Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://timelesstoday.tv/",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        # Fallback a en-US si la API regional específica no responde a tiempo
        if LANG_CODE != "en-US":
            try:
                fallback_url = f"https://api3.timelesstoday.io/v2/cms/products/en-US/group/2/{LIMIT}/{offset}"
                req_fb = Request(fallback_url, headers=headers)
                with urlopen(req_fb, timeout=5) as resp_fb:
                    return json.loads(resp_fb.read().decode("utf-8"))
            except Exception:
                pass
        return None


def main():
    # 1. SI ES ESPAÑOL: LECTURA ULTRA RÁPIDA DESDE EL BANCO LOCAL
    if IDIOMA == "es" and BANCO_JSON_PATH.exists():
        try:
            contenido = BANCO_JSON_PATH.read_text(encoding="utf-8")
            eventos = json.loads(contenido)
            if isinstance(eventos, list) and len(eventos) > 0:
                evento = random.choice(eventos)
                cita = (
                    evento.get("cita")
                    or evento.get("quote")
                    or evento.get("tt_one_line_quote")
                )
                texto_limpio = limpiar_texto(cita)
                if texto_limpio:
                    print(texto_limpio)
                    sys.exit(0)
        except Exception:
            pass

    # 2. PARA OTROS IDIOMAS (O SI FALLA EL BANCO LOCAL): CONSULTA DINÁMICA A LA API ONLINE
    primera_pagina = hacer_peticion(0)
    if primera_pagina:
        total_eventos = primera_pagina.get("filter", {}).get("count", 0)
        if total_eventos > 0:
            offsets_posibles = list(range(0, total_eventos, LIMIT))

            for _ in range(MAX_INTENTOS):
                offset_azar = random.choice(offsets_posibles)
                datos = (
                    primera_pagina
                    if offset_azar == 0
                    else hacer_peticion(offset_azar)
                )

                if not datos:
                    continue

                eventos = datos.get("data", [])
                if not eventos:
                    continue

                evento = random.choice(eventos)
                cita = limpiar_texto(evento.get("tt_one_line_quote"))
                if cita:
                    print(cita)
                    sys.exit(0)

    # 3. FALLBACK FINAL SI NO HAY CONEXIÓN WEB
    fallbacks = {
        "es": "La paz es posible en este mundo.",
        "en": "Peace is possible in this world.",
        "pt": "A paz é possível neste mundo.",
        "fr": "La paix est possible dans ce monde.",
        "de": "Frieden ist in dieser Welt möglich.",
        "it": "La pace è possibile in questo mondo.",
    }
    print(fallbacks.get(IDIOMA, "Peace is possible in this world."))
    sys.exit(0)


if __name__ == "__main__":
    main()
