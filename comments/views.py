from django.shortcuts import HttpResponse, render


# Create your views here.
def comments_view(request):
    return HttpResponse(b"Comments Page")
