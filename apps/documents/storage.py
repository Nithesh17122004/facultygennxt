from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateDocumentStorage(FileSystemStorage):
    """Filesystem storage whose files are only reachable through guarded views."""

    def __init__(self, **kwargs):
        kwargs.setdefault("location", str(settings.PRIVATE_MEDIA_ROOT))
        kwargs.setdefault("base_url", None)
        super().__init__(**kwargs)

    def url(self, name):  # pragma: no cover - defensive
        raise ValueError("Private documents do not have public URLs.")


private_storage = PrivateDocumentStorage()
