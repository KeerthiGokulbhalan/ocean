from fastapi import APIRouter, Query

from app.schemas import WeatherPoint
from app.services.weather import fetch_marine_point

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherPoint)
async def get_weather(lat: float = Query(...), lon: float = Query(...)):
    data = await fetch_marine_point(lat, lon)
    return WeatherPoint(lat=lat, lon=lon, **data)
