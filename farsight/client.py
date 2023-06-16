import fcntl
import ipaddress
import json
import socket
import sys
import toml

from . import nbd


def make_client_socket(addr, port):
    obj = ipaddress.ip_address(addr)
    proto = socket.AF_INET6 if obj.version == 6 else socket.AF_INET
    sock = socket.socket(proto, socket.SOCK_STREAM)
    sock.connect((addr, port))
    return sock


def make_nbd_fd(config, num_blocks):
    fd = open(config['file'], 'rb+')
    fcntl.ioctl(fd, nbd.NBD_CLEAR_SOCK)
    fcntl.ioctl(fd, nbd.NBD_SET_BLKSIZE, config['blocksize'])
    fcntl.ioctl(fd, nbd.NBD_SET_SIZE_BLOCKS, num_blocks)
    fcntl.ioctl(fd, nbd.NBD_SET_TIMEOUT, config.get('timeout', 10))
    fcntl.ioctl(fd, nbd.NBD_SET_FLAGS, (1 << 0) | (1 << 2))
    return fd


def main():
    if len(sys.argv) != 2:
        print("usage: client toml-config-file-path")
        sys.exit(0)

    with open(sys.argv[1], 'r') as fp:
        config = toml.load(fp)

    nbd_conf = config['nbd']
    server_conf = config['server']
    sock = make_client_socket(server_conf.get('address', '127.0.0.1'),
                              server_conf.get('port', 65000))

    backend_conf = config['backend']
    backend_conf['blocksize'] = nbd_conf.get('blocksize', 1024)
    sock.sendall(json.dumps(backend_conf).encode('utf-8'))

    resp = json.loads(sock.recv(1024).decode('utf-8'))
    if 'error' not in resp:
        print("invalid server response: %s" % resp)
        sys.exit(0)
    elif resp['error']:
        print('server responded with error: %s' % resp['error'])
        sys.exit(0)

    # Handshake completed.
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass

    fd = make_nbd_fd(nbd_conf, int(resp['blocks']))
    fcntl.ioctl(fd, nbd.NBD_SET_SOCK, sock.fileno())

    try:
        # This is where we block. This ioctl makes the calling process
        # serve NBD requests until interrupted or killed.
        fcntl.ioctl(fd, nbd.NBD_DO_IT)
    except BaseException:
        pass

    fcntl.ioctl(fd, nbd.NBD_DISCONNECT)
    fcntl.ioctl(fd, nbd.NBD_CLEAR_SOCK)
    fd.close()
    sock.close()


if __name__ == '__main__':
    main()
