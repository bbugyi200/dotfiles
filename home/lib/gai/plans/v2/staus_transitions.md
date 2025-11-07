In v2 of gai the ChangeSpec STATUS field should support the following transitions:


| From | To | Trigger |
|------|-----|---------|
| Ready | Creating CL | new-failed-tests / new-ez-feature workflow starts |
| Creating CL | Ready | new-failed-tests / new-ez-feature fails or Ctrl+C |
| Creating CL | Created TDD CL | new-failed-tests creates CL |
| Creating CL | Running TAP Tests | new-ez-feature creates CL |
| Created TDD CL | Fixing Tests | fix-tests workflow starts |
| Fixing Tests | Created TDD CL | fix-tests workflow fails on a TDD CL |
| Fixing Tests | Created EZ CL | fix-tests workflow fails on an EZ CL |
| Fixing Tests | Running TAP Tests | fix-tests workflow succeeds |
| Running TAP Tests | Tests Failed | one or more TAP tests failed (manual user transition) |
| Running TAP Tests | Tests Passed | all TAP tests passed (manual user transition) |
| Tests Failed | Fixing Tests | fix-tests workflow starts  |
| Tests Passed | Running QA Checks | qa workflow starts |
| Running QA Checks | Pre-Mailed | CL is ready to be user-reviewed and mailed |
| Pre-Mailed | Mailed | CL has been user-reviewed and mailed (manual user transition) |
| Mailed | Mailed (with comments) | reviewer(s) have left comments on a mailed CL |
| Mailed (with comments) | Mailed | comments have been resolved |
| Mailed | LGTM | reviewer(s) have LGTMed the CL |
| Mailed (with comments) | LGTM | comments have been resolved on a LGTMed CL |
| LGTM | Tests Failed | tests failed while attempting to submit a CL (manual user transition) |
