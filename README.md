# Datascape: The Algorithm of "True View" (眞景山水) and Robotic Fabrication

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Arduino-00979D?style=flat&logo=arduino&logoColor=white" alt="Arduino">
  <img src="https://img.shields.io/badge/G--Code-4E4E4E?style=flat&logo=rapid&logoColor=white" alt="G-Code">
  <img src="https://img.shields.io/badge/Google_Earth_Engine-4285F4?style=flat&logo=google-earth&logoColor=white" alt="GEE">
</p>

> **"From 18th-century realism to 21st-century data: Redefining 'True View' (眞景) through procedural ink logic and robotic fabrication."**

<p align="center">
  <img src="assets/simulation_preview.png" width="100%" alt="Datascape Simulation Results">
  <br>
  <i>Fig 1. Datascape Simulation Pipeline: (1) Ink Density (Peak & Ridge), (2) Stroke Vectors (Panorama), (3) Combined Guide.</i>
</p>

## 1. Philosophy: Evolution of "True View" (眞景山水畵)

### **The 18th Century: Physical Realism**
In the 18th century, **Jinkyung-sansu-hwa** (眞景山水畵: True-view landscape painting) emerged as a revolutionary movement. Masters like Jeong Seon broke away from idealized Chinese landscapes to capture the actual Korean scenery through direct physical experience and observation. At that time, "True" meant the landscape one could physically step upon and see with human eyes.

### **The 21st Century: Digital Realism**
Three centuries later, our perception of nature has evolved through technology. In an era where high-resolution satellites and LiDAR scan the Earth’s surface in millimeter units, quantified terrain data is no longer a mere imitation. This digital data—objective, precise, and invisible to the naked eye—is the most authentic **"True View" (眞景)** of nature in the 21st century.

**Datascape** bridges these two eras. It discovers that the process of traditional masters—who "decomposed" nature into algorithmic rules like *Nongdam* (ink density) and *Junbeop* (stroke types)—is fundamentally identical to modern digital data processing.

---

## 2. Technical Implementation
This project translates the "algorithm of decomposition" from the human mind into machine language:
* **Algorithmic Mapping:** Elevation and vegetation data are transposed into ink density (Nongdam) and voids.
* **Feature Decomposition:** Land attributes are decomposed into over 10 traditional brushstroke classes (e.g., *Bubyeokjun*) and reassembled through code.
* **Robotic Fabrication:** The digital landscape escapes the screen through a custom **Arduino-based robotic plotter**. By precisely controlling brush pressure, this system proposes a new paradigm: the **Mass Production of "True Views,"** evolving the one-time nature of 18th-century art into a scalable 21st-century system.

---

## 3. Project Pipeline
1. **Data Extraction (GEE):** Harvesting global DEM and multispectral imagery via Google Earth Engine.
2. **Topographic Analysis:** Calculating **TPI (Topographic Position Index)** for peak and ridge identification using Python.
3. **Stroke Classification:** Procedural mapping of land cover to traditional stroke logic.
4. **Kinetic Realization:** Translating digital vectors into **G-code** to drive robotic motors via Arduino for physical ink wash output.

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
