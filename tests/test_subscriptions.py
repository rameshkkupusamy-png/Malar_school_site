import pytest
from django.urls import reverse

from portal.models import Subscriber
from portal.notifications import notify_subscribers


@pytest.mark.django_db
def test_subscribe_creates_subscriber(client):
    client.post(reverse("portal:subscribe"), {"email": "parent@example.com", "name": "Asha"})
    assert Subscriber.objects.get(email="parent@example.com").is_active


@pytest.mark.django_db
def test_subscribe_again_reactivates_without_duplicate(client):
    Subscriber.objects.create(email="parent@example.com", is_active=False)
    client.post(reverse("portal:subscribe"), {"email": "PARENT@example.com"})
    assert Subscriber.objects.count() == 1
    assert Subscriber.objects.get().is_active


@pytest.mark.django_db
def test_subscribe_with_invalid_email_creates_nothing(client):
    response = client.post(reverse("portal:subscribe"), {"email": "not-an-email"}, follow=True)
    assert Subscriber.objects.count() == 0
    assert b"Enter a valid email address" in response.content


@pytest.mark.django_db
def test_unsubscribe_needs_post(client):
    subscriber = Subscriber.objects.create(email="parent@example.com")
    url = subscriber.get_unsubscribe_url()

    client.get(url)
    subscriber.refresh_from_db()
    assert subscriber.is_active

    client.post(url)
    subscriber.refresh_from_db()
    assert not subscriber.is_active


def test_notify_emails_active_subscribers_only(make_event, mailoutbox):
    Subscriber.objects.create(email="a@example.com")
    Subscriber.objects.create(email="b@example.com", is_active=False)
    event = make_event("Science fair", location="Gym")

    sent = notify_subscribers(event)

    assert sent == 1
    assert mailoutbox[0].to == ["a@example.com"]
    assert "Science fair" in mailoutbox[0].subject
    assert "/unsubscribe/" in mailoutbox[0].body
    event.refresh_from_db()
    assert event.notified_at is not None
