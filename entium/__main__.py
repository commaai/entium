from .converter import convert_tiles, convert_hierarchy
from argparse import ArgumentParser, ArgumentTypeError, Action
from enum import Enum
import os

def main():
  parser = ArgumentParser(description='Convert the entwine hierarchy to a cesium tileset')

  class FullPaths(Action):
    def __call__(self, parser, namespace, values, option_string=None):
      setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))

  def is_dir(dirname):
    if not os.path.isdir(dirname):
      msg = "{0} is not a directory".format(dirname)
      raise ArgumentTypeError(msg)
    else:
      return dirname

  parser.add_argument('mode', choices=['tileset', 'tile', 'both'])
  parser.add_argument('input', action=FullPaths, type=is_dir, help='The input folder for entwine')
  parser.add_argument('output', action=FullPaths, type=is_dir, help='The output folder for the cesium tilests')
  parser.add_argument('--precision', nargs='?', type=float, default=0.01)
  parser.add_argument('--threads', type=int, default=1)
  parser.add_argument('--validate', action='store_true')

  args = parser.parse_args()

  # TODO - Multithread
  if args.mode == 'both' or args.mode == 'tile':
    print('Converting tiles...')
    convert_tiles(args.input, args.output, args.precision, args.validate)

  if args.mode == 'both' or args.mode == 'tileset':
    print('Generating tileset hierarchy...')
    convert_hierarchy(args.input, args.output)

if __name__ == '__main__':
  main()