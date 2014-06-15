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

import re
import time

import ldap
import six

from stackalytics.openstack.common import log as logging
from stackalytics.processor import utils


LOG = logging.getLogger(__name__)

LDAP_URI_PREFIX = r'^ldap:\/\/'
NAME_AND_DATE_PATTERN = r'<h3>(?P<member_name>[^<]*)[\s\S]*?' \
                        r'<div class="span-7 last">(?P<date_joined>[^<]*)'
COMPANY_PATTERN = r'<strong>Date\sJoined[\s\S]*?<b>(?P<company_draft>[^<]*)' \
                  r'[\s\S]*?From\s(?P<date_from>[\s\S]*?)\(Current\)'
CNT_EMPTY_MEMBERS = 50


class Mps(object):
    def __init__(self, uri):
        self.uri = uri

    def setup(self):
        pass

    def log(self):
        pass


class Web(Mps):

    def __init__(self, uri):
        self.uri = uri

    def _convert_str_fields_to_unicode(self, result):
        for field, value in result.iteritems():
            if type(value) is str:
                try:
                    value = six.text_type(value, 'utf8')
                    result[field] = value
                except Exception:
                    pass

    def _retrieve_member(self, member_id, html_parser):

        content = utils.read_uri(self.uri)

        if not content:
            return {}

        member = {}

        for rec in re.finditer(NAME_AND_DATE_PATTERN, content):
            result = rec.groupdict()

            member['member_id'] = member_id
            member['member_name'] = result['member_name']
            member['date_joined'] = result['date_joined']
            member['member_uri'] = self.uri
            break

        member['company_draft'] = '*independent'
        for rec in re.finditer(COMPANY_PATTERN, content):
            result = rec.groupdict()

            company_draft = html_parser.unescape(result['company_draft'])
            member['company_draft'] = company_draft

        return member

    def log(self, runtime_storage_inst, days_to_update_members):
        LOG.debug('Retrieving new openstack.org members')

        last_update_members_date = runtime_storage_inst.get_by_key(
            'last_update_members_date') or 0
        last_member_index = runtime_storage_inst.get_by_key(
            'last_member_index') or 0

        update_interval_seconds = days_to_update_members * 24 * 60 * 60
        end_update_date = int(time.time()) - update_interval_seconds

        if last_update_members_date <= end_update_date:
            last_member_index = 0
            last_update_members_date = int(time.time())

            runtime_storage_inst.set_by_key('last_update_members_date',
                                            last_update_members_date)

        cnt_empty = 0
        cur_index = last_member_index + 1
        html_parser = six.moves.html_parser.HTMLParser()

        while cnt_empty < CNT_EMPTY_MEMBERS:

            profile_uri = self.uri + str(cur_index)
            member = self._retrieve_member(profile_uri,
                                           str(cur_index), html_parser)

            if 'member_name' not in member:
                cnt_empty += 1
                cur_index += 1
                continue

            self._convert_str_fields_to_unicode(member)

            cnt_empty = 0
            last_member_index = cur_index
            cur_index += 1
            LOG.debug('New member: %s', member['member_id'])
            yield member

        LOG.debug('Last_member_index: %s', last_member_index)
        runtime_storage_inst.set_by_key('last_member_index', last_member_index)


class Ldap(Mps):

    def __init__(self, uri, **kwargs):
        super(Ldap, self).__init__(uri)
        self.base_dn = kwargs.get('base_dn')

    def setup(self):
        self.connection = ldap.initialize(self.uri)

    def _connect(self):
        try:
            self.connection.start_tls_s()
            self.bind_s()
        except ldap.INVALID_CREDENTIALS:
            LOG.error("LDAP Credentials are invalid %s" % self.server)
        except ldap.LDAPError:
            LOG.error("Could not connect to LDAP Server %s" % self.server)

    def _disconnect(self):
        self.connection.unbind()

    def log(self, runtime_storage_inst=None, days_to_update_members=None):
        filter = '(objectclass=identityPerson)'

        try:
            users = self.connection.search_s(self.base_dn,
                                             ldap.SCOPE_SUBTREE, filter)
        except ldap.LDAPError as e:
            LOG.error("%s" % e)

        for user in users:
            LOG.debug('New member: %s', user)
            # The data we want is on the right side of the user tuple
            data = user[1]
            member = {}
            member['member_id'] = data.get('uid', None)
            member['member_name'] = data.get('cn', None)
            member['date_joined'] = None
            member['country'] = data.get("country", None)
            member['company_draft'] = data.get("o", "*independent")
            member['email'] = data.get("mail", None)
            yield member


def get_mps(uri):
    LOG.debug('Member list is requested for uri %s' % uri)
    match = re.search(LDAP_URI_PREFIX, uri)
    if match:
        return Ldap(uri)
    else:
        return Web(uri)
