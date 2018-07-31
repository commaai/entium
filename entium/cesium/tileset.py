import json
import os
from math import sqrt


class Tile():

  def __init__(self, depth, x, y, z):
    self.x = x
    self.y = y
    self.z = z
    self.depth = depth

  def get_content_url(self, meta):
    raise Exception('Must override function!')

  def __repr__(self):
    return '[x %d, y %d, z %d, d %d]' % (self.x, self.y, self.z, self.depth)

  def _localize_bounds(self, meta, min_size=5000):
    scale_factor = pow(2, self.depth)
    bounds = meta['bounds']
    dimensions = map(lambda idx: abs(bounds[idx] - bounds[idx + 3]) / scale_factor, range(0, 3))

    min_dimensions = map(lambda x: max(min_size, x), dimensions)
    return {
      'x': bounds[0] + (dimensions[0] * self.x + (dimensions[0] / 2)),
      'y': bounds[1] + (dimensions[1] * self.y + (dimensions[1] / 2)),
      'z': bounds[2] + (dimensions[2] * self.z + (dimensions[2] / 2)),
      'width': min_dimensions[0],
      'depth': min_dimensions[1],
      'height': min_dimensions[2]
    }

  def get_json(self, meta):
    bounds = self._localize_bounds(meta)
    return {
      'content': {
        'uri': self.get_content_url()
      },
      'refine': 'ADD',
      'geometricError': sqrt(pow(bounds['width'], 2) + pow(bounds['depth'], 2) + pow(bounds['height'], 2)) / 2,
      'boundingVolume': {
        'box': [
          bounds['x'], bounds['y'], bounds['z'],     # Center
          bounds['width'], 0, 0, # X Transform
          0, bounds['depth'], 0, # Y Transform
          0, 0, bounds['height'] # Z Transform
        ]
      }
    }

class DirectTile(Tile):

  def __init__(self, depth, x, y, z, extension='pnts', children=None):
    Tile.__init__(self, depth, x, y, z)
    if children is None:
      children = []
    self.extension = extension

    self.children = children

  def get_json(self, meta):
    serialized = Tile.get_json(self, meta)
    if (len(self.children) > 0):
      serialized['children'] = map(lambda x: x.get_json(meta), self.children)
    return serialized

  
  def get_content_url(self):
    return '%d-%d-%d-%d.%s' % (self.depth, self.x, self.y, self.z, self.extension)


class ReferenceTile(Tile):

  def __init__(self, depth, x=0, y=0, z=0):
    Tile.__init__(self, depth, x, y, z)
  
  def get_content_url(self):
    return 'tileset-%d-%d-%d-%d.json' % (self.depth, self.x, self.y, self.z)
