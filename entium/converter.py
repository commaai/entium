import glob
import json
import logging
import os

from .cesium.tiles import create_pointcloud, Mode, BatchComponentType, QUANTIZED_ECEF_CONSTANT
from .cesium.tileset import DirectTile, ReferenceTile
from enum import Enum, IntEnum
import numpy as np


logger = logging.getLogger(__name__)

def get_tileset_json(header, root_directory, global_meta):
  tileset = {}

  def _find_children(tile):
    if tile.depth + 1 not in tileset:
      return []
    x = tile.x * 2
    y = tile.y * 2
    z = tile.z * 2

    def is_within_cartesian(test_tile):
      return x <= test_tile.x < x + 2 and y <= test_tile.y < y + 2 and z <= test_tile.z < z + 2

    return filter(is_within_cartesian, tileset[tile.depth + 1])

  def _link_children(parents):
    for parent in parents:
      if isinstance(parent, ReferenceTile):
        continue
      parent.children = _find_children(parent)
      _link_children(parent.children)
    return parents
  
  # Get basic info on depth requirements
  base_depth = int(header.split('-')[0])
  step_size = 0 if 'hierarchyStep' not in global_meta else global_meta['hierarchyStep']

  tileset_path = os.path.join(root_directory, 'h', header)
  with open(tileset_path) as data_file:
    data = json.load(data_file)
    for tile_file in data.keys():
      tile_meta = map(int, tile_file.split('.')[0].split('-'))
      depth = tile_meta[0]
      if depth not in tileset:
        tileset[depth] = []
      is_reference = step_size != 0 and depth != base_depth and depth % step_size == 0
      tileset[depth].append(ReferenceTile(*tile_meta) if is_reference else DirectTile(*tile_meta))

  # Find all children at 
  root = _link_children(tileset[base_depth])[0]

  return {
    'asset': {
      'version': '0.0'
    },
    'geometricError': root.get_geometric_error(global_meta),
    'root': root.get_json(global_meta)
  }

def convert_hierarchy(input_path, output_path):
  if not os.path.isdir(input_path):
    raise 'Path provided is not a directory'
  
  logger.info('Reading meta...')
  with open(os.path.join(input_path, 'entwine.json'), 'r') as meta_file:
    meta = json.load(meta_file)

  headers_path = os.path.join(input_path, 'h')
  for header in os.listdir(headers_path):
    if not os.path.isfile(os.path.join(headers_path, header)):
      logger.warning('Skipping! %s' % header)
      continue

    header_id = int(header.split('-')[0])
    name = 'tileset.json' if header_id is 0 else 'tileset-' + header
    logging.info('Creating %s' % name)
    data = get_tileset_json(header, input_path, meta)
    with open(os.path.join(output_path, name), 'w') as outfile:
      logging.info('Writing %s'  % name)
      json.dump(data, outfile, indent=4)
      logging.info('Finished %s' % name)

def import_entwine_table(input_path, batch_header, groups, batched):
  entwine_header_dtype = np.dtype([ (x['name'], x['type'].value) for x in batch_header ])
  with open(input_path, 'rb') as raw_tile:
    content = np.fromfile(raw_tile, dtype=entwine_header_dtype)
    tile = create_pointcloud(content, mode=Mode.QUANTIZED, groups=groups, batch_columns=batched)
    if 'OriginId' in tile.batch_table:
      tile.batch_table.remove('OriginId') # Remove origin ID (artifact from cesium) when present
    return tile

# Cesium does not support > 16 bit integers, store bytes in alternate
class EntwineScemaType(Enum):
  INT8 = BatchComponentType.BYTE 
  INT16 = BatchComponentType.SHORT
  UINT8 = BatchComponentType.UNSIGNED_BYTE 
  UINT16 = BatchComponentType.UNSIGNED_SHORT
  FLOAT = BatchComponentType.FLOAT
  #UINT32 = BatchComponentType.FLOAT # Temporarily disabled for lack of webgl support
  #INT32 = BatchComponentType.FLOAT # Temporarily disabled for lack of webgl support
  #INT64 = BatchComponentType.DOUBLE # Temporarily disabled for lack of webgl support
  #UINT64 = BatchComponentType.DOUBLE Temporarily disabled for lack of webgl support 
  #DOUBLE = BatchComponentType.DOUBLE # Temporarily disabled for lack of webgl support

# Get header
def get_schema_type(name, type):
  raw_schema_type = str(type).strip().upper()
  if name in ['X', 'Y', 'Z'] and raw_schema_type == 'DOUBLE':
    return BatchComponentType.DOUBLE # Allow an exception for the double type for position data
  if name == 'OriginId':
    return BatchComponentType.UNSIGNED_INT
  if raw_schema_type not in EntwineScemaType.__members__:
    raise Exception('Unknown schema type: %s (%s)' % (raw_schema_type, name))
  return EntwineScemaType[raw_schema_type].value

def convert_tiles(input_path, export_path, precision=None, validate=False, groups=None, batched=None):
  total_points, total_tiles, high_precision_tiles = 0, 0, 0
  with open(os.path.join(input_path, 'entwine.json'), 'r') as meta_file:
    metadata = json.load(meta_file)
    header = [ { 'name': str(x['name']), 'type': get_schema_type(x['name'], x['type']) } for x in metadata['schema'] ]

  
  for bin_file in glob.iglob(os.path.join(input_path, '*.bin')):
    logging.info('Converting %s' % bin_file)
    tile = import_entwine_table(bin_file, header, groups, batched)
  
    points_column = tile.points
    if np.any((tile.bounds['max'] - tile.bounds['min']) / QUANTIZED_ECEF_CONSTANT > precision):
      tile.mode = Mode.FLOATING_QUANTIZED
      high_precision_tiles += 1

    cesium_file_name = '%s.pnts' % os.path.splitext(os.path.basename(bin_file))[0]
    cesium_file_path = os.path.join(export_path, cesium_file_name)
    tile.save(cesium_file_path)

    if validate:
      if points_column.mode is Mode.RTC_CENTER:
        converted_points = points_column.data() + points_column.rtc_point
      else:
        multiplier = points_column.quantized_scale 
        multiplier *= 1.0 / QUANTIZED_ECEF_CONSTANT if points_column.mode is Mode.QUANTIZED else 1.0
        converted_points = (points_column.data() * multiplier) + points_column.bounds['min']
      
      original_points = points_column.data
      distances = np.abs(converted_points - original_points)
      for idx in xrange(len(original_points)):
        distance = distances[idx]
        if np.any(distance > 1):
          original = original_points[idx]
          converted = converted_points[idx]
          logging.warning('\t- Outside Tolerance ' + str(original) + ' ~ ' + str(np.abs(original - converted)))


    total_points += tile.total_points
    total_tiles += 1

  logging.info('Completed Tiling')
  logging.info('\t- Tiles {:,}'.format(total_tiles))
  logging.info('\t- High Precision Tiles {:,}'.format(high_precision_tiles))
  logging.info('\t- Points {:,}'.format(total_points))
