"""Parents can put the site on their phone's home screen with the school crest as its icon."""

import json

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse
from PIL import Image


@pytest.mark.django_db
def test_manifest_describes_the_school_app(client, settings):
    settings.SCHOOL_NAME = "SJK (T) Ladang Semenyih"
    settings.SCHOOL_SHORT_NAME = "SJKT Semenyih"

    response = client.get(reverse("portal:manifest"))

    assert response["Content-Type"] == "application/manifest+json"
    manifest = json.loads(response.content)
    assert manifest["name"] == "SJK (T) Ladang Semenyih"
    assert manifest["short_name"] == "SJKT Semenyih"
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#14295F"
    assert manifest["background_color"] == "#FFFFFF"
    sizes = {(icon["sizes"], icon.get("purpose", "any")) for icon in manifest["icons"]}
    assert sizes == {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")}


@pytest.mark.parametrize(
    ("name", "size"),
    [("icon-192.png", 192), ("icon-512.png", 512), ("icon-maskable-512.png", 512)],
)
def test_icons_exist_and_are_square(name, size):
    path = finders.find(f"portal/{name}")
    assert path, f"portal/{name} is missing"
    with Image.open(path) as icon:
        assert icon.size == (size, size)
        assert icon.mode == "RGB"  # no transparency: home screens show it on any colour


def test_manifest_icon_paths_point_at_real_files(client, db):
    manifest = json.loads(client.get(reverse("portal:manifest")).content)
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/static/")
        relative = icon["src"].split("/static/", 1)[1]
        assert finders.find(relative), icon["src"]


@pytest.mark.django_db
def test_every_page_links_to_the_manifest(client, settings):
    settings.SCHOOL_SHORT_NAME = "SJKT Semenyih"

    html = client.get(reverse("portal:home")).content.decode()

    assert f'<link rel="manifest" href="{reverse("portal:manifest")}">' in html
    assert '<meta name="theme-color" content="#14295F">' in html
    assert '<meta name="apple-mobile-web-app-title" content="SJKT Semenyih">' in html
