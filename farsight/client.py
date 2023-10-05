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

import json
import os
import subprocess
import sys


def _check_output(*args):
    return subprocess.check_output(args).encode('utf-8')


def nvme_list_subsystems():
    ret = json.loads(_check_output('nvme', 'list-subsys',
                                   '--output-format=json'))
    try:
        return ret['Subsystems']
    except Exception:
        return []


def nvme_by_ns(device, nsid):
    ret = json.loads(_check_output('nvme', 'list-ns', '-o', 'json', device))
    try:
        for i, sub in enumerate(ret['nsid_list']):
            if sub.get('nsid') == nsid:
                return i + 1   # Host namespaces start at 1.
    except Exception:
        return None


def nvme_by_nqn(nqn):
    subs = nvme_list_subsystems()
    for sub in subs:
        if sub.get('NQN') == nqn:
            return sub


def find_device(nqn, nsid):
    """
    Find the device in the host that matches an NQN and a namespace-id.
    """
    sub = nvme_by_nqn(nqn)
    if sub is not None:
        for path in sub.get('Paths', ()):
            name = path.get('Name')
            if not name:
                continue
            elif not name.startswith('/dev'):
                name = '/dev/' + name

            dev = nvme_by_ns(name, nsid)
            if dev:
                return '%sn%d' % (name, dev)


def detach_device(dev):
    """
    Reset an NVME device, making it possible to detach it from the DPU.
    """
    if dev.startswith('/dev/'):
        dev = dev[4:]
    try:
        os.sync()
        subprocess.call('echo 1 > /sys/block/%s/device/reset_controller' % dev,
                        shell=True)
    except Exception:
        pass


if __name__ == '__main__':
    nargs = len(sys.argv)
    if nargs == 4 and sys.argv[1] == 'find':
        print(find_device(sys.argv[2], sys.argv[3]))
    elif nargs == 3 and sys.argv[1] == 'detach':
        detach_device(sys.argv[2])
    else:
        print('usage: dpu_client.py find|detach ...args')
