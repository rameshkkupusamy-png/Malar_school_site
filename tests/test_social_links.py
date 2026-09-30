import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from portal.models import SocialLink


@pytest.mark.django_db
def test_footer_lists_published_links_in_order(client):
    SocialLink.objects.create(platform="youtube", url="https://youtube.com/@school", order=2)
    SocialLink.objects.create(
        platform="facebook", url="https://facebook.com/school", label="PIBG Facebook", order=1
    )
    SocialLink.objects.create(platform="tiktok", url="https://tiktok.com/@x", is_published=False)

    response = client.get(reverse("portal:event_list"))

    assert [link.name for link in response.context["social_links"]] == [
        "PIBG Facebook",
        "YouTube",
    ]
    html = response.content.decode()
    assert "Follow the school" in html
    assert 'href="https://youtube.com/@school"' in html
    assert "tiktok.com" not in html


@pytest.mark.django_db
def test_footer_hides_section_without_links(client):
    SocialLink.objects.create(platform="x", url="https://x.com/school", is_published=False)

    response = client.get(reverse("portal:home"))

    assert "Follow the school" not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/school"])
def test_only_web_addresses_are_allowed(url):
    link = SocialLink(platform="facebook", url=url)
    with pytest.raises(ValidationError) as error:
        link.full_clean()
    assert "url" in error.value.message_dict


@pytest.mark.django_db
def test_other_platform_needs_a_name():
    link = SocialLink(platform="other", url="https://example.com")
    with pytest.raises(ValidationError) as error:
        link.full_clean()
    assert "label" in error.value.message_dict


@pytest.mark.django_db
def test_editors_can_manage_social_links():
    call_command("setup_roles", stdout=None)
    codenames = set(
        Group.objects.get(name="Editors").permissions.values_list("codename", flat=True)
    )
    assert {"add_sociallink", "change_sociallink", "delete_sociallink"} <= codenames
