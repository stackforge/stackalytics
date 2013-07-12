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

import logging

import re
import urllib

import memcache
from oslo.config import cfg

LOG = logging.getLogger(__name__)


class RuntimeStorage(object):
    def __init__(self, uri):
        pass

    def set_records(self, records_iterator):
        pass

    def get_head_commit_id(self, uri, branch):
        pass

    def set_head_commit_id(self, uri, branch, head_commit_id):
        pass

    def get_update(self, pid):
        pass

    def active_pids(self, pids):
        pass

    def get_pid_update_time(self, pid):
        pass

    def set_pid_update_time(self, pid, time):
        pass

    def get_repo_update_time(self):
        pass

    def set_repo_update_time(self, time):
        pass


class MemcachedStorage(RuntimeStorage):

    def __init__(self, uri):
        super(MemcachedStorage, self).__init__(uri)

        stripped = re.sub(r'memcached:\/\/', '', uri)
        if stripped:
            storage_uri = stripped.split(',')
            self.memcached = memcache.Client(storage_uri)
            self._build_index()
        else:
            raise Exception('Invalid storage uri %s' % cfg.CONF.storage_uri)

    def set_records(self, records_iterator):
        for record in records_iterator:
            if record['commit_id'] in self.commit_id_index:
                # update
                record_id = self.commit_id_index[record['commit_id']]
                old_record = self.memcached.get(
                    self._get_record_name(record_id))
                old_record['branches'] |= record['branches']
                LOG.debug('Update record %s' % record)
                self.memcached.set(self._get_record_name(record_id),
                                   old_record)
            else:
                # insert record
                record_id = self._get_record_count()
                record['record_id'] = record_id
                LOG.debug('Insert new record %s' % record)
                self.memcached.set(self._get_record_name(record_id), record)
                self._set_record_count(record_id + 1)

            self._commit_update(record_id)

    def get_head_commit_id(self, uri, branch):
        key = str(urllib.quote_plus(uri) + ':' + branch)
        return self.memcached.get(key)

    def set_head_commit_id(self, uri, branch, head_commit_id):
        key = str(urllib.quote_plus(uri) + ':' + branch)
        self.memcached.set(key, head_commit_id)

    def get_update(self, pid):
        last_update = self.memcached.get('pid:%s' % pid)
        update_count = self._get_update_count()

        self.memcached.set('pid:%s' % pid, update_count)
        self._set_pids(pid)

        if not last_update:
            for record_id in range(0, self._get_record_count()):
                yield self.memcached.get(self._get_record_name(record_id))
        else:
            for update_id in range(last_update, update_count):
                yield self.memcached.get(self._get_record_name(
                    self.memcached.get('update:%s' % update_id)))

    def active_pids(self, pids):
        stored_pids = self.memcached.get('pids') or set()
        for pid in stored_pids:
            if pid not in pids:
                self.memcached.delete('pid:%s' % pid)
                self.memcached.delete('pid_update_time:%s' % pid)

        self.memcached.set('pids', pids)

        # remove unneeded updates
        min_update = self._get_update_count()
        for pid in pids:
            n = self.memcached.get('pid:%s' % pid)
            if n:
                if n < min_update:
                    min_update = n

        first_valid_update_id = self.memcached.get('first_valid_update_id')
        if not first_valid_update_id:
            first_valid_update_id = 0

        for i in range(first_valid_update_id, min_update):
            self.memcached.delete('update:%s' % i)

        self.memcached.set('first_valid_update_id', min_update)

    def get_pid_update_time(self, pid):
        return self.memcached.get('pid_update_time:%s' % pid) or 0

    def set_pid_update_time(self, pid, time):
        self.memcached.set('pid_update_time:%s' % pid, time)

    def get_repo_update_time(self):
        return self.memcached.get('repo_update_time') or 0

    def set_repo_update_time(self, time):
        self.memcached.set('repo_update_time', time)

    def _get_update_count(self):
        return self.memcached.get('update:count') or 0

    def _set_pids(self, pid):
        pids = self.memcached.get('pids') or set()
        if pid in pids:
            return
        pids.add(pid)
        self.memcached.set('pids', pids)

    def _get_record_name(self, record_id):
        return 'record:%s' % record_id

    def _get_record_count(self):
        return self.memcached.get('record:count') or 0

    def _set_record_count(self, count):
        self.memcached.set('record:count', count)

    def _get_all_records(self):
        count = self.memcached.get('record:count') or 0
        for i in range(0, count):
            yield self.memcached.get('record:%s' % i)

    def _commit_update(self, record_id):
        count = self._get_update_count()
        self.memcached.set('update:%s' % count, record_id)
        self.memcached.set('update:count', count + 1)

    def _build_index(self):
        self.commit_id_index = {}
        for record in self._get_all_records():
            self.commit_id_index[record['commit_id']] = record['record_id']


def get_runtime_storage(uri):
    LOG.debug('Runtime storage is requested for uri %s' % uri)
    match = re.search(r'^memcached:\/\/', uri)
    if match:
        return MemcachedStorage(uri)
    else:
        raise Exception('Unknown runtime storage uri %s' % uri)
