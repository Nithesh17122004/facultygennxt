from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import EmailPreferenceForm
from .models import EmailPreference, Notification


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    unread_only = request.GET.get("unread") == "1"
    if unread_only:
        notifications = notifications.filter(is_read=False)
    notifications = notifications[:100]
    return render(
        request,
        "notifications/list.html",
        {"notifications": notifications, "unread_only": unread_only},
    )


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    if notification.url.startswith("/"):
        return redirect(notification.url)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications:list")


@login_required
def preferences(request):
    preference, _ = EmailPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = EmailPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, "Your email preferences have been saved.")
            return redirect("notifications:preferences")
    else:
        form = EmailPreferenceForm(instance=preference)
    return render(
        request, "notifications/preferences.html", {"form": form, "preference": preference}
    )


@ratelimit(key="ip", rate="10/m", method="GET", block=True)
def unsubscribe(request, token):
    try:
        data = signing.loads(token, salt="email-preferences", max_age=60 * 60 * 24 * 180)
    except signing.BadSignature as exc:
        raise Http404("This unsubscribe link is invalid or has expired.") from exc
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=data.get("user_id")).first()
    preference = None
    if user:
        preference, _ = EmailPreference.objects.get_or_create(user=user)
    if request.method == "POST":
        if preference:
            preference.marketing = False
            preference.save(update_fields=["marketing", "updated_at"])
        messages.success(request, "You will no longer receive marketing emails.")
        return redirect("core:home")
    return render(
        request,
        "notifications/unsubscribe.html",
        {"target_user": user, "preference": preference},
    )
