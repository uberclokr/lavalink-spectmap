import numpy as np
from geopy import distance
from typing import Tuple, List

class CoverageCalculator:
    def __init__(self, antenna_height: float, beamwidth: float = 60.0, beamheight: float = 30.0):
        """
        :param antenna_height: Height above ground in meters
        :param beamwidth: Horizontal beamwidth in degrees (default 60° for typical sector antennas)
        """
        self.antenna_height = antenna_height
        self.beamwidth = beamwidth
        self.beamheight = beamheight
    
    def calculate_coverage_cone(self, center_lat: float, center_lon: float,
                              azimuth: float, downtilt: float, distance_m: float = 5000) -> List[Tuple[float, float]]:
        """
        Calculate polygon points for the coverage area
        
        :param distance_m: Maximum distance to calculate coverage (in meters)
        :return: List of (lat, lon) points forming the coverage polygon
        """
        # Convert angles to radians
        azimuth_rad = np.radians(azimuth)
        downtilt_rad = np.radians(abs(downtilt))
        
        # Calculate the main direction point
        points = []
        steps = 36  # Number of points in the arc
        
        # Handle downtilt = 0 to avoid division by zero
        if downtilt_rad == 0:
            ground_distance = distance_m  # Or use a large default value
        else:
            ground_distance = self.antenna_height / np.tan(downtilt_rad)
            print(f"Ground distance calculated: {ground_distance} m")


        for i in range(steps + 1):
            angle = azimuth_rad - np.radians(self.beamwidth/2) + np.radians(self.beamwidth) * i/steps
            dist = min(ground_distance, distance_m)
            
            # Calculate new point
            new_point = distance.distance(meters=dist).destination(
                point=(center_lat, center_lon),
                bearing=np.degrees(angle)
            )
            
            points.append((new_point.latitude, new_point.longitude))
        

        # Include the radio's coordinates as the first point in the polygon
        points.insert(0, (center_lat, center_lon))

        return points