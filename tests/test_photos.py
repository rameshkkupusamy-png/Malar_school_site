"""Photos are turned upright, shrunk and stripped of hidden details (such as GPS) on upload."""

from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import ExifTags, Image

from portal.images import MAX_SIDE, shrink
from portal.models import Album, Event, Photo


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def photo_bytes(size=(4000, 3000), fmt="JPEG", mode="RGB", exif=None):
    image = Image.new(mode, size, (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30))
    out = BytesIO()
    image.save(out, fmt, **({"exif": exif} if exif is not None else {}))
    return out.getvalue()


def upload(name, data):
    return SimpleUploadedFile(name, data)


def opened(content):
    data = content.read() if hasattr(content, "read") else content
    return Image.open(BytesIO(data))


def test_large_photo_becomes_a_2000_pixel_jpeg():
    result = shrink(upload("IMG_0001.JPG", photo_bytes((4000, 3000))))

    image = opened(result)
    assert image.format == "JPEG"
    assert image.size == (MAX_SIDE, 1500)
    assert result.name == "IMG_0001.jpg"


def test_small_photo_keeps_its_size():
    image = opened(shrink(upload("small.jpg", photo_bytes((800, 600)))))
    assert image.size == (800, 600)


def test_sideways_phone_photo_is_turned_upright():
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6  # "rotate 90° clockwise to view"

    image = opened(shrink(upload("sideways.jpg", photo_bytes((400, 200), exif=exif.tobytes()))))

    assert image.size == (200, 400)
    assert ExifTags.Base.Orientation not in image.getexif()


def test_gps_location_is_removed():
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Phone"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (2.0, 58.0, 30.0)
    original = Image.open(BytesIO(photo_bytes((400, 300), exif=exif.tobytes())))
    assert original.getexif().get_ifd(ExifTags.IFD.GPSInfo)  # the test photo really has GPS

    image = opened(shrink(upload("gps.jpg", photo_bytes((400, 300), exif=exif.tobytes()))))

    assert not image.getexif().get_ifd(ExifTags.IFD.GPSInfo)
    assert not image.getexif()


def test_iphone_heic_photo_becomes_jpeg():
    result = shrink(upload("IMG_1234.HEIC", photo_bytes((3024, 4032), fmt="HEIF")))

    image = opened(result)
    assert image.format == "JPEG"
    assert image.size == (1500, MAX_SIDE)
    assert result.name == "IMG_1234.jpg"


def test_transparent_png_stays_png():
    result = shrink(upload("logo.png", photo_bytes((3000, 1000), fmt="PNG", mode="RGBA")))

    image = opened(result)
    assert image.format == "PNG"
    assert image.mode == "RGBA"
    assert image.size == (MAX_SIDE, 667)
    assert result.name == "logo.png"


def test_album_photo_is_shrunk_when_saved(db, media):
    album = Album.objects.create(title="Sports day")
    photo = Photo.objects.create(album=album, image=upload("IMG_0001.JPG", photo_bytes()))

    assert photo.image.name.startswith("gallery/") and photo.image.name.endswith(".jpg")
    assert Image.open(photo.image.path).size == (MAX_SIDE, 1500)


def test_event_image_is_shrunk_when_saved(db):
    event = Event.objects.create(
        title="Sports day",
        starts_at=timezone.now(),
        image=upload("IMG_0002.HEIC", photo_bytes(fmt="HEIF")),
    )
    assert event.image.name.endswith(".jpg")
    assert Image.open(event.image.path).size == (MAX_SIDE, 1500)


def test_editing_a_caption_does_not_touch_the_photo(db):
    album = Album.objects.create(title="Sports day")
    photo = Photo.objects.create(album=album, image=upload("IMG_0001.JPG", photo_bytes()))
    path = Path(photo.image.path)
    before = path.stat().st_mtime_ns

    photo = Photo.objects.get(pk=photo.pk)
    photo.caption = "Relay race"
    photo.save()

    assert Photo.objects.get(pk=photo.pk).image.name == photo.image.name
    assert path.stat().st_mtime_ns == before


def test_admin_accepts_heic_photos_in_an_album(admin_client):
    response = admin_client.post(
        reverse("admin:portal_album_add"),
        {
            "title_ta": "விளையாட்டு நாள்",
            "is_published": "on",
            "photos-TOTAL_FORMS": "1",
            "photos-INITIAL_FORMS": "0",
            "photos-MIN_NUM_FORMS": "0",
            "photos-MAX_NUM_FORMS": "1000",
            "photos-0-image": upload("IMG_1234.HEIC", photo_bytes((3024, 4032), fmt="HEIF")),
            "photos-0-order": "0",
        },
    )

    assert response.status_code == 302, response.content.decode()[-3000:]
    photo = Photo.objects.get()
    assert photo.image.name.endswith(".jpg")
    assert Image.open(photo.image.path).size == (1500, MAX_SIDE)


def test_web_sized_jpeg_without_hidden_details_is_kept_as_is():
    data = photo_bytes((800, 600))

    result = shrink(upload("ready.jpg", data))

    assert result.read() == data
    assert result.name == "ready.jpg"


def test_web_sized_jpeg_with_xmp_location_is_still_cleaned():
    image = Image.new("RGB", (800, 600), (200, 30, 30))
    out = BytesIO()
    xmp = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><exif:GPSLatitude>2,58.5N</exif:GPSLatitude></x:xmpmeta>'
    image.save(out, "JPEG", xmp=xmp)
    assert "xmp" in Image.open(BytesIO(out.getvalue())).info

    result = opened(shrink(upload("xmp.jpg", out.getvalue())))

    assert "xmp" not in result.info
