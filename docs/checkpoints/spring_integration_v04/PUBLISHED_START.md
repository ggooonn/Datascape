# Published Spring v04 checkpoint: next-Work starting point

Use the remotely fetchable checkpoint commit:

**`90bb2572a35731ccdb38ec332456f2f94ac76456`**

```bash
git fetch origin checkpoint/spring-integration-v04
git switch -c work/mid-far-vegetation-grammar-v01 90bb2572a35731ccdb38ec332456f2f94ac76456
```

This commit contains the complete prepared checkpoint: all 67 additions and the
entire Git file tree are identical to local HEAD
`65fef315d1382163745689844669cabc0a2afaa6`.

## Local to API commit mapping

| Preserved original | Published equivalent |
| --- | --- |
| Checkpoint artifact `fb30861729395f5d052c5f535c37cca7a2b483a0` | `6915bc377b6f7d3621cd8a3c5a7b9d31183ac044` |
| Prepared HEAD `65fef315d1382163745689844669cabc0a2afaa6` | `90bb2572a35731ccdb38ec332456f2f94ac76456` |

Each mapped pair has the exact same root Git tree SHA, including original
filenames, modes and every byte of code/configuration/vectors/review assets.
The existing remote ancestry through PR #20 is preserved. API commit author,
committer/date metadata and explanatory messages change commit IDs; the
local-only commit objects themselves are not imported by this API interface.
Their contents and mapping remain explicit.

The older START_HERE.md, historical READMEs and archive manifests are preserved
verbatim. Their local-only hashes are provenance, not remotely fetchable
starting points. **Use this note and the Draft PR's published commit instead.**
This note is a publication-only addition after the immutable checkpoint above.
It does not revise the 67 prepared additions or Spring geometry.

## Handoff and scope

- [Handoff](HANDOFF.md)
- [File summary and review](README.md)
- [Reproduction](REPRODUCE.md)
- [Validation](VALIDATION.md)
- [Temporary placement inventory](placement_inventory.csv)

Keep F2-C and PR #16 A .25 locked; Tree v10 = PR #18, Rock & Ground v05 = PR #19.
The next Work primarily develops mid/far vegetation grammar, clustered
relationships, actual mist transitions and A-displaced middle/far color support.
Current scene placement, scale, weak C/color density, rhythm and woody wash
remain provisional. No Spring refinement or merge was performed here.

## Publication route for future approved Work checkpoints

GitHub plugin/API authorization, local shell Git credentials and user approval
are separate. This checkpoint was published through the connected GitHub API:
create_branch, create_blob, create_tree, create_commit, update_ref and
create_pull_request. No shell Git credentials or pasted personal token were used.

For an approved future checkpoint: verify the intended diff; upload only relevant
file bytes; compare returned blob SHAs and complete root tree SHAs; create a
commit with the existing branch parent; update only the authorized head branch
with an expected-head lease; create a Draft PR against its explicit base; verify
the result. Commit SHA preservation is not guaranteed through the exposed API;
preserve local provenance and report an exact, verified file-tree mapping.
