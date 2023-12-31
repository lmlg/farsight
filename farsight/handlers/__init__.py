HANDLER_CLASSES = {}

try:
    from . import rbd
    HANDLER_CLASSES['rbd'] = rbd.RBDHandler
except ImportError as exc:
    HANDLER_CLASSES['rbd'] = exc


def get_handler_class(name):
    return HANDLER_CLASSES.get(name)
