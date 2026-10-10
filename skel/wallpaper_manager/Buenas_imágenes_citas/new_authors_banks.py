#!/usr/bin/env python3

import sys
import os
import json
import random
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

# Cargar la base de datos JSON de autores
with open("/usr/share/wallpaper_manager/Buenas_imágenes_citas/autores_completos_db.json", encoding="utf-8") as f:
    autores_db = json.load(f)

# Si no se pasa un argumento, elige un autor aleatorio del JSON
if len(sys.argv) > 1:
    AUTHOR = sys.argv[1]
    # Buscar el autor ingresado
    author_data = next((data for data in autores_db.values() if data.get("nombre", "").lower() == AUTHOR.lower()), None)
else:
    # Elegir un autor aleatorio del diccionario
    author_data = random.choice(list(autores_db.values()))
    AUTHOR = author_data.get("nombre", "Desconocido")
    print(f"Autor aleatorio seleccionado: {AUTHOR}")

# Obtener la URL limpia
url_raw = author_data.get("url", "") if author_data else ""
STRING_URL_NAME = url_raw.replace("/author/", "")

BASE_URL = f"https://www.azquotes.com/author/{STRING_URL_NAME}"

print(f"URL generada: {BASE_URL}")


def obtener_pagina(url):
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def extraer_citas(html):
    soup = BeautifulSoup(html, "html.parser")
    citas = []

    for enlace in soup.select(
        f'a.title[data-author="{AUTHOR}"]'
    ):
        quote_id = enlace.get("id", "").replace(
            "title_quote_link_", ""
        )

        texto = enlace.get_text(" ", strip=True)
        url = enlace.get("href")

        if texto and url:
            citas.append(
                {
                    "id": quote_id,
                    "texto": texto,
                    "url": url,
                }
            )

    return citas


def main():
    todas = []

    for pagina in range(1, 14):
        url = BASE_URL if pagina == 1 else f"{BASE_URL}?p={pagina}"
        print(f"Rastreando página {pagina}...")

        try:
            html = obtener_pagina(url)
        except Exception:
            break  # Detiene el bucle si una página da error o ya no existe
            
        citas = extraer_citas(html)
        if not citas:
            break  # Detiene el bucle si la página no tiene citas

        print(f"  Encontradas: {len(citas)}")
        todas.extend(citas)

    # Eliminar duplicados por ID
    unicas = list({cita["id"]: cita for cita in todas}.values())

    print()
    print(f"Total encontradas: {len(todas)}")
    print(f"Total únicas:      {len(unicas)}")
    print()

    # Definir la ruta de destino exacta (cambiando la extensión a .txt)
    carpeta_destino = "/usr/share/wallpaper_manager/Buenas_imágenes_citas/Quotes"
    os.makedirs(carpeta_destino, exist_ok=True)

    autor_limpio = AUTHOR.replace(" ", "_")
    ruta_archivo = os.path.join(carpeta_destino, f"banco_{autor_limpio}.txt")

    # Guardar las citas con el formato de texto original
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        for cita in unicas:
            f.write(f'[{cita["id"]}] {cita["texto"]}\n')
            f.write(f'{cita["url"]}\n\n')

    print(f"Archivo guardado en: {ruta_archivo}")


if __name__ == "__main__":
    main()
