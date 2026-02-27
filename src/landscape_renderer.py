import numpy as np

class LandscapeRenderer:
    """Simulates traditional Oriental perspective and manages visualization."""
    
    def __init__(self, z_scale=650.0):
        self.z_scale = z_scale
        self.angle = np.radians(15)
        self.pitch = 0.15

    def project(self, x, y, z):
        """Projects 3D coordinates into 2D landscape view."""
        rx = x * np.cos(self.angle) - y * np.sin(self.angle)
        ry = x * np.sin(self.angle) + y * np.cos(self.angle)
        
        xp = rx
        yp = ry * self.pitch - z * self.z_scale
        return xp, yp

    def update_horizon(self, py, ix, buffer, offset):
        """Hidden line removal logic using horizon buffer."""
        idx = int(ix) + offset
        if 0 <= idx < len(buffer):
            return py < buffer[idx] + 1.5
        return False