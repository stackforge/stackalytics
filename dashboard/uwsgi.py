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
