#! /usr/bin/env python

import json
import logging
import random
import string
import subprocess
import time

logger = logging.getLogger(__name__)
RADIX_CHARS = string.digits + string.ascii_uppercase + string.ascii_lowercase


def _check_output(*args):
    return subprocess.check_output(args).decode('utf-8')


def _select_manager():
    out = json.loads(_check_output('snap_rpc.py', 'emulation_managers_list'))
    for elem in out:
        if 'emulation_manager' not in elem:
            continue
        supported_types = elem.get('supported_types', ())
        if 'nvme' in supported_types:
            mgr = elem['emulation_manager']
            logger.info('Found emulation manager: %s' % mgr)
            return mgr

    logger.error('No emulation manager found')


def unique_id():
    val = int(str(time.time()).replace('.', ''))
    result = ''
    rlen = len(RADIX_CHARS)
    while val:
        result += RADIX_CHARS[val % rlen]
        val //= rlen
    return result


def _create_subsystem():
    serial = ''.join(random.choice(RADIX_CHARS) for _ in range(15))
    model = 'EMULATED-NVME'
    ret = json.loads(_check_output('snap_rpc.py', 'subsystem_nvme_create',
                                   serial, model))
    return ret


def _list_controllers():
    return [Controller(c) for c in
            json.loads(_check_output('snap_rpc.py', 'controller_list'))]


def _list_subsystems():
    return json.loads(_check_output('snap_rpc.py', 'subsystem_nvme_list'))


class Controller:
    def __init__(self, kwargs):
        self.name = kwargs['name']
        self.max_nsid = kwargs['max_nsid']
        self.pci_bdf = kwargs['pci_bdf']
        self.pci_index = kwargs['pci_index']
        self.nqn = kwargs['subnqn']

    def next_nsid(self):
        ret = json.loads(_check_output('snap_rpc.py',
                                       'controller_nvme_namespace_list',
                                       '-c', self.name))
        s = set(nx['nsid'] for nx in ret.get('Namespaces', ()))
        for i in range(1, self.max_nsid + 1):
            if i not in s:
                return i

        logger.error('No more namespaces available for controller %s' %
                     self.name)
        return None


class SNAP:
    def __init__(self, config):
        self.service_name = config.get('service_name', 'mlnx_snap')
        self.manager = _select_manager()
        self.controllers = _list_controllers()
        self.subsystems = _list_subsystems()
        self.num_pf = config.get('num_pf', 2)

    def _get_controller(self, host):
        # XXX: For now, we assume the first controller is always valid.
        # The implementation here will depend on what information
        # Cinder provides us (i.e: PCI bridge)
        try:
            return self.controllers[0]
        except Exception:
            raise KeyError('no controller found for host: %s' % host)

    def stop_service(self):
        _check_output('systemctl', 'stop', self.service_name)

    def start_service(self):
        _check_output('systemctl', 'start', self.service_name)

    def restart_service(self):
        self.stop_service()
        self.start_service()

    def setup_controllers(self):
        controllers = []
        subsystems = []
        for i in range(self.num_pf):
            try:
                subsys = _create_subsystem()
                subsystems.append(subsys)
                ret = _check_output('snap_rpc.py', 'controller_nvme_create',
                                    '--subsys_id', subsys['subsys_id'],
                                    '--pf_id', i, self.manager)
                controllers.append(json.loads(ret))
            except Exception:
                for c in controllers:
                    _check_output('snap_rpc.py', 'controller_nvme_delete',
                                  '-c', c.name)
                for s in subsystems:
                    _check_output('snap_rpc.py', 'subsystem_nvme_delete',
                                  s['nqn'])
                logger.exception('Failed to create controller for PF: %d' % i)
                raise

        self.controllers = controllers
        return controllers

    def create_rbd_dev(self, config_file, ceph_user, pool, img):
        uid = unique_id()
        cluster_name = 'cluster-' + uid
        _check_output('spdk_rpc.py', 'bdev_rbd_register_cluster',
                      '--config-file', config_file, '--user',
                      ceph_user, cluster_name)
        logger.info('Created RBD cluster: %s' % cluster_name)
        try:
            bdev_name = 'rbd-' + uid
            _check_output('spdk_rpc.py', 'bdev_rbd_create', bdev_name)
            logger.info('Created RBD bdev: %s' % bdev_name)
            return bdev_name
        except Exception:
            _check_output('spdk_rpc.py', 'bdev_rbd_unregister_cluster',
                          cluster_name)
            raise

    def delete_rbd_dev(self, name):
        suffix = name[4:]   # Skip 'rbd-'
        cluster_name = 'cluster-' + suffix
        _check_output('spdk_rpc.py', 'bdev_rbd_delete', name)
        logger.info('Deleted RBD bdev: %s' % name)
        _check_output('spdk_rpc.py', 'bdev_rbd_unregister_cluster',
                      cluster_name)
        logger.info('Deleted RBD cluster: %s' % cluster_name)

    def attach_device(self, host, name):
        controller = self._get_controller(host)
        nsid = controller.next_nsid()
        if nsid is None:
            raise OverflowError('max number of namespaces reached')
        _check_output('snap_rpc.py', 'controller_nvme_namespace_attach',
                      '-c', controller.name, 'spdk', name, nsid)
        logger.info('Attached device %s - NQN=%s, namespace=%d' %
                    (name, controller.nqn, nsid))
        return (controller.nqn, nsid)

    def detach_device(self, host, nsid):
        controller = self._get_controller(host)
        _check_output('snap_rpc.py', 'controller_nvme_namespace_detach',
                      '-c', controller.name, nsid)
        logger.info('Detached device with namespace: %d' % nsid)
