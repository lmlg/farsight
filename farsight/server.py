#!/usr/bin/env python3
#
# Copyright 2023 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from flask import Flask, request, jsonify
from .snap import SNAP
import sys
import toml

app = Flask(__name__)
snap = None


@app.route('/device', methods=['POST'])
def device_post():
    args = request.args
    typ = args.get('type', 'rbd')
    if typ == 'rbd':
        try:
            ret = snap.create_rbd_dev(args['config-file'], args['ceph-user'],
                                      args['pool'], args['image'])
            return jsonify({'name': ret, 'error': None})
        except Exception as exc:
            return jsonify({'error': str(exc)})
    else:
        return jsonify({'error': 'unknown device type: %s' % typ})


@app.route('/attach', methods=['POST'])
def attach_post():
    try:
        nqn, nsid = snap.attach_device(request.args['host'],
                                       request.args['device-name'])
        return jsonify({'nqn': nqn, 'nsid': nsid, 'error': None})
    except Exception as exc:
        return jsonify({'error': str(exc)})


@app.route('/attach', methods=['DELETE'])
def attach_delete():
    try:
        snap.detach_device(request.args['host'], request.args['nsid'])
        return jsonify({'error': None})
    except Exception as exc:
        return jsonify({'error': str(exc)})


def main():
    global snap
    if len(sys.argv) != 2:
        print('usage: server toml-config-file-path')
        sys.exit(0)

    with open(sys.argv[1], 'r') as fp:
        config = toml.load(fp)

    snap = SNAP(config['snap'])
    server_conf = config['server']
    app.run(host=server_conf.get('host', '0.0.0.0'),
            port=server_conf.get('port', 7979))


if __name__ == '__main__':
    main()
