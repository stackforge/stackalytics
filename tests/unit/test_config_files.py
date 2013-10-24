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

import json

import jsonschema
import testtools


class TestConfigFiles(testtools.TestCase):
    def setUp(self):
        super(TestConfigFiles, self).setUp()
        self.longMessage = True
        self.maxDiff = 2048

    def _read_file(self, file_name):
        with open(file_name, 'r') as content_file:
            content = content_file.read()
            return json.loads(content)

    def test_corrections(self):
        corrections = self._read_file('etc/corrections.json')
        schema = self._read_file('etc/corrections.schema.json')
        jsonschema.validate(corrections, schema)

    def test_default_data(self):
        default_data = self._read_file('etc/default_data.json')
        schema = self._read_file('etc/default_data.schema.json')
        jsonschema.validate(default_data, schema)

    def test_companies_in_alphabetical_order(self):
        companies = self._read_file('etc/default_data.json')['companies']
        sorted_companies = sorted(companies, key=lambda x: x['domains'][0])
        self.assertListEqual(
            companies, sorted_companies,
            'List of companies should be ordered by the first domain')

    def test_users_in_alphabetical_order(self):
        users = self._read_file('etc/default_data.json')['users']
        sorted_users = sorted(users, key=lambda x: x['launchpad_id'])
        self.assertListEqual(users, sorted_users,
                             'List of users should be ordered by launchpad id')
