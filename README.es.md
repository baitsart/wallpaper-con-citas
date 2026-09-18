# Wallpaper Manager con Citas

**Wallpaper Manager con Citas** es una aplicación gráfica desarrollada en Python y GTK3, diseñada para descargar automáticamente fondos de pantalla de alta calidad e integrar citas textuales inspiradoras sobre las imágenes.

Permite seleccionar autores para las citas, como **Prem Rawat**, **Sadhguru**, **Siva P. de PVH**, **Sri Sri Ravi Shankar** y **Otros autores (Búsqueda / Aleatorio)** que toma de todos los existentes en A-Z Quotes.

También ofrece una lista de tags para buscar imágenes a gusto del usuario.

El programa gestiona de forma transparente la descarga desde fuentes externas como **Wallhaven** y **Picsum**, aplicando un renderizado estilizado del texto sobre la imagen antes de establecer el resultado como fondo de escritorio.

## Características

* **Interfaz nativa GTK3:** Integración visual fluida con entornos de escritorio basados en GNOME/XFCE/MATE.
* **Colección de citas customizable:** Selección de textos por autor o categoría temática.
* **Búsqueda de imágenes por tags:** Permite elegir los tags utilizados para buscar los fondos de pantalla.
* **Integración en el sistema:** Despliega su configuración y scripts directamente en `~/.wallpaper_manager` y `~/.config/wallpaper_manager`.
* **Reemplazo automático:** Reemplaza y entra en conflicto directo con las versiones heredadas de `wallpaper-manager` para evitar problemas de dependencias.

## Instalación desde PPA

```bash```
sudo add-apt-repository ppa:baitsart/wallpaper-con-citas
sudo apt update
sudo apt install wallpaper-con-citas
```

---

[🇬🇧 English](README.en.md)

