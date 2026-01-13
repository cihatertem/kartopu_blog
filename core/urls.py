from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("hakkimizda/", views.about_view, name="about"),
    path("iletisim/", views.contact_view, name="contact"),
]
