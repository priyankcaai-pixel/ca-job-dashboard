# CA Job Dashboard

From the portal folder, run these commands with Python 3.12 or newer.

    python jobs.py import
    python serve.py

Open http://127.0.0.1:8765/ and click **Fetch vacancies**. You can also run
`python jobs.py refresh` from the command line. The workbook import reads the
Jobs sheet and accepts a different path via `--workbook`. Manual vacancies and
stage changes live in browser storage for this URL. Editing a live vacancy's
stage keeps it in the tracker even after it leaves the employer feed.

The employer boards in `sources.json` use Greenhouse, Lever, SmartRecruiters
and Ashby. The feed looks for India-based roles with evidence of a full CA
qualification. View a vacancy's Details to read the source excerpt. Ambiguous,
preferred, alternative and part-qualified criteria are excluded when detected.
The workbook rows appear under **All tracker records** and count toward the
summary even when their CA requirement has not been verified.

LinkedIn Posts, LinkedIn Jobs, Indeed and Naukri have search links and manual
capture. For an authorized provider that supplies normalized JSON, add an
entry with type `json`, a `company`, a `label`, and a `url` or `urlEnv`.
Use `tokenEnv` for a bearer token. The feed must return an array of records
with role, location and URL in the `role`, `location` and `url` fields.
Include `description` with the qualification text. Optional fields are
`company`, `posted` and `mode`.

The included GitHub Pages workflow deploys the public job feed and refreshes
it every six hours on GitHub Actions. In the GitHub repository, choose
**Settings ? Pages ? Source ? GitHub Actions** before running it. The build
publishes only the portal assets and fetched vacancies. Workbook records,
application stages, resume links and tracker exports stay off the public site.

To move tracker data to your phone, choose **Download tracker** on your local
portal, transfer the JSON file privately, and choose **Import tracker** on the
phone. Changes are saved separately in each browser.
