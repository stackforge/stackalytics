# Copyright (c) 2014 Mirantis Inc.
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

from __future__ import print_function

import os
import time

from oslo.config import cfg
import uwsgidecorators as udec

from dashboard import vault
from dashboard import web

application = web.app


def get_vault():
    with application.test_request_context():
        return vault.get_vault()


@udec.postfork
def postfork():
    # we have data of parent process so we should register in Memcached
    runtime_storage = get_vault()['runtime_storage']
    pid = os.getpid()
    runtime_storage.set_by_key('pid:%s' % pid, runtime_storage.last_update)
    runtime_storage._set_pids(pid)


def update():
    # loading data from Memcached
    get_vault()


@udec.thread
def update_thread():
    while True:
        time.sleep(cfg.CONF.dashboard_update_interval)
        get_vault()


update()
update_thread()
