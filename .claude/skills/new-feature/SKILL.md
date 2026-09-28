---
name: new-feature
description: Adds a new feature to the school portal (models, admin, views, templates, tests). Use when the user asks to add, build or implement a new feature, page or content type.
argument-hint: <short description of the feature>
---

# Add a feature to the school portal

1. Restate the feature in one sentence from a parent's or staff member's point of view, and list assumptions.
2. Models: add or change them in `portal/models.py`. Public content needs `is_published` and a queryset `published()` helper. Then run `python manage.py makemigrations portal` and `python manage.py migrate`.
3. Admin: register the model in `portal/admin.py` with sensible `list_display`, `list_filter` and `search_fields` so staff can manage it without training. If staff editors should manage it, add its permissions to `EDITOR_PERMISSIONS` in `portal/management/commands/setup_roles.py`.
4. Public pages: views in `portal/views.py`, routes in `portal/urls.py`, templates in `portal/templates/portal/` extending `base.html`. Reuse partials (`_datestamp.html`, `_pager.html`) and follow the Design section of `CLAUDE.md`. Write an empty state for every list.
5. Tests in `tests/`: normal case, unpublished/hidden case, and one edge case.
6. Run `pytest` and `ruff check .`; fix failures.
7. Summarize: what staff do in the admin, what parents see, files changed, and test results.
