#! /usr/bin/env python3

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


install_requires = ['toml']
test_requires = ['tox >= 2.3.1']
version = '0.1'


class Tox(TestCommand):

    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import tox
        import shlex
        import sys
        args = self.tox_args
        # remove the 'test' arg from argv as tox passes it to stestr which
        # breaks it.
        sys.argv.pop()
        if args:
            args = shlex.split(self.tox_args)
        errno = tox.cmdline(args=args)
        sys.exit(errno)


setup(
    name='farsight',
    version=version,
    description='client/server application for userspace block devices',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Topic :: System',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
    ],
    url='https://github.com/lmlg/farsight',
    author='Canonical Storage Team',
    license='Apache-2.0: http://www.apache.org/licenses/LICENSE-2.0',
    packages=find_packages(exclude=['unit_tests']),
    cmdclass={'test': Tox},
    install_requires=install_requires,
    extras_require={'testing': test_requires},
    tests_require=test_requires,
)
