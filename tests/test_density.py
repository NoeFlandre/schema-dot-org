import pytest

from wdcgeo.density import CELLS_PER_DEGREE, cell, density, grid_shape


def test_default_resolution_is_a_quarter_of_a_degree():
    assert CELLS_PER_DEGREE == 4
    assert grid_shape(CELLS_PER_DEGREE) == (720, 1440)


def test_grid_shape_follows_the_resolution():
    assert grid_shape(1) == (180, 360)
    assert grid_shape(10) == (1800, 3600)


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        (90.0, -180.0, (0, 0)),
        (89.9, -179.9, (0, 0)),
        (0.0, 0.0, (360, 720)),
        (-89.9, 179.9, (719, 1439)),
        (48.8584, 2.2945, (164, 729)),
        (-33.8688, 151.2093, (495, 1324)),
    ],
)
def test_cell_maps_degrees_to_a_row_and_column(latitude, longitude, expected):
    assert cell(latitude, longitude, CELLS_PER_DEGREE) == expected


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [
        (-90.0, 180.0, (719, 1439)),
        (-90.0, -180.0, (719, 0)),
        (90.0, 180.0, (0, 1439)),
    ],
)
def test_cell_keeps_the_edges_of_the_world_inside_the_grid(latitude, longitude, expected):
    assert cell(latitude, longitude, CELLS_PER_DEGREE) == expected


def test_north_is_up_and_east_is_right():
    north, _ = cell(60.0, 0.0, CELLS_PER_DEGREE)
    south, _ = cell(-60.0, 0.0, CELLS_PER_DEGREE)
    _, west = cell(0.0, -60.0, CELLS_PER_DEGREE)
    _, east = cell(0.0, 60.0, CELLS_PER_DEGREE)
    assert north < south
    assert west < east


def test_density_counts_points_per_cell():
    points = [(48.8584, 2.2945), (48.8584, 2.2945), (48.9, 2.4), (-33.8688, 151.2093)]
    assert density(points, CELLS_PER_DEGREE) == {(164, 729): 3, (495, 1324): 1}


def test_density_of_nothing_is_empty():
    assert density([], CELLS_PER_DEGREE) == {}


def test_density_separates_cells_a_resolution_step_apart():
    points = [(0.0, 0.0), (0.0, 0.25), (0.0, 0.24)]
    assert density(points, CELLS_PER_DEGREE) == {(360, 720): 2, (360, 721): 1}
