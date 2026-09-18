# Wallpaper Manager con Citas

**Wallpaper Manager con Citas** is a graphical application developed in Python and GTK3, designed to automatically download high-quality wallpapers and overlay stylized quotes directly onto the image.

It offers a selection of authors for the quotes—such as **Prem Rawat**, **Sadhguru**, **Siva P. from PVH**, **Sri Sri Ravi Shankar**, and **Other authors (Search / Random)**, using quotes from authors available on A-Z Quotes.

As well has a list of tags for searching images according to the user's preference.

The application manages downloads from external platforms like **Wallhaven** and **Picsum**, applying clean typography rendering over the image before updating your desktop wallpaper.

## Key Features

* **Native GTK3 Interface:** Seamless integration with GNOME, XFCE, and MATE desktop environments.
* **Custom Quote Collection:** Includes configurable quotes sorted by author and topic.
* **Image Search by Tags:** Choose the tags used to search for wallpapers.
* **System Integration:** Automatically deploys configuration and files under `~/.wallpaper_manager` and `~/.config/wallpaper_manager`.
* **Clean Conflict Rule:** Replaces and explicitly conflicts with legacy builds of `wallpaper-manager` to ensure clean updates.

## Installation via PPA

```bash```
sudo add-apt-repository ppa:baitsart/wallpaper-con-citas
sudo apt update
sudo apt install wallpaper-con-citas
```

---

[🇪🇸 Español](README.es.md)

