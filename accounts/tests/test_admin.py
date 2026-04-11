from allauth.socialaccount.models import SocialApp
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from accounts.admin import CustomSocialAppForm, UserAdmin
from accounts.models import User


class MockSuperUser:
    def has_perm(self, perm, obj=None):
        return True


class UserAdminActionTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.factory = RequestFactory()

        self.user1 = User.objects.create_user(email="user1@example.com", password="pwd")
        self.user2 = User.objects.create_user(email="user2@example.com", password="pwd")
        self.user3 = User.objects.create_user(email="user3@example.com", password="pwd")

    def get_request(self):
        request = self.factory.get("/")
        request.user = MockSuperUser()
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    def test_make_superuser(self):
        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.make_superuser(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.user3.refresh_from_db()
        self.assertTrue(self.user1.is_superuser)
        self.assertTrue(self.user1.is_staff)
        self.assertTrue(self.user2.is_superuser)
        self.assertTrue(self.user2.is_staff)
        self.assertFalse(self.user3.is_superuser)

    def test_remove_superuser(self):
        self.user1.is_superuser = True
        self.user1.save()
        self.user2.is_superuser = True
        self.user2.save()

        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.remove_superuser(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_superuser)
        self.assertFalse(self.user2.is_superuser)

    def test_make_staff(self):
        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.make_staff(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertTrue(self.user1.is_staff)
        self.assertTrue(self.user2.is_staff)

    def test_remove_staff(self):
        self.user1.is_staff = True
        self.user1.save()
        self.user2.is_staff = True
        self.user2.save()

        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.remove_staff(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_staff)
        self.assertFalse(self.user2.is_staff)

    def test_make_active(self):
        self.user1.is_active = False
        self.user1.save()
        self.user2.is_active = False
        self.user2.save()

        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.make_active(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertTrue(self.user1.is_active)
        self.assertTrue(self.user2.is_active)

    def test_make_passive(self):
        request = self.get_request()
        queryset = User.objects.filter(id__in=[self.user1.id, self.user2.id])

        with self.assertNumQueries(1):
            self.admin.make_passive(request, queryset)

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()
        self.assertFalse(self.user1.is_active)
        self.assertFalse(self.user2.is_active)


class CustomSocialAppAdminTests(TestCase):
    def test_custom_social_app_form_includes_avatar_url_field(self):
        """Test that CustomSocialAppForm includes avatar_url_field correctly"""
        form = CustomSocialAppForm()
        self.assertIn("avatar_url_field", form.fields)

    def test_custom_social_app_form_saves_settings(self):
        """Test that avatar_url_field is correctly saved into settings JSON"""
        form_data = {
            "provider": "google",
            "name": "Google",
            "client_id": "testclient",
            "secret": "testsecret",
            "key": "testkey",
            "avatar_url_field": "custom_picture_key",
        }
        form = CustomSocialAppForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        instance = form.save(commit=True)
        self.assertIn("avatar_url_field", instance.settings)
        self.assertEqual(instance.settings["avatar_url_field"], "custom_picture_key")

        form_edit = CustomSocialAppForm(instance=instance)
        self.assertEqual(
            form_edit.fields["avatar_url_field"].initial, "custom_picture_key"
        )

    def test_custom_social_app_form_removes_settings_if_empty(self):
        """Test that avatar_url_field is removed from settings JSON if submitted empty"""
        app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="testclient",
            secret="testsecret",
            settings={"avatar_url_field": "custom_picture_key"},
        )

        form_data = {
            "provider": "google",
            "name": "Google",
            "client_id": "testclient",
            "secret": "testsecret",
            "key": "testkey",
            "avatar_url_field": "",  # Empty string
        }
        form = CustomSocialAppForm(data=form_data, instance=app)
        self.assertTrue(form.is_valid(), form.errors)

        instance = form.save(commit=True)
        self.assertNotIn("avatar_url_field", instance.settings)

    def test_custom_social_app_form_no_instance_pk(self):
        """Test form initialization without an existing instance"""
        form = CustomSocialAppForm()
        # Default initial for CharField is None if not specified
        self.assertIsNone(form.fields["avatar_url_field"].initial)

    def test_custom_social_app_form_instance_with_no_settings(self):
        """Test form initialization with instance that has no settings"""
        app = SocialApp(provider="google", name="Google")
        # No settings assigned, and no PK yet
        form = CustomSocialAppForm(instance=app)
        self.assertIsNone(form.fields["avatar_url_field"].initial)

    def test_custom_social_app_form_instance_with_pk_no_settings(self):
        """Test form initialization with instance that has PK but no settings"""
        app = SocialApp.objects.create(provider="google", name="Google")
        form = CustomSocialAppForm(instance=app)
        # Should be "" because settings is None or {} and we use .get(..., "")
        self.assertEqual(form.fields["avatar_url_field"].initial, "")


class UserAdminConfigurationTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)

    def test_user_admin_list_display(self):
        self.assertEqual(
            self.admin.list_display,
            (
                "email",
                "full_name",
                "is_staff",
                "is_active",
                "last_login",
                "updated_at",
                "created_at",
            ),
        )

    def test_user_admin_search_fields(self):
        self.assertEqual(
            self.admin.search_fields,
            (
                "email",
                "first_name",
                "last_name",
            ),
        )

    def test_user_admin_list_filter(self):
        self.assertEqual(
            self.admin.list_filter,
            (
                "is_staff",
                "is_active",
                "created_at",
                "updated_at",
                "last_login",
            ),
        )
