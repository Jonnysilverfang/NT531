# Mode B Execution Roadmap

## Gate 0 — implementation

- [x] Audit baseline before changes.
- [x] Register exactly TC01/TC02/TC03.
- [x] Pin `us-east-1/us-east-1a`.
- [x] Implement SSM-only three-node topology, split IAM, encrypted evidence, dedicated TGW attachment subnets.
- [x] Implement fail-closed preflight, runner, analyzer, and graphs.
- [x] Pass unit tests and Terraform `fmt/init/validate/plan`.

## Gate 1 — authority and cost

- [ ] Confirm flat two-spoke TGW intent.
- [ ] Supply an assumed-role or IAM Identity Center profile.
- [ ] Review the 56-create plan and billable components.
- [ ] Save an approved plan before apply.

## Gate 2 — deployment

- [ ] `terraform apply` the approved plan.
- [ ] Record exact account, AMI, resource IDs, routes, and billable inventory.
- [ ] Wait for all three nodes to become SSM Online and bootstrap-complete.

## Gate 3 — AWS preflight

- [ ] Stage the hash-addressed runtime bundle on all nodes.
- [ ] Run preflight through SSM on the EC2 client.
- [ ] Require route/port/MTU/ENA/native-XDP PASS.

## Gate 4 — pilot

- [ ] Execute pilot N=3.
- [ ] Verify manifests, checksums, cells, environment stability, native-XDP evidence, and saturation-prefix semantics.
- [ ] Analyze the pilot and record an explicit accept/reject decision.

## Gate 5 — final

- [ ] Execute final N=10 without changing code/config/infrastructure.
- [ ] Download and verify the immutable run tree.
- [ ] Emit `results/final_summary.json`.
- [ ] Generate the four registered PNGs.
- [ ] Complete `docs/FINAL_EXPERIMENT_REPORT.md` using only validated final evidence.

## Gate 6 — teardown

- [ ] Preserve S3 evidence before teardown.
- [ ] Review a Terraform destroy plan.
- [ ] Destroy only after explicit confirmation and verify that billable resources are gone.
