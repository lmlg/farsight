import asyncio
import ipaddress
import json
import logging
import signal
import socket
import struct
import sys
import toml

import nbd

from handlers import get_handler_class


class Client(object):
    def __init__(self, handler, sock):
        self.handler = handler
        self.sock = sock
        self.num_errors = 0


class Server(object):
    def __init__(self, loop, logger, config):
        self.loop = loop
        self.logger = logger
        self.fds = {}
        self.config = config
        self.max_errors = config['server'].get('max_errors', 10)

    def get_client(self, sock):
        return self.fds.get(sock.fileno())

    def add_client(self, client):
        self.fds[client.sock.fileno()] = client

    def del_socket(self, sock):
        self.loop.remove_reader(sock)
        sock.close()

    def del_client(self, client):
        self.fds.pop(client.sock.fileno())
        self.del_socket(client.sock)

    def client_error(self, client):
        client.num_errors += 1
        if client.num_errors == self.max_errors:
            self.logger.info('disconnecting client due to too many errors')
            self.del_client(client)

    def close(self):
        self.loop.close()
        for client in self.fds.values():
            client.sock.close()


def make_server_socket(addr, port):
    obj = ipaddress.ip_address(addr)
    proto = socket.AF_INET6 if obj.version == 6 else socket.AF_INET
    sock = socket.socket(proto, socket.SOCK_STREAM)
    sock.bind((addr, port))
    sock.listen()
    sock.setblocking(0)
    return sock


def make_handler(server, config):
    name = config.get('name')
    handler_cls = get_handler_class(name)
    if not handler_cls:
        raise KeyError('no handler found for %s backend' % name)
    return handler_cls(config, server)


def handle_client(sock, server):
    client = server.get_client(sock)
    logger = server.logger

    if client is None:
        # Handshake phase
        try:
            data = json.loads(sock.recv(1024).decode('utf-8'))
            logger.info('client handshake: "%s"' % data)
            handler = make_handler(server, data)
        except Exception as exc:
            logger.exception(exc)
            response = {'error': str(exc)}
            sock.send(json.dumps(response).encode('utf-8'))
            server.del_socket(sock)
            return

        server.add_client(Client(handler, sock))
        # Inform the client of the backing store size.
        response = {'error': None,
                    'blocks': handler.get_blocks(data['blocksize'])}
        sock.send(json.dumps(response).encode('utf-8'))
    else:
        # Operational phase.
        header = sock.recv(nbd.NBD_HEADER_SIZE)
        if not header:
            logger.info('client disconnected')
            server.del_client(client)
            return
        elif len(header) != nbd.NBD_HEADER_SIZE:
            logger.error('invalid header size (got: %d bytes)', len(header))
            server.client_error(client)
            return

        try:
            magic, cmd, cookie, off, size = struct.unpack('>LLQQL', header)
        except struct.error:
            logger.error("client sent an invalid NBD header")
            server.client_error(client)
            return

        if magic != nbd.NBD_REQUEST:
            logger.error('invalid NBD magic value (got: %s)' % magic)
        elif cmd == nbd.NBD_CMD_DISC:
            logger.info('client disconnected')
            server.del_client(client)
        elif cmd == nbd.NBD_CMD_WRITE:
            buf = sock.recv(size)
            if len(buf) != size:
                server.logger.error(
                    'invalid size or truncated message (got %d instead of %d)' %
                    (len(buf), size))
                server.client_error(client)
            else:
                logger.info('got a write request for %d bytes', size)
                client.handler.write(client, cookie, off, buf)
        elif cmd == nbd.NBD_CMD_READ:
            logger.info('got a read request for %d bytes', size)
            client.handler.read(client, cookie, off, size)
        elif cmd == nbd.NBD_CMD_FLUSH:
            logger.info('got a flush request')
            client.handler.flush(client, cookie)
        else:
            logger.error('invalid NBD command (got: %s)' % cmd)
            server.client_error(client)


def handle_server_sock(sock, server):
    new_sock, _ = sock.accept()
    new_sock.setblocking(0)
    server.loop.add_reader(new_sock, handle_client, new_sock, server)


def main():
    if len(sys.argv) != 2:
        print("usage: server toml-config-file-path")
        sys.exit(0)

    with open(sys.argv[1], 'r') as fp:
        config = toml.load(fp)

    server_conf = config['server']
    sock = make_server_socket(server_conf['address'], server_conf['port'])

    logging.basicConfig(level=logging.NOTSET)
    logger = logging.getLogger('farsight-server')
    loop = asyncio.new_event_loop()
    server = Server(loop, logger, config)

    loop.add_reader(sock, handle_server_sock, sock, server)
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    loop.add_signal_handler(signal.SIGINT, loop.stop)

    loop.run_forever()
    logger.info('server shutting down')
    server.close()
    sock.close()


if __name__ == '__main__':
    main()
