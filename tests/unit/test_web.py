import unittest

from dashboard import web


class DashboardTestCase(unittest.TestCase):
    def setUp(self):
        web.app.config['TESTING'] = True
        self.app = web.app.test_client()

    def tearDown(self):
        pass

    def test_home_page(self):
        rv = self.app.get('/')
        assert rv.status_code == 200
