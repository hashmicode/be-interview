from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlmodel import select, Session
from typing import Optional, Tuple
from app.db import get_db
from app.models import Location, Organisation, CreateOrganisation

router = APIRouter()

@router.post("/create", response_model=Organisation)
def create_organisation(create_organisation: CreateOrganisation, session: Session = Depends(get_db)) -> Organisation:
    """Create an organisation."""
    organisation = Organisation(name=create_organisation.name)
    session.add(organisation)
    session.commit()
    session.refresh(organisation)
    return organisation




@router.get("/", response_model=list[Organisation])
def get_organisations(session: Session = Depends(get_db)) -> list[Organisation]:
    """
    Get all organisations.
    """
    organisations = session.exec(select(Organisation)).all()
    return organisations



@router.get("/{organisation_id}", response_model=Organisation)
def get_organisation(organisation_id: int, session: Session = Depends(get_db)) -> Organisation:
    """
    Get an organisation by id.
    """
    organisation = session.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return organisation


@router.post("/create/locations")
def create_location():
    raise NotImplementedError


@router.get("/{organisation_id}/locations", response_model=list[Location])
def get_organisation_locations(
        organisation_id: int,
        bounding_box: Optional[Tuple[float, float, float, float]] = Query(
            None,
            description="Bounding box as (min_latitude, max_latitude, min_longitude, max_longitude)"
        ),
        session: Session = Depends(get_db)
) -> list[Location]:
    #location_ids = session.exec(select(Location.id).where(Location.organisation_id==organisation_id)).all()
    #result = []
    #for location_id in location_ids:
    #    location = session.exec(select(Location).where(Location.id == location_id)).one()
    #    result.append({"location_name": location.location_name, "location_longitude": location.longitude, "location_latitude": location.latitude })
    #return result

    # getting all locations for the given organisation in a single query
    qry = select(Location).where(Location.organisation_id == organisation_id)
    if bounding_box:
        min_lat, max_lat, min_long, max_long = bounding_box
        qry = qry.where(
            (Location.latitude >= min_lat) &
            (Location.latitude <= max_lat) &
            (Location.longitude >= min_long) &
            (Location.longitude <= max_long)
        )
    locations = session.exec(qry).all()
    if not locations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No locations found for organisation with ID {organisation_id} with the given bounding box"
        )
    return locations

@router.post("/{organisation_id}/create/location", response_model=Location)
def create_location(
    organisation_id: int,
    location_data: Location,
    session: Session = Depends(get_db)
) -> Location:
    """
    create a location for an organisation.
    """
    organisation = session.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")

    # create and add  new location
    location = Location(
        organisation_id=organisation_id,
        location_name=location_data.location_name,
        longitude=location_data.longitude,
        latitude=location_data.latitude
    )
    session.add(location)
    session.commit()
    session.refresh(location)
    return location