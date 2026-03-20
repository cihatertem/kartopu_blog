from django.test import RequestFactory, SimpleTestCase

from core.services.pagination import get_page_obj


class PaginationServicesTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.items = list(range(1, 26))

    def test_get_page_obj_no_page_param(self):
        request = self.factory.get("/")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 1)
        self.assertEqual(list(page_obj.object_list), list(range(1, 11)))
        self.assertTrue(page_obj.has_next())
        self.assertFalse(page_obj.has_previous())

    def test_get_page_obj_valid_page(self):
        request = self.factory.get("/?page=2")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(list(page_obj.object_list), list(range(11, 21)))
        self.assertTrue(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())

    def test_get_page_obj_last_page(self):
        request = self.factory.get("/?page=3")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 3)
        self.assertEqual(list(page_obj.object_list), list(range(21, 26)))
        self.assertFalse(page_obj.has_next())
        self.assertTrue(page_obj.has_previous())

    def test_get_page_obj_out_of_bounds_large_page(self):
        request = self.factory.get("/?page=100")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 3)
        self.assertEqual(list(page_obj.object_list), list(range(21, 26)))

    def test_get_page_obj_invalid_page_string(self):
        request = self.factory.get("/?page=abc")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 1)
        self.assertEqual(list(page_obj.object_list), list(range(1, 11)))

    def test_get_page_obj_negative_page(self):
        request = self.factory.get("/?page=-1")
        page_obj = get_page_obj(request, self.items, per_page=10)

        self.assertEqual(page_obj.number, 3)
        self.assertEqual(list(page_obj.object_list), list(range(21, 26)))

    def test_get_page_obj_custom_page_param(self):
        request = self.factory.get("/?custom_page=2")
        page_obj = get_page_obj(
            request, self.items, per_page=10, page_param="custom_page"
        )

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(list(page_obj.object_list), list(range(11, 21)))

    def test_get_page_obj_custom_page_param_ignored_default(self):
        request = self.factory.get("/?page=2")
        page_obj = get_page_obj(
            request, self.items, per_page=10, page_param="custom_page"
        )

        self.assertEqual(page_obj.number, 1)
        self.assertEqual(list(page_obj.object_list), list(range(1, 11)))
