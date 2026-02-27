# Datascape: The Algorithm of "True View" (眞景) and Robotic Fabrication

> **"Defining the digital landscape as the 21st-century's 'True View' and realizing it through procedural ink logic and robotic fabrication."**

<p align="center">
  <img src="assets/simulation_preview.png" width="100%" alt="Datascape Simulation Results">
</p>

## 1. Philosophy: Digital "True View" (眞景)
Traditionally, **Jingyeong-sansu** (True-view landscape painting) referred to artists capturing the landscape they physically stepped upon and saw. Today, in an era where high-resolution satellites and LiDAR scan the Earth’s surface in millimeter units, quantified terrain data is not a mere imitation. This digital data itself is the most objective and "True View" of nature in the 21st century.

**Datascape** discovers the fundamental similarity between the working methods of historical landscape masters and modern digital algorithms. Historical masters did not simply copy nature; they "decomposed" it and applied "rules." They mapped towering peaks to ink density and categorized rock formations into symbolic stroke types like *Bubyeokjun*. In essence, the process of traditional landscape painting was already a sophisticated form of **algorithmic data processing** within the artist's mind.

---

## 2. Technical Implementation
This project translates the "algorithm of decomposition and recombination" from the human mind into machine language.
* **Algorithmic Mapping:** Elevation and vegetation data are transposed into ink density and voids.
* **Feature Decomposition:** Land attributes are decomposed into over 10 traditional brushstroke classes and reassembled through code.
* **Robotic Fabrication:** The digital landscape escapes the screen through a custom-designed **robotic plotter**. By precisely controlling brush pressure on traditional paper, this system proposes a new paradigm: the **Mass Production of "True Views,"** moving beyond the one-time nature of traditional art.

---

## 3. Project Pipeline
1. **Data Extraction (GEE):** Harvesting global DEM and multispectral imagery.
2. **Terrain Analysis:** Calculating **TPI (Topographic Position Index)** for peak/ridge identification.
3. **Stroke Classification:** Procedural mapping of land cover to traditional stroke logic.
4. **Kinetic Realization:** Generating robotic G-code for physical ink wash output.

---

## 4. Core Modules
* **`gee/data_extraction.js`**: JavaScript module for automated geospatial data harvesting.
* **`src/`**: Modularized Python engine for analysis and visualization.
  * `terrain_analyzer.py`: GIS feature extraction and prominence mapping.
  * `landscape_renderer.py`: Traditional perspective projection with horizon buffer.
  * `gcode_engine.py` (WIP): Robotic trajectory and pressure control interface.

---

## 5. Attribution & Copyright
* **Platform:** Processed via **Google Earth Engine (GEE)**.
* **Data Sources:** NASA SRTM 30m, Sentinel-2 L2A, Dynamic World V1.
* **Copyright:** Map data ©2026 Google / NASA / USGS. Algorithmic logic and robotic system design ©2026 Seong Geon Lee.
