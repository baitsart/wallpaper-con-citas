#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta
from html import unescape
import random
import os
import sys
import re

# --- Capturar e identificar Idioma ---
IDIOMA = sys.argv[1].lower() if len(sys.argv) > 1 else "es"

# Mapeo de prefijos permitidos para la URL de Sadhguru
# Si es 'en', la estructura oficial no suele llevar prefijo o usa raíz, pero manejamos la ruta estándar.
IDIOMAS_SADHGURU = {
    "es": "es",
    "ar": "ar",
    "bn": "bn",
    "en": "en",
    "fr": "fr",
    "de": "de",
    "gu": "gu",
    "hi": "hi",
    "id": "id",
    "it": "it",
    "ja": "ja",
    "lt": "lt",
    "fa": "fa",
    "pt": "pt",
    "ro": "ro",
    "ru": "ru",
    "sk": "sk",
    "th": "th",
    "uk": "uk"
}

# Construcción dinámica del prefijo (ej: "/es/", "/pt/", etc.)
# Para inglés, la web de Isha suele aceptar la ruta vacía o /en/ según el enrutamiento.
if IDIOMA in IDIOMAS_SADHGURU:
    if IDIOMA == "en":
        PREFIX_LANG = "" 
    else:
        PREFIX_LANG = f"{IDIOMA}/"
else:
    PREFIX_LANG = "es/"

MAX_INTENTOS = 5

def obtener_fecha_aleatoria():
    start_date = datetime(2022, 1, 1)
    end_date = datetime.now()
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)
    random_date = start_date + timedelta(days=random_days)
    return random_date.strftime("%B-%d-%Y").lower()

def extraer_cita(html):
    try:
        match_next = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match_next:
            json_puro = match_next.group(1)
            candidatos = re.findall(r'"(?:text|body|quote_text|description|content)":\s*"([^"]+)"', json_puro)
            
            for texto in candidatos:
                texto_limpio = texto.strip()
                if re.match(r'https?://', texto_limpio) or len(texto_limpio) < 20:
                    continue
                
                texto_limpio = unescape(texto_limpio)
                try:
                    texto_limpio = texto_limpio.encode('utf-8').decode('unicode-escape')
                    try:
                        texto_limpio = texto_limpio.encode('latin-1').decode('utf-8')
                    except Exception:
                        pass
                except Exception:
                    pass
                
                texto_limpio = unescape(texto_limpio)
                texto_limpio = re.sub(r'Sadhguru Quotes\s*[-–—:]\s*', '', texto_limpio, flags=re.IGNORECASE).strip()
                return texto_limpio

        match = re.search(r'<meta name="description" content="([^"]+)"', html)
        if match:
            texto = unescape(match.group(1))
            texto = re.sub(r'Sadhguru Quotes\s*[-–—:]\s*', '', texto, flags=re.IGNORECASE).strip()
            texto = re.sub(r'\.\.\.$', '', texto).strip()
            return texto

    except Exception:
        return None
    return None

def main():
    for intento in range(1, MAX_INTENTOS + 1):
        fecha = obtener_fecha_aleatoria()
        url = f"https://isha.sadhguru.org/{PREFIX_LANG}wisdom/quotes/date/{fecha}".replace("//", "/")
        # Corrección por si el prefijo queda vacío y deja doble barra al inicio tras el dominio
        url = url.replace("https:/isha", "https://isha")
        
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if response.status_code == 200:
                response.encoding = "utf-8"
                cita = extraer_cita(response.text)
                
                if cita:
                    print(f"Cita: {cita}")
                    print("Autor: Sadhguru")
                    print(f"Fecha: {fecha}")
                    print(f"URL: {url}")
                    sys.exit(0)
        except Exception:
            pass

    print(f"Error: No se pudo obtener una cita válida tras {MAX_INTENTOS} intentos.")
    sys.exit(1)

if __name__ == "__main__":
    main()
