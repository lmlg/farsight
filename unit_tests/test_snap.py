from collections import defaultdict
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import farsight.snap as snap
import farsight.client as client
from . import rpc_mocks


CALLS = defaultdict(list)


def mock_check_snap_output(*args):
    if args[0] == 'snap_rpc.py':
        return rpc_mocks.snap_rpc_handle(args)
    elif args[0] == 'spdk_rpc.py':
        return rpc_mocks.spdk_rpc_handle(args)
    else:
        CALLS[args[0]].append(args[1:])


def mock_check_nvme_output(*args):
    if args[0] != 'nvme':
        raise KeyError('Invalid command name')
    elif args[1] == 'list-subsys':
        return """
{
  "Subsystems" : [
    {
      "NQN" : "nqn.0",
      "Paths" : [
        {
          "Name" : "nvme1"
        }]}]
}
        """
    elif args[1] == 'list-ns':
        if not args[-1].startswith('/dev'):
            raise KeyError('Invalid device name')
        return """
{
  "nsid_list" : [
    {
      "nsid" : 2
    },
    {
      "nsid" : 5
    }]
}
        """


class TestSNAP(unittest.TestCase):
    def setUp(self):
        super().setUp()
        rpc_mocks.init()

    @patch.object(snap, '_check_output')
    def test_snap(self, check_output):
        check_output.side_effect = mock_check_snap_output
        CALLS.clear()

        with tempfile.NamedTemporaryFile(mode='w+') as srv_file, \
             tempfile.TemporaryDirectory() as tmp_dir, \
             tempfile.NamedTemporaryFile(mode='w+') as env_file:
            srv_file.write('[Service]\nEnvironmentFile=%s' % env_file.name)
            env_file.write('SPDK_RPC_INIT_CONF=spdk.conf\n')
            env_file.write('SNAP_RPC_INIT_CONF=snap.conf\n')
            srv_file.flush()
            env_file.flush()

            s = snap.SNAP({'service_file': srv_file.name,
                           'dpu_dir': tmp_dir})
            s.stop_service = MagicMock()
            s.start_service = MagicMock()
            s.setup_service()
            s.stop_service.assert_called()
            s.start_service.assert_called()

            env_file.seek(0)
            env_contents = env_file.read()
            self.assertIn('LD_PRELOAD=%s/libxrbd.so' % tmp_dir,
                          env_contents)
            self.assertIn('SNAP_RPC_INIT_CONF=%s/empty.conf' % tmp_dir,
                          env_contents)
            self.assertIn('SPDK_RPC_INIT_CONF=%s/empty.conf' % tmp_dir,
                          env_contents)

            copies = CALLS['cp']
            self.assertIn(('spdk.conf', tmp_dir), copies)
            self.assertIn(('snap.conf', tmp_dir), copies)
            self.assertIn(((tmp_dir + '/empty.conf',)), CALLS['touch'])

            self.assertEqual(s.manager, 'mlx5_0')
            self.assertEqual(len(s.controllers), 2)
            rv = s.create_rbd_dev('config', 'user', 'pool', 'img')
            self.assertTrue(rv.startswith('rbd-'))
            self.assertTrue(rpc_mocks.rbd_present(rv))
            nqn, nsid = s.attach_device('host', rv)
            self.assertEqual(nsid, 1)
            self.assertTrue(nqn.startswith('nqn'))
            self.assertIsNone(s.detach_device('host', nsid))

            with self.assertRaises(KeyError):
                s.detach_device('host', nsid)

            self.assertIsNone(s.delete_rbd_dev(rv))
            with self.assertRaises(KeyError):
                s.delete_rbd_dev(rv)

            self.assertFalse(rpc_mocks.rbd_present(rv))

    @patch.object(client, '_check_output')
    def test_client(self, check_output):
        check_output.side_effect = mock_check_nvme_output
        rv = client.find_device('nqn.0', 5)
        self.assertEqual(rv, '/dev/nvme1n2')
