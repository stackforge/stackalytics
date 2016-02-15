# Copyright (c) 2016 OpenStack Foundation
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

import datetime
import re
import time

from oslo_log import log as logging
import requests

from stackalytics.processor import utils


LOG = logging.getLogger(__name__)

DAY = 24 * 60 * 60
ZANATA_URI = 'https://translate.openstack.org/rest/%s'
ZANATA_VERSION_PATTERN = re.compile(r'^(master|stable-[a-z]+)$')
ZANATA_FIRST_RECORD = '2015-09-01'

zanata_session = requests.Session()


def zanata_get_projects():
    uri = ZANATA_URI % 'projects'
    LOG.debug("Reading projects from %s" % uri)
    projects_data = utils.read_json_from_uri(uri, session=zanata_session)

    return (p['id'] for p in projects_data)


def _is_valid_version(version):
    return ZANATA_VERSION_PATTERN.match(version)


def _zanata_get_project_versions(project_id):
    LOG.debug("Reading iterations for project %s" % project_id)
    uri = ZANATA_URI % ('projects/p/%s' % project_id)
    project_data = utils.read_json_from_uri(uri, session=zanata_session)

    for iteration_data in project_data.get('iterations') or []:
        if _is_valid_version(iteration_data['id']):
            yield iteration_data['id']


def _zanata_get_user_stats(project_id, iteration_id, zanata_user_id,
                           start_date, end_date):
    uri = ZANATA_URI % ('stats/project/%s/version/%s/contributor/%s/%s..%s'
                        % (project_id, iteration_id, zanata_user_id,
                           start_date, end_date))
    return utils.read_json_from_uri(uri, session=zanata_session)


def _timestamp_to_date(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')


def _date_to_timestamp(d):
    return int(time.mktime(
        datetime.datetime.strptime(d, '%Y-%m-%d').timetuple()))


def log(runtime_storage_inst):

    last_update_key = 'zanata:last_update'
    last_update = (runtime_storage_inst.get_by_key(last_update_key) or
                   _date_to_timestamp(ZANATA_FIRST_RECORD))
    now = time.time()

    languages = runtime_storage_inst.get_by_key('languages')

    users = [u for u in runtime_storage_inst.get_all_users()
             if 'zanata_id' in u]

    project_list = zanata_get_projects()
    for project_id in project_list:
        for version in _zanata_get_project_versions(project_id):
            for user in users:
                user_id = user['zanata_id']

                for day in range(int(last_update), int(now), DAY):
                    day_str = _timestamp_to_date(day)

                    stats = _zanata_get_user_stats(
                        project_id, version, user_id, day_str, day_str)
                    user_stats = stats[user_id]

                    if user_stats:
                        for lang, data in user_stats.items():
                            record = dict(
                                zanata_id=user_id,
                                date=day,
                                language_code=lang,
                                language=languages.get(lang) or lang,
                                translated=data['translated'],
                                approved=data['approved'],
                                module=project_id,
                                branch=version,  # todo adapt version to branch
                            )
                            yield record

    runtime_storage_inst.set_by_key(last_update_key, last_update)
