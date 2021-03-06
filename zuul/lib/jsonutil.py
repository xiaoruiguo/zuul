# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import types


class ZuulJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, types.MappingProxyType):
            return dict(o)
        return json.JSONEncoder.default(self, o)


def json_dumps(obj):
    return json.dumps(obj, cls=ZuulJSONEncoder)
