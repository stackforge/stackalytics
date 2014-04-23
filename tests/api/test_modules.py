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

from tests.api import test_api


class TestAPIModules(test_api.TestAPI):

    def test_get_modules(self):
        with test_api.make_runtime_storage(
                {'repos': [{'module': 'nova', 'organization': 'openstack',
                            'uri': 'git://github.com/openstack/nova.git'},
                           {'module': 'glance', 'organization': 'openstack',
                            'uri': 'git://github.com/openstack/glance.git'}],
                 'module_groups': {
                     'nova-group': {'id': 'nova-group',
                                    'module_group_name': 'nova-group',
                                    'modules': ['nova', 'nova-cli'],
                                    'tag': 'group'},
                     'nova': test_api.make_module('nova'),
                     'nova-cli': test_api.make_module('nova-cli'),
                     'glance': test_api.make_module('glance'),
                 },
                 'project_types': [
                     {'id': 'all', 'title': 'All',
                      'modules': ['nova', 'glance', 'nova-cli']},
                     {'id': 'integrated', 'title': 'Integrated',
                      'modules': ['nova', 'glance']}]},
                test_api.make_records(record_type=['commit'],
                                      module=['glance', 'nova', 'nova-cli'])):

            response = self.app.get('/api/1.0/modules?'
                                    'project_type=all&metric=commits')
            modules = json.loads(response.data)['modules']
            self.assertEqual(
                [{'id': 'glance', 'text': 'glance', 'tag': 'module'},
                 {'id': 'nova', 'text': 'nova', 'tag': 'module'},
                 {'id': 'nova-cli', 'text': 'nova-cli', 'tag': 'module'},
                 {'id': 'nova-group', 'text': 'nova-group', 'tag': 'group'}],
                modules,
                message='Expected modules belonging to project type plus '
                        'module groups that are completely within '
                        'project type')

            response = self.app.get('/api/1.0/modules?module=nova-group&'
                                    'project_type=integrated&metric=commits')
            modules = json.loads(response.data)['modules']
            self.assertEqual(
                [{'id': 'glance', 'text': 'glance', 'tag': 'module'},
                 {'id': 'nova', 'text': 'nova', 'tag': 'module'}],
                modules,
                message='Expected modules belonging to project type plus '
                        'module groups that are completely within '
                        'project type')

            response = self.app.get('/api/1.0/modules?query=glance&'
                                    'project_type=all&metric=commits')
            modules = json.loads(response.data)['modules']
            self.assertEqual(
                [{'id': 'glance', 'text': 'glance', 'tag': 'module'}],
                modules,
                message='Expected modules which name contains query')

    def test_get_module(self):
        with test_api.make_runtime_storage(
                {'repos': [{'module': 'nova', 'organization': 'openstack',
                            'uri': 'git://github.com/openstack/nova.git'}],
                 'module_groups': {
                     'nova-group': {'id': 'nova-group',
                                    'module_group_name': 'nova-group',
                                    'modules': ['nova', 'nova-cli'],
                                    'tag': 'group'},
                     'nova': test_api.make_module('nova'),
                     'nova-cli': test_api.make_module('nova-cli'),
                 }},
                test_api.make_records(record_type=['commit'])):

            response = self.app.get('/api/1.0/modules/nova')
            module = json.loads(response.data)['module']
            self.assertEqual(
                {'id': 'nova', 'text': 'nova', 'tag': 'module'}, module)

            response = self.app.get('/api/1.0/modules/nova-group')
            module = json.loads(response.data)['module']
            self.assertEqual(
                {'tag': 'group', 'id': 'nova-group', 'text': 'nova-group'},
                module)
