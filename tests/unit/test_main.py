# Copyright (c) 2014 Rec Hat, Inc.
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

import os

import testtools

from spectrometer.processor import main


class TestMain(testtools.TestCase):

    def test_read_official_programs_yaml(self):
        path_to_test_data = os.getcwd() + '/etc/test_programs.yaml'
        programs_uri = 'file://{}'.format(path_to_test_data)
        RELEASES = ["Hydrogen", "Helium"]
        module_groups = main._read_official_programs_yaml(programs_uri,
                                                          RELEASES)

        bootstrap = module_groups['official-bootstrap']['releases']
        incubation = module_groups['official-incubation']['releases']
        core = module_groups['official-core']['releases']

        self.assertIn('controller', bootstrap['hydrogen'])
        self.assertIn('controller', core['helium'])
        self.assertIn('foo', incubation['helium'])
