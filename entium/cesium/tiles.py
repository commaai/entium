import glob
import json
import os
import struct

from enum import IntEnum, Enum
import numpy as np
from numpy.lib.recfunctions import merge_arrays


def get_padding_bytes(total_bytes, required_multiple):
  if total_bytes % required_multiple != 0:
    return required_multiple - (total_bytes % required_multiple)
  else:
    return 0 

def binjsonify(func):
  def wrapper(*args, **kwargs):
    result = func(*args, **kwargs)
    json_dump = json.dumps(result, separators=(',', ':'))
    # Required 4  byte Padding for parsing of data (https://github.com/AnalyticalGraphicsInc/3d-tiles/blob/master/TileFormats/BatchTable/README.md#implementation-notes)
    # Doubled to 8 since 8 is the largest amount of bytes that can be stored
    json_dump += ' ' * get_padding_bytes(len(json_dump), 8) 
    return json_dump.encode('utf-8'); 
  return wrapper

class BatchComponentType(Enum):
  BYTE = np.int8 
  UNSIGNED_BYTE = np.uint8
  SHORT = np.int16
  UNSIGNED_SHORT = np.uint16
  INT = np.int32
  UNSIGNED_INT = np.uint32
  FLOAT = np.float32
  DOUBLE = np.float64

class BatchType(Enum):
  SCALAR = 1
  VEC2 = 2
  VEC3 = 3
  VEC4 = 4
  
class Mode(Enum):
  STANDARD = 0
  QUANTIZED = 1
  FLOATING_QUANTIZED = 2
  RTC_CENTER = 3

# Required by cesium to properly scale
# https://github.com/AnalyticalGraphicsInc/3d-tiles/tree/master/TileFormats/PointCloud#quantized-positions
QUANTIZED_ECEF_CONSTANT = float(pow(2, 16) - 1)

class AbstractColumn(object):
  def __init__(self, name, data):
    self.name = name
    self._data = data
    self.dtype = self._data.dtype.type if self.count() == 1 else self._data.dtype[0].type

    if self.count() > 1 and any([ data.dtype[name].type != self.dtype for name in data.dtype.names ]):
      info = ', '.join([ '%s(%s)' % (x, str(data.dtype[x])) for x in data.dtype.names ])
      raise ValueError('Datatypes are not matching %s' % info)

  def __eq__(self, other):
    if isinstance(other, BatchColumn):
        return self.name == other.name
    elif isinstance(other, str):
      return self.name == other
    return False

  def data(self):
    return self._data

  def count(self):
    return 1 if self._data.dtype.names is None else len(self._data.dtype.names)

  def names(self):
    if self.count() == 1:
      return [ self.name ]
    else:
      return self._data.dtype.names
  
  def get_itemsize(self):
    return self.data().itemsize

  def get_size(self):
    return self.data().nbytes

  def get_header(self, offset):
    raise NotImplementedError('get_header has not been implemented!')


class BatchColumn(AbstractColumn):
  def __init__(self, name, data, is_instanced=False):
    super(BatchColumn, self).__init__(name, data)
    self.is_instanced = is_instanced

  def get_component_type(self):
    return BatchComponentType(self.dtype)

  def get_batch_type(self):
    return BatchType(self.count())

  def get_header(self, offset):
    if self.is_instanced:
      if self.count() == 1:
        content = self._data.tolist()
      else:
        content = { name: self._data[name].tolist() for name in self._data.dtype.names }
    else:
      content = {
        'byteOffset': offset,
        'componentType': self.get_component_type().name,
        'type': self.get_batch_type().name
      }

    return { self.name: content }

class FeatureColumn(AbstractColumn):

  # Feature types and what is batch_item
  # https://github.com/AnalyticalGraphicsInc/3d-tiles/blob/master/TileFormats/PointCloud/README.md#point-semantics
  TYPES = {
    'position': 3,
    'rgb': 3,
    'rgba': 4,
    'rgb565': 1,
    'normal': 3,
    'normal_oct16p': 2,
    'batch_id': 1
  }

  def __init__(self, name, data, header_semantics=None):
    super(FeatureColumn, self).__init__(name, data)
    
    if header_semantics is None:
      header_semantics = {}

    if self.count() != FeatureColumn.TYPES[name]:
      raise Exception('Expected %d items in %s but recieved %d.' % (FeatureColumn.TYPES[name], name, self.count()))
    
    self.header_semantics = header_semantics

  def get_header(self, offset):
    header = {
      self.name.upper(): {
        'byteOffset': offset
      }
    }

    header.update(self.header_semantics)

    return header

class PositionColumn(FeatureColumn):
  def __init__(self, name, data, mode):
    super(PositionColumn, self).__init__(name, data)
    self.length = self._data.size # Save the size before transform
    self._data = self._data.view((self.dtype, 3))
    self.mode = mode

  def get_header(self, offset):
    if self.mode is Mode.RTC_CENTER or self.mode is Mode.STANDARD:
      header = {
        'POSITION': {
          'byteOffset': offset
        }
      }

      if self.mode is Mode.RTC_CENTER:
        header['RTC_CENTER'] = self.rtc_point.tolist()

    else:
      header = {
        'QUANTIZED_VOLUME_SCALE': self.quantized_scale.tolist(),
        'QUANTIZED_VOLUME_OFFSET': self.bounds['min'].tolist()
      }

      if self.mode is Mode.FLOATING_QUANTIZED:
        header['FLOATING_POSITION_QUANTIZED'] = {
          'byteOffset': offset
        }
      else:
        header['POSITION_QUANTIZED'] = {
          'byteOffset': offset
        }

    header['POINTS_LENGTH'] = self.length
    return header

  @property
  def bounds(self):
    return {
      'min': np.min(self._data, axis=0),
      'max': np.max(self._data, axis=0)
    }

  def data(self):
    if self.mode is Mode.RTC_CENTER:
      return self.rtc_points
    elif self.mode is Mode.QUANTIZED:
      return self.quantized_points
    elif self.mode is Mode.FLOATING_QUANTIZED:
      return self.normalized_points

  @property
  def rtc_point(self):
    return self.bounds['min'] + (self.bounds['max'] / 2.0)

  @property
  def rtc_points(self):
    return (self._data - self.rtc_point) \
      .astype(np.float32)

  @property
  def quantized_scale(self):
    return np.absolute(self.bounds['max'] - self.bounds['min']) 
      
  @property
  def quantized_points(self):
    multiplier = QUANTIZED_ECEF_CONSTANT / self.quantized_scale
    return ((self._data - self.bounds['min']) * multiplier) \
      .astype(np.uint16)

  @property
  def normalized_points(self):
    return np.nan_to_num((self._data - self.bounds['min']) / self.quantized_scale) \
      .astype(np.float32)

class Table(list):

  @binjsonify
  def get_header(self):
    table = {}
    offset = 0
    for item in self:
      offset += get_padding_bytes(offset, item.get_itemsize())
      table.update(item.get_header(offset))
      offset += item.get_size()

    return table

  def get_size(self):
    return reduce(lambda offset, item: offset + get_padding_bytes(offset, item.get_itemsize()) + item.get_size(), self, 0)

  def write(self, write_buffer, byte_offset=0):
    # Write Batch Table
    write_buffer.write(self.get_header())
    # Write each property sequentially
    for item in self:
      # Write padding to fix offset (Required that data starts on multiple of byte size to be parsed in JS)
      padding = get_padding_bytes(byte_offset, item.get_itemsize())
      write_buffer.write(struct.pack('x' * padding))
      byte_offset += padding

      item.data().tofile(write_buffer)
      byte_offset += item.get_size()


DEFAULT_GROUPS = { 'position': ['X', 'Y', 'Z'] }

def merge_dicts(x, y):
    z = x.copy() # start with x's keys and values
    z.update(y)  # modifies z with y's keys and values & returns None
    return z

def create_pointcloud(data, mode=None, groups=None, batch_columns=None):
  if mode is None:
    mode = Mode.STANDARD
  if groups is None:
    groups = {}
  groups = merge_dicts(DEFAULT_GROUPS, groups)
  if batch_columns is None:
    batch_columns = []

  columns = []
  def add(name, data):
    if name == 'position':
      columns.append(PositionColumn(name, data, mode))
    elif name.lower() in FeatureColumn.TYPES:
      columns.append(FeatureColumn(name.lower(), data))
    else:
      columns.append(BatchColumn(name, data))


  # Remap columns based off their groupings
  grouped = set()
  for name, selection in groups.iteritems():
    add(name, data[selection])
    grouped.update(selection if isinstance(selection, list) else [selection])
  for column in (set(data.dtype.names) - grouped):
    add(column, data[column])

  # Find all mapped values and replace it with their mapping
  if len(batch_columns) > 0:
    r_columns, r_names = [], []
    for column in batch_columns:
      if column not in columns:
        raise Exception('Column %s does not exist' % column)
      r_column = columns[columns.index(column)]
      r_columns.append(r_column)
      r_names.extend(r_column.names())

    merged_data = merge_arrays([ x.data() for x in r_columns ], flatten=True, usemask=False)
    merged_data.dtype.names = r_names
    batch_groups, batch_ids = np.unique(merged_data, axis=0, return_inverse=True)
    batch_ids = batch_ids.astype(np.uint16)

    idx_offset = 0
    for column in r_columns:
      column.is_instanced = True
      d_names = column.names()
      selector = d_names[0] if column.count() == 1 else d_names
      column._data = batch_groups[selector]

    columns.append(FeatureColumn('batch_id', batch_ids, { 'BATCH_LENGTH': len(batch_groups) }))

  return PointcloudTile(columns)

class PointcloudTile(object):

  def __init__(self, columns):
    self.total_points = -1
    self.position_column = None
    self.feature_table = Table()
    self.batch_table = Table()

    for column in columns:
      if isinstance(column, PositionColumn):
        self.position_column = column
      if isinstance(column, FeatureColumn):
        self.feature_table.append(column)
      elif isinstance(column, BatchColumn):
        self.batch_table.append(column)
      else:
        raise Exception('Unknown column type!')

    # Validate the minimum amount of data is present
    if self.position_column is None:
      raise Exception('Position is not present!')

    self.total_points = self.position_column.length

  @property
  def points(self):
    return self.position_column
  
  @property
  def bounds(self):
    return self.points.bounds

  @property
  def mode(self):
    self.points.mode

  @mode.setter
  def mode(self, mode):
    self.points.mode = mode

  def save(self, output_path):
    with open(output_path, 'wb') as cesium_tile:
      header_struct = struct.Struct('4sIIIIII')

      feature_header = self.feature_table.get_header()
      feature_size = self.feature_table.get_size()
      padding = get_padding_bytes(header_struct.size + feature_size + len(feature_header), 8)

      # Skip writing if size is 0
      if len(self.batch_table) > 0:
        batch_header_length = len(self.batch_table.get_header())
        batch_size = self.batch_table.get_size()
      else:
        batch_header_length = 0
        batch_size = 0

      # Write Header
      cesium_tile.write(header_struct.pack(
        'pnts',                  # magic key (DO NOT CHANGE)
        1,                       # Version, It has to be one according ot docs
        0,                       # Byte length (currently unread)
        len(feature_header),     # byte space of json info
        feature_size + padding,  # byte space of feature data, we include padding as it will be excluded later
        batch_header_length,     # byte space of json info
        batch_size              # byte space of batch data
      ))

      self.feature_table.write(cesium_tile) # Write Feature Table
      cesium_tile.write(struct.pack('x' * padding)) # Write Padding
      if len(self.batch_table) > 0:
        self.batch_table.write(cesium_tile) # Write Batch table

