# Dependency audit and patched runtime

The npm audit reported zero advisories. The declared Python API requirements
and their twelve resolved dependencies also reported zero advisories.

The broader research/ADS audit initially reported six records representing
three distinct advisories (duplicate alias records were not six distinct bugs):

| Package | Inherited pin | Patched pin | Evidence and scope |
| --- | --- | --- | --- |
| PyArrow | 23.0.0 | 23.0.1 | Arrow IPC pre-buffering use-after-free, CVE-2026-25087; [Apache security index](https://arrow.apache.org/security/), [advisory record](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg) |
| pytest | 9.0.2 | 9.0.3 | Unix temporary-directory handling, CVE-2025-71176; [reviewed advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g) |
| Streamlit | 1.53.1 | 1.54.0 | Windows component-path SSRF/NTLM exposure; [maintainer advisory](https://github.com/streamlit/streamlit/security/advisories/GHSA-7p48-42j8-8846) |

The pins in requirements.txt were updated and installed in the project
`.venv-live` environment. Use its Python executable for the local demo and
future research. Test/audit records state their actual runtime and scope.
No locked QC/protocol rule, station target, previous result artifact or
experimental production deployment was changed by dependency remediation.

The already-running archive worker retains its loaded libraries and same ADS
job IDs. Future starts use the patched environment. These fixes do not prove
penetration resistance or absence of unknown vulnerabilities. The pre-patch
audit is preserved in research_dependency_audit_before_patch.json; the fresh
resolved audit and validation records are under results/project_hardening.
