from codecs import open
from os.path import abspath, dirname, join
from subprocess import call

from setuptools import Command, find_packages, setup

from entium import __version__


project_dir = abspath(dirname(__file__))
with open(join(project_dir, 'README.rst'), encoding='utf-8') as file:
  long_description = file.read()

with open(join('requirements.txt')) as file:
  required = file.read().splitlines()

setup(
  name='entium',
  version= __version__,
  keywords='cli, entwine, cesium, converter',
  description='A skeleton command line program in Python.',
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='https://github.com/commaai/entium',
  author='Brandon Barker',
  author_email='brandon@comma.ai',
  license = 'UNLICENSE',
  packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
  install_requires=required,
  classifiers=[
    'Intended Audience :: Developers',
    'Topic :: Utilities',
    'License :: Public Domain',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Development Status :: 4 - Beta',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4'
  ],
  entry_points={
    'console_scripts': [
      'entium=entium.__main__:main',
    ]
  }
)
