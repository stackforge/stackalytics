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

import os
import re
import shutil

import git
import gitdb
from oslo_log import log as logging

from stackalytics.processor import utils


LOG = logging.getLogger(__name__)


class VcsException(Exception):
    pass


class Vcs(object):
    def __init__(self, repo, sources_root):
        self.repo = repo
        self.sources_root = sources_root
        if not os.path.exists(sources_root):
            os.mkdir(sources_root)
        else:
            if not os.access(sources_root, os.W_OK):
                raise Exception('Sources root folder %s is not writable' %
                                sources_root)

    def get_release_index(self):
        pass

    def log(self, branch, head_commit_id=None):
        pass

    def get_last_id(self, branch):
        pass


CO_AUTHOR_PATTERN_RAW = ('(?P<author_name>.*?)\s*'
                         '<?(?P<author_email>[\w\.-]+@[\w\.-]+)>?')
CO_AUTHOR_PATTERN = re.compile(CO_AUTHOR_PATTERN_RAW, re.IGNORECASE)

MESSAGE_PATTERNS = {
    'bug_id': re.compile(r'bug[\s#:]*(?P<id>\d+)', re.IGNORECASE),
    'blueprint_id': re.compile(r'\b(?:blueprint|bp)\b[ \t]*[#:]?[ \t]*'
                               r'(?P<id>[a-z0-9-]+)', re.IGNORECASE),
    'change_id': re.compile('Change-Id: (?P<id>I[0-9a-f]{40})', re.IGNORECASE),
    'coauthor': re.compile(r'(?:Co-Authored-By|Also-By|Co-Author):'
                           r'\s*(?P<id>%s)\s' % CO_AUTHOR_PATTERN_RAW,
                           re.IGNORECASE)
}


def extract_message(s):
    return '\n'.join(line for line in s.splitlines()[1:] if line.strip())


class Git(Vcs):

    def __init__(self, repo, sources_root):
        super(Git, self).__init__(repo, sources_root)
        uri = self.repo['uri']
        match = re.search(r'([^/]+)\.git$', uri)
        if match:
            self.folder = os.path.normpath(
                os.path.join(self.sources_root, match.group(1)))
        else:
            raise Exception('Unexpected uri %s for git' % uri)
        self.git_repo = self._fetch()
        self.release_index = self.get_release_index()

    def _fetch(self):
        LOG.debug('Fetching repo uri %s', self.repo['uri'])

        if os.path.exists(self.folder):
            # check that repo folder is readable and matches configured URI
            repo = git.Repo(self.folder)
            try:
                uri = next(repo.remotes.origin.urls)
            except gitdb.exc.ODBError:
                LOG.error('Unable to get config for git repo %s. Ignore it',
                          self.repo['uri'], exc_info=True)
                return {}

            if uri != self.repo['uri']:
                LOG.warning('Repo uri %(uri)s differs from cloned %(old)s',
                            {'uri': self.repo['uri'], 'old': uri})
                shutil.rmtree(self.folder)

        if not os.path.exists(self.folder):
            try:
                repo = git.Repo.clone_from(self.repo['uri'], self.folder)
            except gitdb.exc.ODBError:
                msg = 'Unable to clone git repo %s into %s' % (
                    self.repo['uri'], self.folder)
                LOG.error(msg, exc_info=True)
                raise VcsException(msg)
        else:
            repo = git.Repo(self.folder)
            try:
                repo.remotes.origin.fetch()
            except gitdb.exc.ODBError:
                LOG.error('Unable to fetch git repo %s. Ignore it',
                          self.repo['uri'], exc_info=True)

        return repo

    def get_release_index(self):
        LOG.debug('Get release index for repo: %s', self.repo['uri'])
        release_index = {}
        for release in self.repo.get('releases', []):
            release_name = release['release_name'].lower()

            if 'branch' in release:
                branch = release['branch']
            else:
                branch = 'master'

            tag_to = release['tag_to']
            if tag_to == 'HEAD':
                tag_to = branch

            if 'tag_from' in release:
                tag_range = release['tag_from'] + '..' + tag_to
            else:
                tag_range = tag_to

            try:
                for rec in self.git_repo.iter_commits(tag_range):
                    release_index[rec.hexsha] = release_name

            except gitdb.exc.ODBError:
                LOG.error('Unable to get log of git repo %s. Ignore it',
                          self.repo['uri'], exc_info=True)
        return release_index

    def log(self, branch, head_commit_id=None):
        LOG.debug('Parsing git log for repo: %s', self.repo['uri'])

        if not self.get_last_id(branch):  # branch not exist
            return

        commit_range = 'origin/' + branch
        if head_commit_id:
            commit_range = head_commit_id + '..' + commit_range

        merge_refs = {}

        for rec in self.git_repo.iter_commits(commit_range):

            if len(rec.parents) > 1:  # merge commit
                for one in rec.parents[1:]:  # first refers to commit in master
                    merge_refs[one.hexsha] = rec
                continue

            if not rec.author.email:
                # ignore commits with empty email (there are some < Essex)
                continue

            commit = {
                'commit_id': rec.hexsha,
                'author_name': rec.author.name,
                'author_email': utils.keep_safe_chars(rec.author.email),
                'date': rec.authored_date,
                'author_date': rec.authored_date,
                'subject': rec.summary,
                'message': extract_message(rec.message),
                'module': self.repo['module'],
                'branches': {branch},
                'files_changed': rec.stats.total['files'],
                'lines_added': rec.stats.total['insertions'],
                'lines_deleted': rec.stats.total['deletions'],
            }

            # update with date and author of merge
            if rec.hexsha in merge_refs:
                mc = merge_refs[rec.hexsha]
                commit.update({
                    'date': mc.authored_date,  # override with merge date
                    'merge_author_name': mc.author.name,
                    'merge_author_email': utils.keep_safe_chars(
                        mc.author.email),
                })

            # extract attributes out of commit message
            for pattern_name, pattern in MESSAGE_PATTERNS.items():
                collection = set()
                for item in re.finditer(pattern, commit['message']):
                    collection.add(item.group('id'))
                if collection:
                    commit[pattern_name] = list(sorted(collection))

            # set release if we know for sure
            if commit['commit_id'] in self.release_index:
                commit['release'] = self.release_index[commit['commit_id']]
            else:
                commit['release'] = None

            if commit['release'] == 'ignored':
                # drop commits that are marked by 'ignored' release
                continue

            # make link to blueprint (legacy)
            if 'blueprint_id' in commit:
                commit['blueprint_id'] = [(commit['module'] + ':' + bp_name)
                                          for bp_name
                                          in commit['blueprint_id']]

            # extract co-authors out of the message
            if 'coauthor' in commit:
                verified_coauthors = []
                for coauthor in commit['coauthor']:
                    m = re.match(CO_AUTHOR_PATTERN, coauthor)
                    if m and utils.check_email_validity(
                            m.group("author_email")):
                        verified_coauthors.append(m.groupdict())

                if verified_coauthors:
                    commit['coauthor'] = verified_coauthors
                else:
                    del commit['coauthor']  # no valid authors

            yield commit

    def get_last_id(self, branch):
        LOG.debug('Get head commit for repo uri: %s', self.git_repo)

        try:
            return self.git_repo.commit('origin/' + branch).hexsha
        except gitdb.exc.ODBError:
            LOG.error('Unable to get HEAD for git repo %s. Ignore it',
                      self.git_repo, exc_info=True)

        return None


def get_vcs(repo, sources_root):
    uri = repo['uri']
    LOG.debug('Factory is asked for VCS uri: %s', uri)
    match = re.search(r'\.git$', uri)
    if match:
        return Git(repo, sources_root)
    else:
        LOG.warning('Unsupported VCS, fallback to dummy')
        return Vcs(repo, uri)
