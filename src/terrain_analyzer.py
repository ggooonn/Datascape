import numpy as np
import cv2
import rasterio

class TerrainAnalyzer:
    """Extracts topographic features from GIS data for artistic interpretation."""
    
    def __init__(self, data):
        self.dem = data['dem']
        self.slope = data['slope']
        self.ndvi = data['ndvi']

    def calculate_prominence(self, kernel_size=81):
        """Calculates Topographic Position Index (TPI) to find local peaks."""
        dem_norm = np.clip(self.dem / np.max(self.dem), 0, 1)
        local_mean = cv2.GaussianBlur(dem_norm, (kernel_size, kernel_size), 0)
        tpi = dem_norm - local_mean
        return np.clip(tpi * 6.0, 0, 1)

    def get_gradients(self):
        """Calculates flow angles for stroke orientation."""
        dem_smooth = cv2.GaussianBlur(self.dem, (11, 11), 3)
        dy, dx = np.gradient(dem_smooth)
        return np.arctan2(dy, dx)