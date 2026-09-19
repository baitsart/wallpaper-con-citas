#!/usr/bin/env python3

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
    letra_inicial = re.sub(r'[^a-z]', '', nombre.lower())
    if not letra_inicial:
        raise RuntimeError("El nombre del autor no contiene letras válidas.")
    
    letra = letra_inicial[0]
    palabras_buscadas = [p for p in re.split(r'\W+', nombre.lower()) if len(p) > 2]
    
    # Recorrer páginas del abecedario
    for pagina in range(1, 20):
        url_indice = f"{BASE_URL}/quotes/authors/{letra}/{pagina}" if pagina > 1 else f"{BASE_URL}/quotes/authors/{letra}/"
        
        try:
            html = descargar(url_indice)
        except Exception:
            break

        # Aislamiento estricto: Extraer SOLO el contenido de la tabla principal
        match_tabla = re.search(r'<table[^>]*class=["\'][^"\']*\btable\b[^"\']*["\'][^>]*>(.*?)</table>', html, re.IGNORECASE | re.DOTALL)
        if not match_tabla:
            continue

        contenido_tabla = match_tabla.group(1)

        # Extraer enlaces de autores dentro de la tabla
        enlaces = re.findall(r'href=["\'](/author/\d+-[^"\']+)["\'][^>]*>(.*?)</a>', contenido_tabla, re.IGNORECASE | re.DOTALL)
        
        if not enlaces:
            break

        for url_relativa, texto_html in enlaces:
            nombre_encontrado = re.sub(r'<[^>]+>', '', texto_html).strip().lower()
            nombre_encontrado_limpio = " ".join(nombre_encontrado.split())
            
            # Verificar si las palabras clave principales están en el nombre encontrado
            # Permite tolerar errores como "Gandi" -> "Gandhi"
            coincide = True
            for p in palabras_buscadas:
                # Comprobación flexible (subcadena de al menos 4 caracteres si la palabra es larga)
                raiz = p[:4] if len(p) >= 4 else p
                if raiz not in nombre_encontrado_limpio:
                    coincide = False
                    break
            
            if coincide:
                return url_relativa

    # Intento directo de slug si falla el índice (ej: mahatma_gandhi)
    slug = re.sub(r'[^a-z0-9]+', '_', nombre.lower()).strip('_')
    try:
        html_directo = descargar(f"{BASE_URL}/author/{slug}")
        match_canonical = re.search(r'href=["\'](/author/\d+-[^"\']+)["\']', html_directo, re.IGNORECASE)
        if match_canonical:
            return match_canonical.group(1)
    except Exception:
        pass

    raise RuntimeError(f"No se encontró el autor: {nombre}")


def obtener_citas(url_autor):
    html = descargar(BASE_URL + url_autor)

    urls = re.findall(
        r'href=["\']([^"\']*/quote/\d+)["\']',
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
