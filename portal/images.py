"""Make uploaded photos web-sized.

Phone photos are 3-5 MB, often stored sideways with a "rotate me" note, and carry hidden
details such as the GPS location where they were taken. Each new event image and album photo
is turned upright, shrunk to at most MAX_SIDE pixels and saved again without those details.
"""

from io import BytesIO
from pathlib import PurePath

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_SIDE = 2000
JPEG_QUALITY = 85


def _has_transparency(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def shrink(file) -> ContentFile:
    """The photo upright, at most MAX_SIDE pixels on its long side, as JPEG (PNG if it has
    transparent parts), with no EXIF data. The colour profile is kept so colours don't shift."""
    file.seek(0)
    with Image.open(file) as original:
        if (
            original.format == "JPEG"
            and max(original.size) <= MAX_SIDE
            and not original.getexif()
            and not {"xmp", "photoshop", "comment"} & original.info.keys()  # other hidden data
        ):
            # Already web-sized with nothing hidden: saving again would only lose quality.
            file.seek(0)
            return ContentFile(file.read(), name=PurePath(file.name).name)
        keep_png = original.format == "PNG" and _has_transparency(original)
        icc_profile = original.info.get("icc_profile")
        image = ImageOps.exif_transpose(original)  # a new, upright copy
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    out = BytesIO()
    stem = PurePath(file.name).stem
    extra = {"icc_profile": icc_profile} if icc_profile else {}
    if keep_png:
        image.save(out, "PNG", optimize=True, **extra)
        name = f"{stem}.png"
    else:
        image.convert("RGB").save(
            out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True, **extra
        )
        name = f"{stem}.jpg"
    return ContentFile(out.getvalue(), name=name)


def shrink_new_upload(field_file):
    """The web-sized version of a file just chosen in a form, or the stored file unchanged."""
    if field_file and not field_file._committed:
        return shrink(field_file)
    return field_file
