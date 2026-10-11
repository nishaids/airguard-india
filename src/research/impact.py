"""Coverage-aware population exposure aggregation for licensed supplied cells."""
import math


def population_exposure(cells, forecast_date, data_hash):
    if not data_hash or not forecast_date: raise ValueError('Versioned population data and target date required')
    seen=set();covered=poor=total=0;excluded=0
    for cell in cells:
        key=cell['cell_id']
        if key in seen: raise ValueError('Population cells must be disjoint and unique')
        seen.add(key);population=cell['population']
        if isinstance(population,bool) or not isinstance(population,(float,int)) or not math.isfinite(population) or population<0:
            raise ValueError('Nonnegative population counts required (not densities)')
        total+=population
        if cell.get('forecast_date')!=forecast_date or cell.get('aqi') is None:
            excluded+=1;continue
        aqi=cell['aqi']
        if isinstance(aqi,bool) or not isinstance(aqi,(float,int)) or not math.isfinite(aqi) or aqi<0: raise ValueError('Invalid AQI')
        covered+=population
        if aqi>200: poor+=population
    return {'target_date':forecast_date,'population_data_hash':data_hash,'covered_population':covered,
        'poor_plus_population':poor,'uncovered_population':total-covered,'excluded_cells':excluded,
        'interpretation':'Modelled area exposure estimate, not individual exposure or health outcome. Uncovered cells are not assumed clean.'}
