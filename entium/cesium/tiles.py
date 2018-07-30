from enum import IntEnum, Enum
import numpy as np
import glob
import struct
import json
import os

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

class Mode(Enum):
  QUANTIZED = 0
  FLOATING_QUANTIZED = 1
  RTC_CENTER = 3

# Required by cesium to properly scale
# https://github.com/AnalyticalGraphicsInc/3d-tiles/tree/master/TileFormats/PointCloud#quantized-positions
QUANTIZED_ECEF_CONSTANT = float(pow(2, 16) - 1)

class BatchColumn(object):
  def __init__(self, name, data):
    self.name = name
    self._data = data
    self.dtype = self._data.dtype.type if self.count == 1 else self._data.dtype[0].type

    if self.count > 1 and any(map(lambda name: data.dtype[name].type != self.dtype, data.dtype.names)):
      info = ', '.join(map(lambda x: x + ' (' + str(data.dtype[x]) + ')', data.dtype.names))
      raise Exception('Datatypes are not matching %s' % info)

  def __eq__(self, other):
    if isinstance(other, BatchColumn):
        return self.name == other.name
    elif isinstance(other, str):
      return self.name == other
    return False

  def data(self):
    return self._data

  @property
  def count(self):
    return 1 if self._data.dtype.names is None else len(self._data.dtype.names)
  
  def get_itemsize(self):
    return self.data().itemsize

  def get_size(self):
    return self.data().nbytes

  def get_component_type(self):
    return BatchComponentType(self.dtype)

  def get_batch_type(self):
    return BatchType(self.count)

  def get_header(self, offset=0):
    return {
      self.name: {
        'byteOffset': offset,
        'componentType': self.get_component_type().name,
        'type': self.get_batch_type().name
      }
    }

class FeatureColumn(BatchColumn):

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

  def __init__(self, name, data):
    BatchColumn.__init__(self, name, data)
    if self.count != FeatureColumn.TYPES[name]:
      raise Exception('Expected %d items in %s but recieved %d.' % (FeatureColumn.TYPES[name], name, self.count))

  def get_header(self, offset=0):
    return {
      self.name.upper(): {
        'byteOffset': offset
      }
    }

class PositionColumn(FeatureColumn):
  def __init__(self, name, data, mode):
    FeatureColumn.__init__(self, name, data)
    self.length = self._data.size # Save the size before transform
    self._data = self._data.view((self.dtype, 3))
    self.mode = mode

  def get_header(self, offset):
    if self.mode is Mode.RTC_CENTER:
      header = {
        'RTC_CENTER': self.rtc_point.tolist(),
        'POSITION': {
          'byteOffset': 0
        }
      }
    else:
      header = {
        'QUANTIZED_VOLUME_SCALE': self.quantized_scale.tolist(),
        'QUANTIZED_VOLUME_OFFSET': self.bounds['min'].tolist(),
      }
      if self.mode is Mode.FLOATING_QUANTIZED:
        header['FLOATING_POSITION_QUANTIZED'] = {
          'byteOffset': 0
        }
      else:
        header['POSITION_QUANTIZED'] = {
          'byteOffset': 0
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

class PointcloudTile(object):

  def __init__(self, data, groups=None, mode=None):
    if groups is None:
      groups = { 'position': ['X', 'Y', 'Z'] }
    if mode is None:
      mode = Mode.QUANTIZED
    self.total_points = data.size
    self.position_column = None
    self.feature_table = Table()
    self.batch_table = Table()

    def add(name, data):
      if name == 'position':
        self.position_column = PositionColumn(name, data, mode)
        self.feature_table.insert(0, self.position_column)
      elif name in FeatureColumn.TYPES:
        self.feature_table.append(FeatureColumn(name, data))
      else:
        self.batch_table.append(BatchColumn(name, data))
    
    # Remap columns based off their groupings.
    grouped = set()
    for name, columns in groups.iteritems():
      add(name, data[columns])
      grouped.update(columns)
    for column in (set(data.dtype.names) - grouped):
      add(column, data[column])

    # Validate the minimum amount of data is present
    if self.position_column is None:
      raise Exception('Position is not present!')

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

