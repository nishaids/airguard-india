"""Next-day AQI forecasts from current conditions.

The 1.0 application forecasts from a historical record that ends in 2020. This
package feeds the same trained model with today's conditions instead.

What "today's conditions" are matters, and is stated on everything this package
returns: the inputs are **modelled** concentrations from the CAMS global
atmospheric model (via Open-Meteo), on a grid of roughly 40 km. They are not
station measurements. No current government-monitor measurement was obtainable
when this was built (see ``docs/airguard2/live_data_implementation.md``).
"""
