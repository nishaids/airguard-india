# 210 difficult viva questions with concise answers

Answers describe the current evidence, not promised future results. Source-specific numbers are anchored below. Practice saying limitations directly.


## Problem

1. **Why forecast rather than show current AQI?**

   Tomorrow’s information supports planning; it is useful only with validated provenance and honest uncertainty.

2. **Who needs this most?**

   People planning outdoor exposure, especially those with fewer flexible options; benefit has not been measured.

3. **What problem can you actually prove?**

   Fragmented source, forecast and quality information; our code integrates them with explicit limitations.

4. **What would falsify the project’s value?**

   Poor warnings, misunderstood precision or no useful action in user studies would weaken its case.

5. **Does everyone need another AQI app?**

   No; existing apps are useful. We must demonstrate clearer trustworthy decisions, not assume demand.

6. **What is the biggest current weakness?**

   The primary CAMS experiment is unfinished and strict preliminary Severe forecasts all under-warned.


## Existing systems

7. **Isn’t this just CAMS with a UI?**

   CAMS supplies physics forecasts; we built QC, provenance, index transformation, APIs and auditable evaluation. Correction benefit is pending.

8. **Why not simply show CPCB values?**

   They are valuable official monitoring information; this prototype explores a separate non-official next-day workflow.

9. **Why not use Google AQI?**

   Product capabilities vary; we claim transparent methodology and reproducibility, not universal superiority.

10. **Why not use OpenAQ directly?**

   OpenAQ provides measurements; we add QC, aggregation, forecast integration and user-facing failure states.

11. **Do other apps already give advice?**

   Yes. Our proposed distinction is explicit evidence and trade-off evaluation, which still needs validation.

12. **Are you unfairly comparing competitors?**

   Unknown features are marked unknown; no absence or inferiority is asserted without a product audit.


## Novelty

13. **What is your real novelty?**

   An auditable Indian station/forecast/index/advisory integration and its validation design, not a new atmospheric model.

14. **Hasn’t this already been done?**

   Components have been studied; full-review acceptance is incomplete, so we avoid originality claims beyond our implementation.

15. **What exactly did you build?**

   Provider orchestration, QC, index engine, station matching, APIs/UI, immutable ledgers and reproducible experiments.

16. **Did you invent residual learning?**

   No. We evaluate an established technique against direct learners and raw CAMS.

17. **Can you claim world first?**

   No verified systematic evidence supports that claim.

18. **What would strengthen novelty evidence?**

   Complete the targeted literature comparison, primary experiment and prospective evaluation without outcome-driven amendments.


## Datasets

19. **Is this synthetic data?**

   Targets are real station measurements; CAMS/weather are model output. Synthetic fault fixtures are tests only.

20. **What is actually measured?**

   Pollutant concentrations at instruments distributed by OpenAQ with upstream provider identity.

21. **What is modelled?**

   CAMS atmospheric fields and weather forecasts; derived AQI is index arithmetic, not a new measurement.

22. **How large is the measured study?**

   The current verified artifact lists 107,280 rows, 64,799 valid targets and 179 usable stations in 100 parsed cities.

23. **Why should we trust the datasets?**

   Hashes, provenance, locked QC and reconstruction support auditing; they cannot prove every instrument is accurate.

24. **Can you call all 481 stations training data?**

   No. That is the eligible catalogue; the frozen sample and acquired/usable cohorts are smaller.


## CPCB

25. **Is AirGuard an official CPCB forecast?**

   No. It is an AirGuard CPCB-style forecast using a declared aggregation convention.

26. **Why use the maximum pollutant sub-index?**

   The central implementation follows the selected index methodology; it is not a sum of disease risks.

27. **Why require three pollutants including PM?**

   It is the declared engine minimum; otherwise the index is insufficient rather than a fabricated value.

28. **Why CO and ozone use eight-hour windows?**

   The shared engine applies complete trailing windows; high ozone also needs its declared one-hour treatment.

29. **Is AQI 401 an exact Severe observation?**

   No. It represents a lower bound when the open-ended band prevents identifying the true index.

30. **Why not convert every ppb station gas?**

   Reliable conversion needs atmospheric conditions and trustworthy unit semantics; those station labels are not assumed valid.


## OpenAQ

31. **Does OpenAQ operate these monitors?**

   It distributes upstream measurements; provider/owner and sensor identities must be retained.

32. **What if OpenAQ lists a retired sensor first?**

   Rank evidenced sensor dates and coverage, not list order or larger sensor ID.

33. **Can old readings be used as fresh current data?**

   No; contributing pollutant age and coverage determine eligibility/freshness.

34. **How do you handle failed station downloads?**

   Resume checksummed completed work; retain unavailable station records and the upstream failure.

35. **Why is Chhatikara incomplete?**

   The audited upstream endpoints returned HTTP 500; no readings or sensor dates were fabricated.

36. **Do you know original publication latency?**

   OpenAQ ingestion times are absent; historical observation features are conditional on the declared healthy-feed assumption.


## CAMS

37. **What did the 134-byte probe prove?**

   It decoded as nine PM2.5 grid values with forecast type, run, lead and valid time; size alone is not validity.

38. **Why is archived forecast different from reanalysis?**

   A forecast is tied to an initialisation and future leads; reanalysis can use later observations.

39. **How do you prove forecast timing?**

   Decode init, lead and valid time and check valid equals init plus lead; retain request and raw checksum.

40. **Why not download the whole globe?**

   The frozen station envelope and required dates/parameters/leads are sufficient and cheaper to audit.

41. **Can current past-hours fields replace the archive?**

   No; missing historical run identity cannot be repaired by relabelling present API fields.

42. **Does a smoke file prove a complete baseline?**

   No. Every required cube, gas conversion, grid/time match and availability bound still needs validation.


## Weather

43. **Why include weather?**

   Meteorology can explain conditional bias, but only ablation on identical development rows establishes useful contribution.

44. **Can observed tomorrow weather be a feature?**

   No; its outcome availability would leak future information.

45. **What does previous_day2 mean here?**

   The existing weather archive uses a conservative forecast lead; run provenance is checked before use.

46. **What if boundary-layer height is missing?**

   It is unavailable in the inherited archive; do not impute a fabricated forecast feature.

47. **Can all weather units be assumed correct?**

   No. Adapter metadata and transformation must be checked before feature construction.

48. **Did weather improve the preliminary Ridge?**

   Its paired MAE addition improved the non-CAMS comparison; this does not establish gain with CAMS present.


## FIRMS

49. **Does a fire pixel measure local AQI?**

   No; it is satellite active-fire context, not breathing-zone concentration.

50. **Does acquisition time prove publication time?**

   No; that is why strict historical fire predictors remain withheld without release evidence.

51. **Can you say a fire caused this pollution?**

   No. Proximity and forecast feature importance are not causal attribution.

52. **What happens if FIRMS is unavailable?**

   Optional context is absent; a valid core forecast can remain available.

53. **Why is fire not automatically included?**

   It needs issue-time provenance and the locked ablation admission rule, not intuitive plausibility alone.

54. **Do no detections mean no smoke?**

   No; satellite detection limits and transport prevent that inference.


## Data quality

55. **What if the sensor data are wrong?**

   QC catches declared defects, preserves raw data/reasons and discloses remaining undetected error.

56. **Why reject exact zeros?**

   The locked v3.1 rule treats indistinguishable outage zeros conservatively; it can also remove genuine near-zero ozone.

57. **Why reject six repeated hourly values?**

   It flags a declared stuck-run defect; the threshold is not changed after final results.

58. **Why keep extreme spikes?**

   Real pollution episodes can be spikes; automatic deletion would bias extreme-event evaluation.

59. **Why keep PM2.5 above PM10?**

   The pair is inconsistent but does not identify which instrument is wrong; flag and retain it.

60. **Do you silently drop rejected days?**

   No; the station-day ledger retains invalid targets and reason counts.


## ML

61. **Why Ridge?**

   Regularisation gives a stable simple reference with train-only scaling and alpha selection.

62. **Why LightGBM?**

   It handles tabular nonlinear interactions; it must earn its complexity through fair development comparison.

63. **Why XGBoost?**

   It supplies another preregistered boosted-tree candidate; its brand is not evidence of better forecasting.

64. **Why not deep learning?**

   Incomplete heterogeneous histories do not automatically justify complexity; a future preregistered study can test it.

65. **Why not an LLM?**

   Numeric environmental forecasting must be tied to data and verified errors, not generated plausible numbers.

66. **What if a learner performs worse than CAMS?**

   Report it and carry raw CAMS forward under the frozen selection rule.


## Feature engineering

67. **Can station IDs memorise locations?**

   Yes; spatial holdouts and static-support policies must expose that transfer limitation.

68. **Can target-day missingness be a predictor?**

   No. Freeze support before issue; target-matched support is an evaluation annotation only.

69. **Why recent measured-minus-CAMS bias?**

   It may describe systematic local error, but only completed pre-issue pairs can contribute.

70. **Can neighbouring observations leak?**

   Yes, if later bins or outcome-based station selection enter; apply the same cutoffs to neighbours.

71. **What if a feature is mostly missing?**

   Fit missingness handling on training only and assess whether it adds supported information.

72. **Are feature importance explanations causal?**

   No. They describe fitted prediction behaviour, not intervention effects.


## Baselines

73. **Why climatology?**

   It tests whether a forecast adds skill beyond station-season average conditions.

74. **Why persistence?**

   Pollution can persist; beating yesterday/current levels is a meaningful operational hurdle.

75. **Why raw CAMS?**

   Correction must demonstrate added value over the physics forecast it starts from.

76. **Is the old 2015–2020 city model comparable?**

   Not directly to this station/day target; legacy results remain separate.

77. **Are baseline rows identical?**

   Primary evaluation requires the declared common availability set; pair counts must be reported.

78. **Can you mark baselines complete without CAMS?**

   Only for an explicitly non-CAMS preliminary study; primary readiness remains false.


## Metrics

79. **Is R² your accuracy?**

   No. It is variance-relative regression fit and can be negative.

80. **Why MAE is primary?**

   It is interpretable in index units and less dominated by large errors than squared loss.

81. **Why also RMSE and bias?**

   They reveal large-error sensitivity and systematic under-/overprediction that average absolute loss hides.

82. **Does category accuracy capture severe misses?**

   Not adequately; also report severity-specific under-warning and exceedance diagnostics.

83. **Can a lower average error still be dangerous?**

   Yes. Severe misses or badly calibrated tails can coexist with improved average MAE.

84. **What does a confidence interval include?**

   The declared paired date-block resampling uncertainty, not all data/model/operational uncertainty.


## Leakage

85. **How do you prove there is no leakage?**

   Timestamp guards, chronological/global-date partitions, train-only preprocessing and final isolation provide evidence, not an absolute universal proof.

86. **Why not random date splits?**

   They mix future/past regimes and can leak lagged or repeated station information.

87. **Can future station selection leak?**

   Yes; training-only eligibility and frozen catalogue membership prevent outcome-based final selection.

88. **Can scaling on all data leak?**

   Yes. Fit scaler and imputer only on each training partition.

89. **Can calibration see test labels?**

   No. Calibration and policy selection use their own preceding window.

90. **What would invalidate your research?**

   Final-test tuning, fabricated archive provenance, outcome-driven QC or broken target/availability semantics.


## Temporal validation

91. **Why expanding windows?**

   They reproduce accumulating historical information under the locked date geometry.

92. **Why an embargo?**

   It separates adjacent partitions and reduces boundary contamination; it is not a cure for every dependency.

93. **Do all stations move together by date?**

   Yes. A global date belongs to one role, preventing cross-station future-date leakage.

94. **What if the first fold lacks 120 training days?**

   Report insufficient eligibility; do not weaken the primary threshold after observing results.

95. **How do you show temporal degradation?**

   Report every fold and seasonal errors beside pooled comparisons.

96. **Is development validation the final test?**

   No. The latest 90 days are held separately until committed model selection.


## Spatial validation

97. **What happens at an unseen station?**

   Raw-grid fallback remains; station correction requires validated transfer/support evidence.

98. **Why hold cities or clusters out?**

   Nearby stations can share pollution and grid context, inflating station-only transfer estimates.

99. **Why 25 km clusters?**

   That is the locked grouping convention; it is not proof of atmospheric independence.

100. **Can a held-out station use its own history?**

   The protocol reports both with-history and no-local-monitor regimes separately.

101. **Are spatial groups selected from outcome coverage?**

   No. Group assignments use frozen metadata, with training-only coverage checks.

102. **Can you claim nationwide calibrated precision?**

   No; missing regions/monitors and coarse forecast cells limit transfer claims.


## Severe AQI

103. **Why exclude Severe from exact regression fitting?**

   The true value is unidentified above the lower bound; training on a fabricated exact 401 biases the model.

104. **How do you score Severe?**

   Category/exceedance detection, share below 401 and lower-bound shortfall.

105. **What negative result did you get?**

   All strict preliminary baseline forecasts on 363 censored Severe validation days fell below 401.

106. **Can an interval reaching 401 prove Severe coverage?**

   No. It is compatibility with a lower bound, not coverage of the unknown true upper value.

107. **Can you repair Severe performance after final test?**

   Not in that evaluation; any change requires a future version and fresh held-out evidence.

108. **Is Severe rarity an excuse?**

   No. Report sample size and failures prominently, even when learning extremes is difficult.


## Uncertainty

109. **Does 90% nominal mean every user gets 90% coverage?**

   No. Marginal calibration can fail by location, season, severity and dependent days.

110. **Why conformal prediction?**

   A separate empirical calibration step is auditable and can complement point forecasts.

111. **What is Mondrian conformal here?**

   Calibration by forecast-defined groups, not by unknowable observed test categories.

112. **What if an interval is huge?**

   Communicate its width and limitations; width alone does not justify a safety claim or automatic abstention.

113. **What if group calibration has few samples?**

   Disclose insufficient support or use a declared fallback; do not invent precise conditional guarantees.

114. **Can calibrated intervals be deployed now?**

   Not as validated CAMS correction intervals while the primary experiment remains incomplete.


## Health/advisory

115. **Is the health advisory medically validated?**

   No. It is environmental exposure guidance with no clinical outcome calibration.

116. **Does vulnerability mean personal disease risk?**

   No. Cohorts are communication/exposure strata, not diagnoses.

117. **How is under-warning defined?**

   Issued category lower than the observed category; serious under-warning is at least two categories below.

118. **Why measure over-warning?**

   Unnecessary restrictions and alert fatigue are real trade-offs, even for cautious policies.

119. **Is P3 a guaranteed risk controller?**

   No dependent-day guarantee is claimed; its calibration-window target is an empirical aim.

120. **Can you change cohort thresholds after final results?**

   No. Keep the committed policy and report its actual performance.


## Architecture

121. **Why separate live and research paths?**

   Production availability and scientific issue-time validation have different provenance and release requirements.

122. **Where is AQI calculated?**

   The shared Python engine supplies targets, forecasts and scenario calculations under one version.

123. **What if cache serves the wrong day?**

   IST-aware expiry and browser rollover tests prevent stale target-day reuse.

124. **Why bounded concurrent provider work?**

   It limits latency and quotas while permitting independent source failures to be reported.

125. **Does caching improve scientific accuracy?**

   No. It improves availability/cost and must preserve freshness/source identity.

126. **Can experimental code silently replace live forecast?**

   No automatic promotion occurs; production release is a separate approval and verification step.


## Frontend

127. **What if geolocation is denied?**

   Manual place or coordinate search remains available.

128. **What if JSON is malformed?**

   The response contract fails before caching/rendering, showing an error rather than fabricated values.

129. **What if search results have invalid coordinates?**

   Filter them with the same service-region check and reject malformed result arrays.

130. **Can old requests overwrite a newly selected place?**

   Cancellation/state guards and regression tests protect against that race.

131. **Is the browser storing my health diagnosis?**

   It stores a locally selected advisory cohort, not a diagnosis; location links still reveal selected coordinates.

132. **What if charts fail?**

   Text tables and explicit missing states provide a usable fallback; accessibility is still subject to user testing.


## Backend

133. **What happens if all APIs fail?**

   No substitute AQI is invented; the API returns unavailable and the UI shows it.

134. **How are invalid inputs handled?**

   Allowlisted parameters, finite service-region coordinates and bounded labels are checked before provider calls.

135. **Do retries bypass limits?**

   No; each transport attempt consumes shared quotas and uses bounded retry logic.

136. **Can user input choose an outbound URL?**

   No. Adapters use fixed provider endpoints rather than arbitrary hosts.

137. **Why HTTP 202?**

   It represents queued provider work, not a completed forecast.

138. **Do errors reveal database credentials?**

   Public errors are generic and logs should retain safe classes/redacted diagnostics only.


## Database

139. **What do you store?**

   Environmental records, caches, quotas, snapshots, forecast artifacts and verification pairs; no diagnosis is required.

140. **Does RLS make service-role endpoints safe?**

   Not by itself; privileged server credentials still require operation authorisation and input validation.

141. **Why immutable forecasts?**

   Verification must compare a forecast actually issued before the outcome, not a rewritten prediction.

142. **How do you pair verification?**

   Use issue/target/location/station/method identity and retain provenance; never bind stations after seeing outcomes.

143. **What if a forecast lacks a station binding?**

   Report the gap; do not manufacture a measured-station verification later.

144. **What if the database is corrupted?**

   Fail closed, restore verified evidence and audit pairing/checksums before claiming valid performance.


## Security

145. **Where is the ADS token displayed?**

   Nowhere in output; the official client consumes private configuration with logging suppressed.

146. **Can the client receive the service-role key?**

   Server-only secret names/values are audited out of browser source/assets.

147. **Is a secret scan a penetration test?**

   No. It is a scoped static/material check with explicit remaining security limits.

148. **Can URLs disclose a place of interest?**

   Yes. Shareable location parameters and infrastructure logs create privacy considerations.

149. **How are internal refresh operations protected?**

   Authenticated server routes and allowlisted operations; public selectors cannot invoke refresh.

150. **What remains before commercial release?**

   Privacy/retention review, penetration testing, licensing, load testing and approved release validation.


## Deployment

151. **Have you deployed this correction?**

   No. Experimental station correction and source hardening remain separate from the existing production release.

152. **What commit produced a research result?**

   Each immutable result records its source SHA; current code changes do not rewrite prior provenance.

153. **Why not merge automatically?**

   Research selection does not authorise a production deployment; release requires explicit permission.

154. **Can a successful build prove live reliability?**

   No. Real provider, database, browser and failure checks are needed too.

155. **How does local demo run?**

   Run the Python API on 8787 and Next development server on 3000; development rewrites connect them.

156. **What is the backup if providers fail?**

   Show a clearly labelled archived research/fault-demo artifact; never pretend it is live data.


## Cost

157. **Is everything free?**

   No. Free tiers have quotas/terms, and commercial licences/support/hosting can require payment.

158. **What is the biggest research cost?**

   Archive latency/storage and repeated development fitting, separate from user-serving inference.

159. **Can you quote production cost exactly?**

   Not without measured traffic, retention, licences and current provider quotes.

160. **Does one user require new provider calls?**

   A validated shared grid/cache hit can avoid them; cache freshness still matters.

161. **Could API quota kill a demo?**

   Yes; use bounded cached locations and an honest backup, not evasion or fake success.

162. **Why not promise zero-cost national deployment?**

   Licensing, infrastructure, monitoring and support scale beyond a prototype.


## Scalability

163. **What happens with ten users?**

   Shared cache/leases reduce redundant work, but cold misses and upstream availability still matter.

164. **What about ten thousand users?**

   Batch popular grids, measure contention, licence APIs and capacity-test queues/cache/database.

165. **What about one million users?**

   The prototype has no such load evidence; require a redesigned capacity plan and empirical tests.

166. **Why batch by grid?**

   Many nearby users share the same atmospheric cell and forecast run.

167. **What is the storage bottleneck?**

   Dated parameter/lead/grid fields and immutable ledgers under retention requirements.

168. **Can station models train per user request?**

   They should be trained offline; user-serving requests apply frozen versions, never tune from outcomes.


## Ethics

169. **Can you call a lower-pollution time safe?**

   No. It is relatively lower exposure, not zero risk or medical clearance.

170. **Does an explanation prove causation?**

   No. Feature importance and scenario arithmetic are predictive/assumptive, not intervention effects.

171. **Who is disadvantaged by missing stations?**

   Poorly monitored regions and people without flexible work options; fallback availability does not equal accuracy.

172. **Could warnings cause harm?**

   Under-warning can reassure falsely; over-warning can impose costs or fatigue. Both are evaluated.

173. **Why disclose failures to judges?**

   Scientific integrity requires reporting them; hiding poor Severe performance defeats the project’s use case.

174. **Is this personalised healthcare?**

   No. It is environmental information with broad exposure strata.


## Failure handling

175. **What if the forecast interval is huge?**

   Display uncertainty and limits; do not manufacture confidence or equate width with guaranteed danger.

176. **What if a sensor is stuck?**

   Research QC rejects the locked run and retains its reason; do not claim universal live deployment.

177. **What if CAMS acquisition is delayed?**

   Resume existing IDs and continue independent hardening/documentation; never substitute reanalysis.

178. **What if only one provider works?**

   Display only what its provenance supports and withhold unsupported claims.

179. **What if stale data look plausible?**

   Plausibility does not make them fresh; show timestamp/status and enforce cutoffs.

180. **What if a provider changes schema?**

   Fail closed, inspect actual metadata and version the adapter before accepting new semantics.


## People impact

181. **How does this help society?**

   It may support preparation and exposure-aware planning; no measured clinical or behavioural benefit is claimed.

182. **Who will actually use it?**

   Families, schools, commuters, outdoor workers and researchers are hypotheses to validate through user studies.

183. **What if users cannot change activity timing?**

   Acknowledge constraints and provide context without blaming individuals or promising protection.

184. **Can hospitals rely on it for admissions planning?**

   Not as a validated clinical demand forecast; only supplementary environmental context.

185. **Can traffic police use street-level predictions?**

   No street-level accuracy is established from a coarse grid; institutional local monitoring remains important.

186. **How would you measure benefit next?**

   Preregister usability, decision comprehension and feasible-action studies; separate them from clinical claims.


## Research contribution

187. **Are you cherry-picking results?**

   Report all declared folds/learners, paired rows, negatives and immutable artifacts; final isolation is tested.

188. **Why not publish only the best season?**

   That would hide transfer degradation; seasons/regions and insufficient sample counts must be listed.

189. **Does preliminary success prove CAMS correction?**

   No. The current Ridge comparison lacks raw archived CAMS and must be labelled non-CAMS.

190. **What is reproducible today?**

   The measured table and preliminary artifacts have raw-cache/fresh-checkout evidence with a reused pinned runtime.

191. **What is not yet reproduced?**

   The primary CAMS model experiment and an independent installed environment need their own audits.

192. **How do you select the final model?**

   Development rolling-fold mean MAE under the locked tie/fallback rule, then commit all configuration/hashes before final access.


## Limitations

193. **Can AirGuard predict my street?**

   It returns a grid-scale estimate; street-level variation is unsupported.

194. **Can you guarantee every location has measured AQI?**

   No. Coverage/units/freshness can fail and must be visible.

195. **What is your most serious negative result?**

   Complete under-warning by strict preliminary baselines on evaluated censored Severe days.

196. **Does current station selection create bias?**

   Yes. Selecting active current monitors creates survivorship; disclose it rather than claiming historical representativeness.

197. **Does conformal fix distribution shift?**

   No. It calibrates under assumptions that shift or dependence can violate.

198. **What is missing from research readiness?**

   Complete genuine CAMS evaluation, accepted literature review, primary reproduction and a real 30-day verified record.


## Future work

199. **What should happen immediately after archive arrival?**

   Validate complete fields/units/times, match frozen data and run development only before selecting a model.

200. **When can final test run?**

   Only after a committed MODEL_SELECTION_LOCK with isolation/hash/configuration checks; the latest request authorises one such evaluation.

201. **What happens after poor final performance?**

   Report it without retuning; future changes need a new study and held-out evidence.

202. **When can a correction be deployed?**

   After validated evidence plus explicit separate production-release approval.

203. **Would deep learning be future work?**

   Possibly, with sufficient data, preregistered comparisons and proper cost/transfer evaluation.

204. **What prospective milestone remains?**

   Thirty real elapsed and verified days; it cannot be achieved by backdating or synthetic outcomes.


## Commercialization

205. **How could this become a product?**

   Validate demand, warnings and usability, obtain licences, test capacity/privacy/security and release conservatively.

206. **Who is a plausible customer?**

   Institutions or users needing transparent environmental planning; willingness to pay is unmeasured.

207. **Is the research score a revenue argument?**

   Not directly. Reliability, decisions, distribution and compliance need separate evidence.

208. **Could you sell vulnerability risk predictions?**

   Not as personal medical risk without the appropriate independent validation; current scope is environmental guidance.

209. **What would an investor criticise most?**

   Unproven demand, provider dependence and unfinished forecasting advantage; acknowledge those honestly.

210. **What is the defensible commercial promise now?**

   An auditable prototype and research workflow, not nationwide calibrated accuracy or health outcomes.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
