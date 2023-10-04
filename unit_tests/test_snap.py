import unittest
from unittest.mock import patch

import farsight.snap as snap
import farsight.client as client
from . import rpc_mocks


def mock_check_snap_output(*args):
    if args[0] == 'snap_rpc.py':
        return rpc_mocks.snap_rpc_handle(args)
    elif args[0] == 'spdk_rpc.py':
        return rpc_mocks.spdk_rpc_handle(args)


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
        s = snap.SNAP({})
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
