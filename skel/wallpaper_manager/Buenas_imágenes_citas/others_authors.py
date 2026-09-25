#!/usr/bin/env python3

import json
from pathlib import Path
import random
import re
import sys
from html import unescape
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://www.azquotes.com"


def descargar(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def buscar_autor(nombre):
    autor_buscado = nombre.strip().lower()
    if not autor_buscado:
        raise RuntimeError("El nombre del autor está vacío.")

    rutas_json = [
        Path("/usr/share/wallpaper_manager/Buenas_imágenes_citas/autores_completos_db.json"),
        Path(__file__).parent / "autores_completos_db.json"
    ]
    
    palabras_buscadas = [p for p in re.split(r'\W+', autor_buscado) if len(p) > 2]

    for json_path in rutas_json:
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    db_data = json.load(f)
                    
                    valores = db_data.values() if isinstance(db_data, dict) else db_data
                    
                    # 1. Búsqueda exacta ("exacto" o "nombre")
                    for entry in valores:
                        if not isinstance(entry, dict):
                            continue
                        n = entry.get("nombre", "").strip().lower()
                        e = entry.get("exacto", "").strip().lower()
                        if autor_buscado == n or autor_buscado == e:
                            url = entry.get("url", "")
                            if url:
                                if url.startswith("http"):
                                    return url.replace(BASE_URL, "")
                                return url
                    
                    # 2. Búsqueda flexible por palabras clave
                    if palabras_buscadas:
                        for entry in valores:
                            if not isinstance(entry, dict):
                                continue
                            n = entry.get("nombre", "").strip().lower()
                            e = entry.get("exacto", "").strip().lower()
                            
                            coincide = True
                            for p in palabras_buscadas:
                                if p not in n and p not in e:
                                    coincide = False
                                    break
                            if coincide:
                                url = entry.get("url", "")
                                if url:
                                    if url.startswith("http"):
                                        return url.replace(BASE_URL, "")
                                    return url
            except Exception as e:
                print(f"Aviso leyendo base de datos JSON: {e}", file=sys.stderr)

    # Respaldo web si no está en el JSON
    letra_inicial = re.sub(r'[^a-z]', '', autor_buscado)
    if not letra_inicial:
        raise RuntimeError("El nombre del autor no contiene letras válidas.")
    
    letra = letra_inicial[0]
    
    for pagina in range(1, 20):
        url_indice = f"{BASE_URL}/quotes/authors/{letra}/{pagina}" if pagina > 1 else f"{BASE_URL}/quotes/authors/{letra}/"
        try:
            html = descargar(url_indice)
        except Exception:
            break

        match_tabla = re.search(r'<table[^>]*class=["\'][^"\']*\btable\b[^"\']*["\'][^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
        if not match_tabla:
            continue

        contenido_tabla = match_tabla.group(1)
        enlaces = re.findall(r'href=["\'](/author/\d+-[^"\']+)["\'][^>]*>(.*?)</a>', contenido_tabla, re.IGNORECASE | re.DOTALL)
        
        if not enlaces:
            break

        for url_relativa, texto_html in enlaces:
            nombre_encontrado = re.sub(r'<[^>]+>', '', texto_html).strip().lower()
            nombre_encontrado_limpio = " ".join(nombre_encontrado.split())
            
            coincide = True
            for p in palabras_buscadas:
                raiz = p[:4] if len(p) >= 4 else p
                if raiz not in nombre_encontrado_limpio:
                    coincide = False
                    break
            
            if coincide:
                return url_relativa

    raise RuntimeError(f"No se encontró el autor: {nombre}")


def obtener_citas(url_autor):
    html = descargar(BASE_URL + url_autor)

    urls = re.findall(
        r'href=["\']([^"\']*/quote/\d+)["\']',
        html,
        re.IGNORECASE,
    )

    if not urls:
        urls = re.findall(
            r'href=["\'](/quote/\d+-[^"\']+)["\']',
            html,
            re.IGNORECASE,
        )

    urls = list(dict.fromkeys(urls))

    if not urls:
        raise RuntimeError("No se encontraron citas para este autor.")

    return urls


def limpiar_texto(texto):
    if not texto:
        return ""
    texto = unescape(texto)
    texto = " ".join(texto.split())
    texto = re.sub(r'^[“"\'\s]+|[”"\'\s]+$', '', texto)
    return texto.strip()


def obtener_cita(url):
    html = descargar(BASE_URL + url)

    patrones = [
        r'<a[^>]+class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</a>',
        r'<h1[^>]*>(.*?)</h1>',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
    ]

    texto = None
    for patron in patrones:
        match = re.search(patron, html, re.IGNORECASE | re.DOTALL)
        if match:
            candidato = re.sub(r"<[^>]+>", "", match.group(1))
            candidato = limpiar_texto(candidato)
            if candidato:
                texto = candidato
                break

    if not texto:
        raise RuntimeError(f"No se encontró el texto de la cita: {url}")

    match_id = re.search(r"/quote/(\d+)", url)
    if not match_id:
        raise RuntimeError(f"ID inválido: {url}")

    return match_id.group(1), texto


def main():
    if len(sys.argv) != 2:
        print(f"Uso: {sys.argv[0]} \"Nombre del autor\"", file=sys.stderr)
        sys.exit(1)

    autor = sys.argv[1]
    print(f"Buscando: {autor}", file=sys.stderr)

    try:
        url_autor = buscar_autor(autor)
        print(f"Página del autor: {BASE_URL + url_autor}", file=sys.stderr)

        citas = obtener_citas(url_autor)
        url_cita = random.choice(citas)

        quote_id, texto = obtener_cita(url_cita)

        print(f"[{quote_id}] {texto}")
        print(f"{BASE_URL}/quote/{quote_id}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
