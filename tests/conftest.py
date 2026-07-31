import pytest

from gdm.distribution import DistributionSystem


_MODEL_PATH = "examples/models/p5r.json"


@pytest.fixture()
def system():
    """Load the local p5r model which has time series data.

    Skips when the model file is not present (e.g. a non-source checkout).
    """
    import os

    if not os.path.exists(_MODEL_PATH):
        pytest.skip("p5r.json model not found")
    return DistributionSystem.from_json(_MODEL_PATH)


@pytest.fixture(scope="session")
def p5r_system():
    """Download p5r model once per session; skip all tests if download fails."""
    try:
        from gdmloader.constants import GCS_CASE_SOURCE
        from gdmloader.source import SystemLoader

        loader = SystemLoader()
        loader.add_source(GCS_CASE_SOURCE)
        system = loader.load_dataset(
            system_type=DistributionSystem,
            source_name=GCS_CASE_SOURCE.name,
            dataset_name="p5r",
        )
    except Exception as exc:
        pytest.skip(f"Could not download p5r model: {exc}")
    return system
