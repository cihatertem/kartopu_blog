from django.shortcuts import HttpResponse


# Create your views here.
def portfolio_view(request):
    return HttpResponse(b"Portfolio Page")
