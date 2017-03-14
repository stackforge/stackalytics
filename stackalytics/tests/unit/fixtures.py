# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import

import fixtures
from oslo_config import cfg


CONF = cfg.CONF


CONF.import_opt('query_launchpad', 'stackalytics.config')


class ConfigFixture(fixtures.Fixture):
    """Fixture to patch and restore global CONF.

    This also resets overrides for everything that is patched during
    it's teardown.

    """

    def __init__(self, **kwargs):
        """Constructor

        :params group: if specified all config options apply to that group.

        :params **kwargs: the rest of the kwargs are processed as a
        set of key/value pairs to be set as configuration override.

        """
        super(ConfigFixture, self).__init__()
        self.group = kwargs.pop('group', None)
        self.args = kwargs

    def setUp(self):
        super(ConfigFixture, self).setUp()
        for k, v in self.args.items():
            self.addCleanup(CONF.clear_override, k, self.group)
            CONF.set_override(k, v, self.group)
