* Add support for a new change spec status value: `needs_pre_submits`.
* Transition a change spec into `needs_pre_submits` when the `new_tdd` workflow completes.
* When a change spec is in `needs_pre_submits`, show a new option:

  * short key: `r`
  * long description: **Run Presubmit**
* The Run Presubmit option should run the command:

  * `bb_hg_pre_submit`
* Run `bb_hg_pre_submit` as a fully **disowned** process so it continues after the `gai` script closes.
* Store the output of `bb_hg_pre_submit` into a file under the **gai home directory structure**.
* Add a new field to the change spec spec:

  * `pre_submit`
  * set **only when** `bb_hg_pre_submit` is run
  * value is the **file path** where that command’s output is stored.
* When `bb_hg_pre_submit` is initiated, immediately update status to:

  * `running pre-submits...`
* Extend periodic checking to include change specs with status:

  * `running pre-submits...`
* This check should run on the same cadence as other periodic checks:

  * **every 5 minutes**.
* The periodic check for `running pre-submits...` should determine:

  * whether `bb_hg_pre_submit` has completed
  * and whether it completed successfully.
* Status transitions based on presubmit result:

  * success: `running pre-submits...` → `needs_qa`
  * failure: `running pre-submits...` → `needs_pre_submits`
* Gate/align this with the existing periodic-check framework timing (5-minute cadence).
* Update availability of the existing QA option:

  * the option with short key `r` and long description **RunQA** should be available **only when** status is `needs_qa`.
* When RunQA is selected and the QA workflow completes, update status to:

  * `pre-mailed`
