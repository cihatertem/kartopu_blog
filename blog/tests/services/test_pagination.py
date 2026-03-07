from django.test import RequestFactory, TestCase

from core.services.pagination import get_page_obj


class PaginationServicesTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_page_obj(self):
        items = list(range(1, 15))  # 1 to 14

        request = self.factory.get("/", {"page": "2"})
        page_obj = get_page_obj(request, items, per_page=10)

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.object_list, [11, 12, 13, 14])

    def test_get_page_obj_invalid_page(self):
        items = list(range(1, 15))
        request = self.factory.get("/", {"page": "abc"})
        page_obj = get_page_obj(request, items, per_page=10)

        self.assertEqual(page_obj.number, 1)

    def test_get_page_obj_empty_page(self):
        items = []
        request = self.factory.get("/", {"page": "1"})
        page_obj = get_page_obj(request, items, per_page=10)

        self.assertEqual(page_obj.number, 1)
        self.assertEqual(page_obj.object_list, [])

    def test_get_page_obj_out_of_bounds_page_negative(self):
        items = list(range(1, 15))
        request = self.factory.get("/", {"page": "-1"})
        page_obj = get_page_obj(request, items, per_page=10)

        # Negative page should return the last page in Django Paginator (if < 1)
        # Note: 'get_page' converts negative values to the last page!
        self.assertEqual(page_obj.number, 2)

    def test_get_page_obj_out_of_bounds_page_too_large(self):
        items = list(range(1, 15))
        request = self.factory.get("/", {"page": "99"})
        page_obj = get_page_obj(request, items, per_page=10)

        # Page > max_pages should return the last page
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.object_list, [11, 12, 13, 14])

    def test_get_page_obj_custom_page_param(self):
        items = list(range(1, 15))
        request = self.factory.get("/", {"custom_page": "2"})
        page_obj = get_page_obj(request, items, per_page=10, page_param="custom_page")

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.object_list, [11, 12, 13, 14])
