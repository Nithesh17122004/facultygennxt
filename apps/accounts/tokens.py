from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Single-use, expiring token bound to the user's email state."""

    def _make_hash_value(self, user, timestamp):
        verified = user.email_verified_at.isoformat() if user.email_verified_at else "unverified"
        return f"{user.pk}{timestamp}{user.email}{verified}{user.password[-12:]}"

    def check_token(self, user, token):
        if not user or not token:
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        if (self._num_seconds(self._now()) - ts) > settings.EMAIL_VERIFICATION_MAX_AGE:
            return False
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token):
                return True
        return False


email_verification_token = EmailVerificationTokenGenerator()
