"""Staff sign-in rules: Google accounts are accepted only for emails on the staff list."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from .management.commands.setup_roles import EDITOR_GROUP
from .models import StaffMember

NOT_ON_LIST = gettext_noop(
    "%(email)s isn't on the staff list. Ask the school office to add your email, "
    "then sign in again."
)
NO_VERIFIED_EMAIL = gettext_noop(
    "Google didn't share a confirmed email address. Try another Google account."
)


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """Nobody can create an account with a password; staff are added in the admin."""

    def is_open_for_signup(self, request):
        return False


class StaffListSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = verified_email(sociallogin)
        if email is None:
            reject(request, _(NO_VERIFIED_EMAIL))

        member = StaffMember.objects.filter(email=email, is_active=True).first()
        if member is None:
            reject(request, _(NOT_ON_LIST) % {"email": email})

        if not sociallogin.is_existing:
            # Reuse the account from an earlier sign-in, or one staff made by hand.
            user = member.user or User.objects.filter(email__iexact=email).first()
            if user is not None:
                sociallogin.connect(request, user)
                link(member, user)

    def is_open_for_signup(self, request, sociallogin):
        return True  # pre_social_login has already checked the staff list

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        email = verified_email(sociallogin)
        member = StaffMember.objects.get(email=email)
        if member.name and not (user.first_name or user.last_name):
            user.first_name = member.name
            user.save(update_fields=["first_name"])
        link(member, user)
        return user


def verified_email(sociallogin) -> str | None:
    for address in sociallogin.email_addresses:
        if address.verified:
            return address.email.strip().lower()
    return None


def link(member: StaffMember, user: User) -> None:
    """Give the user staff access with the Editors group and remember who they are."""
    user.is_staff = True
    user.is_active = True
    user.save(update_fields=["is_staff", "is_active"])
    editors = Group.objects.filter(name=EDITOR_GROUP).first()
    if editors is not None:
        user.groups.add(editors)
    if member.user_id != user.pk:
        member.user = user
        member.save(update_fields=["user"])


def reject(request, message: str):
    messages.error(request, message)
    raise ImmediateHttpResponse(redirect("admin:login"))
