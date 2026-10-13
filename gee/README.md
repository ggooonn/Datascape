# Google Earth Engine

- [Seoul North v0.2](seoul_north_v02.js): preserved supplied script; exports a 13-band MASTER at 30 m and an 8-band VEG raster at 10 m.
- [Dataset specification](../docs/datasets/seoul_north_v02.json): expected metadata, not measured validation results.
- [Initial extraction script](archive/geedata_extraction.js): preserved from the original repository. Its exact relationship to historical production inputs still needs confirmation.

Keep raw GeoTIFFs locally. Verify their CRS, grids, masks, ranges, and observation counts in Python. Resampling does not add terrain detail beyond the source DEM. Winter combines December–February observations across multiple years.
