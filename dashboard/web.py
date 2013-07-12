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

import cgi
import datetime
import functools
import json
import os
import re
import urllib

import flask
from flask.ext import gravatar as gravatar_ext
import time

from dashboard import memory_storage
from stackalytics.processor import persistent_storage
from stackalytics.processor import runtime_storage
from stackalytics.processor import user_utils


# Constants and Parameters ---------

DEBUG = True
RUNTIME_STORAGE_URI = 'memcached://127.0.0.1:11211'
PERSISTENT_STORAGE_URI = 'mongodb://localhost'

DEFAULTS = {
    'metric': 'commits',
    'release': 'havana',
    'project_type': 'openstack',
}

METRIC_LABELS = {
    'loc': 'Lines of code',
    'commits': 'Commits',
}

PROJECT_TYPES = {
    'openstack': 'OpenStack',
    'stackforge': 'StackForge',
}

DEFAULT_RECORDS_LIMIT = 10


# Application objects ---------

app = flask.Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('DASHBOARD_CONF', silent=True)


def get_vault():
    vault = getattr(app, 'stackalytics_vault', None)
    if not vault:
        vault = {}
        vault['runtime_storage'] = runtime_storage.get_runtime_storage(
            RUNTIME_STORAGE_URI)
        vault['persistent_storage'] = (
            persistent_storage.get_persistent_storage(
                PERSISTENT_STORAGE_URI))
        vault['memory_storage'] = memory_storage.get_memory_storage(
            memory_storage.MEMORY_STORAGE_CACHED,
            vault['runtime_storage'].get_update(os.getpid()))

        releases = vault['persistent_storage'].get_releases()
        vault['releases'] = dict((r['release_name'].lower(), r)
                                 for r in releases)
        modules = vault['persistent_storage'].get_repos()
        vault['modules'] = dict((r['module'].lower(),
                                 r['project_type'].lower()) for r in modules)
        app.stackalytics_vault = vault
    return vault


def get_memory_storage():
    return get_vault()['memory_storage']


# Utils ---------

def get_default(param_name):
    if param_name in DEFAULTS:
        return DEFAULTS[param_name]
    else:
        return None


def get_parameter(kwargs, singular_name, plural_name, use_default=True):
    if singular_name in kwargs:
        p = kwargs[singular_name]
    else:
        p = (flask.request.args.get(singular_name) or
             flask.request.args.get(plural_name))
    if p:
        return p.split(',')
    elif use_default:
        default = get_default(singular_name)
        return [default] if default else None
    else:
        return []


# Decorators ---------

def record_filter(ignore=None, use_default=True):
    if not ignore:
        ignore = []

    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):

            vault = get_vault()
            memory_storage = vault['memory_storage']
            record_ids = memory_storage.get_record_ids()

            if 'module' not in ignore:
                param = get_parameter(kwargs, 'module', 'modules', use_default)
                if param:
                    record_ids &= (
                        memory_storage.get_record_ids_by_modules(param))

            if 'project_type' not in ignore:
                param = get_parameter(kwargs, 'project_type', 'project_types',
                                      use_default)
                if param:
                    modules = [module for module, project_type
                               in vault['modules'].iteritems()
                               if project_type in param]
                    record_ids &= (
                        memory_storage.get_record_ids_by_modules(modules))

            if 'launchpad_id' not in ignore:
                param = get_parameter(kwargs, 'launchpad_id', 'launchpad_ids')
                if param:
                    record_ids &= (
                        memory_storage.get_record_ids_by_launchpad_ids(param))

            if 'company' not in ignore:
                param = get_parameter(kwargs, 'company', 'companies')
                if param:
                    record_ids &= (
                        memory_storage.get_record_ids_by_companies(param))

            if 'release' not in ignore:
                param = get_parameter(kwargs, 'release', 'releases',
                                      use_default)
                if param:
                    if 'all' not in param:
                        record_ids &= (
                            memory_storage.get_record_ids_by_releases(
                                c.lower() for c in param))

            kwargs['records'] = memory_storage.get_records(record_ids)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def aggregate_filter():
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):

            metric_param = (flask.request.args.get('metric') or
                            get_default('metric'))
            metric = metric_param.lower()
            if metric == 'commits':
                metric_filter = lambda r: 1
            elif metric == 'loc':
                metric_filter = lambda r: r['loc']
            else:
                raise Exception('Invalid metric %s' % metric)

            kwargs['metric_filter'] = metric_filter
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def exception_handler():
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                print e
                flask.abort(404)

        return decorated_function

    return decorator


def templated(template=None):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):

            vault = get_vault()
            template_name = template
            if template_name is None:
                template_name = (flask.request.endpoint.replace('.', '/') +
                                 '.html')
            ctx = f(*args, **kwargs)
            if ctx is None:
                ctx = {}

            # put parameters into template
            metric = flask.request.args.get('metric')
            if metric not in METRIC_LABELS:
                metric = None
            ctx['metric'] = metric or get_default('metric')
            ctx['metric_label'] = METRIC_LABELS[ctx['metric']]

            project_type = flask.request.args.get('project_type')
            if project_type not in PROJECT_TYPES:
                project_type = None
            ctx['project_type'] = project_type or get_default('project_type')
            ctx['project_type_label'] = PROJECT_TYPES[ctx['project_type']]

            release = flask.request.args.get('release')
            releases = vault['releases']
            if release:
                release = release.lower()
                if release not in releases:
                    release = None
                else:
                    release = releases[release]['release_name']
            ctx['release'] = (release or get_default('release')).lower()

            return flask.render_template(template_name, **ctx)

        return decorated_function

    return decorator


# Handlers ---------

@app.route('/')
@templated()
def overview():
    pass


@app.errorhandler(404)
def page_not_found(e):
    return flask.render_template('404.html'), 404


def contribution_details(records, limit=DEFAULT_RECORDS_LIMIT):
    blueprints_map = {}
    bugs_map = {}
    commits = []
    loc = 0

    for record in records:
        loc += record['loc']
        commits.append(record)
        blueprint = record['blueprint_id']
        if blueprint:
            if blueprint in blueprints_map:
                blueprints_map[blueprint].append(record)
            else:
                blueprints_map[blueprint] = [record]

        bug = record['bug_id']
        if bug:
            if bug in bugs_map:
                bugs_map[bug].append(record)
            else:
                bugs_map[bug] = [record]

    blueprints = sorted([{'id': key,
                          'module': value[0]['module'],
                          'records': value}
                         for key, value in blueprints_map.iteritems()],
                        key=lambda x: x['id'])
    bugs = sorted([{'id': key, 'records': value}
                   for key, value in bugs_map.iteritems()],
                  key=lambda x: x['id'])
    commits.sort(key=lambda x: x['date'], reverse=True)

    result = {
        'blueprints': blueprints,
        'bugs': bugs,
        'commits': commits[0:limit],
        'loc': loc,
    }
    return result


@app.route('/companies/<company>')
@exception_handler()
@templated()
@record_filter()
def company_details(company, records):
    details = contribution_details(records)
    details['company'] = company
    return details


@app.route('/modules/<module>')
@exception_handler()
@templated()
@record_filter()
def module_details(module, records):
    details = contribution_details(records)
    details['module'] = module
    return details


@app.route('/engineers/<launchpad_id>')
@exception_handler()
@templated()
@record_filter()
def engineer_details(launchpad_id, records):
    persistent_storage = get_vault()['persistent_storage']
    user = list(persistent_storage.get_users(launchpad_id=launchpad_id))[0]

    details = contribution_details(records)
    details['launchpad_id'] = launchpad_id
    details['user'] = user
    return details


# AJAX Handlers ---------

def _get_aggregated_stats(records, metric_filter, keys, param_id,
                          param_title=None):
    param_title = param_title or param_id
    result = dict((c, 0) for c in keys)
    titles = {}
    for record in records:
        result[record[param_id]] += metric_filter(record)
        titles[record[param_id]] = record[param_title]

    response = [{'id': r, 'metric': result[r], 'name': titles[r]}
                for r in result if result[r]]
    response.sort(key=lambda x: x['metric'], reverse=True)
    return response


@app.route('/data/companies')
@exception_handler()
@record_filter()
@aggregate_filter()
def get_companies(records, metric_filter):
    response = _get_aggregated_stats(records, metric_filter,
                                     get_memory_storage().get_companies(),
                                     'company_name')
    return json.dumps(response)


@app.route('/data/modules')
@exception_handler()
@record_filter()
@aggregate_filter()
def get_modules(records, metric_filter):
    response = _get_aggregated_stats(records, metric_filter,
                                     get_memory_storage().get_modules(),
                                     'module')
    return json.dumps(response)


@app.route('/data/engineers')
@exception_handler()
@record_filter()
@aggregate_filter()
def get_engineers(records, metric_filter):
    response = _get_aggregated_stats(records, metric_filter,
                                     get_memory_storage().get_launchpad_ids(),
                                     'launchpad_id', 'author')
    return json.dumps(response)


@app.route('/data/timeline')
@exception_handler()
@record_filter(ignore='release')
def timeline(records, **kwargs):
    # find start and end dates
    release_names = get_parameter(kwargs, 'release', 'releases')
    releases = get_vault()['releases']
    if not release_names:
        flask.abort(404)
    if not (set(release_names) & set(releases.keys())):
        flask.abort(404)
    release = releases[release_names[0]]

    start_date = release_start_date = user_utils.timestamp_to_week(
        user_utils.date_to_timestamp(release['start_date']))
    end_date = release_end_date = user_utils.timestamp_to_week(
        user_utils.date_to_timestamp(release['end_date']))
    now = user_utils.timestamp_to_week(int(time.time()))

    # expand start-end to year if needed
    if release_end_date - release_start_date < 52:
        expansion = (52 - (release_end_date - release_start_date)) // 2
        if release_end_date + expansion < now:
            end_date += expansion
        else:
            end_date = now
        start_date = end_date - 52

    # empty stats for all weeks in range
    weeks = range(start_date, end_date)
    week_stat_loc = dict((c, 0) for c in weeks)
    week_stat_commits = dict((c, 0) for c in weeks)
    week_stat_commits_hl = dict((c, 0) for c in weeks)

    # fill stats with the data
    for record in records:
        week = record['week']
        if week in weeks:
            week_stat_loc[week] += record['loc']
            week_stat_commits[week] += 1
            if 'all' in release_names or record['release'] in release_names:
                week_stat_commits_hl[week] += 1

    # form arrays in format acceptable to timeline plugin
    array_loc = []
    array_commits = []
    array_commits_hl = []

    for week in weeks:
        week_str = user_utils.week_to_date(week)
        array_loc.append([week_str, week_stat_loc[week]])
        array_commits.append([week_str, week_stat_commits[week]])
        array_commits_hl.append([week_str, week_stat_commits_hl[week]])

    return json.dumps([array_commits, array_commits_hl, array_loc])


# Jinja Filters ---------

@app.template_filter('datetimeformat')
def format_datetime(timestamp):
    return datetime.datetime.utcfromtimestamp(
        timestamp).strftime('%d %b %Y @ %H:%M')


@app.template_filter('launchpadmodule')
def format_launchpad_module_link(module):
    return '<a href="https://launchpad.net/%s">%s</a>' % (module, module)


@app.template_filter('encode')
def safe_encode(s):
    return urllib.quote_plus(s)


@app.template_filter('link')
def make_link(title, uri=None):
    param_names = ('release', 'metric', 'project_type')
    param_values = {}
    for param_name in param_names:
        v = get_parameter({}, param_name, param_name)
        if v:
            param_values[param_name] = ','.join(v)
    if param_values:
        uri += '?' + '&'.join(['%s=%s' % (n, v)
                               for n, v in param_values.iteritems()])
    return '<a href="%(uri)s">%(title)s</a>' % {'uri': uri, 'title': title}


@app.template_filter('commit_message')
def make_commit_message(record):
    s = record['message']
    module = record['module']

    # clear text
    s = cgi.escape(re.sub(re.compile('\n{2,}', flags=re.MULTILINE), '\n', s))

    # insert links
    s = re.sub(re.compile('(blueprint\s+)([\w-]+)', flags=re.IGNORECASE),
               r'\1<a href="https://blueprints.launchpad.net/' +
               module + r'/+spec/\2">\2</a>', s)
    s = re.sub(re.compile('(bug\s+)#?([\d]{5,7})', flags=re.IGNORECASE),
               r'\1<a href="https://bugs.launchpad.net/bugs/\2">\2</a>', s)
    s = re.sub(r'\s+(I[0-9a-f]{40})',
               r' <a href="https://review.openstack.org/#q,\1,n,z">\1</a>', s)
    return s


gravatar = gravatar_ext.Gravatar(app, size=100, rating='g',
                                 default='wavatar')

if __name__ == '__main__':
    app.run('0.0.0.0')
