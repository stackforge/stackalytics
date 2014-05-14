# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import testtools

from stackalytics.processor import utils


class TestUtils(testtools.TestCase):
    def setUp(self):
        super(TestUtils, self).setUp()

    def _test_one_range(self, start, end, step):
        elements = set()
        for chunk in utils.make_range(start, end, step):
            for item in chunk:
                self.assertFalse(item in elements)
                elements.add(item)

        self.assertTrue(set(range(start, end)) == elements)

    def test_make_range_0_10_1(self):
        self._test_one_range(0, 10, 1)

    def test_make_range_0_10_3(self):
        self._test_one_range(0, 10, 3)

    def test_make_range_3_5_4(self):
        self._test_one_range(3, 5, 4)

    def test_make_range_5_26_10(self):
        self._test_one_range(5, 26, 10)

    def test_email_valid(self):
        self.assertTrue(utils.check_email_validity('pupkin@gmail.com'))
        self.assertTrue(utils.check_email_validity('v.pup_kin2@ntt.co.jp'))

    def test_email_invalid(self):
        self.assertFalse(utils.check_email_validity('pupkin@localhost'))
        self.assertFalse(utils.check_email_validity('222@some.(trash)'))

    def test_unwrap(self):
        original = 'Lorem ipsum. Dolor\nsit amet.\n Lorem\n ipsum.\ndolor!\n'
        expected = 'Lorem ipsum. Dolor sit amet.\n Lorem\n ipsum.\ndolor!'

        self.assertEqual(expected, utils.unwrap_text(original))

    def test_format_text_split_long_link(self):
        original = ('https://blueprints.launchpad.net/stackalytics/+spec/'
                    'stackalytics-core')
        expected = ('https://&#8203;blueprints.launchpad.net/&#8203;'
                    'stackalytics/&#8203;+spec/&#8203;stackalytics-core')

        self.assertEqual(expected, utils.format_text(original))

    def test_add_index(self):
        sequence = [{'name': 'A'}, {'name': 'B'}, {'name': 'C'}]
        expected = [{'index': 1, 'name': 'A'}, {'index': 2, 'name': 'B'},
                    {'index': 3, 'name': 'C'}]
        self.assertEqual(expected, utils.add_index(sequence))

    def test_add_index_with_filter(self):
        sequence = [{'name': 'A'}, {'name': 'B'}, {'name': 'C'}]
        expected = [{'index': 0, 'name': 'A'}, {'index': '', 'name': 'B'},
                    {'index': 1, 'name': 'C'}]
        self.assertEqual(expected, utils.add_index(
            sequence, start=0, item_filter=lambda x: x['name'] != 'B'))

    def test_normalize_company_name(self):
        company_names = ['EMC Corporation', 'Abc, corp..', 'Mirantis IT.',
                         'Red Hat, Inc.', 'abc s.r.o. ABC', '2s.r.o. co',
                         'AL.P.B L.P. s.r.o. s.r.o. C ltd.']
        correct_normalized_company_names = ['emc', 'abc', 'mirantis',
                                            'redhat', 'abcabc', '2sro',
                                            'alpbc']
        normalized_company_names = [utils.normalize_company_name(name)
                                    for name in company_names]

        self.assertEqual(normalized_company_names,
                         correct_normalized_company_names)
