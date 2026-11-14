import secrets

from django.conf import settings


class SecurityHeadersMiddleware:
    """Adds Content-Security-Policy and privacy-hardening response headers.

    Scripts are restricted to self-hosted assets plus a per-request nonce, so
    inline structured data can be allowed without enabling arbitrary inline
    JavaScript.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        nonce = secrets.token_urlsafe(18)
        request.csp_nonce = nonce
        response = self.get_response(request)

        extra_scripts = tuple(
            item
            for item in getattr(settings, "CSP_EXTRA_SCRIPT_SRC", ())
            if item
        )
        extra_connects = tuple(
            item
            for item in getattr(settings, "CSP_EXTRA_CONNECT_SRC", ())
            if item
        )
        extra_frames = tuple(
            item for item in getattr(settings, "CSP_EXTRA_FRAME_SRC", ()) if item
        )

        policy = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self' 'nonce-{}' {}".format(
                    nonce, " ".join(extra_scripts)
                ).strip(),
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data:",
                "font-src 'self'",
                "connect-src 'self' {}".format(" ".join(extra_connects)).strip(),
                "frame-src 'self' {}".format(" ".join(extra_frames)).strip(),
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "upgrade-insecure-requests" if not settings.DEBUG else "",
            ]
        ).strip("; ")

        response.headers["Content-Security-Policy"] = policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), " 
            "usb=(), interest-cohort=()"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if not settings.DEBUG:
            response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        return response
