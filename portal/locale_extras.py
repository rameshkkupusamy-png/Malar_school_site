"""Date and time words that Django's own Tamil and Malay translations are missing or get wrong.

This module is never imported. It only lists the words so `scripts/translations.py update`
adds them to locale/*/django.po, where our translations take priority over Django's.
For example, Django's Malay turns "3 p.m." into "3 malam" (3 at night); ours says "3 ptg".
"""

from django.utils.translation import gettext_noop, ngettext_lazy

# django/utils/dateformat.py
gettext_noop("a.m.")
gettext_noop("p.m.")
gettext_noop("AM")
gettext_noop("PM")
gettext_noop("noon")
gettext_noop("midnight")

# django/utils/dates.py (the day on the date stamps)
gettext_noop("Mon")
gettext_noop("Tue")
gettext_noop("Wed")
gettext_noop("Thu")
gettext_noop("Fri")
gettext_noop("Sat")
gettext_noop("Sun")

# django/utils/timesince.py ("Next at school, in 2 days, 5 hours")
ngettext_lazy("%(num)d year", "%(num)d years", "num")
ngettext_lazy("%(num)d month", "%(num)d months", "num")
ngettext_lazy("%(num)d week", "%(num)d weeks", "num")
ngettext_lazy("%(num)d day", "%(num)d days", "num")
ngettext_lazy("%(num)d hour", "%(num)d hours", "num")
ngettext_lazy("%(num)d minute", "%(num)d minutes", "num")
gettext_noop(", ")
