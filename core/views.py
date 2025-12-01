from django.shortcuts import HttpResponse


# Create your views here.
def home_view(request):
    return HttpResponse("Welcome to the Home Page")


def about_view(request):
    return HttpResponse("About Us Page")


def contact_view(request):
    return HttpResponse("Contact Us Page")
