# Verified live deployment

Status: **PRODUCTION_DEPLOYED_AND_VERIFIED**.

- Live URL: https://webapp-phi-taupe.vercel.app
- Deployment URL: https://webapp-4kwhperqo-nishanth-s-projects-e335f110.vercel.app
- Deployed Git commit: 35c2ca08b86a53dcc27da11f79edb311d0e77ffe
- Existing project: prj_CRhIlQYLGST3dBwUfTiFgJXa25qe
- Workflow: push the research branch; create a production-configured candidate without changing domains; test; promote using the existing Vercel project. No connected Git production trigger is configured.

## Verification

Fresh lint, typecheck and production build passed. 43 frontend unit tests, 37 public API/route/security checks and 16 actual browser checks passed. Browser checks cover eight core routes at 375px and 1280px, mobile navigation, horizontal overflow, uncaught page exceptions and same-origin HTTP failures.

The owner-confirmed GitHub email resolved Vercel commit attribution. A mobile first-click race was fixed by disabling the menu before hydration. The additional JavaScript lint check used the installed JSX-capable parser; the earlier default-parser failure and corrected evidence are retained in the machine-readable report.

The latest secret audit found zero history, worktree or built-browser-asset credential hits. Experimental correction models remain disabled. The locked final test was not opened or scored.

## Paper work

Paper work stopped at the owner's request. New local paper changes, PDF, artifact package and generator remain uncommitted and unpushed. Existing historical commits were preserved. They are outside the website deployment upload.

No human action is required for this completed deployment.

See [verification artifact](../../results/release/website_deployment_verification.json).
