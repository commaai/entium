# entium
A command line tool to read [entwine's](http://entwine.io) output and convert it into
[Cesium 3DTiles](https://github.com/AnalyticalGraphicsInc/3d-tiles).

## Installation
Entium supports python 2.7 or greater. To install run: 
`pip install entium`
Ensure there is an active installation of python on the machine!

### Development
To make modifications or install a development version run:
```
git clone https://github.com/commaai/entium.git
cd entium
pip install .
```

## Command Usage
```
usage: entium [-h] [-p [PRECISION]] [-c [CONFIG]] [--validate]
              {tileset,tile,both} entwine_dir output_dir

Convert the entwine hierarchy to a cesium tileset

positional arguments:
  {tileset,tile,both}
  entwine_dir           input folder for entwine
  output_dir            output folder for the cesium tilests

optional arguments:
  -h, --help            show this help message and exit
  -p [PRECISION], --precision [PRECISION]
                        precision in meters required to use quantized tiles
  -c [CONFIG], --config [CONFIG]
                        filepath to config file to use advanced features
  --validate            run post-process to validate point precision
```

## Configuration
The average user will not need a configuration file if the intent is to directly convert entwines output into cesium tiles. However, if the goal is to use more component types larger than a scalar many of the configuration options may be helpful. The config is a `.json` intended to exist within the `entwine.json`.

### Grouping Attributes
Grouping works for both **batch table** properties and **feature table** properties. To have grouped component stored as a feature table value instead of batch table use one of the specified names:
 - RGB
 - RGBA
 - RGB565
 - NORMAL
 - NORMAL_OCT16P
 - BATCH_ID

See [point semantics](https://github.com/AnalyticalGraphicsInc/3d-tiles/blob/master/specification/TileFormats/PointCloud/README.md#semantics) for more information about these properties. Its also import to note that the order the items are defined in the array will define the order they exist in the component.
#### Example 1 
*RGB* will be recognized as a feature attribute and grouped while *pose* will be recognized and grouped as a batch attribute.
```json\
"cesium": {
    "groups": {
        "rgb": [
            "r", 
            "g", 
            "b"
        ], 
        "pose": [
            "poseX", 
            "poseY", 
            "poseZ",
	        "poseW"
        ]
    }
}
```

### Example 2 
Single properties can also be renamed. In this example, *color* is being renamed to *rgb565*.
```json
    "cesium": {
        "groups": {
            "rgb565": "color"
        }
    }
```
### Batching Table Attributes (Experimental)
Sometimes points have metadata attached to them but that value is representative of some kind of group. This has the potential to reduce data duplication and provide enhanced styling through cesium. Currently the design allows for some attributes to not be in a batch table and rather act as a batch attribute. The hope is sometime in the future both types of batch attributes can be used in unison. 

#### Example
```json
    "cesium": {
        "batched": [
            "id",
            "version"
        ]
    }
```


## Todo
 - [X] Property grouping
 - [X] Support batch properties
 - [X] Support batch tables
 - [ ] Add unit testing 
 - [ ] Only update modified tiles
 - [ ] Parallelize conversion to 3DTiles