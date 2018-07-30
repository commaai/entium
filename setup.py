from codecs import open
from os.path import abspath, dirname, join
from subprocess import call

from setuptools import Command, find_packages, setup

from entium import __version__


project_dir = abspath(dirname(__file__))
with open(join(project_dir, 'README.rst'), encoding='utf-8') as file:
    long_description = file.read()

"""
class RunTests(Command):
    """Run all tests."""
    description = 'run tests'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """Run all tests!"""
        errno = call(['py.test', '--cov=entium', '--cov-report=term-missing'])
        raise SystemExit(errno)
"""

setup(
    name='entium',
    version= __version__,
    description='A skeleton command line program in Python.',
    long_description=long_description,
    url='https://github.com/commaai/entium',
    author='Brandon Barker',
    author_email='brandon@comma.ai',
    license = 'UNLICENSE',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Utilities',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7'
    ],
    keywords='cli',
    entry_points={
        'console_scripts': [
            'entium=entium.__main__:main',
        ]
    }
)
