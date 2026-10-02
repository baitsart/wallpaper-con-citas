#!/usr/bin/env python3

import sys
import json
import time
import urllib.parse
import urllib.request

def traducir_texto(texto, idioma_destino="es"):
    url_base = "https://translate.googleapis.com/translate_a/single"
    parametros = {
        "client": "dict-chrome-ex",
        "sl": "auto",
        "tl": idioma_destino,
        "dt": "t",
        "q": texto,
    }

    url = f"{url_base}?{urllib.parse.urlencode(parametros)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0"
    }

    for intento in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                respuesta_json = json.loads(response.read().decode("utf-8"))
                texto_traducido = "".join(
                    [item[0] for item in respuesta_json[0] if item[0]]
                )
                return texto_traducido
        except urllib.error.HTTPError as e:
            if e.code == 429:
                tiempo_espera = (intento + 1) * 4
                print(f"  [!] IP limitada temporalmente (429). Reintentando en {tiempo_espera}s...")
                time.sleep(tiempo_espera)
            else:
                print(f"  [!] Error HTTP {e.code}")
                break
        except Exception as e:
            print(f"  [!] Error de red: {e}")
            break

    return texto


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 auto-translate.py 'Texto o archivo' [idioma_destino]")
        print("Ejemplo: python3 auto-translate.py 'we are the world' fr")
        return

    entrada_usuario = sys.argv[1]
    # Si pasas un segundo argumento, lo usa como idioma; si no, por defecto usa "es"
    idioma_destino = sys.argv[2] if len(sys.argv) > 2 else "es"

    if entrada_usuario.endswith(".txt") or "/" in entrada_usuario:
        try:
            with open(entrada_usuario, "r", encoding="utf-8") as f:
                contenido = f.read()
            citas = [c.strip() for c in contenido.split("\n\n") if c.strip()]
            print(f"Procesando archivo '{entrada_usuario}' a [{idioma_destino}] ({len(citas)} bloques)...")
            
            resultados = []
            for i, cita in enumerate(citas, 1):
                print(f"Traduciendo bloque {i}/{len(citas)}...")
                traducida = traducir_texto(cita, idioma_destino)
                resultados.append(f"--- Cita {i} ---\n{traducida}\n")
                time.sleep(3)

            archivo_salida = f"traducido_{idioma_destino}_" + entrada_usuario.split('/')[-1]
            with open(archivo_salida, "w", encoding="utf-8") as f:
                f.write("\n".join(resultados))
            print(f"\n¡Listo! Guardado en '{archivo_salida}'.")

        except FileNotFoundError:
            print(f"[!] No se encontró el archivo: {entrada_usuario}")
    else:
        print(f"Traduciendo al [{idioma_destino}]...")
        resultado = traducir_texto(entrada_usuario, idioma_destino)
        print(f"\nOriginal:  {entrada_usuario}")
        print(f"Destino ({idioma_destino}): {resultado}")


if __name__ == "__main__":
    main()
