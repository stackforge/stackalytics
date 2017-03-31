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

import collections
import uuid

import mock
import testtools

from stackalytics.processor import vcs


Author = collections.namedtuple('Author', ['name', 'email'])
Stats = collections.namedtuple('Stats', ['total'])
Commit = collections.namedtuple(
    'Commit', ['hexsha', 'author', 'authored_date', 'parents', 'summary',
               'message', 'stats'])


class RepoMock(object):
    def __init__(self, commits):
        self.commits = commits
        super(RepoMock, self).__init__()

    def iter_commits(self, commits_range):
        for commit in self.commits:
            yield commit


class TestVcsProcessor(testtools.TestCase):
    def setUp(self):
        super(TestVcsProcessor, self).setUp()

    @mock.patch('stackalytics.processor.vcs.Git._fetch')
    @mock.patch('stackalytics.processor.vcs.Git.get_last_id')
    def test_log_commit(self, mock_gli, mock_fetch):
        repo_dfn = dict(module='dummy', uri='git://github.com/dummy/dummy.git')
        message = '''
Fixes bug 1167901.
Implements blueprint fix-me.

This commit also removes backslashes for line break.

Change-Id: Id26fdfd2af4862652d7270aec132d40662efeb96
        '''
        commit_id = uuid.uuid4().hex
        parent_id = uuid.uuid4().hex
        source_commit = Commit(
            hexsha=commit_id,
            author=Author('Homer Simpson', 'homer@simpson.name'),
            authored_date=1234567890,
            parents=[parent_id],
            summary='Remove class-based import in the code repo',
            message=message,
            stats=Stats(dict(insertions=12, deletions=23, files=2)))
        mock_fetch.return_value = RepoMock([source_commit])

        git_vcs = vcs.Git(repo_dfn, '/tmp')

        observed_commits = list(git_vcs.log('master', None))

        self.assertEqual(1, len(observed_commits))

        expected_commit = {
            'author_email': 'homer@simpson.name',
            'author_name': 'Homer Simpson', 'authored_date': 1234567890,
            'blueprint_id': ['dummy:fix-me'],
            'branches': {'master'},
            'bug_id': ['1167901'],
            'change_id': ['Id26fdfd2af4862652d7270aec132d40662efeb96'],
            'commit_id': commit_id,
            'date': 1234567890,
            'files_changed': 2, 'lines_added': 12, 'lines_deleted': 23,
            'message': 'Fixes bug 1167901.\nImplements blueprint '
                       'fix-me.\nThis commit also removes backslashes for '
                       'line break.\nChange-Id: '
                       'Id26fdfd2af4862652d7270aec132d40662efeb96',
            'module': 'dummy', 'release': None,
            'subject': 'Remove class-based import in the code repo'
        }

        self.assertEqual(expected_commit, observed_commits[0])

    @mock.patch('stackalytics.processor.vcs.Git._fetch')
    @mock.patch('stackalytics.processor.vcs.Git.get_last_id')
    def test_log_commit_with_coauthors(self, mock_gli, mock_fetch):
        repo_dfn = dict(module='dummy', uri='git://github.com/dummy/dummy.git')
        message = '''
Simpsons have a party!

Co-Authored-By: Bart <bart@simpson.name>
Also-By: Lisa <lisa@simpson.name>
Also-By: Anonymous <wrong@email>

Change-Id: Id26fdfd2af4862652d7270aec132d40662efeb96
        '''
        commit_id = uuid.uuid4().hex
        parent_id = uuid.uuid4().hex
        source_commit = Commit(
            hexsha=commit_id,
            author=Author('Homer Simpson', 'homer@simpson.name'),
            authored_date=1234567890,
            parents=[parent_id],
            summary='Remove class-based import in the code repo',
            message=message,
            stats=Stats(dict(insertions=12, deletions=23, files=2)))
        mock_fetch.return_value = RepoMock([source_commit])

        git_vcs = vcs.Git(repo_dfn, '/tmp')

        observed_commits = list(git_vcs.log('master', None))

        self.assertEqual(1, len(observed_commits))

        expected_commit = {
            'author_email': 'homer@simpson.name',
            'author_name': 'Homer Simpson', 'authored_date': 1234567890,
            'branches': {'master'},
            'change_id': ['Id26fdfd2af4862652d7270aec132d40662efeb96'],
            'coauthor': [
                {'author_email': 'bart@simpson.name', 'author_name': 'Bart'},
                {'author_email': 'lisa@simpson.name', 'author_name': 'Lisa'}],
            'commit_id': commit_id,
            'date': 1234567890,
            'files_changed': 2, 'lines_added': 12, 'lines_deleted': 23,
            'message': 'Simpsons have a party!\nCo-Authored-By: Bart '
                       '<bart@simpson.name>\nAlso-By: Lisa '
                       '<lisa@simpson.name>\nAlso-By: Anonymous '
                       '<wrong@email>\nChange-Id: '
                       'Id26fdfd2af4862652d7270aec132d40662efeb96',
            'module': 'dummy', 'release': None,
            'subject': 'Remove class-based import in the code repo'
        }

        self.assertEqual(expected_commit, observed_commits[0])

    @mock.patch('stackalytics.processor.vcs.Git._fetch')
    @mock.patch('stackalytics.processor.vcs.Git.get_last_id')
    def test_log_commit_with_merge(self, mock_gli, mock_fetch):
        repo_dfn = dict(module='dummy', uri='git://github.com/dummy/dummy.git')
        commit_id = uuid.uuid4().hex
        commit_parent_id = uuid.uuid4().hex
        merge_parent_ids = [uuid.uuid4().hex, commit_id]
        source_commit = Commit(
            hexsha=commit_id,
            author=Author('Homer Simpson', 'homer@simpson.name'),
            authored_date=1234567890,
            parents=[commit_parent_id],
            summary='Commit summary',
            message='Commit message',
            stats=Stats(dict(insertions=12, deletions=23, files=2)))
        merge_commit = Commit(
            hexsha=commit_id,
            author=Author('Jenkins', 'jenkins@openstack.org'),
            authored_date=1234567899,
            parents=merge_parent_ids,
            summary='Merge of Commit summary',
            message='Commit message',
            stats=Stats(dict(insertions=12, deletions=23, files=2)))
        mock_fetch.return_value = RepoMock([merge_commit, source_commit])

        git_vcs = vcs.Git(repo_dfn, '/tmp')

        observed_commits = list(git_vcs.log('master', None))

        self.assertEqual(1, len(observed_commits))

        expected_commit = {
            'author_email': 'homer@simpson.name',
            'author_name': 'Homer Simpson', 'authored_date': 1234567890,
            'branches': {'master'},
            'commit_id': commit_id,
            'date': 1234567899,
            'files_changed': 2, 'lines_added': 12, 'lines_deleted': 23,
            'merge_author_email': 'jenkins@openstack.org',
            'merge_author_name': 'Jenkins',
            'message': '',
            'module': 'dummy', 'release': None,
            'subject': 'Commit summary'
        }

        self.assertEqual(expected_commit, observed_commits[0])
