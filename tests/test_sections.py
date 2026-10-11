import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.urls import reverse

from portal.models import SiteSections

KEYS = ["news", "events", "photos", "documents", "pibg", "achievements", "search"]


def pause(*keys):
    record = SiteSections.load()
    for key in keys:
        setattr(record, key, False)
    record.save()


@pytest.mark.django_db
def test_every_section_is_on_before_anyone_saves():
    record = SiteSections.load()
    assert record.pk is None
    assert all(getattr(record, key) for key in KEYS)


@pytest.mark.django_db
def test_there_is_only_ever_one_record():
    SiteSections(news=False).save()
    SiteSections(events=False).save()
    assert SiteSections.objects.count() == 1
    assert SiteSections.load().events is False


@pytest.mark.django_db
def test_superuser_can_pause_a_section(admin_client):
    data = {key: "on" for key in KEYS if key != "photos"}
    response = admin_client.post(reverse("admin:portal_sitesections_add"), data)
    assert response["Location"] == reverse("admin:portal_sitesections_change", args=[1])
    assert SiteSections.load().photos is False
    assert SiteSections.load().news is True


@pytest.mark.django_db
def test_admin_explains_what_pausing_events_stops(admin_client):
    html = admin_client.get(reverse("admin:portal_sitesections_add")).content.decode()
    assert "Also stops email sign-ups, event emails and reminders." in html


@pytest.mark.django_db
def test_site_sections_cannot_be_deleted(admin_client):
    SiteSections().save()
    url = reverse("admin:portal_sitesections_delete", args=[1])
    assert admin_client.get(url).status_code == 403


def editor(client, *extra_permissions):
    call_command("setup_roles", stdout=None)
    user = User.objects.create_user("editor", password="x", is_staff=True)
    user.groups.add(Group.objects.get(name="Editors"))
    user.user_permissions.add(*Permission.objects.filter(codename__in=extra_permissions))
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_editors_cannot_see_or_open_site_sections(client):
    editor(client)
    SiteSections().save()
    assert "Site sections" not in client.get(reverse("admin:index")).content.decode()
    url = reverse("admin:portal_sitesections_change", args=[1])
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_editor_given_the_permission_by_hand_still_cannot_open_it(client):
    editor(client, "view_sitesections", "change_sitesections", "add_sitesections")
    assert client.get(reverse("admin:portal_sitesections_add")).status_code == 403
    SiteSections().save()
    url = reverse("admin:portal_sitesections_change", args=[1])
    assert client.get(url).status_code == 403
