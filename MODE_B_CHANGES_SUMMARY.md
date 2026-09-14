# Mode B Implementation Changes

Baseline: `ac5f39b`; current worktree is not yet committed.

- Added the required pre-change audit at `docs/IMPLEMENTATION_AUDIT.md`.
- Replaced the former four-test contract with three performance tests in `us-east-1/us-east-1a`.
- Removed active PrivateLink and placement-group infrastructure and benchmark code.
- Reduced the deployment to two VPCs and three identical AL2023 `c6i.large` nodes.
- Added dedicated TGW attachment subnets and an explicit flat two-spoke TGW route table.
- Removed SSH; split client/server roles; scoped client Run Command access to the two DUT instance ARNs and `AWS-RunShellScript`.
- Added KMS-encrypted S3 artifacts, encrypted VPC/TGW flow logs, EBS encryption, and a hash-addressed SSM staging/controller flow.
- Expanded AWS preflight to fail on identity, SSM, route, port, MTU, ENA, or native-XDP mismatch.
- Added TC01 ping jitter/loss, TC02 ENA packet-rate and retransmit analysis, and TC03 maximum-sustainable-PPS/censoring logic.
- Added final graph generation and a guarded final report shell.
- Installed Terraform 1.16.2 and locked providers; `fmt/init/validate/plan` pass.
- AWS apply/pilot/final remain intentionally blocked pending TGW intent and short-lived credentials.
