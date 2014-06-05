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

import functools
import json

import flask
import six
from werkzeug import exceptions

from dashboard import helpers
from dashboard import parameters
from dashboard import vault
from stackalytics.openstack.common import log as logging
from stackalytics.processor import utils
from stackalytics import version as stackalytics_version


LOG = logging.getLogger(__name__)


def _prepare_params(kwargs, ignore):
    params = kwargs.get('_params')

    if not params:
        params = {'action': flask.request.path}
        for key in parameters.FILTER_PARAMETERS:
            params[key] = parameters.get_parameter(kwargs, key, key)

        if params['start_date']:
            params['start_date'] = [utils.round_timestamp_to_day(
                params['start_date'][0])]
        if params['end_date']:
            params['end_date'] = [utils.round_timestamp_to_day(
                params['end_date'][0])]

        kwargs['_params'] = params

    if ignore:
        return dict([(k, v if k not in ignore else [])
                     for k, v in six.iteritems(params)])
    else:
        return params


def cached(ignore=None):
    def decorator(func):
        @functools.wraps(func)
        def prepare_params_decorated_function(*args, **kwargs):

            params = _prepare_params(kwargs, ignore)

            cache_inst = vault.get_vault()['cache']
            key = json.dumps(params)
            value = cache_inst.get(key)

            if not value:
                value = func(*args, **kwargs)
                cache_inst[key] = value
                vault.get_vault()['cache_size'] += len(key) + len(value)
                LOG.debug('Cache size: %(size)d, entries: %(len)d',
                          {'size': vault.get_vault()['cache_size'],
                           'len': len(cache_inst.keys())})

            return value

        return prepare_params_decorated_function

    return decorator


def record_filter(ignore=None):

    def decorator(f):

        def _filter_records_by_days(start_date, end_date, memory_storage_inst):
            if start_date:
                start_date = utils.date_to_timestamp_ext(start_date[0])
            else:
                start_date = memory_storage_inst.get_first_record_day()
            if end_date:
                end_date = utils.date_to_timestamp_ext(end_date[0])
            else:
                end_date = utils.date_to_timestamp_ext('now')

            start_day = utils.timestamp_to_day(start_date)
            end_day = utils.timestamp_to_day(end_date)

            return memory_storage_inst.get_record_ids_by_days(
                six.moves.range(start_day, end_day + 1))

        def _filter_records_by_modules(memory_storage_inst, mr):
            selected = set([])
            for m, r in mr:
                if r is None:
                    selected |= memory_storage_inst.get_record_ids_by_modules(
                        [m])
                else:
                    selected |= (
                        memory_storage_inst.get_record_ids_by_module_release(
                            m, r))
            return selected

        def _intersect(first, second):
            if first is not None:
                return first & second
            return second

        @functools.wraps(f)
        def record_filter_decorated_function(*args, **kwargs):

            memory_storage_inst = vault.get_memory_storage()
            record_ids = None

            params = _prepare_params(kwargs, ignore)

            release = params['release']
            if release:
                if 'all' not in release:
                    record_ids = (
                        memory_storage_inst.get_record_ids_by_releases(
                            c.lower() for c in release))

            project_type = params['project_type']
            mr = None
            if project_type:
                mr = set(vault.resolve_modules(vault.resolve_project_types(
                    project_type), release))

            module = params['module']
            if module:
                mr = _intersect(mr, set(vault.resolve_modules(
                    module, release)))

            if mr is not None:
                record_ids = _intersect(
                    record_ids, _filter_records_by_modules(
                        memory_storage_inst, mr))

            user_id = params['user_id']
            user_id = [u for u in user_id
                       if vault.get_user_from_runtime_storage(u)]
            if user_id:
                record_ids = _intersect(
                    record_ids,
                    memory_storage_inst.get_record_ids_by_user_ids(user_id))

            company = params['company']
            if company:
                record_ids = _intersect(
                    record_ids,
                    memory_storage_inst.get_record_ids_by_companies(company))

            metric = params['metric']
            if 'all' not in metric:
                for metric in metric:
                    if metric in parameters.METRIC_TO_RECORD_TYPE:
                        record_ids = _intersect(
                            record_ids,
                            memory_storage_inst.get_record_ids_by_type(
                                parameters.METRIC_TO_RECORD_TYPE[metric]))

            if 'tm_marks' in metric:
                filtered_ids = []
                review_nth = int(parameters.get_parameter(
                    kwargs, 'review_nth')[0])
                for record in memory_storage_inst.get_records(record_ids):
                    parent = memory_storage_inst.get_record_by_primary_key(
                        record['review_id'])
                    if (parent and ('review_number' in parent) and
                            (parent['review_number'] <= review_nth)):
                        filtered_ids.append(record['record_id'])
                record_ids = filtered_ids

            blueprint_id = params['blueprint_id']
            if blueprint_id:
                record_ids = _intersect(
                    record_ids,
                    memory_storage_inst.get_record_ids_by_blueprint_ids(
                        blueprint_id))

            start_date = params['start_date']
            end_date = params['end_date']

            if start_date or end_date:
                record_ids = _intersect(
                    record_ids, _filter_records_by_days(start_date, end_date,
                                                        memory_storage_inst))

            kwargs['record_ids'] = record_ids
            kwargs['records'] = memory_storage_inst.get_records(record_ids)

            return f(*args, **kwargs)

        return record_filter_decorated_function

    return decorator


def incremental_filter(result, record, param_id, context):
    result[record[param_id]]['metric'] += 1


def loc_filter(result, record, param_id, context):
    result[record[param_id]]['metric'] += record['loc']


def mark_filter(result, record, param_id, context):
    result_by_param = result[record[param_id]]
    if record['type'] == 'Workflow' and record['value'] == 1:
        value = 'A'
    else:
        value = record['value']
        result_by_param['metric'] += 1
    result_by_param[value] = result_by_param.get(value, 0) + 1

    if record.get('disagreement'):
        result_by_param['disagreements'] = (
            result_by_param.get('disagreements', 0) + 1)


def mark_finalize(record):
    new_record = record.copy()

    positive = 0
    numeric = 0
    mark_distribution = []
    for key in [-2, -1, 1, 2, 'A']:
        if key in record:
            if key in [1, 2]:
                positive += record[key]
            if key in [-2, -1, 1, 2]:
                numeric += record[key]
            mark_distribution.append(str(record[key]))
        else:
            mark_distribution.append('0')
            new_record[key] = 0

    new_record['disagreements'] = record.get('disagreements', 0)
    if numeric:
        positive_ratio = '%.1f%%' % (
            (positive * 100.0) / numeric)
        new_record['disagreement_ratio'] = '%.1f%%' % (
            (record.get('disagreements', 0) * 100.0) / numeric)
    else:
        positive_ratio = helpers.INFINITY_HTML
        new_record['disagreement_ratio'] = helpers.INFINITY_HTML
    new_record['mark_ratio'] = (
        '|'.join(mark_distribution) + ' (' + positive_ratio + ')')
    new_record['positive_ratio'] = positive_ratio

    return new_record


def person_day_filter(result, record, param_id, context):
    if record['record_type'] == 'commit' or record['record_type'] == 'member':
        # 1. commit is attributed with the date of the merge which is not an
        # effort of the author (author's effort is represented in patches)
        # 2. registration on openstack.org is not an effort
        return

    day = utils.timestamp_to_day(record['date'])
    # fact that record-days are grouped by days in some order is used
    if context.get('last_processed_day') != day:
        context['last_processed_day'] = day
        context['counted_user_ids'] = set()

    user = vault.get_user_from_runtime_storage(record['user_id'])
    user_id = user['seq']

    value = record[param_id]
    if user_id not in context['counted_user_ids']:
        context['counted_user_ids'].add(user_id)
        result[value]['metric'] += 1


def generate_records_for_person_day(record_ids):
    memory_storage_inst = vault.get_memory_storage()
    for values in memory_storage_inst.day_index.values():
        for record in memory_storage_inst.get_records(record_ids & values):
            yield record


def aggregate_filter():
    def decorator(f):
        @functools.wraps(f)
        def aggregate_filter_decorated_function(*args, **kwargs):

            metric_param = (flask.request.args.get('metric') or
                            parameters.get_default('metric'))
            metric = metric_param.lower()

            metric_to_filters_map = {
                'commits': (None, None),
                'loc': (loc_filter, None),
                'marks': (mark_filter, mark_finalize),
                'tm_marks': (mark_filter, mark_finalize),
                'emails': (incremental_filter, None),
                'bpd': (incremental_filter, None),
                'bpc': (incremental_filter, None),
                'members': (incremental_filter, None),
                'person-day': (person_day_filter, None),
            }
            if metric not in metric_to_filters_map:
                metric = parameters.get_default('metric')

            kwargs['metric_filter'] = metric_to_filters_map[metric][0]
            kwargs['finalize_handler'] = metric_to_filters_map[metric][1]

            if metric == 'person-day':
                kwargs['records'] = generate_records_for_person_day(
                    kwargs['record_ids'])

            return f(*args, **kwargs)

        return aggregate_filter_decorated_function

    return decorator


def exception_handler():
    def decorator(f):
        @functools.wraps(f)
        def exception_handler_decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                if isinstance(e, exceptions.HTTPException):
                    raise  # ignore Flask exceptions
                LOG.exception(e)
                flask.abort(404)

        return exception_handler_decorated_function

    return decorator


def templated(template=None, return_code=200):
    def decorator(f):
        @functools.wraps(f)
        def templated_decorated_function(*args, **kwargs):

            vault_inst = vault.get_vault()
            template_name = template
            if template_name is None:
                template_name = (flask.request.endpoint.replace('.', '/') +
                                 '.html')
            ctx = f(*args, **kwargs)
            if ctx is None:
                ctx = {}

            # put parameters into template
            metric = flask.request.args.get('metric')
            if metric not in parameters.METRIC_LABELS:
                metric = None
            ctx['metric'] = metric or parameters.get_default('metric')
            ctx['metric_label'] = parameters.METRIC_LABELS[ctx['metric']]

            project_type = flask.request.args.get('project_type')
            if not vault.is_project_type_valid(project_type):
                project_type = parameters.get_default('project_type')
            ctx['project_type'] = project_type

            release = flask.request.args.get('release')
            releases = vault_inst['releases']
            if release:
                release = release.lower()
                if release != 'all':
                    if release not in releases:
                        release = None
                    else:
                        release = releases[release]['release_name']
            ctx['release'] = (release or
                              parameters.get_default('release')).lower()
            ctx['review_nth'] = (flask.request.args.get('review_nth') or
                                 parameters.get_default('review_nth'))

            ctx['project_type_options'] = vault.get_project_types()
            ctx['release_options'] = vault.get_release_options()
            ctx['metric_options'] = sorted(parameters.METRIC_LABELS.items(),
                                           key=lambda x: x[0])

            ctx['company'] = parameters.get_single_parameter(kwargs, 'company')
            ctx['company_original'] = (
                vault.get_memory_storage().get_original_company_name(
                    ctx['company']))

            module = parameters.get_single_parameter(kwargs, 'module')
            ctx['module'] = module
            if module and module in vault_inst['module_id_index']:
                ctx['module_inst'] = vault_inst['module_id_index'][module]

            ctx['user_id'] = parameters.get_single_parameter(kwargs, 'user_id')
            ctx['page_title'] = helpers.make_page_title(
                ctx['company'], ctx['user_id'], ctx['module'], ctx['release'])
            ctx['stackalytics_version'] = (
                stackalytics_version.version_info.version_string())
            ctx['stackalytics_release'] = (
                stackalytics_version.version_info.release_string())
            ctx['runtime_storage_update_time'] = (
                vault_inst['runtime_storage_update_time'])

            return flask.render_template(template_name, **ctx), return_code

        return templated_decorated_function

    return decorator


def jsonify(root='data'):
    def decorator(func):
        @functools.wraps(func)
        def jsonify_decorated_function(*args, **kwargs):
            value = func(*args, **kwargs)
            if isinstance(value, tuple):
                result = dict([(root[i], value[i])
                               for i in six.moves.range(min(len(value),
                                                            len(root)))])
            else:
                result = {root: value}
            return json.dumps(result)

        return jsonify_decorated_function

    return decorator


def response():
    def decorator(func):
        @functools.wraps(func)
        def response_decorated_function(*args, **kwargs):
            callback = flask.app.request.args.get('callback', False)
            data = func(*args, **kwargs)

            if callback:
                data = str(callback) + '(' + data + ')'
                mimetype = 'application/javascript'
            else:
                mimetype = 'application/json'

            return flask.current_app.response_class(data, mimetype=mimetype)

        return response_decorated_function

    return decorator


def query_filter(query_param='query'):
    def decorator(f):
        @functools.wraps(f)
        def query_filter_decorated_function(*args, **kwargs):

            query = flask.request.args.get(query_param)
            if query:
                kwargs['query_filter'] = lambda x: x.lower().find(query) >= 0
            else:
                kwargs['query_filter'] = lambda x: True

            return f(*args, **kwargs)

        return query_filter_decorated_function

    return decorator
