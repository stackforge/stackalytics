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
import logging
import re

from sh import curl

LOG = logging.getLogger(__name__)


COMMIT_PROCESSOR_DUMMY = 0
COMMIT_PROCESSOR_CACHED = 1


class CommitProcessor(object):
    def __init__(self, persistent_storage):
        self.persistent_storage = persistent_storage

    def process(self, commit_iterator, repo, branch):
        pass


class DummyProcessor(CommitProcessor):
    def __init__(self, persistent_storage):
        super(DummyProcessor, self).__init__(persistent_storage)

    def process(self, commit_iterator, repo, branch):
        return commit_iterator


class CachedProcessor(CommitProcessor):
    def __init__(self, persistent_storage):
        super(CachedProcessor, self).__init__(persistent_storage)

        domains = persistent_storage.get_domains()
        self.domains_index = dict(
            [(i['domain'], i['company_name']) for i in domains])

        users = persistent_storage.get_users()
        self.users_index = {}
        for user in users:
            for email in user['emails']:
                self.users_index[email] = user

    def _find_company(self, companies, date):
        for r in companies:
            if date < r['end_date']:
                return r['company_name']
        return companies[-1]['company_name']

    def process(self, commit_iterator, repo, branch):

        for commit in commit_iterator:

            commit['branch'] = branch
            commit['repo'] = repo['uri']

            email = commit['author_email'].lower()
            if email in self.users_index:
                user = self.users_index[email]
                commit['launchpad_id'] = user['launchpad_id']
                commit['company_name'] = self._find_company(user['companies'],
                                                            commit['date'])
            else:
                lp_profile_json = curl('-k',
                                       'https://api.launchpad.net/1.0/people/'
                                       '?ws.op=getByEmail&email=%s' % email)
                if not lp_profile_json:
                    commit['launchpad_id'] = None
                    commit['company_name'] = self.domains_index['']
                else:
                    lp_profile = json.loads(lp_profile_json)
                    company = self._get_company_by_email(email)
                    user = {
                        'launchpad_id': lp_profile['name'],
                        'user_name': lp_profile['display_name'],
                        'emails': [email],
                        'companies': {
                            'company_name': company,
                            'end_date': 0
                        }
                    }

                    # todo user may already exist, but his email was not
                    # known to us  for existing user we may get a different
                    # company -> make a record that he changed job
                    self.users_index[lp_profile['name']] = user
                    self.persistent_storage.insert_user(user)
                    commit['launchpad_id'] = user['launchpad_id']
                    commit['company_name'] = company

            yield commit

    def _get_company_by_email(self, email):
        match = re.match(r'([\w\d_-]+\.\w+)$', email)
        if match:
            domain = match.group(1)
            if domain in self.domains_index:
                return self.domains_index[match.group(1)]
        return self.domains_index['']


class CommitProcessorFactory(object):
    @staticmethod
    def get_processor(commit_processor_type, persistent_storage):
        if commit_processor_type == COMMIT_PROCESSOR_DUMMY:
            return DummyProcessor(persistent_storage)
        elif commit_processor_type == COMMIT_PROCESSOR_CACHED:
            return CachedProcessor(persistent_storage)
        else:
            raise Exception('Unknown commit processor type %s' %
                            commit_processor_type)
