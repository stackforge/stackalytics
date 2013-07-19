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

from oslo.config import cfg

OPTS = [
    cfg.StrOpt('default-data', default='etc/default_data.json',
               help='Default data'),
    cfg.StrOpt('sources-root', default='/var/local/stackalytics',
               help='The folder that holds all project sources to analyze'),
    cfg.StrOpt('runtime-storage-uri', default='memcached://127.0.0.1:11211',
               help='Storage URI'),
    cfg.StrOpt('persistent-storage-uri', default='mongodb://localhost',
               help='URI of persistent storage'),
    cfg.BoolOpt('sync-default-data', default=False,
                help='Update persistent storage with default data. '
                     'Existing data is not overwritten'),
    cfg.BoolOpt('force-sync-default-data', default=False,
                help='Completely overwrite persistent storage with the '
                     'default data'),
    cfg.BoolOpt('filter-robots', default=True,
                help='Filter out commits from robots'),
    cfg.StrOpt('listen-host', default='127.0.0.1',
               help='The address dashboard listens on'),
    cfg.IntOpt('listen-port', default=8080,
               help='The port dashboard listens on'),
    cfg.StrOpt('corrections-uri',
               default=('https://raw.github.com/stackforge/stackalytics/'
                        'master/etc/corrections.json'),
               help='The address of file with corrections data'),
    cfg.StrOpt('review-uri', default='gerrit://review.openstack.org',
               help='URI of review system'),
    cfg.StrOpt('ssh-key-filename', default='/home/ishakhat/.ssh/4launchpad_id',
               help='SSH key for gerrit review system access'),
    cfg.StrOpt('ssh-username', default='ishakhat',
               help='SSH username for gerrit review system access'),
]
