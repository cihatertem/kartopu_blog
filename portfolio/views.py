from django.http.response import HttpResponse


# Create your views here.
def portfolio_view(request):
    return HttpResponse(b"Portfolio Page")
