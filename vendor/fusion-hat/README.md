# Reviewed Fusion HAT+ driver patch

Upstream revision and all patch hashes are recorded in `manifest.json`.
The upstream driver and derived patches are GPL-3.0; see `COPYING`.
This directory contains source patches, not an installed kernel module.

The `1.1.0-ninja1` contract rejects invalid/expired battery cache reads, returns
PWM write failures, starts enabled channels at zero, tracks uncertain PWM state,
and limits PWM/speaker attribute permissions to owner/group. Battery cache expires
after three seconds (three normal worker intervals); a failed poll invalidates it
immediately. File read time is never used as sample time.

The application must set period explicitly before enabling a channel and must
hold exclusive session ownership. A kernel error cannot guarantee a physical
stop on a disconnected bus; the application must report the failed stop, retain
its safety latch and direct the operator to remove actuator power if necessary.

Build validation uses the kernel's build target directly, not the vendor
Makefile's installer or automatic package-install targets. No tests load modules.
The installation wrapper must verify source and patch hashes, preserve existing
system files and require explicit apply. Never run the mutable upstream installer.

Run the simulated contract check against a prepared patched source directory:

```bash
uv run --frozen python scripts/reproduce_fusion_vendor_contract.py /path/to/patched-source --patched
```

This checks C control flow with simulated bus operations, not physical timing or
concurrency. Kernel build and Raspberry Pi acceptance remain separate checks.
