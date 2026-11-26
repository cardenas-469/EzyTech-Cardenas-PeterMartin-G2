"""Project-wide error handlers that render friendly pages instead of tracebacks."""

from django.shortcuts import render


def permission_denied(request, exception=None):
    """Render the custom 403 page."""
    return render(request, '403.html', status=403)


def page_not_found(request, exception=None):
    """Render the custom 404 page."""
    return render(request, '404.html', status=404)


def server_error(request):
    """Render the custom 500 page (used when DEBUG is False)."""
    return render(request, '500.html', status=500)
