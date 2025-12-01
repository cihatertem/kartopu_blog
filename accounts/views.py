from django.shortcuts import HttpResponse, render


# Create your views here.
def author_profile_view(request):
    return HttpResponse(b"Author Profile Page")
