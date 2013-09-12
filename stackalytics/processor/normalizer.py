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

from stackalytics.openstack.common import log as logging
from stackalytics.processor import utils

LOG = logging.getLogger(__name__)


def get_user_id(launchpad_id, email):
    return launchpad_id or email


def normalize_user(user):
    user['emails'] = [email.lower() for email in user['emails']]
    if user['launchpad_id']:
        user['launchpad_id'] = user['launchpad_id'].lower()

    for c in user['companies']:
        end_date_numeric = 0
        if c['end_date']:
            end_date_numeric = utils.date_to_timestamp(c['end_date'])
        c['end_date'] = end_date_numeric

    # sort companies by end_date
    def end_date_comparator(x, y):
        if x["end_date"] == 0:
            return 1
        elif y["end_date"] == 0:
            return -1
        else:
            return cmp(x["end_date"], y["end_date"])

    user['companies'].sort(cmp=end_date_comparator)
    user['user_id'] = get_user_id(user['launchpad_id'], user['emails'][0])


def _normalize_users(users):
    for user in users:
        if ('launchpad_id' not in user) or ('emails' not in user):
            LOG.warn('Skipping invalid user: %s', user)
            continue

        normalize_user(user)


def _normalize_releases(releases):
    for release in releases:
        release['release_name'] = release['release_name'].lower()
        release['end_date'] = utils.date_to_timestamp(release['end_date'])
    releases.sort(key=lambda x: x['end_date'])


def _normalize_repos(repos):
    for repo in repos:
        if 'releases' not in repo:
            repo['releases'] = []  # release will be assigned automatically


NORMALIZERS = {
    'users': _normalize_users,
    'releases': _normalize_releases,
    'repos': _normalize_repos,
}


def normalize_default_data(default_data):
    for key, normalizer in NORMALIZERS.iteritems():
        if key in default_data:
            normalizer(default_data[key])
