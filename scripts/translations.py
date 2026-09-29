"""Collect the site's words for translation, and build the files Django reads.

Django's own `makemessages` / `compilemessages` need GNU gettext, which isn't installed on
Windows by default. This does the same job with Babel (pure Python):

    python scripts/translations.py update    # find new/changed text, update locale/*/django.po
    python scripts/translations.py compile   # turn the .po files into the .mo files Django uses

Translators edit locale/ta/LC_MESSAGES/django.po (Tamil) and locale/ms/LC_MESSAGES/django.po
(Malay): each `msgid` is the English text, and its `msgstr` is the translation.
"""

import io
import sys
from pathlib import Path

import django
from babel.messages.catalog import Catalog
from babel.messages.extract import extract_python
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ["ta", "ms"]
KEYWORDS = {
    "_": None,
    "gettext": None,
    "gettext_lazy": None,
    "gettext_noop": None,
    "ngettext": (1, 2),
    "ngettext_lazy": (1, 2),
    "pgettext_lazy": ((1, "c"), 2),
    "pgettext": ((1, "c"), 2),
    "npgettext": ((1, "c"), 2, 3),
}


def source_files():
    app = ROOT / "portal"
    for path in sorted(app.rglob("*")):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix in {".py", ".html", ".txt"} and path.is_file():
            yield path


def extract() -> Catalog:
    from django.utils.translation.template import templatize

    catalog = Catalog(project="school-portal", charset="utf-8")
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        if path.suffix != ".py":
            text = templatize(text, origin=str(path))
        found = extract_python(io.BytesIO(text.encode("utf-8")), KEYWORDS, [], {})
        for lineno, function, message, _comments in found:
            # Babel returns the call's arguments; keep the context and the text parts only.
            context = None
            if function in ("pgettext", "pgettext_lazy", "npgettext"):
                context, message = message[0], message[1:]
            if isinstance(message, tuple):
                message = message[:2] if "ngettext" in function else message[0]
            if not message or (isinstance(message, tuple) and not all(message)):
                continue
            location = (path.relative_to(ROOT).as_posix(), lineno)
            catalog.add(message, locations=[location], context=context)
    return catalog


def update() -> None:
    template = extract()
    for language in LANGUAGES:
        po_path = ROOT / "locale" / language / "LC_MESSAGES" / "django.po"
        po_path.parent.mkdir(parents=True, exist_ok=True)
        if po_path.exists():
            with po_path.open("rb") as handle:
                catalog = read_po(handle, locale=language)
            catalog.update(template, no_fuzzy_matching=True)
        else:
            catalog = Catalog(locale=language, project="school-portal", charset="utf-8")
            catalog.update(template, no_fuzzy_matching=True)
        with po_path.open("wb") as handle:
            write_po(handle, catalog, width=100, omit_header=False, ignore_obsolete=True)
        missing = [m.id for m in catalog if m.id and not m.string]
        print(f"{language}: {len(catalog)} phrases, {len(missing)} not translated yet")


def compile_all() -> None:
    for language in LANGUAGES:
        po_path = ROOT / "locale" / language / "LC_MESSAGES" / "django.po"
        with po_path.open("rb") as handle:
            catalog = read_po(handle, locale=language)
        with po_path.with_suffix(".mo").open("wb") as handle:
            write_mo(handle, catalog, use_fuzzy=False)
        print(f"{language}: compiled {po_path.with_suffix('.mo').relative_to(ROOT)}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "school_portal.settings")
    django.setup()
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "update":
        update()
    elif command == "compile":
        compile_all()
    else:
        print(__doc__)
        sys.exit(1)
