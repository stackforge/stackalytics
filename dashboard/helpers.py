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

import datetime
import re

from flask.ext import gravatar as gravatar_ext
import six

from dashboard import parameters
from dashboard import vault
from stackalytics.processor import utils


INFINITY_HTML = '&#x221E;'

gravatar = gravatar_ext.Gravatar(None, size=64, rating='g', default='wavatar')


def _extend_author_fields(record):
    record['author_link'] = make_link(
        record['author_name'], '/',
        {'user_id': record['user_id'], 'company': ''})
    record['company_link'] = make_link(
        record['company_name'], '/',
        {'company': record['company_name'], 'user_id': ''})
    record['gravatar'] = gravatar(record.get('author_email', 'stackalytics'))


def _extend_record_common_fields(record):
    _extend_author_fields(record)
    record['date_str'] = format_datetime(record['date'])
    record['module_link'] = make_link(
        record['module'], '/',
        {'module': record['module'], 'company': '', 'user_id': ''})
    record['blueprint_id_count'] = len(record.get('blueprint_id', []))
    record['bug_id_count'] = len(record.get('bug_id', []))

    for coauthor in record.get('coauthor') or []:
        _extend_author_fields(coauthor)


def _extend_by_parent_info(record, parent):
    parent = vault.extend_record(parent)
    _extend_record_common_fields(parent)
    for k, v in six.iteritems(parent):
        record['parent_' + k] = v


def extend_record(record):
    record = vault.extend_record(record)
    _extend_record_common_fields(record)

    if record['record_type'] == 'commit':
        record['branches'] = ','.join(record['branches'])
        if 'correction_comment' not in record:
            record['correction_comment'] = ''
        record['message'] = make_commit_message(record)
        if record['commit_date']:
            record['commit_date_str'] = format_datetime(record['commit_date'])
    elif record['record_type'] == 'mark':
        parent = vault.get_memory_storage().get_record_by_primary_key(
            record['review_id'])
        if not parent:
            return None

        _extend_by_parent_info(record, parent)
    elif record['record_type'] == 'patch':
        parent = vault.get_memory_storage().get_record_by_primary_key(
            record['review_id'])
        _extend_by_parent_info(record, parent)
    elif record['record_type'] == 'email':
        record['email_link'] = record.get('email_link') or ''
        record['blueprint_links'] = []
        for bp_id in record.get('blueprint_id', []):
            bp_module, bp_name = bp_id.split(':')
            record['blueprint_links'].append(
                make_blueprint_link(bp_module, bp_name))
    elif record['record_type'] in ['bpd', 'bpc']:
        record['summary'] = utils.format_text(record['summary'])
        if record.get('mention_count'):
            record['mention_date_str'] = format_datetime(
                record['mention_date'])
        record['blueprint_link'] = make_blueprint_link(record['module'],
                                                       record['name'])

    return record


def extend_user(user):
    user = user.copy()

    user['id'] = user['user_id']
    user['text'] = user['user_name']
    if user['companies']:
        company_name = user['companies'][-1]['company_name']
        user['company_link'] = make_link(
            company_name, '/', {'company': company_name, 'user_id': ''})
    else:
        user['company_link'] = ''
    if user['emails']:
        user['gravatar'] = gravatar(user['emails'][0])
    else:
        user['gravatar'] = gravatar(user['user_id'])

    return user


def get_activity(records, start_record, page_size, query_message=None):
    if query_message:
        records = [vault.extend_record(r) for r in records]
        records = [r for r in records
                   if (r.get('message') and
                       r.get('message').find(query_message) > 0)]
    records_sorted = sorted(records, key=lambda x: x['date'], reverse=True)

    result = []
    for record in records_sorted[start_record:]:
        processed_record = extend_record(record)
        if processed_record:
            result.append(processed_record)
            if len(result) == page_size:
                break

    return result


def get_contribution_summary(records):
    marks = dict((m, 0) for m in [-2, -1, 0, 1, 2, 'A'])
    commit_count = 0
    loc = 0
    drafted_blueprint_count = 0
    completed_blueprint_count = 0
    email_count = 0

    for record in records:
        record_type = record['record_type']
        if record_type == 'commit':
            commit_count += 1
            loc += record['loc']
        elif record['record_type'] == 'mark':
            if record['type'] == 'APRV':
                marks['A'] += 1
            else:
                marks[record['value']] += 1
        elif record['record_type'] == 'email':
            email_count += 1
        elif record['record_type'] == 'bpd':
            drafted_blueprint_count += 1
        elif record['record_type'] == 'bpc':
            completed_blueprint_count += 1

    result = {
        'drafted_blueprint_count': drafted_blueprint_count,
        'completed_blueprint_count': completed_blueprint_count,
        'commit_count': commit_count,
        'email_count': email_count,
        'loc': loc,
        'marks': marks,
    }
    return result


def format_datetime(timestamp):
    return datetime.datetime.utcfromtimestamp(
        timestamp).strftime('%d %b %Y %H:%M:%S')


def format_date(timestamp):
    return datetime.datetime.utcfromtimestamp(timestamp).strftime('%d %b %Y')


def format_launchpad_module_link(module):
    return '<a href="https://launchpad.net/%s">%s</a>' % (module, module)


def make_link(title, uri=None, options=None):
    param_names = ('release', 'project_type', 'module', 'company', 'user_id',
                   'metric')
    param_values = {}
    for param_name in param_names:
        v = parameters.get_parameter({}, param_name, param_name)
        if v:
            param_values[param_name] = ','.join(v)
    if options:
        param_values.update(options)
    if param_values:
        uri += '?' + '&'.join(['%s=%s' % (n, utils.safe_encode(v))
                               for n, v in six.iteritems(param_values)])
    return '<a href="%(uri)s">%(title)s</a>' % {'uri': uri, 'title': title}


def make_blueprint_link(module, name):
    uri = '/report/blueprint/' + module + '/' + name
    return '<a href="%(uri)s">%(title)s</a>' % {'uri': uri, 'title': name}


def make_commit_message(record):
    s = record['message']
    module = record['module']

    s = utils.format_text(s)

    # insert links
    s = re.sub(re.compile('(blueprint\s+)([\w-]+)', flags=re.IGNORECASE),
               r'\1<a href="https://blueprints.launchpad.net/' +
               module + r'/+spec/\2" class="ext_link">\2</a>', s)
    s = re.sub(re.compile('(bug[\s#:]*)([\d]{5,7})', flags=re.IGNORECASE),
               r'\1<a href="https://bugs.launchpad.net/bugs/\2" '
               r'class="ext_link">\2</a>', s)
    s = re.sub(r'\s+(I[0-9a-f]{40})',
               r' <a href="https://review.openstack.org/#q,\1,n,z" '
               r'class="ext_link">\1</a>', s)

    s = utils.unwrap_text(s)
    return s


def make_page_title(company, user_id, module, release):
    if company:
        memory_storage = vault.get_memory_storage()
        company = memory_storage.get_original_company_name(company)
    if company or user_id:
        if user_id:
            s = vault.get_user_from_runtime_storage(user_id)['user_name']
            if company:
                s += ' (%s)' % company
        else:
            s = company
    else:
        s = 'OpenStack community'
    s += ' contribution'
    if module:
        s += ' to %s' % module
    if release != 'all':
        s += ' in %s release' % release.capitalize()
    else:
        s += ' in all releases'
    return s
