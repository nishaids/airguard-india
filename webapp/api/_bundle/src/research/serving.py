"""Deployment-support gate. No model can be enabled merely by an average MAE gain."""
from src.research.protocol import VERSION,PROTOCOL,aware


def support_reason(model,station_pk,features,now):
    if not model or model.get('deployment_status')!='VALIDATED':return 'MODEL_NOT_VALIDATED'
    if model.get('protocol_version')!=VERSION or model.get('feature_version')!=PROTOCOL['feature_version']:return 'VERSION_MISMATCH'
    if station_pk not in model.get('validated_stations',[]):return 'LOCATION_OUTSIDE_VALIDATED_SUPPORT'
    required=('temporal','spatial','severity','uncertainty','advisory','paired_comparison')
    if not all(model.get('gates',{}).get(x) is True for x in required):return 'SCIENTIFIC_GATES_INCOMPLETE'
    if any(x not in features['features'] for x in model.get('required_features',[])):return 'MISSING_REQUIRED_FEATURES'
    if (aware(now)-aware(features['feature_cutoff'])).total_seconds()>PROTOCOL['freshness_hours']['cams']*3600:return 'STALE_INPUT'
    return None


def choose_forecast(cams_aqi,model,station_pk,features,now,infer=None):
    """An offline approved lightweight inference callable may be supplied; never train."""
    fallback={'aqi':cams_aqi,'forecast_mode':'CAMS_BASED_NATIONWIDE','cams_baseline_aqi':cams_aqi,'corrected_aqi':None,'prediction_interval':None,'model_version':None}
    reason=support_reason(model,station_pk,features,now)
    if reason or infer is None:return {**fallback,'correction_status':reason or 'INFERENCE_NOT_CONFIGURED'}
    try:
        from math import isfinite
        point,lower,upper=infer(features['features'])
        if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and isfinite(x) for x in (point,lower,upper)) or not 0<=lower<=point<=upper:raise ValueError('Invalid predictive output')
        return {'aqi':point,'forecast_mode':'STATION_CALIBRATED_AIRGUARD','cams_baseline_aqi':cams_aqi,'corrected_aqi':point,
                'prediction_interval':{'lower':lower,'upper':upper,'coverage':.9},'model_version':model['model_version'],'correction_status':'VALIDATED'}
    except Exception:return {**fallback,'correction_status':'MODEL_FAILURE'}
