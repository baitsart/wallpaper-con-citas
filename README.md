# Wallpaper Manager con Citas

[Español](#español) | [English](#english)

---

## Español

**Wallpaper Manager con Citas** es una aplicación gráfica desarrollada en Python y GTK3, diseñada para descargar automáticamente fondos de pantalla de alta calidad e integrar citas textuales inspiradoras sobre las imágenes.

Permite seleccionar autores para las citas, como **Prem Rawat**, **Sadhguru**, **Siva P. de PVH**, **Sri Sri Ravi Shankar** y **Otros autores (Búsqueda / Aleatorio)**, que toma de todos los existentes en A-Z Quotes.

También ofrece una lista de tags para buscar imágenes a gusto del usuario.

El programa gestiona de forma transparente la descarga desde fuentes externas como **Wallhaven** y **Picsum**, aplicando un renderizado estilizado del texto sobre la imagen antes de establecer el resultado como fondo de escritorio.

### Características

* **Interfaz nativa GTK3:** Integración visual fluida con entornos de escritorio basados en GNOME/XFCE/MATE.
* **Colección de citas customizable:** Selección de textos por autor o categoría temática.
* **Búsqueda de imágenes por tags:** Permite elegir los tags utilizados para buscar los fondos de pantalla.
* **Integración en el sistema:** Despliega su configuración y scripts directamente en `~/.wallpaper_manager` y `~/.config/wallpaper_manager`.
* **Reemplazo automático:** Reemplaza y entra en conflicto directo con las versiones heredadas de `wallpaper-manager` para evitar problemas de dependencias.

### Instalación desde PPA

```bash```
sudo add-apt-repository ppa:baitsart/wallpaper-con-citas
sudo apt update
sudo apt install wallpaper-con-citas
```


---

## English

**Wallpaper Manager con Citas** is a graphical application developed in Python and GTK3, designed to automatically download high-quality wallpapers and overlay stylized quotes directly onto the image.

It offers a selection of authors for the quotes—such as **Prem Rawat**, **Sadhguru**, **Siva P. from PVH**, **Sri Sri Ravi Shankar**, and **Other authors (Search / Random)**, using quotes from authors available on A-Z Quotes.

As well has a list of tags for searching images according to the user's preference.

The application manages downloads from external platforms like **Wallhaven** and **Picsum**, applying clean typography rendering over the image before updating your desktop wallpaper.

### Key Features

* **Native GTK3 Interface:** Seamless integration with GNOME, XFCE, and MATE desktop environments.
* **Custom Quote Collection:** Includes configurable quotes sorted by author and topic.
* **Image Search by Tags:** Choose the tags used to search for wallpapers.
* **System Integration:** Automatically deploys configuration and files under `~/.wallpaper_manager` and `~/.config/wallpaper_manager`.
* **Clean Conflict Rule:** Replaces and explicitly conflicts with legacy builds of `wallpaper-manager` to ensure clean updates.

### Installation via PPA

```bash```
sudo add-apt-repository ppa:baitsart/wallpaper-con-citas
sudo apt update
sudo apt install wallpaper-con-citas
```


---
