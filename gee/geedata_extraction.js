/**
 * Datascape: Universal Oriental Ink Painting Generative System
 * Module 0: Geospatial Data Extraction & Pre-processing
 * * This script extracts multispectral imagery, elevation, and land cover data 
 * from Google Earth Engine for artistic interpretation.
 */

// 1. Define Area of Interest (AOI)
// You can change these coordinates to any location worldwide.
var roi = ee.Geometry.Polygon([
  [[128.020, 38.610],
   [128.110, 38.610],
   [128.110, 38.670],
   [128.020, 38.670]]
]);

Map.centerObject(roi, 13);
var startDate = '2023-09-01'; 
var endDate = '2023-10-31';

// 2. Sentinel-2 Satellite Imagery & NDVI (Vegetation Index)
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(roi)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
  .median()
  .clip(roi);

var ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI');

// 3. Dynamic World (Land Cover Classification Mask)
var dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
  .filterBounds(roi)
  .filterDate(startDate, endDate)
  .select('label')
  .mode()
  .clip(roi);

// 4. Digital Elevation Model (SRTM 30m)
// Bilinear resampling to 10m to match Sentinel-2 resolution for high-fidelity analysis.
var dem = ee.Image("USGS/SRTMGL1_003")
  .select('elevation')
  .resample('bilinear')
  .clip(roi);

var slope = ee.Terrain.slope(dem);
var aspect = ee.Terrain.aspect(dem);

// 5. Batch Export to Google Drive
var exportScale = 10; 
var exportCrs = 'EPSG:32652'; 

var layers = {
  'Kumgang_DEM': dem,
  'Kumgang_Slope': slope,
  'Kumgang_Aspect': aspect,
  'Kumgang_NDVI': ndvi,
  'Kumgang_DynamicWorld': dw
};

// Iterative export (ES5 syntax for GEE compatibility)
Object.keys(layers).forEach(function(key) {
  Export.image.toDrive({
    image: layers[key],
    description: key,
    folder: 'Datascape',
    scale: exportScale,
    crs: exportCrs,
    region: roi
  });
});