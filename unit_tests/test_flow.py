import os
import signal
import socket
import sys
import tempfile

import unittest
from unittest.mock import patch, ANY

import client
import server


class MockHandler:
    def __init__(self, *args, **kwargs):
        pass

    def get_blocks(self, *args, **kwargs):
        return 1


class TestFlow(unittest.TestCase):
    def setUp(self):
        super().setUp()

    def make_sockets(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('', 0))
        server_sock.listen()

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect(server_sock.getsockname())
        return client_sock, server_sock

    @patch.object(client, 'make_client_socket')
    @patch.object(client.fcntl, 'ioctl')
    @patch.object(server, 'make_server_socket')
    @patch.object(server, 'make_handler')
    @patch.object(client, 'make_nbd_fd')
    def test_flow(self, make_nbd_fd, make_handler, make_server_socket,
                  ioctl, make_client_socket):
        socks = self.make_sockets()
        make_handler.return_value = MockHandler()
        make_client_socket.return_value = socks[0]
        make_server_socket.return_value = socks[1]

        if os.fork() == 0:
            # Run the client in the parent.
            with tempfile.NamedTemporaryFile(mode='w+') as client_conf:
                client_conf.write('''
                    [nbd]
                    blocksize = 1
                    [server]
                    [backend]
                    name = "dummy"
                ''')
                client_conf.flush()
                sys.argv = [None, client_conf.name]
                client.main()
                # Interrupt child process so it terminates gracefully.
                os.kill(os.getppid(), signal.SIGTERM)
        else:
            # Run the server in the child.
            with tempfile.NamedTemporaryFile(mode='w+') as server_conf:
                server_conf.write('''
                [server]
                address = "127.0.0.1"
                port = 0
                ''')
                server_conf.flush()
                sys.argv = [None, server_conf.name]
                server.main()
