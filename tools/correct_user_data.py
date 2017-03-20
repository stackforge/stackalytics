# Copyright (c) zhangyujun@gmail.com
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
import requests


def filter_record(record, data_filter):
    for key in data_filter:
        if record[key] != data_filter[key]:
            return False
    return True


def correct(data, data_filter, correction, select_keys):
    for record in filter(lambda r: filter_record(r, data_filter), data):
        selected = {k: record[k] for k in select_keys}
        selected.update(correction)
        yield selected


def main():
    res_fmt = 'http://stackalytics.com/api/1.0/{resource}'
    query_params = {
        'user_id': 'zhangyujun',
        'project_type': 'opnfv-group',
        'metric': 'commits',
        'release': 'all',
        'page_size': 100,
        'start_record': 0
    }

    resource_name = 'activity'
    res = requests.get(res_fmt.format(resource=resource_name), params = query_params)

    records = json.loads(res.text)[resource_name]

    data_filter = {
        'author_email': 'zhang.yujunz@zte.com.cn'
    }
    correction = {
        "user_id": "yujunz",
        "user_name": "Yujun Zhang",
        "company_name": "ZTE Corporation",
        "correction_comment": "Related-Bug: #1634020"
    }
    select_keys = ('primary_key',)

    correction = correct(records, data_filter, correction, select_keys)
    print(json.dumps(list(correction)))

if __name__ == '__main__':
    main()
