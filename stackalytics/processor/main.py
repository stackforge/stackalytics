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
import urllib2

from oslo.config import cfg
import psutil
from psutil import _error

from stackalytics.openstack.common import log as logging
from stackalytics.processor import config
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


def process_repo(repo, runtime_storage, commit_processor,
                 rcs_inst, review_processor):
    uri = repo['uri']
    LOG.debug('Processing repo uri %s' % uri)

    vcs_inst = vcs.get_vcs(repo, cfg.CONF.sources_root)
    vcs_inst.fetch()

    for branch in repo['branches']:
        LOG.debug('Processing repo %s, branch %s', uri, branch)

        head_commit_id = runtime_storage.get_head_commit_id(uri, branch)

        commit_iterator = vcs_inst.log(branch, head_commit_id)
        processed_commit_iterator = commit_processor.process(commit_iterator)
        runtime_storage.set_records(processed_commit_iterator, _merge_commits)

        head_commit_id = vcs_inst.get_head_commit_id(branch)
        runtime_storage.set_head_commit_id(uri, branch, head_commit_id)

        LOG.debug('Processing reviews for repo %s, branch %s', uri, branch)

        reviews_iterator = rcs_inst.log(repo, branch, 0)
        processed_review_iterator = review_processor.process(reviews_iterator)
        runtime_storage.set_records(processed_review_iterator)


def update_repos(runtime_storage, persistent_storage):
    repos = persistent_storage.get_repos()
    commit_processor = record_processor.get_record_processor(
        record_processor.COMMIT_PROCESSOR, persistent_storage)
    review_processor = record_processor.get_record_processor(
        record_processor.REVIEW_PROCESSOR, persistent_storage)
    rcs_inst = rcs.get_rcs(cfg.CONF.review_uri)
    rcs_inst.setup(key_filename=cfg.CONF.ssh_key_filename,
                   username=cfg.CONF.ssh_username)

    for repo in repos:
        process_repo(repo, runtime_storage, commit_processor,
                     rcs_inst, review_processor)


def apply_corrections(uri, runtime_storage_inst):
    corrections_fd = urllib2.urlopen(uri)
    raw = corrections_fd.read()
    corrections_fd.close()
    corrections = json.loads(raw)['corrections']
    for c in corrections:
        c['primary_key'] = c['commit_id']
    runtime_storage_inst.apply_corrections(corrections)


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

    if conf.sync_default_data or conf.force_sync_default_data:
        LOG.info('Going to synchronize persistent storage with default data '
                 'from file %s' % cfg.CONF.default_data)
        persistent_storage_inst.sync(cfg.CONF.default_data,
                                     force=conf.force_sync_default_data)
        return 0

    runtime_storage_inst = runtime_storage.get_runtime_storage(
        cfg.CONF.runtime_storage_uri)

    update_pids(runtime_storage_inst)

    update_repos(runtime_storage_inst, persistent_storage_inst)

    apply_corrections(cfg.CONF.corrections_uri, runtime_storage_inst)


if __name__ == '__main__':
    main()
