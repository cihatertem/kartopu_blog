from django.http import Http404
from django.shortcuts import HttpResponse


# Create your views here.
def author_profile_view(request):
    return HttpResponse(b"Author Profile Page")


def disabled_account_view(request):
    raise Http404("This account endpoint has been disabled.")
