# BASELINES

B0 train-only station/month climatology with month/global-median fallbacks; B1 latest complete measured rolling CPCB-style AQI available at issuance; B2 raw CAMS from the frozen forecast; B3 legacy LightGBM only in its separate historical experiment; B4 ridge residual; B5 LightGBM residual; B6 XGBoost residual; direct LightGBM AQI is also compared. The primary correction family is predeclared LightGBM. All primary comparisons share exactly the same station/date rows. No modern baseline score exists yet.
