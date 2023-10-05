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


SUBSYS_ID = 0
RBD_CLUSTERS = set()
RBD_DEVS = set()
NVME_NS = set()

SNAP_PROG_LIST = ('emulation_managers_list', 'subsystem_nvme_create',
                  'controller_nvme_namespace_list', 'controller_nvme_create',
                  'controller_nvme_delete', 'subsystem_nvme_delete',
                  'controller_nvme_namespace_attach', 'controller_list',
                  'controller_nvme_namespace_detach', 'subsystem_nvme_list')

SPDK_PROG_LIST = ('bdev_rbd_register_cluster', 'bdev_rbd_create',
                  'bdev_rbd_unregister_cluster', 'bdev_rbd_delete')

SNAP_PROGS = {}
SPDK_PROGS = {}


def emulation_managers_list(args):
    return b"""
[
  {
    "emulation_manager": "mlx5_0",
    "hotplug_support": false,
    "supported_types": [
      "nvme",
      "virtio_blk"
    ]
  }
]

"""


def controller_nvme_create(args):
    return b"""
{
  "name": "NvmeEmu0pf%d",
  "cntlid": 0,
  "version": "1.3.0",
  "offload": false,
  "mempool": false,
  "max_nsid": 1024,
  "max_namespaces": 1024
}
""" % int(args[-2])


def subsystem_nvme_create(args):
    global SUBSYS_ID
    sid = SUBSYS_ID
    SUBSYS_ID += 1
    return b"""
{
  "nqn": "nqn.%d"
  "subsys_id": %d
}
""" % (sid, sid)


def controller_list(args):
    return b"""
[
  {
    "subnqn": "nqn.2021-06.mlnx.snap:0efe63449b474bcc874534840193e5f1:0",
    "cntlid": 1,
    "version": "1.3.0",
    "offload": false,
    "mempool": false,
    "max_nsid": 1024,
    "max_namespaces": 1024,
    "name": "NvmeEmu0pf1",
    "emulation_manager": "mlx5_0",
    "type": "nvme",
    "pci_index": 1,
    "pci_bdf": "82:00.3"
  },
  {
    "subnqn": "nqn.2021-06.mlnx.snap:0efe63449b474bcc874534840193e5f1:0",
    "cntlid": 0,
    "version": "1.3.0",
    "offload": false,
    "mempool": false,
    "max_nsid": 1024,
    "max_namespaces": 1024,
    "name": "NvmeEmu0pf0",
    "emulation_manager": "mlx5_0",
    "type": "nvme",
    "pci_index": 0,
    "pci_bdf": "82:00.2"
  }
]
"""


def controller_nvme_namespace_list(args):
    return ("""
{
  "name": "%s",
  "cntlid": 0,
  "Namespaces": [
    {
      "nsid": 0,
      "bdev": "aio0",
      "bdev_type": "spdk"
    },
    {
      "nsid": 2,
      "bdev": "rbd0"
    }
]
}
""" % args[-1]).encode('utf-8')


def subsystem_nvme_list(args):
    return b'[]'


def controller_nvme_namespace_attach(args):
    if 'spdk' != args[-3]:
        raise KeyError('Invalid device type')
    if not args[2].startswith('NvmeEmu'):
        raise KeyError('Invalid controller name')
    if args[-1] in NVME_NS:
        raise KeyError('Namespace already attached')
    NVME_NS.add(args[-1])
    return b''


def controller_nvme_namespace_detach(args):
    if args[-1] not in NVME_NS:
        raise KeyError('Namespace not attached')

    NVME_NS.remove(args[-1])
    return b''


def _rbd_register(place, kind, args):
    name = args[-1]
    if name in place:
        raise KeyError('%s %s already present' % (kind, name))

    place.add(name)
    return b''


def _rbd_unregister(place, kind, args):
    name = args[-1]
    if name not in place:
        raise KeyError('%s %s not present' % (kind, name))
    place.remove(name)
    return b''


def bdev_rbd_register_cluster(args):
    return _rbd_register(RBD_CLUSTERS, 'RBD cluster', args)


def bdev_rbd_create(args):
    return _rbd_register(RBD_DEVS, 'RBD', args)


def bdev_rbd_unregister_cluster(args):
    return _rbd_unregister(RBD_CLUSTERS, 'RBD cluster', args)


def bdev_rbd_delete(args):
    return _rbd_unregister(RBD_DEVS, 'RBD', args)


def _register_progs(table, lst):
    for prog in lst:
        val = globals().get(prog)
        if val is not None:
            table[prog] = val


def _rpc_call(table, args):
    prog = table.get(args[1], lambda *_: b"")
    return prog(args[1:]).decode('utf-8')


def snap_rpc_handle(argv):
    return _rpc_call(SNAP_PROGS, argv)


def spdk_rpc_handle(argv):
    return _rpc_call(SPDK_PROGS, argv)


def rbd_cluster_present(name):
    return name in RBD_CLUSTERS


def rbd_present(name):
    return name in RBD_DEVS


def init():
    _register_progs(SNAP_PROGS, SNAP_PROG_LIST)
    _register_progs(SPDK_PROGS, SPDK_PROG_LIST)
