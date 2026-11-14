from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailAuthenticationBackend(ModelBackend):
    """Case-insensitive email login with Django's permission handling."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = username or kwargs.get(User.EMAIL_FIELD) or kwargs.get("email")
        if not email or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=email.strip())
        except User.DoesNotExist:
            User().set_password(password)  # mitigate timing differences
            return None
        except User.MultipleObjectsReturned:  # pragma: no cover - DB constraint prevents
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
