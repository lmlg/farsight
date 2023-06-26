from . import base

import errno
import os

import rados
import rbd


class RBDHandler(base.HandlerBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rbd_conf = self.get_server_opt('rbd')
        conffile = rbd_conf.get('ceph_conf', '/etc/ceph/ceph.conf')
        user = rbd_conf.get('ceph_user', 'client.admin')
        pool = self.get_client_opt('pool')
        image = self.get_client_opt('image')

        self.cluster = rados.Rados(conffile=conffile, name=user)
        self.cluster.connect()
        self.ioctx = self.cluster.open_ioctx(pool)
        self.image = rbd.Image(self.ioctx, image)

    def _reply_exc(self, client, cookie, exc):
        # Try to extract the errno code out of an OS Exception.
        err = getattr(exc, 'errno', errno.EIO)
        self.reply(client, cookie, err)

    def _error_tuple(self, code):
        return (errno.errocode.get(code, '???'), os.strerror(code))

    def get_size(self):
        return self.image.stat()['size']

    def flush(self, client, cookie):
        try:
            self.logger.info('RBD: flushing image')
            self.image.flush()
            self.reply(client, cookie, 0)
        except Exception as exc:
            self.logger.exception('RBD: failed to flush image')
            self._reply_exc(client, cookie, exc)

    def read(self, client, cookie, off, size):
        def oncomplete(obj, buf):
            if buf is None:
                # Couldn't read any data - Reply with an error.
                if obj.exc_info is not None:
                    err = getattr(obj, 'errno', obj.exc_info[1], errno.EIO)
                else:
                    err = errno.EIO
                self.logger.error('RBD: failed to read: (%s: %s)' %
                                  self._error_tuple(err))
                self.reply(client, cookie, err)
            else:
                # Reply with the read data.
                self.logger.info('RBD: read %d bytes' % len(buf))
                self.reply(client, cookie, 0, buf)

        try:
            self.image.aio_read(off, size, oncomplete)
        except Exception as exc:
            self.logger.exception('RBD: failed to queue read operation')
            self._reply_exc(client, cookie, exc)

    def write(self, client, cookie, off, data):
        def oncomplete(obj, _):
            err = obj.get_return_value()
            if err < 0:
                self.logger.error('RBD: failed to write: (%s: %s)' %
                                  self._error_tuple(-err))
            self.reply(client, cookie, 0 if err >= 0 else -err)

        try:
            self.image.aio_write(data, off, oncomplete)
        except Exception as exc:
            self.logger.exception('RBD: failed to queue write operation')
            self._reply_exc(client, cookie, exc)

    def close(self):
        self.image.close()
        self.ioctx.close()
        self.cluster.shutdown()
