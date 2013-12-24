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

MEMORY_STORAGE_CACHED = 0


class MemoryStorage(object):
    def __init__(self):
        pass


class CachedMemoryStorage(MemoryStorage):
    def __init__(self):
        super(CachedMemoryStorage, self).__init__()

        # common indexes
        self.records = {}
        self.primary_key_index = {}
        self.record_types_index = {}
        self.module_index = {}
        self.user_id_index = {}
        self.company_index = {}
        self.release_index = {}
        self.blueprint_id_index = {}
        self.company_name_mapping = {}

        self.indexes = {
            'primary_key': self.primary_key_index,
            'record_type': self.record_types_index,
            'company_name': self.company_index,
            'module': self.module_index,
            'user_id': self.user_id_index,
            'release': self.release_index,
        }

    def _save_record(self, record):
        if record.get('company_name') == '*robots':
            return
        self.records[record['record_id']] = record
        for key, index in self.indexes.iteritems():
            self._add_to_index(index, record, key)
        for bp_id in (record.get('blueprint_id') or []):
            if bp_id in self.blueprint_id_index:
                self.blueprint_id_index[bp_id].add(record['record_id'])
            else:
                self.blueprint_id_index[bp_id] = set([record['record_id']])

    def update(self, records):
        have_updates = False

        for record in records:
            have_updates = True
            record_id = record['record_id']
            if record_id in self.records:
                # remove existing record from indexes
                self._remove_record_from_index(self.records[record_id])
            self._save_record(record)

        if have_updates:
            self.company_name_mapping = dict(
                (c.lower(), c) for c in self.company_index.keys())

        return have_updates

    def _remove_record_from_index(self, record):
        for key, index in self.indexes.iteritems():
            index[record[key]].remove(record['record_id'])

    def _add_to_index(self, record_index, record, key):
        record_key = record[key]
        if record_key in record_index:
            record_index[record_key].add(record['record_id'])
        else:
            record_index[record_key] = set([record['record_id']])

    def _get_record_ids_from_index(self, items, index):
        record_ids = set()
        for item in items:
            if item in index:
                record_ids |= index[item]
        return record_ids

    def get_record_ids_by_modules(self, modules):
        return self._get_record_ids_from_index(modules, self.module_index)

    def get_record_ids_by_companies(self, companies):
        return self._get_record_ids_from_index(
            map(self.get_original_company_name, companies),
            self.company_index)

    def get_record_ids_by_user_ids(self, launchpad_ids):
        return self._get_record_ids_from_index(launchpad_ids,
                                               self.user_id_index)

    def get_record_ids_by_releases(self, releases):
        return self._get_record_ids_from_index(releases, self.release_index)

    def get_record_ids_by_blueprint_ids(self, blueprint_ids):
        return self._get_record_ids_from_index(blueprint_ids,
                                               self.blueprint_id_index)

    def get_record_ids(self):
        return self.records.keys()

    def get_record_ids_by_type(self, record_type):
        return self.record_types_index.get(record_type, set())

    def get_records(self, record_ids):
        for i in record_ids:
            yield self.records[i]

    def get_record_by_primary_key(self, primary_key):
        if primary_key in self.primary_key_index:
            record_id = list(self.primary_key_index[primary_key])
            if record_id:
                return self.records[record_id[0]]
        return None

    def get_original_company_name(self, company_name):
        normalized = company_name.lower()
        if normalized not in self.company_name_mapping:
            return normalized
        return self.company_name_mapping[normalized]

    def get_companies(self):
        return self.company_index.keys()

    def get_modules(self):
        return self.module_index.keys()

    def get_user_ids(self):
        return self.user_id_index.keys()


def get_memory_storage(memory_storage_type):
    if memory_storage_type == MEMORY_STORAGE_CACHED:
        return CachedMemoryStorage()
    else:
        raise Exception('Unknown memory storage type %s' % memory_storage_type)
