# Copyright 2017 NEC Corporation.  All rights reserved.
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

import functools
import json
import six


def read_raw_file(file_name):
    if six.PY3:
        opener = functools.partial(open, encoding='utf8')
    else:
        opener = open
    with opener(file_name, 'r') as content_file:
        return content_file.read()


def read_file(file_name):
    return json.loads(read_raw_file(file_name))


def main():
    data = read_file('etc/default_data.json')
    user_data = data['users']
    user_data = sorted(user_data, key=lambda user: user.get('user_name'))
    data['users'] = user_data
    print(json.dumps(data, indent=4))


if __name__ == '__main__':
    main()
