from codecs import open
from os.path import abspath, dirname, join
from subprocess import call

from setuptools import Command, find_packages, setup

from entium import __version__


project_dir = abspath(dirname(__file__))
with open(join(project_dir, 'README.md'), encoding='utf-8') as file:
  long_description = file.read()

with open(join(project_dir, 'requirements.txt')) as file:
  required = file.read().splitlines()

setup(
  name='entium',
  version= __version__,
  keywords='cli, entwine, cesium, converter',
  description='A command line tool to read entwine\'s convert into Cesium 3DTiles',
  long_description=long_description,
  long_description_content_type='text/markdown',
  url='https://github.com/commaai/entium',
  author='Brandon Barker',
  author_email='brandon@comma.ai',
  license='MIT LICENSE',
  packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
  install_requires=required,
  classifiers=[
    'Intended Audience :: Developers',
    'Topic :: Utilities',
    'License :: Public Domain',
    'Natural Language :: English',
    'Operating System :: OS Independent',
    'Development Status :: 4 - Beta',
    'Programming Language :: Python :: 2.7'
  ],
  entry_points={
    'console_scripts': [
      'entium=entium.__main__:main',
    ]
  }
)
