"""Represents the space in which the world exists"""

import logging
import math
import copy

import shapefile
import numpy as np
from scipy import interpolate
from pyproj import Transformer

from ms_abmlux.location import ETRS89_to_WGS84

log = logging.getLogger("map")

class Map:
    """Represents an area to the system.

    This is a square area addressed in ETRS89 format by default.
    """

    def __init__(self, coord, width_m, height_m, border=None, shapefilename=None,
                 shapefile_coordsystem=None):
        """Create a new Map, describing a part of the world.

        Borders are loaded from shapefiles using pyshp, and converted into the ETRS89 coordinate
        system used internally.  The 'shapefile_coordsystem' parameter should be a string
        identifying a coordinate system to use, compatible with the pyproj package.  In practice
        this means using an EPSG number, e.g. 'epsg:3035'.

        Parameters:
            coord (tuple):ETRS89-format 2-tuple of x,y coordinates representing the southwest
                          corner of the map.  Used as an offset for internal points.
            width_m (int):Width of the map in metres
            height_m (int):Height of the map in metres
            border (list):List of Shapes, as read from a shapefile, representing the border.
            shapefilename (str):Filename of a shapefile to load the border from
            shapefile_coordsystem (str):Coordinate system to use when loading the shapefile.
                                        Default is ETRS89.
        """

        self.coord    = coord
        self.wgs84    = ETRS89_to_WGS84(coord)
        self.width_m  = width_m
        self.height_m = height_m

        # Catch a common error where the two shape params are used as locational args
        if border is not None and isinstance(border, str):
            raise ValueError("border parameter must be a list of Shapes, not a string")

        self.border = border
        if shapefilename is not None:
            log.info("Loading shapefile from %s...", shapefilename)
            self.border = shapefile.Reader(shapefilename).shapes()

            # Adjust shape to be at this location
            if shapefile_coordsystem:
                log.info("Adjusting shapefile to ETRS89 coordinate system...")
                trans = Transformer.from_crs(shapefile_coordsystem, 'epsg:3035')
                for shape in self.border:
                    shape.points = [trans.transform(p[1], p[0]) for p in shape.points]
                    shape.points = [(p[1], p[0]) for p in shape.points]
        if self.border is None:
            self.border = []
        log.debug("new Map (%ix%im) at %i, %im with %i border shapes", self.width_m, self.height_m,
                  self.coord[0], self.coord[1], len(self.border))

    def width(self):
        """Return the width in m"""
        return self.width_m

    def height(self):
        """Return the height in m"""
        return self.height_m

    def plot_border(self, plt):
        """Plot the border onto a matplotlib figure using ETRS89 coordinates.

        Parameters:
            plt (matplotlib figure):The Matplotlib object to plot to
        """
        for shape in self.border:
            x = [i[0] for i in shape.points[:]]
            y = [i[1] for i in shape.points[:]]
            plt.plot(x,y)


    def __str__(self):
        return f"<{self.__class__.__name__} {self.coord=} {self.width()}x{self.height()}m>"



class DensityMap(Map):
    """A Map that contains population density information"""

    def __init__(self, prng, coord, width_m, height_m, cell_size_m, border=None, shapefilename=None,
                 shapefile_coordsystem=None):
        """Create a new DensityMap, describing a part of the world along with its population
        density.

        Population density is stored in a grid of square cells.  This allows weighted sampling
        from the grid in order to sample points, or visualisation/examination of the weights
        across the space.

        Parameters:
            coord (tuple):ETRS89-format 2-tuple of x,y coordinates representing the southwest
                          corner of the map.  Used as an offset for internal points.
            width_m (int):Width of the map in metres
            height_m (int):Height of the map in metres
            cell_size_m (int):Width (and height) of each cell in metres.  Cells are square.
            border (list):List of Shapes, as read from a shapefile, representing the border.
            shapefilename (str):Filename of a shapefile to load the border from
            shapefile_coordsystem (str):Coordinate system to use when loading the shapefile.
                                        Default is ETRS89.
        """

        super().__init__(coord, width_m, height_m, border, shapefilename, shapefile_coordsystem)

        self.prng        = prng
        self.cell_size_m = cell_size_m
        self.density     = [[0 for x in range(math.ceil(width_m / cell_size_m))]
                            for y in range(math.ceil(height_m / cell_size_m))]

        log.debug("Created DensityMap with %ix%i cells", len(self.density), len(self.density[0]))
        self._recompute_marginals()

    def width_grid(self):
        """Return the width in grid cells"""
        return len(self.density[0])

    def height_grid(self):
        """Return the height in grid cells"""
        return len(self.density)

    def set_density(self, x, y, dens):
        """Set the population density at a given grid cell"""
        self.density[y][x] = dens
        self._recompute_marginals()

    def get_density(self, x, y):
        """Return the population density at a given grid cell"""
        return self.density[y][x]

    def sample_coord(self):
        """Return a random sample weighted by density"""

        # Randomly select a cell
        grid_x, grid_y = self.prng.multinoulli_2d(self.density, self.marginals_cache)

        # Uniform random within the cell (fractional component)
        x = self.coord[0] + self.cell_size_m*grid_x + self.prng.random_float(self.cell_size_m)
        y = self.coord[1] + self.cell_size_m*grid_y + self.prng.random_float(self.cell_size_m)

        return x, y

    def _recompute_marginals(self):
        self.marginals_cache = [sum(x) for x in self.density]

    def force_recompute_marginals(self):
        """Force the method to recompute marginal sums.  This must be called if the internal
        density map is edited directly (i.e. without calling get_density/set_density)."""
        self._recompute_marginals()

    def resample(self, res_fact, normalize=False):
        """Returns a new DensityMap, resampled to a finer grid resolution.

        Parameters:
            res_fact (int):The factor by which the resolution is increased in a given dimension.
                           This should be an even integer, except if res_fact == 1 in which case
                           the original density is returned.
            normalize (boolean):If True then blocks of new squares are normalized to contain equal
                                populations as the original squares

        Returns:
            distribution_new(numpy array):An expanded distribution array of floats
        """

        if res_fact == 1:
            new_map = DensityMap(self.prng, self.coord, self.width_m, self.height_m,
                                 self.cell_size_m, self.border)
            new_map.density = copy.copy(self.density)
            new_map.force_recompute_marginals()
            return new_map

        if res_fact <= 0 or res_fact > 1000 or res_fact % 2 != 0 or not isinstance(res_fact, int):
            raise ValueError("res_fact in distribution_interpolate must be a +ve even integer")

        distribution  = np.array(self.density)
        height, width = distribution.shape

        # Pad with a border of zeros
        padded_height = height + 2
        padded_width  = width + 2

        padded_distribution = np.zeros((padded_height,padded_width))
        padded_distribution[1:height+1,1:width+1] = distribution

        # Map padded_density onto a grid within the unit square
        x = np.linspace(0, 1, num=padded_width, endpoint=True)
        y = np.linspace(0, 1, num=padded_height, endpoint=True)
        z = padded_distribution

        # Linearly interpolate
        interpolated_density = interpolate.interp2d(x, y, z)

        # The resolution of the grid is increased and interpolated vaules are assigned to each
        # new square
        x_indent = 1/((padded_width - 1)*res_fact*2)
        y_indent = 1/((padded_height - 1)*res_fact*2)

        x_new = np.linspace(x_indent, 1-x_indent, num=(padded_width-1)*res_fact, endpoint=True)
        y_new = np.linspace(y_indent, 1-y_indent, num=(padded_height-1)*res_fact, endpoint=True)

        half_res = int(res_fact/2)
        distribution_new = interpolated_density(x_new, y_new)[half_res:len(y_new) - half_res,
                                                              half_res:len(x_new) - half_res]

        # Create a new map and copy metadata in there
        new_map = DensityMap(self.prng, self.coord, self.width_m, self.height_m,
                             self.cell_size_m / res_fact, self.border)
        assert len(new_map.density) == len(distribution_new)
        assert len(new_map.density[0]) == len(distribution_new[0])
        new_map.density = distribution_new

        # Blocks of new squares are normalized to contain equal populations as the original squares
        if normalize:
            for i in range(width):
                for j in range(height):

                    square = distribution_new[j*res_fact:(j+1)*res_fact, i*res_fact:(i+1)*res_fact]

                    newsum = np.sum(square)
                    oldsum = distribution[j][i]

                    if newsum > 0:
                        square *= oldsum/newsum

        new_map.force_recompute_marginals()
        return new_map

    def __str__(self):
        return (f"<{self.__class__.__name__} {self.coord=} {self.width()}x{self.height()}m"
                f" @ {self.cell_size_m} metres/cell>")
