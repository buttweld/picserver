from dataclasses import dataclass
from typing import Optional
import requests


@dataclass
class WeatherData:
    city: str
    country: str
    temp_real: float
    temp_feel: float
    temp_min: float
    temp_max: float
    humidity: int
    wind_speed: float
    description: str

    @classmethod
    def from_api(cls, data: dict) -> "WeatherData":
        """Parse OpenWeatherMap API JSON into WeatherData."""
        try:
            main = data.get("main", {})
            wind = data.get("wind", {})
            weather = data.get("weather", [{}])[0]
            sys = data.get("sys", {})

            return cls(
                city=data.get("name", "Unknown"),
                country=sys.get("country", ""),
                temp_real=main.get("temp", 0) - 273.15,
                temp_feel=main.get("feels_like", 0) - 273.15,
                temp_min=main.get("temp_min", 0) - 273.15,
                temp_max=main.get("temp_max", 0) - 273.15,
                humidity=main.get("humidity", 0),
                wind_speed=wind.get("speed", 0.0),
                description=weather.get("description", "").capitalize(),
            )
        except Exception as e:
            raise ValueError(f"Malformed weather data: {e}")

    def __str__(self) -> str:
        """Return a summary string."""
        return (
            f"{self.city}, {self.country}: {self.temp_real:.1f}°C "
            f"(feels {self.temp_feel:.1f}°C, "
            f"min {self.temp_min:.1f}°C, max {self.temp_max:.1f}°C),\n"
            f"{self.description}, humidity {self.humidity}%, "
            f"wind {self.wind_speed:.1f} m/s"
        )


def get_weather(lat: float, lon: float, key: str) -> Optional[WeatherData]:
    """
    Fetch weather data from OpenWeatherMap and return a WeatherData object.
    Returns None if the request fails or data is malformed.
    """
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return WeatherData.from_api(data)
    except requests.RequestException as e:
        print("HTTP error while fetching weather:", e)
        return None
    except ValueError as e:
        print("Weather parse error:", e)
        return None
