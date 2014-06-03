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

import memcache
import pickle
import six
import sys

from oslo.config import cfg
import re

from stackalytics.openstack.common import log as logging
from stackalytics.processor import config
from stackalytics.processor import runtime_storage


LOG = logging.getLogger(__name__)

OPTS = [
    cfg.BoolOpt('restore',
                short='r',
                help='Restore data into memcached'),
    cfg.StrOpt('file',
               short='f',
               help='File name where to store data'),
    cfg.StrOpt('min-compress-len', default=0,
               short='m',
               help='The threshold length to kick in auto-compression'),
]


def read_records_from_fd(fd):
    while True:
        try:
            record = pickle.load(fd)
        except EOFError:
            break
        yield record


def store_bucket(memcached_inst, bucket):
    res = memcached_inst.set_multi(bucket,
                                   min_compress_len=cfg.CONF.min_compress_len)
    if res:
        LOG.critical('Failed to set values in memcached: %s', res)
        raise Exception('memcached set_multi operation is failed')


def import_data(memcached_inst, fd):
    bucket = {}
    count = 0
    for key, value in read_records_from_fd(fd):
        count += 1
        if len(bucket) < runtime_storage.BULK_READ_SIZE:
            bucket[key] = value
        else:
            store_bucket(memcached_inst, bucket)
            bucket = {}
    if bucket:
        store_bucket(memcached_inst, bucket)


def export_data(memcached_inst, fd):
    slabs = memcached_inst.get_slabs()
    for slab_number, slab in slabs[0][1].iteritems():
        count = int(slab['number'])
        keys = memcached_inst.get_stats(
            'cachedump %s %s' % (slab_number, count))[0][1].keys()

        n = 0
        while n < count:
            LOG.debug('Dumping slab %s, start record %s', slab_number, n)

            for k, v in six.iteritems(memcached_inst.get_multi(
                    keys[n: min(count, n + runtime_storage.BULK_READ_SIZE)])):
                pickle.dump((k, v), fd)

            n += runtime_storage.BULK_READ_SIZE


def _connect_to_memcached(uri):
    stripped = re.sub(runtime_storage.MEMCACHED_URI_PREFIX, '', uri)
    if stripped:
        storage_uri = stripped.split(',')
        return memcache.Client(storage_uri)
    else:
        raise Exception('Invalid storage uri %s' % uri)


def main():
    # init conf and logging
    conf = cfg.CONF
    conf.register_cli_opts(config.OPTS)
    conf.register_cli_opts(OPTS)
    conf.register_opts(config.OPTS)
    conf.register_opts(OPTS)
    conf()

    logging.setup('stackalytics')
    LOG.info('Logging enabled')

    memcached_inst = _connect_to_memcached(cfg.CONF.runtime_storage_uri)

    filename = cfg.CONF.file

    if cfg.CONF.restore:
        if filename:
            fd = open(filename, 'r')
        else:
            fd = sys.stdin
        import_data(memcached_inst, fd)
    else:
        if filename:
            fd = open(filename, 'w')
        else:
            fd = sys.stdout
        export_data(memcached_inst, fd)


if __name__ == '__main__':
    main()
