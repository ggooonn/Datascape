// ============================================================
// DATASCAPE: SEOUL NORTH / FOUR SEASONS
// Google Earth Engine JavaScript - v0.2
// Outputs: 30 m terrain master + 10 m seasonal vegetation
// ============================================================

// [A] CONFIGURATION
var CFG = {
  ROI: [126.82, 37.50, 127.12, 37.71], // W, S, E, N
  START: '2022-01-01',
  END: '2026-01-01',  // exclusive: 2022-2025 observations
  DRIVE_FOLDER: 'Datascape_SeoulNorth',
  CRS: 'EPSG:32652',
  GRID30: [30, 0, 0, 0, -30, 5000000],
  GRID10: [10, 0, 0, 0, -10, 5000000],
  CLOUD_SCORE_MIN: 0.60,
  SCENE_CLOUD_MAX: 80,
  NODATA: -9999,
  EXPORT_VEG_10M: true
};

var roi = ee.Geometry.Rectangle(CFG.ROI, null, false);
var projection10 = ee.Projection(CFG.CRS, CFG.GRID10);

Map.centerObject(roi, 11);
Map.addLayer(roi, {color: 'red'}, 'ROI', false);

// [B] TERRAIN: Copernicus 2024_1 and NASADEM comparison
var copCollection = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1')
  .filterBounds(roi)
  .select('DEM');

// Set mosaic projection BEFORE calculating terrain derivatives.
var copNative = ee.Image(copCollection.first()).projection();
var dem = copCollection.mosaic()
  .setDefaultProjection(copNative)
  .rename('DEM');

var terrain = ee.Terrain.products(dem);
var slope = terrain.select('slope').rename('SLOPE');
var aspect = terrain.select('aspect').rename('ASPECT');
var hillshade = terrain.select('hillshade').rename('HILLSHADE');

var nasa = ee.Image('NASA/NASADEM_HGT/001')
  .select('elevation')
  .rename('DEM_NASA');

// [C] SENTINEL-2: seasonal NDVI with pixel-level cloud masking
var csPlus = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(roi)
  .filterDate(CFG.START, CFG.END)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CFG.SCENE_CLOUD_MAX))
  .linkCollection(csPlus, ['cs_cdf']);

function cleanNDVI(img) {
  var scl = img.select('SCL');
  var valid = scl.neq(0)
    .and(scl.neq(1))
    .and(scl.neq(3))
    .and(scl.neq(8))
    .and(scl.neq(9))
    .and(scl.neq(10))
    .and(scl.neq(11));
  var clear = img.select('cs_cdf').gte(CFG.CLOUD_SCORE_MIN);

  return img.normalizedDifference(['B8', 'B4'])
    .rename('NDVI')
    .updateMask(valid.and(clear))
    .copyProperties(img, ['system:time_start']);
}

var ndviScenes = s2.map(cleanNDVI);

function makeSeason(label, firstMonth, lastMonth) {
  var scenes = ndviScenes.filter(
    ee.Filter.calendarRange(firstMonth, lastMonth, 'month')
  );
  print(label + ' scene count (before pixel mask):', scenes.size());

  // Important: collection composites otherwise default to ~1-degree CRS.
  var ndvi10 = scenes.median()
    .rename('NDVI_' + label)
    .setDefaultProjection(projection10);
  var count10 = scenes.count()
    .rename('N_' + label)
    .setDefaultProjection(projection10);

  // Area-weighted aggregation from ~10 m pixels to the 30 m grid.
  // The output grid is selected by the 30 m export below.
  var ndvi30 = ndvi10.reduceResolution({
    reducer: ee.Reducer.mean(),
    maxPixels: 64
  });
  // Mean valid observation count across the underlying 10 m pixels.
  var count30 = count10.reduceResolution({
    reducer: ee.Reducer.mean(),
    maxPixels: 64
  });

  return {ndvi10: ndvi10, count10: count10,
          ndvi30: ndvi30, count30: count30};
}

var spring = makeSeason('SPRING', 3, 5);
var summer = makeSeason('SUMMER', 6, 8);
var autumn = makeSeason('AUTUMN', 9, 11);
var winter = makeSeason('WINTER', 12, 2);

// [D] PREVIEW
Map.addLayer(dem.clip(roi),
  {min: 0, max: 850, palette: ['152438','526f62','c6b598','f3f1eb']},
  '01 Copernicus DEM', true);
Map.addLayer(hillshade.clip(roi), {min: 0, max: 255},
  '02 Hillshade', false);
Map.addLayer(nasa.clip(roi), {min: 0, max: 850},
  '03 NASADEM comparison', false);
var ndviVis = {min: -0.1, max: 0.85,
  palette: ['c7afa1','efe1a4','80ae6c','1e6a40']};
Map.addLayer(spring.ndvi10.clip(roi), ndviVis, '04 NDVI Spring', false);
Map.addLayer(summer.ndvi10.clip(roi), ndviVis, '05 NDVI Summer', false);
Map.addLayer(autumn.ndvi10.clip(roi), ndviVis, '06 NDVI Autumn', false);
Map.addLayer(winter.ndvi10.clip(roi), ndviVis, '07 NDVI Winter', false);
Map.addLayer(winter.count10.clip(roi),
  {min: 0, max: 30, palette: ['d23838','f0dc67','4c996b']},
  '08 Winter valid-observation count', false);

// [E] EXPORT 1: 30 m MULTIBAND MASTER (13 bands)
var master30 = ee.Image.cat([
  dem, slope, aspect, hillshade, nasa,
  spring.ndvi30, summer.ndvi30, autumn.ndvi30, winter.ndvi30,
  spring.count30, summer.count30, autumn.count30, winter.count30
]).toFloat().clip(roi);

print('MASTER 30 m bands (13):', master30.bandNames());

Export.image.toDrive({
  image: master30.unmask(CFG.NODATA),
  description: 'SeoulNorth_v02_MASTER_30m',
  fileNamePrefix: 'SeoulNorth_v02_MASTER_30m',
  folder: CFG.DRIVE_FOLDER,
  region: roi,
  crs: CFG.CRS,
  crsTransform: CFG.GRID30,
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF',
  formatOptions: {noData: CFG.NODATA, cloudOptimized: true}
});

// [F] EXPORT 2: NATIVE-DETAIL 10 m VEGETATION (8 bands)
var vegetation10 = ee.Image.cat([
  spring.ndvi10, summer.ndvi10, autumn.ndvi10, winter.ndvi10,
  spring.count10, summer.count10, autumn.count10, winter.count10
]).toFloat().clip(roi);

print('VEGETATION 10 m bands (8):', vegetation10.bandNames());

if (CFG.EXPORT_VEG_10M) {
  Export.image.toDrive({
    image: vegetation10.unmask(CFG.NODATA),
    description: 'SeoulNorth_v02_VEG_10m',
    fileNamePrefix: 'SeoulNorth_v02_VEG_10m',
    folder: CFG.DRIVE_FOLDER,
    region: roi,
    crs: CFG.CRS,
    crsTransform: CFG.GRID10,
    maxPixels: 1e9,
    fileFormat: 'GeoTIFF',
    formatOptions: {noData: CFG.NODATA, cloudOptimized: true}
  });
}

print('Ready: open the Tasks tab and RUN the two export tasks.');
