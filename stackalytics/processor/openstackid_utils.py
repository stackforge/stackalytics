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

import collections

from oslo_log import log as logging
import requests

from stackalytics.processor import utils


LOG = logging.getLogger(__name__)

OSID_URI = ('https://openstackid-resources.openstack.org/'
            'api/public/v1/members?'
            'filter=email==%s&relations=all_affiliations')

openstackid_session = requests.Session()


def link_to_launchpad_id(link):
    return link[link.find('~') + 1:]


def _openstack_profile_by_email(email):
    LOG.debug('Lookup user email %s at OpenStackID', email)
    uri = OSID_URI % email
    data = utils.read_json_from_uri(uri, session=openstackid_session)

    if not data:
        return None

    if not data.get('data'):
        return None  # not found

    return data['data'][-1]  # return the last (most recent) record


Interval = collections.namedtuple('Interval', ['start', 'end', 'value'])


def _iterate_intervals(intervals, threshold=60 * 60 * 24):
    """Iterate intervals and fill gaps around of them

    :param intervals: list of Interval objects
    :param threshold: do not yield intervals shorted than threshold
    """
    if not intervals:
        yield Interval(0, 0, None)
    else:
        intervals.sort(key=lambda x: x.start)

        prev_start = 0

        for interval in intervals:
            if interval.start and interval.start - prev_start > threshold:
                yield Interval(prev_start, interval.start, None)  # prior

            yield interval

            prev_start = interval.end

        last_end = intervals[-1].end
        if last_end:
            yield Interval(last_end, 0, None)


def user_profile_by_email(email):
    data = _openstack_profile_by_email(email)

    if not data:  # user is not found
        return None

    intervals = [Interval(a.get('start_date'), a.get('end_date') or 0,
                          a.get('organization', {}).get('name'))
                 for a in data.get('affiliations', [])]
    companies = [dict(company_name=interval.value or '*independent',
                      end_date=interval.end)
                 for interval in _iterate_intervals(intervals)]
    user = {
        'openstack_id': data['id'],
        'user_name': ' '.join([data.get('first_name'), data.get('last_name')]),
        'emails': [email],
        'companies': companies,
    }
    return user
