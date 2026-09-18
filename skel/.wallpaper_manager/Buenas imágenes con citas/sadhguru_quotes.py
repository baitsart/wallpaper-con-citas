#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta
from html import unescape
import random
import os
import sys
import re

# --- Capturar Idioma ---
IDIOMA = sys.argv[1] if len(sys.argv) > 1 else "es"
PREFIX_LANG = "es/" if IDIOMA.lower() == "es" else ""

HISTORIAL_PATH = os.path.expanduser("~/.citas_sadhguru.txt")
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
                texto_limpio = texto_limpio.replace("Sadhguru Quotes - ", "").strip()
                return texto_limpio

        match = re.search(r'<meta name="description" content="([^"]+)"', html)
        if match:
            texto = unescape(match.group(1))
            texto = texto.replace(" - Sadhguru", "").replace("Sadhguru Quotes - ", "").strip()
            texto = re.sub(r'\.\.\.$', '', texto).strip()
            return texto

    except Exception:
        return None
    return None

def es_duplicado(cita_texto):
    if not os.path.exists(HISTORIAL_PATH):
        return False
    with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
        historial = f.read()
        return cita_texto in historial

def guardar_en_historial(cita_texto, fecha):
    with open(HISTORIAL_PATH, "a", encoding="utf-8") as f:
        f.write(f"{cita_texto} | Fecha origen: {fecha}\n")

def main():
    for intento in range(1, MAX_INTENTOS + 1):
        fecha = obtener_fecha_aleatoria()
        url = f"https://isha.sadhguru.org/{PREFIX_LANG}wisdom/quotes/date/{fecha}"
        
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if response.status_code == 200:
                response.encoding = "utf-8"
                cita = extraer_cita(response.text)
                
                if cita and not es_duplicado(cita):
                    guardar_en_historial(cita, fecha)
                    
                    print(f"Cita: {cita}")
                    print("Autor: Sadhguru")
                    print(f"Fecha: {fecha}")
                    sys.exit(0)
        except Exception:
            pass

    print(f"Error: No se pudo obtener una cita válida tras {MAX_INTENTOS} intentos.")
    sys.exit(1)

if __name__ == "__main__":
    main()
