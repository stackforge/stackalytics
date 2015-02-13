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


from oslo.config import cfg


from stackalytics.openstack.common import log as logging
from stackalytics.processor import config
from stackalytics.processor import runtime_storage


LOG = logging.getLogger(__name__)

OPTS = [
    cfg.StrOpt('key', default=False,
               help='Name of key to be searched from memcached. This option '
               'works for storage only'),
]


def search_key(key, record):
    if key in record.values():
        return True
    else:
        return False


def print_runtime_info(mem_key, runtime_storage_inst):
    record = runtime_storage_inst.get_by_key(mem_key)
    if record:
        print(json.dumps(record, indent=4, sort_keys=True))
    else:
        if mem_key.isdigit():
            mem_key = int(mem_key)
        for mem_record in runtime_storage_inst.get_all_records():
            if search_key(mem_key, mem_record):
                print(json.dumps(mem_record, indent=4, sort_keys=True))


def main():
    # init conf and logging
    conf = cfg.CONF
    conf.register_cli_opts(config.OPTS)
    conf.register_cli_opts(OPTS)
    conf.register_opts(config.OPTS)
    conf.register_opts(OPTS)
    conf(project='stackalytics')
    logging.setup('stackalytics.storage')
    LOG.info('Storage logging enabled')
    runtime_storage_inst = runtime_storage.get_runtime_storage(
        cfg.CONF.runtime_storage_uri)
    mem_key = cfg.CONF.key
    if mem_key != "False":
        print_runtime_info(mem_key, runtime_storage_inst)
        return 1

if __name__ == '__main__':
        main()
