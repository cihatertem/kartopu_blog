from django.shortcuts import render


# Create your views here.
def author_profile_view(request):
    return render(request, "accounts/author_profile.html")


def disabled_account_view(request):
    return render(request, "accounts/disabled_account.html", status=404)
