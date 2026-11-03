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
