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

import itertools
import time

import mock
import six
import testtools

from spectrometer.processor import record_processor
from spectrometer.processor import runtime_storage
from spectrometer.processor import utils


RELEASES = [
    {
        'release_name': 'prehistory',
        'end_date': utils.date_to_timestamp('2011-Apr-21')
    },
    {
        'release_name': 'Diablo',
        'end_date': utils.date_to_timestamp('2011-Sep-08')
    },
    {
        'release_name': 'Zoo',
        'end_date': utils.date_to_timestamp('2035-Sep-08')
    },
]

REPOS = [
    {
        "branches": ["master"],
        "module": "stackalytics",
        "project_type": "stackforge",
        "uri": "git://github.com/stackforge/stackalytics.git"
    }
]


class TestRecordProcessor(testtools.TestCase):
    def setUp(self):
        super(TestRecordProcessor, self).setUp()

    def tearDown(self):
        super(TestRecordProcessor, self).tearDown()

    # get_company_by_email
    def test_get_company_by_email_mapped(self):
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}]
        )
        email = 'jdoe@ibm.com'
        res = record_processor_inst._get_company_by_email(email)
        self.assertEqual('IBM', res)

    def test_get_company_by_email_with_long_suffix_mapped(self):
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'NEC', 'domains': ['nec.co.jp']}]
        )
        email = 'man@mxw.nes.nec.co.jp'
        res = record_processor_inst._get_company_by_email(email)
        self.assertEqual('NEC', res)

    def test_get_company_by_email_with_long_suffix_mapped_2(self):
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'NEC',
                        'domains': ['nec.co.jp', 'nec.com']}]
        )
        email = 'man@mxw.nes.nec.com'
        res = record_processor_inst._get_company_by_email(email)
        self.assertEqual('NEC', res)

    def test_get_company_by_email_not_mapped(self):
        record_processor_inst = self.make_record_processor()
        email = 'foo@boo.com'
        res = record_processor_inst._get_company_by_email(email)
        self.assertEqual(None, res)

    # commit processing
    def test_process_commit_existing_user(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': '*independent',
                         'end_date': 1234567890},
                        {'company_name': 'NEC',
                         'end_date': 0},
                    ]
                }
            ])

        processed_commit = list(record_processor_inst.process(
            generate_commits(author_email='johndoe@gmail.com',
                             author_name='John Doe')))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_commit_existing_user_old_job(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': '*independent',
                         'end_date': 1234567890},
                        {'company_name': 'NEC',
                         'end_date': 0},
                    ]
                }
            ])

        processed_commit = list(record_processor_inst.process(
            generate_commits(author_email='johndoe@gmail.com',
                             author_name='John Doe',
                             date=1000000000)))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': '*independent',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_commit_existing_user_new_email_known_company(self):
        # User is known but his email is new to us, and maps to other
        # company. Will create a new user with no ldap_id
        record_processor_inst = self.make_record_processor(
            users=[
                {'user_id': 'john_doe',
                 'ldap_id': 'john_doe',
                 'user_name': 'John Doe',
                 'emails': ['johndoe@nec.co.jp'],
                 'companies': [{'company_name': 'NEC', 'end_date': 0}]}
            ],
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}])

        processed_commit = list(record_processor_inst.process(
            generate_commits(author_email='johndoe@ibm.com',
                             author_name='John Doe')))[0]

        expected_commit = {
            'ldap_id': None,
            'author_email': 'johndoe@ibm.com',
            'author_name': 'John Doe',
            'company_name': 'IBM',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)
        self.assertIn('johndoe@ibm.com', utils.load_user(
            record_processor_inst.runtime_storage_inst,
            'johndoe@ibm.com')['emails']
        )

    def test_process_commit_new_user(self):
        # User is new to us. Should set user name and empty ldap_id
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}])

        processed_commit = list(record_processor_inst.process(
            generate_commits(author_email='johndoe@ibm.com',
                             author_name='John Doe')))[0]

        expected_commit = {
            'ldap_id': None,
            'author_email': 'johndoe@ibm.com',
            'author_name': 'John Doe',
            'company_name': 'IBM',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)
        user = utils.load_user(
            record_processor_inst.runtime_storage_inst, 'johndoe@ibm.com')
        self.assertIn('johndoe@ibm.com', user['emails'])
        self.assertEqual('IBM', user['companies'][0]['company_name'])
        self.assertEqual(None, user['ldap_id'])

    # process records complex scenarios
    def test_create_member(self):
        member_record = {'member_id': '123456789',
                         'member_name': 'John Doe',
                         'member_uri': 'http://www.openstack.org/community'
                                       '/members/profile/123456789',
                         'date_joined': 'August 01, 2012 ',
                         'company_draft': 'Mirantis'}

        record_processor_inst = self.make_record_processor()
        result_member = record_processor_inst._process_member(
            member_record).next()

        self.assertEqual(result_member['primary_key'], 'member:123456789')
        self.assertEqual(result_member['date'], utils.member_date_to_timestamp(
            'August 01, 2012 '))
        self.assertEqual(result_member['author_name'], 'John Doe')
        self.assertEqual(result_member['company_name'], 'Mirantis')

        result_user = utils.load_user(
            record_processor_inst.runtime_storage_inst, 'member:123456789')

        self.assertEqual(result_user['user_name'], 'John Doe')
        self.assertEqual(result_user['company_name'], 'Mirantis')
        self.assertEqual(result_user['companies'],
                         [{'company_name': 'Mirantis', 'end_date': 0}])

    def test_create_member_ldap(self):
        member_record = {'member_id': 'dave-tucker',
                         'ldap_id': 'dave-tucker',
                         'member_name': 'Dave Tucker',
                         'date_joined': None,
                         'country': 'Great Britain',
                         'company_draft': 'Red Hat',
                         'email': 'dave@dtucker.co.uk'}

        record_processor_inst = self.make_record_processor()
        result_member = record_processor_inst._process_member(
            member_record).next()

        self.assertEqual(result_member['primary_key'], 'member:dave-tucker')
        self.assertEqual(result_member['date'], 0)
        self.assertEqual(result_member['author_name'], 'Dave Tucker')
        self.assertEqual(result_member['company_name'], 'Red Hat')

        result_user = utils.load_user(
            record_processor_inst.runtime_storage_inst, 'dave-tucker')

        self.assertEqual(result_user['user_name'], 'Dave Tucker')
        self.assertEqual(result_user['company_name'], 'Red Hat')
        self.assertEqual(result_user['companies'],
                         [{'company_name': 'Red Hat', 'end_date': 0}])

    def test_update_member(self):
        member_record = {'member_id': '123456789',
                         'member_name': 'John Doe',
                         'member_uri': 'http://www.openstack.org/community'
                                       '/members/profile/123456789',
                         'date_joined': 'August 01, 2012 ',
                         'company_draft': 'Mirantis'}

        record_processor_inst = self.make_record_processor()

        updated_member_record = member_record
        updated_member_record['member_name'] = 'Bill Smith'
        updated_member_record['company_draft'] = 'Rackspace'

        result_member = record_processor_inst._process_member(
            updated_member_record).next()
        self.assertEqual(result_member['author_name'], 'Bill Smith')
        self.assertEqual(result_member['company_name'], 'Rackspace')

        result_user = utils.load_user(
            record_processor_inst.runtime_storage_inst, 'member:123456789')

        self.assertEqual(result_user['user_name'], 'Bill Smith')
        self.assertEqual(result_user['companies'],
                         [{'company_name': 'Rackspace', 'end_date': 0}])

    def test_update_member_ldap(self):
        member_record = {'member_id': 'dave-tucker',
                         'ldap_id': 'dave-tucker',
                         'member_name': 'Dave Tucker',
                         'date_joined': None,
                         'country': 'Great Britain',
                         'company_draft': 'Red Hat',
                         'email': 'dave@dtucker.co.uk'}

        record_processor_inst = self.make_record_processor()

        updated_member_record = member_record
        updated_member_record['member_name'] = 'Baldrick'
        updated_member_record['company_draft'] = 'HP'

        result_member = record_processor_inst._process_member(
            updated_member_record).next()
        self.assertEqual(result_member['author_name'], 'Baldrick')
        self.assertEqual(result_member['company_name'], 'HP')

        result_user = utils.load_user(
            record_processor_inst.runtime_storage_inst, 'dave-tucker')

        self.assertEqual(result_user['user_name'], 'Baldrick')
        self.assertEqual(result_user['companies'],
                         [{'company_name': 'HP', 'end_date': 0}])

    def test_process_email_then_review(self):
        # it is expected that the user profile will contain both email and
        # ldap-id
        record_processor_inst = self.make_record_processor()

        list(record_processor_inst.process([
            {'record_type': 'email',
             'message_id': '<message-id>',
             'author_email': 'john_doe@gmail.com',
             'subject': 'hello, world!',
             'body': 'lorem ipsum',
             'date': 1234567890},
            {'record_type': 'review',
             'id': 'I1045730e47e9e6ad31fcdfbaefdad77e2f3b2c3e',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@gmail.com',
                       'username': 'john_doe'},
             'createdOn': 1379404951,
             'module': 'nova', 'branch': 'master'}
        ]))

        user = {'seq': 1,
                'core': [],
                'user_id': 'john_doe',
                'ldap_id': 'john_doe',
                'user_name': 'John Doe',
                'emails': ['john_doe@gmail.com'],
                'companies': [{'company_name': '*independent', 'end_date': 0}]}
        self.assertEqual(user, utils.load_user(
            record_processor_inst.runtime_storage_inst, 'john_doe@gmail.com'))
        self.assertEqual(user, utils.load_user(
            record_processor_inst.runtime_storage_inst, 'john_doe'))

    def test_process_commit_then_review_with_different_email(self):
        # In this case, we don't know how to associate the email from the
        # commit with the LDAP ID so two users are created.

        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}])

        list(record_processor_inst.process([
            {'record_type': 'commit',
             'commit_id': 'de7e8f297c193fb310f22815334a54b9c76a0be1',
             'author_name': 'John Doe', 'author_email': 'john_doe@gmail.com',
             'date': 1234567890, 'lines_added': 25, 'lines_deleted': 9,
             'release_name': 'havana'},
            {'record_type': 'review',
             'id': 'I1045730e47e9e6ad31fcdfbaefdad77e2f3b2c3e',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'Bill Smith', 'email': 'bill@smith.to',
                       'username': 'bsmith'},
             'createdOn': 1379404951, 'module': 'nova', 'branch': 'master',
             'patchSets': [
                 {'number': '1',
                  'revision': '4d8984e92910c37b7d101c1ae8c8283a2e6f4a76',
                  'ref': 'refs/changes/16/58516/1',
                  'uploader': {'name': 'Bill Smith', 'email': 'bill@smith.to',
                               'username': 'bsmith'},
                  'createdOn': 1385470730,
                  'approvals': [
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '1', 'grantedOn': 1385478464,
                       'by': {'name': 'John Doe', 'email': 'john_doe@ibm.com',
                              'username': 'john_doe'}}]}]}
        ]))
        userA = {'seq': 3,
                 'user_id': 'john_doe',
                 'ldap_id': 'john_doe',
                 'user_name': 'John Doe',
                 'emails': ['john_doe@ibm.com'],
                 'companies': [{'company_name': 'IBM', 'end_date': 0}]}
        userB = {'seq': 1,
                 'user_id': 'john_doe@gmail.com',
                 'ldap_id': None,
                 'user_name': 'John Doe',
                 'emails': ['john_doe@gmail.com'],
                 'companies': [{'company_name': '*independent',
                                'end_date': 0}]}
        self.assertEqual(userA, utils.load_user(
            record_processor_inst.runtime_storage_inst, 'john_doe'))
        self.assertEqual(userB, utils.load_user(
            record_processor_inst.runtime_storage_inst, 'john_doe@gmail.com'))
        self.assertEqual(userA, utils.load_user(
            record_processor_inst.runtime_storage_inst, 'john_doe@ibm.com'))

    def test_merge_users(self):
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}],
        )
        runtime_storage_inst = record_processor_inst.runtime_storage_inst

        runtime_storage_inst.set_records(record_processor_inst.process([
            {'record_type': 'email',
             'message_id': '<message-id>',
             'author_email': 'john_doe@ibm.com', 'author_name': 'John Doe',
             'subject': 'hello, world!',
             'body': 'lorem ipsum',
             'date': 1234567890},
            {'record_type': 'review',
             'id': 'I1045730e47e9e6ad31fcdfbaefdad77e2f3b2c3e',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@ibm.com',
                       'username': 'john_doe'},
             'createdOn': 1379404951,
             'module': 'nova', 'branch': 'master'}
        ]))

        record_processor_inst.update()

        user = {'seq': 1,
                'core': [],
                'user_id': 'john_doe',
                'ldap_id': 'john_doe',
                'user_name': 'John Doe',
                'emails': ['john_doe@ibm.com'],
                'companies': [{'company_name': 'IBM', 'end_date': 0}]}
        runtime_storage_inst = record_processor_inst.runtime_storage_inst
        self.assertEqual(1, runtime_storage_inst.get_by_key('user:count'))
        self.assertEqual(user, utils.load_user(runtime_storage_inst, 1))
        self.assertEqual(user, utils.load_user(runtime_storage_inst,
                                               'john_doe'))
        self.assertEqual(user, utils.load_user(runtime_storage_inst,
                                               'john_doe@ibm.com'))

        # all records should have the same user_id and company name
        for record in runtime_storage_inst.get_all_records():
            self.assertEqual('john_doe', record['user_id'],
                             message='Record %s' % record['primary_key'])
            self.assertEqual('IBM', record['company_name'],
                             message='Record %s' % record['primary_key'])

    def test_core_user_guess(self):
        record_processor_inst = self.make_record_processor(
            companies=[{'company_name': 'IBM', 'domains': ['ibm.com']}],
        )
        runtime_storage_inst = record_processor_inst.runtime_storage_inst

        timestamp = int(time.time())
        runtime_storage_inst.set_records(record_processor_inst.process([
            {'record_type': 'review',
             'id': 'I1045730e47e9e6ad31fcdfbaefdad77e2f3b2c3e',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@ibm.com',
                       'username': 'john_doe'},
             'createdOn': timestamp,
             'module': 'nova',
             'branch': 'master',
             'patchSets': [
                 {'number': '1',
                  'revision': '4d8984e92910c37b7d101c1ae8c8283a2e6f4a76',
                  'ref': 'refs/changes/16/58516/1',
                  'uploader': {
                      'name': 'Bill Smith',
                      'email': 'bill@smith.to',
                      'username': 'bsmith'},
                  'createdOn': timestamp,
                  'approvals': [
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '2', 'grantedOn': timestamp,
                       'by': {
                           'name': 'John Doe',
                           'email': 'john_doe@ibm.com',
                           'username': 'john_doe'}},
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '-1', 'grantedOn': timestamp - 1,  # differ
                       'by': {
                           'name': 'Homer Simpson',
                           'email': 'hsimpson@gmail.com',
                           'username': 'homer'}}
                  ]
                  }]}
        ]))

        record_processor_inst.update()

        user_1 = {'seq': 1, 'user_id': 'john_doe',
                  'ldap_id': 'john_doe', 'user_name': 'John Doe',
                  'emails': ['john_doe@ibm.com'],
                  'core': [('nova', 'master')],
                  'companies': [{'company_name': 'IBM', 'end_date': 0}]}
        user_2 = {'seq': 3, 'user_id': 'homer',
                  'ldap_id': 'homer', 'user_name': 'Homer Simpson',
                  'emails': ['hsimpson@gmail.com'],
                  'core': [],
                  'companies': [{'company_name': '*independent',
                                 'end_date': 0}]}
        runtime_storage_inst = record_processor_inst.runtime_storage_inst
        self.assertEqual(user_1, utils.load_user(runtime_storage_inst,
                                                 'john_doe'))
        self.assertEqual(user_2, utils.load_user(runtime_storage_inst,
                                                 'homer'))

    def test_process_commit_with_coauthors(self):
        record_processor_inst = self.make_record_processor()
        processed_commits = list(record_processor_inst.process([
            {'record_type': 'commit',
             'commit_id': 'de7e8f297c193fb310f22815334a54b9c76a0be1',
             'author_name': 'Jimi Hendrix',
             'author_email': 'jimi.hendrix@openstack.com', 'date': 1234567890,
             'lines_added': 25, 'lines_deleted': 9, 'release_name': 'havana',
             'coauthor': [{'author_name': 'Tupac Shakur',
                           'author_email': 'tupac.shakur@openstack.com'},
                          {'author_name': 'Bob Dylan',
                           'author_email': 'bob.dylan@openstack.com'}]}]))

        self.assertEqual(3, len(processed_commits))

        self.assertRecordsMatch({
            'ldap_id': None,
            'author_email': 'tupac.shakur@openstack.com',
            'author_name': 'Tupac Shakur',
        }, processed_commits[0])
        self.assertRecordsMatch({
            'ldap_id': None,
            'author_email': 'jimi.hendrix@openstack.com',
            'author_name': 'Jimi Hendrix',
        }, processed_commits[2])
        self.assertEqual('tupac.shakur@openstack.com',
                         processed_commits[0]['coauthor'][0]['user_id'])
        self.assertEqual('bob.dylan@openstack.com',
                         processed_commits[0]['coauthor'][1]['user_id'])
        self.assertEqual('jimi.hendrix@openstack.com',
                         processed_commits[0]['coauthor'][2]['user_id'])

    # record post-processing
    def test_review_number(self):
        record_processor_inst = self.make_record_processor()
        runtime_storage_inst = record_processor_inst.runtime_storage_inst

        runtime_storage_inst.set_records(record_processor_inst.process([
            {'record_type': 'review',
             'id': 'I111',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@gmail.com',
                       'username': 'john_doe'},
             'createdOn': 10,
             'module': 'nova', 'branch': 'master'},
            {'record_type': 'review',
             'id': 'I222',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@gmail.com',
                       'username': 'john_doe'},
             'createdOn': 5,
             'module': 'glance', 'branch': 'master'},
        ]))
        record_processor_inst.update()

        review1 = runtime_storage_inst.get_by_primary_key('I111')
        self.assertEqual(2, review1['review_number'])

        review2 = runtime_storage_inst.get_by_primary_key('I222')
        self.assertEqual(1, review2['review_number'])

    def test_mark_disagreement(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {'user_id': 'john_doe',
                 'ldap_id': 'john_doe',
                 'user_name': 'John Doe',
                 'emails': ['john_doe@ibm.com'],
                 'core': [('nova', 'master')],
                 'companies': [{'company_name': 'IBM', 'end_date': 0}]}
            ],
        )
        timestamp = int(time.time())
        runtime_storage_inst = record_processor_inst.runtime_storage_inst
        runtime_storage_inst.set_records(record_processor_inst.process([
            {'record_type': 'review',
             'id': 'I1045730e47e9e6ad31fcdfbaefdad77e2f3b2c3e',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@ibm.com',
                       'username': 'john_doe'},
             'createdOn': timestamp,
             'module': 'nova',
             'branch': 'master',
             'status': 'NEW',
             'patchSets': [
                 {'number': '1',
                  'revision': '4d8984e92910c37b7d101c1ae8c8283a2e6f4a76',
                  'ref': 'refs/changes/16/58516/1',
                  'uploader': {
                      'name': 'Bill Smith',
                      'email': 'bill@smith.to',
                      'username': 'bsmith'},
                  'createdOn': timestamp,
                  'approvals': [
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '2', 'grantedOn': timestamp - 1,
                       'by': {
                           'name': 'Homer Simpson',
                           'email': 'hsimpson@gmail.com',
                           'username': 'homer'}},
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '-2', 'grantedOn': timestamp,
                       'by': {
                           'name': 'John Doe',
                           'email': 'john_doe@ibm.com',
                           'username': 'john_doe'}}
                  ]
                  },
                 {'number': '2',
                  'revision': '4d8984e92910c37b7d101c1ae8c8283a2e6f4a76',
                  'ref': 'refs/changes/16/58516/1',
                  'uploader': {
                      'name': 'Bill Smith',
                      'email': 'bill@smith.to',
                      'username': 'bsmith'},
                  'createdOn': timestamp + 1,
                  'approvals': [
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '1', 'grantedOn': timestamp + 2,
                       'by': {
                           'name': 'Homer Simpson',
                           'email': 'hsimpson@gmail.com',
                           'username': 'homer'}},
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '-1', 'grantedOn': timestamp + 3,
                       'by': {
                           'name': 'Bart Simpson',
                           'email': 'bsimpson@gmail.com',
                           'username': 'bart'}},
                      {'type': 'Code-Review', 'description': 'Code Review',
                       'value': '2', 'grantedOn': timestamp + 4,
                       'by': {
                           'name': 'John Doe',
                           'email': 'john_doe@ibm.com',
                           'username': 'john_doe'}}
                  ]
                  }
             ]}
        ]))
        record_processor_inst.update()

        marks = list([r for r in runtime_storage_inst.get_all_records()
                      if r['record_type'] == 'mark'])

        homer_mark = next(itertools.ifilter(
            lambda x: x['date'] == (timestamp - 1), marks), None)
        self.assertTrue(homer_mark.get('disagreement'),
                        msg='Disagreement: core set -2 after +2')

        homer_mark = next(itertools.ifilter(
            lambda x: x['date'] == (timestamp + 2), marks), None)
        self.assertFalse(homer_mark.get('disagreement'),
                         msg='No disagreement: core set +2 after +1')

        bart_mark = next(itertools.ifilter(
            lambda x: x['date'] == (timestamp + 3), marks), None)
        self.assertTrue(bart_mark.get('disagreement'),
                        msg='Disagreement: core set +2 after -1')

    def test_commit_merge_date(self):
        record_processor_inst = self.make_record_processor()
        runtime_storage_inst = record_processor_inst.runtime_storage_inst

        runtime_storage_inst.set_records(record_processor_inst.process([
            {'record_type': 'commit',
             'commit_id': 'de7e8f2',
             'change_id': ['I104573'],
             'author_name': 'John Doe',
             'author_email': 'john_doe@gmail.com',
             'date': 1234567890,
             'lines_added': 25,
             'lines_deleted': 9,
             'release_name': 'havana'},
            {'record_type': 'review',
             'id': 'I104573',
             'subject': 'Fix AttributeError in Keypair._add_details()',
             'owner': {'name': 'John Doe',
                       'email': 'john_doe@gmail.com',
                       'username': 'john_doe'},
             'createdOn': 1385478465,
             'lastUpdated': 1385490000,
             'status': 'MERGED',
             'module': 'nova', 'branch': 'master'},
        ]))
        record_processor_inst.update()

        commit = runtime_storage_inst.get_by_primary_key('de7e8f2')
        self.assertEqual(1385490000, commit['date'])

    # update records

    def _generate_record_commit(self):
        yield {'commit_id': u'0afdc64bfd041b03943ceda7849c4443940b6053',
               'lines_added': 9,
               'module': u'stackalytics',
               'record_type': 'commit',
               'message': u'Closes bug 1212953\n\nChange-Id: '
                          u'I33f0f37b6460dc494abf2520dc109c9893ace9e6\n',
               'subject': u'Fixed affiliation of Edgar and Sumit',
               'loc': 10,
               'user_id': u'john_doe',
               'primary_key': u'0afdc64bfd041b03943ceda7849c4443940b6053',
               'author_email': u'jdoe@super.no',
               'company_name': u'SuperCompany',
               'record_id': 6,
               'lines_deleted': 1,
               'week': 2275,
               'blueprint_id': None,
               'bug_id': u'1212953',
               'files_changed': 1,
               'author_name': u'John Doe',
               'date': 1376737923,
               'ldap_id': u'john_doe',
               'branches': set([u'master']),
               'change_id': u'I33f0f37b6460dc494abf2520dc109c9893ace9e6',
               'release': u'havana'}

    # mail processing

    def test_process_mail(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': 'NEC', 'end_date': 0},
                    ]
                }
            ],
            repos=[{"module": "stackalytics"}]
        )

        processed_commit = list(record_processor_inst.process(
            generate_emails(
                author_email='johndoe@gmail.com',
                author_name='John Doe',
                subject='[openstack-dev] [Stackalytics] Configuration files')
        ))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
            'module': 'stackalytics',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_mail_guessed(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': 'NEC', 'end_date': 0},
                    ]
                }
            ],
            repos=[{'module': 'nova'}, {'module': 'neutron'}]
        )

        processed_commit = list(record_processor_inst.process(
            generate_emails(
                author_email='johndoe@gmail.com',
                author_name='John Doe',
                subject='[openstack-dev] [Neutron] [Nova] Integration issue')
        ))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
            'module': 'neutron',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_mail_guessed_module_in_body_override(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': 'NEC', 'end_date': 0},
                    ]
                }
            ],
            repos=[{'module': 'nova'}, {'module': 'neutron'}]
        )

        processed_commit = list(record_processor_inst.process(
            generate_emails(
                author_email='johndoe@gmail.com',
                author_name='John Doe',
                module='nova',
                subject='[openstack-dev] [neutron] Comments/questions on the')
        ))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
            'module': 'neutron',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_mail_guessed_module_in_body(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': 'NEC', 'end_date': 0},
                    ]
                }
            ],
            repos=[{'module': 'nova'}, {'module': 'neutron'}]
        )

        processed_commit = list(record_processor_inst.process(
            generate_emails(
                author_email='johndoe@gmail.com',
                author_name='John Doe',
                module='nova',
                subject='[openstack-dev] Comments/questions on the')
        ))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
            'module': 'nova',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_process_mail_unmatched(self):
        record_processor_inst = self.make_record_processor(
            users=[
                {
                    'user_id': 'john_doe',
                    'ldap_id': 'john_doe',
                    'user_name': 'John Doe',
                    'emails': ['johndoe@gmail.com', 'johndoe@nec.co.jp'],
                    'companies': [
                        {'company_name': 'NEC', 'end_date': 0},
                    ]
                }
            ],
            repos=[{'module': 'nova'}, {'module': 'neutron'}]
        )

        processed_commit = list(record_processor_inst.process(
            generate_emails(
                author_email='johndoe@gmail.com',
                author_name='John Doe',
                subject='[openstack-dev] Comments/questions on the')
        ))[0]

        expected_commit = {
            'ldap_id': 'john_doe',
            'author_email': 'johndoe@gmail.com',
            'author_name': 'John Doe',
            'company_name': 'NEC',
            'module': 'unknown',
        }

        self.assertRecordsMatch(expected_commit, processed_commit)

    def test_get_modules(self):
        record_processor_inst = self.make_record_processor()
        with mock.patch('spectrometer.processor.utils.load_repos') as patch:
            patch.return_value = [{'module': 'nova'},
                                  {'module': 'python-novaclient'},
                                  {'module': 'neutron'},
                                  {'module': 'sahara', 'aliases': ['savanna']}]
            modules, module_alias_map = record_processor_inst._get_modules()
            self.assertEqual(set(['nova', 'neutron', 'sahara', 'savanna']),
                             set(modules))
            self.assertEqual({'savanna': 'sahara'}, module_alias_map)

    def test_guess_module(self):
        record_processor_inst = self.make_record_processor()
        with mock.patch('spectrometer.processor.utils.load_repos') as patch:
            patch.return_value = [{'module': 'sahara', 'aliases': ['savanna']}]
            record = {'subject': '[savanna] T'}
            record_processor_inst._guess_module(record)
            self.assertEqual({'subject': '[savanna] T', 'module': 'sahara'},
                             record)

    def assertRecordsMatch(self, expected, actual):
        for key, value in six.iteritems(expected):
            self.assertEqual(value, actual[key],
                             'Values for key %s do not match' % key)

    # Helpers

    def make_record_processor(self, users=None, companies=None, releases=None,
                              repos=None):
        rp = record_processor.RecordProcessor(make_runtime_storage(
            users=users, companies=companies, releases=releases, repos=repos))

        return rp


def generate_commits(author_name='John Doe', author_email='johndoe@gmail.com',
                     date=1999999999):
    yield {
        'record_type': 'commit',
        'commit_id': 'de7e8f297c193fb310f22815334a54b9c76a0be1',
        'author_name': author_name,
        'author_email': author_email,
        'date': date,
        'lines_added': 25,
        'lines_deleted': 9,
        'release_name': 'havana',
    }


def generate_emails(author_name='John Doe', author_email='johndoe@gmail.com',
                    date=1999999999, subject='[openstack-dev]', module=None):
    yield {
        'record_type': 'email',
        'message_id': 'de7e8f297c193fb310f22815334a54b9c76a0be1',
        'author_name': author_name,
        'author_email': author_email,
        'date': date,
        'subject': subject,
        'module': module,
        'body': 'lorem ipsum',
    }


def make_runtime_storage(users=None, companies=None, releases=None,
                         repos=None):
    runtime_storage_cache = {}
    runtime_storage_record_keys = []

    def get_by_key(key):
        if key == 'companies':
            return _make_companies(companies or [
                {"company_name": "*independent", "domains": [""]},
            ])
        elif key == 'users':
            return _make_users(users or [])
        elif key == 'releases':
            return releases or RELEASES
        elif key == 'repos':
            return repos or REPOS
        else:
            return runtime_storage_cache.get(key)

    def set_by_key(key, value):
        runtime_storage_cache[key] = value

    def delete_by_key(key):
        del runtime_storage_cache[key]

    def inc_user_count():
        count = runtime_storage_cache.get('user:count') or 0
        count += 1
        runtime_storage_cache['user:count'] = count
        return count

    def get_all_users():
        for n in xrange(0, (runtime_storage_cache.get('user:count') or 0) + 1):
            u = runtime_storage_cache.get('user:%s' % n)
            if u:
                yield u

    def set_records(records_iterator):
        for record in records_iterator:
            runtime_storage_cache[record['primary_key']] = record
            runtime_storage_record_keys.append(record['primary_key'])

    def get_all_records():
        return [runtime_storage_cache[key]
                for key in runtime_storage_record_keys]

    def get_by_primary_key(primary_key):
        return runtime_storage_cache.get(primary_key)

    rs = mock.Mock(runtime_storage.RuntimeStorage)
    rs.get_by_key = mock.Mock(side_effect=get_by_key)
    rs.set_by_key = mock.Mock(side_effect=set_by_key)
    rs.delete_by_key = mock.Mock(side_effect=delete_by_key)
    rs.inc_user_count = mock.Mock(side_effect=inc_user_count)
    rs.get_all_users = mock.Mock(side_effect=get_all_users)
    rs.set_records = mock.Mock(side_effect=set_records)
    rs.get_all_records = mock.Mock(side_effect=get_all_records)
    rs.get_by_primary_key = mock.Mock(side_effect=get_by_primary_key)

    if users:
        for user in users:
            set_by_key('user:%s' % user['user_id'], user)
            if user.get('ldap_id'):
                set_by_key('user:%s' % user['ldap_id'], user)
            for email in user.get('emails') or []:
                set_by_key('user:%s' % email, user)

    return rs


def _make_users(users):
    users_index = {}
    for user in users:
        if 'user_id' in user:
            users_index[user['user_id']] = user
        if 'ldap_id' in user:
            users_index[user['ldap_id']] = user
        for email in user['emails']:
            users_index[email] = user
    return users_index


def _make_companies(companies):
    domains_index = {}
    for company in companies:
        for domain in company['domains']:
            domains_index[domain] = company['company_name']
    return domains_index
