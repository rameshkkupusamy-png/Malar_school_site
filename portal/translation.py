"""Text staff can write in Tamil, Malay and English (option B: fill in at least one).

django-modeltranslation adds title_ta / title_ms / title_en (and so on) columns. Reading
`event.title` gives the visitor's language, or the first other version that exists
(MODELTRANSLATION_FALLBACK_LANGUAGES). No language is required on its own; the models'
clean() methods require at least one title.
"""

from modeltranslation.translator import TranslationOptions, register

from .models import Album, Announcement, Document, Event, Photo, SchoolContact, UrgentNotice


class AnyLanguage(TranslationOptions):
    required_languages = ()
    fallback_undefined = ""


@register(Event)
class EventTranslation(AnyLanguage):
    fields = ("title", "description", "location")


@register(Announcement)
class AnnouncementTranslation(AnyLanguage):
    fields = ("title", "body")


@register(Album)
class AlbumTranslation(AnyLanguage):
    fields = ("title", "description")


@register(Photo)
class PhotoTranslation(AnyLanguage):
    fields = ("caption",)


@register(Document)
class DocumentTranslation(AnyLanguage):
    fields = ("title", "note")


@register(SchoolContact)
class SchoolContactTranslation(AnyLanguage):
    fields = ("hours",)


@register(UrgentNotice)
class UrgentNoticeTranslation(AnyLanguage):
    fields = ("message",)
