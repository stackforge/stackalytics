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
import logging

import os
import re

from oslo.config import cfg
from sh import git


LOG = logging.getLogger(__name__)


class Vcs(object):
    def __init__(self, uri):
        self.uri = uri
        self.dir = re.search(r'([^\/]+)\.git$', uri).group(1)

    def fetch(self):
        pass

    def log(self, branch, head_commit_id):
        pass

    def get_head_commit_id(self, branch):
        pass


GIT_LOG_PARAMS = [
    ('commit_id', '%H'),
    ('date', '%at'),
    ('author', '%an'),
    ('author_email', '%ae'),
    ('author_email', '%ae'),
    ('subject', '%s'),
    ('message', '%b'),
]
GIT_LOG_FORMAT = ''.join([(r[0] + ':' + r[1] + '%n')
                          for r in GIT_LOG_PARAMS]) + 'diff_stat:'
GIT_LOG_PATTERN = re.compile(''.join([(r[0] + ':(.*?)\n')
                                      for r in GIT_LOG_PARAMS]) +
                             'diff_stat:' +
                             '[^\d]+(\d+)[^\d]*(\d+)[^\d]*(\d+)', re.DOTALL)

MESSAGE_PATTERNS = {
    'bug_id': re.compile('bug\s+#?([\d]{5,7})', re.IGNORECASE),
    'blueprint_id': re.compile('blueprint\s+([\w-]{6,})', re.IGNORECASE),
    'change_id': re.compile('Change-Id: (I[0-9a-f]{40})', re.IGNORECASE),
}


class Git(Vcs):
    def fetch(self):
        LOG.debug('Fetching repo uri %s' % self.uri)

        match = re.search(r'\/([\w\d_-]+)\.git', self.uri)
        if not match:
            raise Exception('Cannot parse uri %s' % self.uri)

        folder_name = match.group(1)
        folder = os.path.normpath(cfg.CONF.sources_root + '/' + folder_name)

        if not os.path.exists(folder):
            os.chdir(cfg.CONF.sources_root)
            git('clone', '%s' % self.uri)
        else:
            os.chdir(folder)
            git('pull', 'origin')

    def log(self, branch, head_commit_id):
        LOG.debug('Parsing git log for repo uri %s' % self.uri)

        git('checkout', '%s' % branch)
        commit_range = 'HEAD'
        if head_commit_id:
            commit_range = head_commit_id + '..HEAD'
        output = git('log', '--pretty=%s' % GIT_LOG_FORMAT, '--numstat', '-M',
                     '--no-merges', commit_range, _tty_out=False)

        for rec in re.finditer(GIT_LOG_PATTERN, str(output)):
            i = 1
            commit = {}
            for param in GIT_LOG_PARAMS:
                commit[param[0]] = rec.group(i)
                i += 1

            commit['files_changed'] = rec.group(i)
            i += 1
            commit['lines_added'] = rec.group(i)
            i += 1
            commit['lines_deleted'] = rec.group(i)

            for key in MESSAGE_PATTERNS:
                match = re.search(MESSAGE_PATTERNS[key], commit['message'])
                if match:
                    commit[key] = match.group(1)
                else:
                    commit[key] = None

            yield commit

    def get_head_commit_id(self, branch):
        LOG.debug('Get head commit for repo uri %s' % self.uri)

        git('checkout', '%s' % branch)
        return str(git('rev-parse', 'HEAD')).strip()


class VcsFactory(object):

    @staticmethod
    def get_vcs(uri):
        LOG.debug('Factory is asked for Vcs uri %s' % uri)
        match = re.search(r'\.git$', uri)
        if match:
            return Git(uri)
            #todo others vcs to be implemented
