from argparse import ArgumentParser, ArgumentTypeError, Action
import json
import logging
import os

from . import __version__
from .converter import convert_tiles, convert_hierarchy
from .cesium.config import cesium_settings_from_entwine_config
from enum import Enum


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
  parser = ArgumentParser(prog='entium', description='Convert the entwine hierarchy to a cesium tileset')

  class FullPaths(Action):
    def __call__(self, parser, namespace, values, option_string=None):
      setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))

  def is_dir(dirname):
    if not os.path.isdir(dirname):
      msg = '{0} is not a directory'.format(dirname)
      raise ArgumentTypeError(msg)
    else:
      return dirname

  def is_json(filename):
    if filename is not None and not os.path.isfile(filename):
      raise ArgumentTypeError('{0} is not a file'.format(filename))
    if not os.path.splitext(filename)[1] == '.json':
      raise ArgumentTypeError('{0} is not a json file'.format(filename))

    return filename

  parser.add_argument('mode', choices=['tileset', 'tile', 'both'])
  parser.add_argument('entwine_dir', action=FullPaths, type=is_dir, help='input folder for entwine')
  parser.add_argument('output_dir', action=FullPaths, type=is_dir, help='output folder for the cesium tilests')
  parser.add_argument('-p', '--precision', nargs='?', type=float, default=0.01, help='precision in meters required to use quantized tiles')
  parser.add_argument('-c', '--config', action=FullPaths, nargs='?', type=is_json, help='filepath to config file to use advanced features')
  parser.add_argument('--validate', action='store_true', help='run post-process to validate point precision')
  parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))

  args = parser.parse_args()

  groups, batched = None, None
  if args.config is not None:
    with open(args.config, 'r') as config_file:
      config = json.load(config_file)

      groups, batched = cesium_settings_from_entwine_config(config)

  # TODO - Multithread
  if args.mode == 'both' or args.mode == 'tile':
    logger.info('Converting tiles...')
    convert_tiles(args.entwine_dir, args.output_dir, args.precision, args.validate, groups, batched)

  if args.mode == 'both' or args.mode == 'tileset':
    logger.info('Generating tileset hierarchy...')
    convert_hierarchy(args.entwine_dir, args.output_dir)

if __name__ == '__main__':
  main()