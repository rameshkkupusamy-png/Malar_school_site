import io

import pytest
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import AnonymousUser, Group, User
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import translation
from openpyxl import Workbook

from portal.models import StaffMember

GOOGLE = {
    "google": {
        "APPS": [{"client_id": "test-client", "secret": "test-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
    }
}


@pytest.fixture
def google_sign_in(rf, settings, db):
    """Finish a Google sign-in as if Google had just confirmed this email address."""
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE
    call_command("setup_roles", verbosity=0)

    def _sign_in(email, verified=True, uid="google-uid-1"):
        request = rf.get("/accounts/google/login/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.user = AnonymousUser()
        # What allauth's middleware does per request; English so the messages can be checked.
        with context.request_context(request), translation.override("en"):
            provider = get_adapter().get_provider(request, "google")
            # The profile Google returns after the person picks their account.
            profile = {"sub": uid, "email": email, "email_verified": verified, "name": "Test"}
            sociallogin = provider.sociallogin_from_response(request, profile)
            response = complete_social_login(request, sociallogin)
        signed_in = request.session.get("_auth_user_id")
        notes = [str(m) for m in get_messages(request)]
        return response, signed_in, notes

    return _sign_in


def test_listed_teacher_gets_a_staff_account_on_first_sign_in(google_sign_in):
    StaffMember.objects.create(email="Siti@Example.com", name="Cikgu Siti")

    response, signed_in, _ = google_sign_in("siti@example.com")

    user = User.objects.get(email="siti@example.com")
    assert signed_in == str(user.pk)
    assert user.is_staff and user.is_active and not user.is_superuser
    assert user.groups.filter(name="Editors").exists()
    assert user.first_name == "Cikgu Siti"
    assert StaffMember.objects.get().user == user
    assert response.url == reverse("admin:index")


def test_second_sign_in_reuses_the_same_account(google_sign_in):
    StaffMember.objects.create(email="siti@example.com")
    google_sign_in("siti@example.com")

    _, signed_in, _ = google_sign_in("siti@example.com")

    assert User.objects.count() == 1
    assert signed_in == str(User.objects.get().pk)


def test_email_not_on_the_list_is_turned_away(google_sign_in):
    response, signed_in, notes = google_sign_in("stranger@example.com")

    assert signed_in is None
    assert not User.objects.exists()
    assert response.url == reverse("admin:login")
    assert "isn't on the staff list" in notes[0]


def test_removed_teacher_cannot_sign_in(google_sign_in):
    StaffMember.objects.create(email="siti@example.com", is_active=False)

    _, signed_in, _ = google_sign_in("siti@example.com")

    assert signed_in is None


def test_unconfirmed_google_email_is_turned_away(google_sign_in):
    StaffMember.objects.create(email="siti@example.com")

    _, signed_in, notes = google_sign_in("siti@example.com", verified=False)

    assert signed_in is None
    assert "confirmed email" in notes[0]


def test_existing_account_with_the_same_email_is_linked_not_duplicated(google_sign_in):
    owner = User.objects.create_user("owner", email="owner@example.com", password="x")
    StaffMember.objects.create(email="owner@example.com")

    _, signed_in, _ = google_sign_in("owner@example.com")

    assert User.objects.count() == 1
    assert signed_in == str(owner.pk)
    assert SocialAccount.objects.get().user == owner


def test_removing_access_deactivates_the_account_immediately(google_sign_in):
    member = StaffMember.objects.create(email="siti@example.com")
    google_sign_in("siti@example.com")

    member.refresh_from_db()
    member.is_active = False
    member.save()
    assert not User.objects.get().is_active

    member.is_active = True
    member.save()
    assert User.objects.get().is_active

    member.delete()
    assert not User.objects.get().is_active


def test_admin_sign_in_page_offers_google_only_when_configured(client, settings, db):
    settings.GOOGLE_CLIENT_ID = ""
    assert "Sign in with Google" not in client.get(reverse("admin:login")).content.decode()

    settings.GOOGLE_CLIENT_ID = "test-client"
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE
    page = client.get(reverse("admin:login")).content.decode()
    assert "Sign in with Google" in page
    assert 'name="password"' in page  # the owner's password login is still there


def test_google_button_sends_staff_to_google(client, settings, db):
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE

    response = client.post("/accounts/google/login/")

    assert response.status_code == 302
    assert response.url.startswith("https://accounts.google.com/")
    assert "client_id=test-client" in response.url
    assert "accounts%2Fgoogle%2Flogin%2Fcallback%2F" in response.url


@pytest.mark.django_db
def test_password_sign_up_is_closed(client):
    client.post(
        "/accounts/signup/",
        {
            "email": "new@example.com",
            "password1": "a-long-pass-123",
            "password2": "a-long-pass-123",
        },
    )
    assert not User.objects.exists()


@pytest.mark.django_db
def test_import_staff_from_csv(tmp_path):
    StaffMember.objects.create(email="old@example.com")
    sheet = tmp_path / "teachers.csv"
    sheet.write_text(
        "Name,Email\nCikgu Siti,SITI@example.com\nMr Tan,old@example.com\n,\nNo email here,\n",
        encoding="utf-8",
    )

    call_command("import_staff", str(sheet))

    assert set(StaffMember.objects.values_list("email", flat=True)) == {
        "old@example.com",
        "siti@example.com",
    }
    assert StaffMember.objects.get(email="siti@example.com").name == "Cikgu Siti"


@pytest.mark.django_db
def test_editors_cannot_manage_the_staff_list():
    call_command("setup_roles", verbosity=0)
    editors = Group.objects.get(name="Editors")
    assert not editors.permissions.filter(content_type__model="staffmember").exists()


@pytest.fixture
def superadmin_client(client, db):
    admin_user = User.objects.create_superuser("head", "head@example.com", "pw")
    client.force_login(admin_user)
    return client


def test_super_admin_adds_staff_from_a_csv_on_the_website(superadmin_client):
    StaffMember.objects.create(email="old@example.com")
    upload = SimpleUploadedFile(
        "teachers.csv", b"Name,Email\nCikgu Siti,siti@example.com\nMr Tan,OLD@example.com\n"
    )

    response = superadmin_client.post(
        reverse("admin:portal_staffmember_import"), {"file": upload}, follow=True
    )

    assert StaffMember.objects.get(email="siti@example.com").name == "Cikgu Siti"
    page = response.content.decode()
    assert "Added 1 staff member(s). 1 were already on the list." in page
    assert "row(s) 1" in page  # the heading row


def test_super_admin_adds_staff_from_an_excel_file(superadmin_client):
    workbook = Workbook()
    workbook.active.append(["Email", "Name"])
    workbook.active.append(["kumar@example.com", "Cikgu Kumar"])
    output = io.BytesIO()
    workbook.save(output)
    upload = SimpleUploadedFile("teachers.xlsx", output.getvalue())

    superadmin_client.post(reverse("admin:portal_staffmember_import"), {"file": upload})

    assert StaffMember.objects.get(email="kumar@example.com").name == "Cikgu Kumar"


def test_unreadable_staff_file_shows_a_clear_error(superadmin_client):
    upload = SimpleUploadedFile("teachers.xlsx", b"not really excel")

    response = superadmin_client.post(reverse("admin:portal_staffmember_import"), {"file": upload})

    assert "opened as an Excel spreadsheet" in response.content.decode()
    assert not StaffMember.objects.exists()


def test_editors_cannot_open_the_staff_import(client, db):
    call_command("setup_roles", verbosity=0)
    teacher = User.objects.create_user("teacher", password="pw", is_staff=True)
    teacher.groups.add(Group.objects.get(name="Editors"))
    client.force_login(teacher)

    assert client.get(reverse("admin:portal_staffmember_import")).status_code == 403
    assert client.get(reverse("admin:portal_staffmember_changelist")).status_code == 403
