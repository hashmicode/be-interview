from pathlib import Path
from typing import Generator
from unittest.mock import patch
from uuid import uuid4
from fastapi import status
import alembic.command
import alembic.config
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import get_database_session
from app.main import app
from app.models import Organisation, Location

_ALEMBIC_INI_PATH = Path(__file__).parent.parent / "alembic.ini"

@pytest.fixture()
def test_client() -> TestClient:
    return TestClient(app)

@pytest.fixture(autouse=True)
def apply_alembic_migrations() -> Generator[None, None, None]:
    # Creates test database per test function
    test_db_file_name = f"test_{uuid4()}.db"
    database_path = Path(test_db_file_name)
    try:
        test_db_url = f"sqlite:///{test_db_file_name}"
        alembic_cfg = alembic.config.Config(_ALEMBIC_INI_PATH)
        alembic_cfg.attributes["sqlalchemy_url"] = test_db_url
        alembic.command.upgrade(alembic_cfg, "head")
        test_engine = create_engine(test_db_url, echo=True)
        with patch("app.db.get_engine") as mock_engine:
            mock_engine.return_value = test_engine
            yield
    finally:
        database_path.unlink(missing_ok=True)


def test_organisation_endpoints(test_client: TestClient) -> None:
    list_of_organisation_names_to_create = ["organisation_a", "organisation_b", "organisation_c"]

    # Validate that organisations do not exist in database
    with get_database_session() as database_session:
        organisations_before = database_session.query(Organisation).all()
        database_session.expunge_all()
    assert len(organisations_before) == 0

    # Create organisations
    for organisation_name in list_of_organisation_names_to_create:
        response = test_client.post("/api/organisations/create", json={"name": organisation_name})
        assert response.status_code == status.HTTP_200_OK

    # Validate that organisations exist in database
    with get_database_session() as database_session:
        organisations_after = database_session.query(Organisation).all()
        database_session.expunge_all()
    created_organisation_names = set(organisation.name for organisation in organisations_after)
    assert created_organisation_names == set(list_of_organisation_names_to_create)

    # Validate that created organisations can be retried via API
    response = test_client.get("/api/organisations")
    organisations = set(organisation["name"] for organisation in response.json())
    assert  set(organisations) == created_organisation_names



def test_create_location_endpoint(test_client: TestClient) -> None:
    # creating an organisation first to associate with a location
    response = test_client.post("/api/organisations/create", json={"name": "organisation_test"})
    assert response.status_code == status.HTTP_200_OK
    organisation_id = response.json()["id"]

    loc_data = {
        "location_name": "Location 1",
        "longitude": -33.32,
        "latitude": 20.10
    }
    response = test_client.post(f"/api/{organisation_id}/create/location", json=loc_data)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["location_name"] == "Location 1"

    with get_database_session() as database_session:
        locations = database_session.query(Location).filter_by(organisation_id=organisation_id).all()
        database_session.expunge_all()
    assert len(locations) == 1
    assert locations[0].location_name == "Location 1"


def test_get_locations_endpoint(test_client: TestClient) -> None:
    # creating an organisation and associated locations
    response = test_client.post("/api/organisations/create", json={"name": "organisation_for_locations"})
    assert response.status_code == status.HTTP_200_OK
    organisation_id = response.json()["id"]

    location_data = [
        {"location_name": "Location 1", "longitude": -65.0, "latitude": 12.6},
        {"location_name": "Location 2", "longitude": -12.5, "latitude": 20.7},
    ]

    for loc in location_data:
        response = test_client.post(f"/api/{organisation_id}/create/location", json=loc)
        assert response.status_code == status.HTTP_200_OK

    #get locations without a bounding box
    response = test_client.get(f"/api/{organisation_id}/locations")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 2

    # get locations with a bounding box which includes only one location
    response = test_client.get(f"/api/{organisation_id}/locations?bounding_box=12.6,20.7,-65.0,-12.5")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1
    assert response.json()[0]["location_name"] == "Location 1"

def test_get_locations_not_found(test_client: TestClient) -> None:
    response = test_client.get("/api/1/locations")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Locations found for organisation with ID 1"