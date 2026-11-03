# Carrier Internship projects

Projects prepared from ten original ZIP archives, retaining the original month and project folder layout. Read each project's README and UPLOAD_NOTES.md for setup context. Python dependencies and Node dependencies must be installed separately; generated executables are excluded.

## Preparation results

| Archive group | Original files | Prepared files* | Prepared MB* |
|---|---:|---:|---:|
| AI_LLM_DEFECTS | 112 | 97 | 181.93 |
| APRIL | 9,511 | 96 | 17.52 |
| AUGUST | 13,063 | 38 | 0.51 |
| FEBRUARY | 383 | 30 | 4.00 |
| JANUARY | 86 | 24 | 10.82 |
| JULY | 1,913 | 678 | 269.46 |
| MARCH | 75,698 | 1,114 | 89.13 |
| MAY | 152 | 130 | 14.84 |
| OCTOBER | 18,039 | 104 | 0.64 |
| SEPTEMBER | 6,515 | 53 | 8.75 |

*Folder sizes include retained local files; existing project .gitignore rules exclude some of these from Git. Recovered nested archive variants are counted separately under legacy_sources. The original ZIP files remain outside this repository.

## Configuration changes

- AI_LLM_DEFECTS/db.py now reads DB_SERVER, DB_DATABASE, DB_USERNAME, and DB_PASSWORD from the environment. Copy .env.example to .env and supply local values. The original embedded database password should be rotated by its owner.
- The Design Hour Estimator and both SAP VC appV2 variants now read FLASK_SECRET_KEY from the environment, with a random process-local fallback. Set a stable secret in the process environment for persistent sessions.
- Notebook code and markdown were retained; saved outputs and execution counts were cleared.
- PyInstaller .spec files and build icons remain eligible for Git tracking.

## Validation and remaining work

- Syntax checked the four modified Python files; verified notebook outputs were cleared.
- Scanned retained text source for common credential patterns. The remaining literal-token match is a dummy test fixture. This is a pattern scan, not proof that binary documents or business datasets contain no sensitive information.
- No application runtime or integration tests were run.
- Some old nested vendor ZIP members could not be decoded, and one nested archive is invalid. Their originals remain in the source ZIPs; local review details are recorded beside this repository in archive-review-needed.csv. Do not assume these archived variants are runnable.
- Business workbooks, datasets, and vendor runtimes remain where needed; this preparation does not establish publication rights.
- The remote URL is configured, but remote history and authentication have not been verified. Fetch and reconcile existing remote history before creating commits and pushing. Nothing has been uploaded.

## Push protection correction

GitHub detected an Asana token stored as an environment-variable fallback. All occurrences of that token and other literal credential fallbacks found in Python source were removed from tracked files. Set ASANA_TOKEN and other API credentials in the process environment. The exposed Asana token should be revoked and replaced by its owner. The initial unpushed commit was amended so the token is absent from the branch history.
