import os
import errno
import math
import struct

from .. import nbd


class HandlerBase(object):
    def __init__(self, client_config, server):
        self.logger = server.logger
        self.loop = server.loop
        self.get_client_opt = client_config.get
        self.get_server_opt = server.config.get

    def close(self):
        pass

    def get_blocks(self, blocksize):
        return int(math.ceil(self.get_size() / blocksize))

    def get_size(self):
        return 1

    def reply(self, client, cookie, error, data=None):
        header = struct.pack('>LLQ', nbd.NBD_RESPONSE, error, cookie)
        if data is not None:
            os.writev(client.sock.fileno(), (header, data))
        else:
            client.sock.send(header)

    def flush(self, client, cookie):
        self.logger.info('flushing client')
        self.reply(client, cookie, 0)

    def read(self, client, cookie, off, size):
        self.reply(client, cookie, errno.ENOSYS)

    def write(self, client, cookie, off, data):
        self.reply(client, cookie, errno.ENOSYS)
