import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")
django.setup()

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import setup_databases, setup_test_environment

from accounts.models import User

setup_test_environment()
old_config = setup_databases(1, False)

u = User.objects.create(email="test_social2@example.com", password="password")
print("Initial avatar:", u.avatar)

url = (
    "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
)
resp = requests.get(url)

u.avatar = SimpleUploadedFile(
    "social_avatar.png", resp.content, content_type="image/png"
)
u.save()

print("Avatar after save:", u.avatar)
print("Avatar URL:", u.avatar.url if u.avatar else "No URL")

# Simulate a comment save flow or simply saving the user again
u.save()
print("Avatar after second save:", u.avatar)
