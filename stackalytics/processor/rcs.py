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
import re

from oslo.config import cfg
import paramiko

from stackalytics.openstack.common import log as logging
from stackalytics.processor import config
from stackalytics.processor import persistent_storage
from stackalytics.processor import record_processor
from stackalytics.processor import runtime_storage


LOG = logging.getLogger(__name__)

DEFAULT_PORT = 29418
GERRIT_URI_PREFIX = r'^gerrit:\/\/'


class Rcs(object):
    def __init__(self, uri):
        pass

    def setup(self, **kwargs):
        pass

    def log(self, repo, branch, last_id):
        pass

    def get_last_id(self, repo, branch):
        pass


class Gerrit(Rcs):
    def __init__(self, uri):
        super(Gerrit, self).__init__(uri)

        stripped = re.sub(GERRIT_URI_PREFIX, '', uri)
        if stripped:
            self.hostname, semicolon, self.port = stripped.partition(':')
            if not self.port:
                self.port = DEFAULT_PORT
        else:
            raise Exception('Invalid rcs uri %s' % uri)

        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def setup(self, **kwargs):
        if 'key_filename' in kwargs:
            self.key_filename = kwargs['key_filename']
        else:
            self.key_filename = None

        if 'username' in kwargs:
            self.username = kwargs['username']
        else:
            self.username = None

    def _connect(self):
        self.client.connect(self.hostname, port=self.port,
                            key_filename=self.key_filename,
                            username=self.username)
        LOG.debug('Successfully connected to Gerrit')

    def log(self, repo, branch, last_id):
        module = repo['module']
        LOG.debug('Retrieve reviews from gerrit for project %s', module)

        self._connect()

        cmd = ('gerrit query --all-approvals --patch-sets --format JSON '
               '%(module)s '
               'branch:%(branch)s' %
               {'module': module, 'branch': branch})

        if last_id:
            cmd += ' NOT resume_sortkey:%016x' % (last_id + 1)

        stdin, stdout, stderr = self.client.exec_command(cmd)
        for line in stdout:
            review = json.loads(line)

            if 'sortKey' in review:
                review['module'] = module
                yield review

    def get_last_id(self, repo, branch):
        module = repo['module']
        LOG.debug('Get last id for module %s', module)

        self._connect()

        cmd = ('gerrit query --all-approvals --patch-sets --format JSON '
               '%(module)s branch:%(branch)s limit:1' %
               {'module': module, 'branch': branch})

        stdin, stdout, stderr = self.client.exec_command(cmd)
        for line in stdout:
            review = json.loads(line)
            if 'sortKey' in review:
                return int(review['sortKey'], 16)

        raise Exception('Last id is not found for module %s' % module)


def get_rcs(uri):
    if not uri:
        return Rcs(uri)

    LOG.debug('Review control system is requested for uri %s' % uri)
    match = re.search(GERRIT_URI_PREFIX, uri)
    if match:
        return Gerrit(uri)
    else:
        raise Exception('Unknown review control system for uri %s' % uri)


if __name__ == '__main__':
    conf = cfg.CONF
    conf.register_cli_opts(config.OPTS)
    conf.register_opts(config.OPTS)
    conf()

    rcs = get_rcs('gerrit://review.openstack.org')
    rcs.setup(key_filename='/home/ishakhat/.ssh/4launchpad_id',
              username='shakhat')

    rs = runtime_storage.get_runtime_storage('memcached://127.0.0.1:11211')
    ps = persistent_storage.get_persistent_storage('mongodb://localhost')

    review_processor = record_processor.get_record_processor(
        record_processor.REVIEW_PROCESSOR, ps)

    reviews_iterator = rcs.log({'module': 'stackalytics'}, 'master', 0)
    reviews = list(review_processor.process(reviews_iterator))
    for review in reviews:
        print(review)

    rs.set_records(reviews)

    last_id = rcs.get_last_id({'module': 'stackalytics'}, 'master')
    print(last_id)
