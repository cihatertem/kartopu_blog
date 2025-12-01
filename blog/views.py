from django.shortcuts import HttpResponse, render


# Create your views here.
def blog_view(request):
    return HttpResponse(b"Blog Page")
