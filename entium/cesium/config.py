def cesium_settings_from_entwine_config(config):
  def asciify(accum, x):
    if isinstance(x[1], list):
      remapped = [ y.encode('ascii', 'ignore') for y in x[1] ]
    else:
      remapped = x[1].encode('ascii', 'ignore')
    accum[x[0].encode('ascii', 'ignore')] = remapped
    return accum

  cesium_config = config['cesium']

  groups, batched = None, None
  if 'groups' in cesium_config:
    groups = reduce(asciify, cesium_config['groups'].iteritems(), {})

  if 'batched' in cesium_config:
    batched =  [ y.encode('ascii', 'ignore') for y in cesium_config['batched'] ]

  return groups, batched
