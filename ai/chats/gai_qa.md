* Add/support a new change spec status value: `needs_qa`.
* The existing option with:

  * short key: `r`
  * long description: **RunQA**
    should be available **only when** the change spec status is `needs_qa`.
* Status entry into `needs_qa` is driven by presubmit results:

  * when `bb_hg_pre_submit` completes successfully, transition:

    * `running pre-submits...` → `needs_qa`.
* When the **RunQA** option is chosen and the **QA workflow completes**, transition:

  * `needs_qa` → `pre-mailed`.
