"""Type-ahead search suggestions for the public header."""
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from apps.institutions.models import Institution
from apps.jobs.models import Department, Job


@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def suggest(request):
    query = (request.GET.get("q") or "").strip()[:100]
    payload = {"query": query, "jobs": [], "institutions": [], "departments": []}
    if len(query) < 2:
        return JsonResponse(payload)
    jobs = (
        Job.objects.live()
        .filter(
            Q(title__icontains=query)
            | Q(designation__name__icontains=query)
            | Q(department__name__icontains=query)
            | Q(institution__name__icontains=query)
        )
        .select_related("institution", "city", "state")[:6]
    )
    payload["jobs"] = [
        {
            "title": job.title,
            "institution": job.institution.name,
            "location": job.location_label,
            "url": job.get_absolute_url(),
        }
        for job in jobs
    ]
    payload["institutions"] = [
        {"name": item.name, "url": item.get_absolute_url()}
        for item in Institution.objects.filter(
            verification_status="verified", is_active=True, name__icontains=query
        )[:4]
    ]
    payload["departments"] = [
        {"name": item.name, "url": f"{reverse('jobs:find')}?department={item.slug}"}
        for item in Department.objects.filter(is_active=True, name__icontains=query)[:4]
    ]
    return JsonResponse(payload)
