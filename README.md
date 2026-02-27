# Datascape
> **Universal generative system for Oriental ink painting via GIS and robotics.**

<p align="center">
  <img src="assets/output8.jpg" width="100%" alt="Datascape Simulation Results">
</p>

## 1. Concept
**Datascape** is a generative framework that translates digital terrain data into the structural logic of traditional **Oriental ink painting**. By bridging geospatial data analysis with robotic kinetic control, the system functions as a universal translator that can interpret any global coordinates into artistic brushstrokes. This project is a synthesis of **Architecture** (spatial logic) and **Oriental Painting** (aesthetic stroke), demonstrating a scalable approach to procedural world-building.

---

## 2. Project Pipeline
1. **Data Extraction (GEE):** Ingests multispectral imagery and Digital Elevation Models (DEM) from any ROI (Region of Interest) worldwide.
2. **Topographic Analysis:** Calculates **TPI (Topographic Position Index)** and slope curvature to determine ink density (Nongdam).
3. **Stroke Classification:** Maps land cover data (NDVI, Dynamic World) to traditional brushstroke classes (Junbeop).
4. **Kinetic Realization:** Converts vectorized paths into **G-code** to drive robotic arms or gantry machines for physical output.

---

## 3. Core Modules
* **`gee/data_extraction.js`**: JavaScript module for automated geospatial data harvesting via Google Earth Engine.
* **`src/terrain_analyzer.py`**: Python engine for feature extraction, prominence mapping, and vectorization.
* **`src/landscape_renderer.py`**: Simulates traditional perspective projection with a custom horizon buffer for hidden-line removal.
* **`src/gcode_engine.py` (WIP)**: Interface for translating digital vectors into physical robotic trajectories.

---

## 4. Data Attribution & Copyright
This project adheres to ethical data usage and respects the intellectual property of original data providers:
* **Platform:** Processed via **Google Earth Engine (GEE)**.
* **Satellite Imagery:** Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED).
* **Land Cover:** Dynamic World V1 (GOOGLE/DYNAMICWORLD/V1).
* **Elevation:** NASA SRTM Digital Elevation 30m (USGS/SRTMGL1_003), resampled to 10m.
* **Copyright:** Map data ©2026 Google / NASA / USGS. Algorithmic logic and artistic system design ©2026 Seong Geon Lee.
