from app.routing.weather_field import WeatherField
from app.services.route_planner import _weather_alerts


def test_weather_alerts_flag_severe_route_segment():
    weather = WeatherField(
        [
            {
                "lat": 10.0,
                "lon": 75.0,
                "wave_height_m": 4.5,
                "wind_speed_kmh": 70.0,
                "data_available": True,
            }
        ]
    )

    alerts = _weather_alerts([(9.9, 74.9), (10.1, 75.1)], weather)

    assert len(alerts) == 1
    assert alerts[0].segment_index == 0
    assert alerts[0].severity == "severe"
    assert alerts[0].wave_height_m == 4.5
    assert alerts[0].wind_speed_kmh == 70.0


def test_weather_alerts_flag_warning_for_moderately_adverse_conditions():
    weather = WeatherField(
        [
            {
                "lat": 10.0,
                "lon": 75.0,
                "wave_height_m": 3.0,
                "wind_speed_kmh": 20.0,
                "data_available": True,
            }
        ]
    )

    alerts = _weather_alerts([(9.9, 74.9), (10.1, 75.1)], weather)

    assert len(alerts) == 1
    assert alerts[0].severity == "warning"


def test_missing_weather_sample_does_not_create_a_false_safe_or_alert_claim():
    weather = WeatherField(
        [
            {
                "lat": 10.0,
                "lon": 75.0,
                "wave_height_m": 0.0,
                "wind_speed_kmh": 0.0,
                "data_available": False,
            }
        ]
    )

    assert weather.data_available is False
    assert weather.coverage_percent == 0.0
    assert _weather_alerts([(9.9, 74.9), (10.1, 75.1)], weather) == []


def test_weather_coverage_reports_partial_samples():
    weather = WeatherField(
        [
            {"lat": 10.0, "lon": 75.0, "data_available": True},
            {"lat": 11.0, "lon": 76.0, "data_available": False},
            {"lat": 12.0, "lon": 77.0, "data_available": True},
            {"lat": 13.0, "lon": 78.0, "data_available": False},
        ]
    )

    assert weather.data_available is True
    assert weather.coverage_percent == 50.0


def test_weather_segment_alert_is_saved_with_voyage(auth_client, vessel):
    response = auth_client.post(
        "/api/voyages",
        json={
            "vessel_id": vessel["id"],
            "start_port": "Chennai Port",
            "end_port": "Mumbai Port",
            "origin": {"lat": 13.098, "lon": 80.293},
            "destination": {"lat": 18.95, "lon": 72.84},
            "strategy": "safest",
            "distance_nm": 1200,
            "duration_hr": 66,
            "fuel_tons": 200,
            "co2_tons": 622.8,
            "route_points": [
                {"lat": 13.098, "lon": 80.293},
                {"lat": 18.95, "lon": 72.84},
            ],
            "risk_segments": [0.2, 0.8],
            "weather_alerts": [
                {
                    "segment_index": 0,
                    "start": {"lat": 13.098, "lon": 80.293},
                    "end": {"lat": 18.95, "lon": 72.84},
                    "midpoint": {"lat": 16.024, "lon": 76.5665},
                    "wave_height_m": 4.2,
                    "wind_speed_kmh": 68.0,
                    "severity": "severe",
                    "message": "Severe weather on route segment 1: waves 4.2 m and wind 68 km/h",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    alerts = auth_client.get("/api/alerts").json()
    weather_alerts = [alert for alert in alerts if alert["type"] == "WeatherWarning"]
    assert len(weather_alerts) == 1
    assert "Severe weather" in weather_alerts[0]["message"]
