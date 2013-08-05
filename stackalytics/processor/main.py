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
import urllib

from oslo.config import cfg
import psutil
from psutil import _error

from stackalytics.openstack.common import log as logging
from stackalytics.processor import config
from stackalytics.processor import default_data_processor
from stackalytics.processor import persistent_storage
from stackalytics.processor import rcs
from stackalytics.processor import record_processor
from stackalytics.processor import runtime_storage
from stackalytics.processor import vcs


LOG = logging.getLogger(__name__)


def get_pids():
    uwsgi_dict = {}
    for pid in psutil.get_pid_list():
        try:
            p = psutil.Process(pid)
            if p.cmdline and p.cmdline[0].find('/uwsgi'):
                if p.parent:
                    uwsgi_dict[p.pid] = p.parent.pid
        except _error.NoSuchProcess:
            # the process may disappear after get_pid_list call, ignore it
            pass

    result = set()
    for pid in uwsgi_dict:
        if uwsgi_dict[pid] in uwsgi_dict:
            result.add(pid)

    return result


def update_pids(runtime_storage):
    pids = get_pids()
    if not pids:
        return
    runtime_storage.active_pids(pids)


def _merge_commits(original, new):
    if new['branches'] < original['branches']:
        return False
    else:
        original['branches'] |= new['branches']
        return True


def _record_typer(record_iterator, record_type):
    for record in record_iterator:
        record['record_type'] = record_type
        yield record


def process_repo(repo, runtime_storage, record_processor_inst):
    uri = repo['uri']
    LOG.debug('Processing repo uri %s' % uri)

    vcs_inst = vcs.get_vcs(repo, cfg.CONF.sources_root)
    vcs_inst.fetch()

    rcs_inst = rcs.get_rcs(repo, cfg.CONF.review_uri)
    rcs_inst.setup(key_filename=cfg.CONF.ssh_key_filename,
                   username=cfg.CONF.ssh_username)

    for branch in repo['branches']:
        LOG.debug('Processing repo %s, branch %s', uri, branch)

        vcs_key = 'vcs:' + str(urllib.quote_plus(uri) + ':' + branch)
        last_id = runtime_storage.get_last_id(vcs_key)

        commit_iterator = vcs_inst.log(branch, last_id)
        commit_iterator_typed = _record_typer(commit_iterator, 'commit')
        processed_commit_iterator = record_processor_inst.process(
            commit_iterator_typed)
        runtime_storage.set_records(processed_commit_iterator, _merge_commits)

        last_id = vcs_inst.get_last_id(branch)
        runtime_storage.set_last_id(vcs_key, last_id)

        LOG.debug('Processing reviews for repo %s, branch %s', uri, branch)

        rcs_key = 'rcs:' + str(urllib.quote_plus(uri) + ':' + branch)
        last_id = runtime_storage.get_last_id(rcs_key)

        review_iterator = rcs_inst.log(branch, last_id)
        review_iterator_typed = _record_typer(review_iterator, 'review')
        processed_review_iterator = record_processor_inst.process(
            review_iterator_typed)
        runtime_storage.set_records(processed_review_iterator)

        last_id = rcs_inst.get_last_id(branch)
        runtime_storage.set_last_id(rcs_key, last_id)


def update_repos(runtime_storage, persistent_storage_inst):
    repos = persistent_storage_inst.find('repos')
    record_processor_inst = record_processor.RecordProcessor(
        persistent_storage_inst)

    for repo in repos:
        process_repo(repo, runtime_storage, record_processor_inst)


def apply_corrections(uri, runtime_storage_inst):
    LOG.info('Applying corrections from uri %s', uri)
    corrections_fd = urllib.urlopen(uri)
    raw = corrections_fd.read()
    corrections_fd.close()
    corrections = json.loads(raw)['corrections']
    valid_corrections = []
    for c in corrections:
        if 'primary_key' in c:
            valid_corrections.append(c)
        else:
            LOG.warn('Correction misses primary key: %s', c)
    runtime_storage_inst.apply_corrections(valid_corrections)


def _read_default_data(uri):
    try:
        fd = urllib.urlopen(uri)
        raw = fd.read()
        fd.close()
        return json.loads(raw)
    except Exception as e:
        LOG.error('Error while reading config: %s' % e)


def main():
    # init conf and logging
    conf = cfg.CONF
    conf.register_cli_opts(config.OPTS)
    conf.register_opts(config.OPTS)
    conf()

    logging.setup('stackalytics')
    LOG.info('Logging enabled')

    persistent_storage_inst = persistent_storage.get_persistent_storage(
        cfg.CONF.persistent_storage_uri)

    runtime_storage_inst = runtime_storage.get_runtime_storage(
        cfg.CONF.runtime_storage_uri)

    default_data = _read_default_data(cfg.CONF.default_data_uri)
    default_data_processor.process(persistent_storage_inst,
                                   runtime_storage_inst,
                                   default_data,
                                   cfg.CONF.sources_root)

    update_pids(runtime_storage_inst)

    update_repos(runtime_storage_inst, persistent_storage_inst)

    apply_corrections(cfg.CONF.corrections_uri, runtime_storage_inst)


if __name__ == '__main__':
    main()
