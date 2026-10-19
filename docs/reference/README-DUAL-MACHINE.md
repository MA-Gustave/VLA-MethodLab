# RVV-VLA Lab Studio — Cloud-V / EPCC machine switch (SSH gateway)

This is a **Studio-only connection upgrade** for the RVV-VLA Lab snapshot from 13 October 2026. It does not rewrite the benchmark workers, change the native RVV engine, alter existing campaign data, or stop remote processes. It is designed to **preserve the previously installed v6.3 campaign-table UI**: the installer changes only the main Studio GUI, the two mirrored SSH backends, and a small Test Runner architecture safeguard.

## Important: EPCC gateway is not the compute VM

The EIDF message confirms authorization to use the **SSH gateway**, but **does not provide access details or hardware specifications of a compute VM**. The command in the email is:

```bash
ssh -J gustave@gateway.epcc.ed.ac.uk internal-host
```

You still need to obtain and verify:

1. The **internal VM hostname** (the value for `internal-host`).
2. The **internal VM username**; it may differ from `gustave`.
3. Authentication for both SSH hops (keys, ssh-agent, or the institution's approved method).
4. The **verified SHA256 SSH host-key fingerprint of each hop**, obtained from a trusted EPCC source or other trusted independent channel (not blindly accepted from an initial key scan).
5. Whether the internal VM is actually `riscv64`, supports RVV, and has a suitable GCC/Clang toolchain and sufficient disk space. A generic EIDF VM may be x86-64 and **cannot execute native RISC-V/RVV binaries**.

A successful gateway account approval **does not** establish that RISC-V benchmark execution is possible.

## Install on Windows — DROP ROOT & OVERWRITE

1. **Close Studio** (detached remote campaigns continue running). Consider saving a backup of your current `RVV-VLA-Lab` directory.
2. Extract `RVV-VLA-Lab_v6.3_DUAL_MACHINE_EPCC_DROP_ROOT.zip` **directly into** `C:\mycode\Simdjson\RVV-VLA-Lab\` and accept overwrite of the matching files. **No installer is required.** Do not flatten the `studio/`, `orchestrator/` or `tools/` subfolders.
3. Restart Studio. Select **Cloud-V — direct RISC-V** or **EPCC — via SSH gateway** at the top and click **SSH Connect**.
4. The Cloud-V `.env` and all remote campaigns remain unchanged. The patch has no embedded passwords or private SSH keys.
5. Offline tests may be run from the project root with `python tools/test_dual_ssh_profiles.py`. They do **not** open an SSH connection.

This root-drop bundle is built against `znapshot_RVV-VLA-Lab_10131011.zip` **plus** the Studio UI v6.3 patch. If you made additional source changes since then, back up or compare your files before overwriting.

## EPCC profile configuration

In Studio, select **EPCC — via SSH gateway** and click **Prepare EPCC profile**. Studio creates `C:\mycode\Simdjson\.env.epcc` **outside the repository** (unless a different EPCC `.env` path was selected). It never overwrites an existing profile and does not insert keys/passwords.

Open that file in your own editor and replace the placeholders with **the internal VM's actual details** and the **two verified host-key fingerprints**:

```ini
# Internal compute VM, NOT the gateway
RVVLAB_HOST=internal-vm-hostname-from-eidf
RVVLAB_PORT=22
RVVLAB_USER=internal-vm-username
RVVLAB_HOST_SHA256=SHA256:<verified-internal-vm-key>
RVVLAB_SSH_KEY=C:\Users\YOURUSER\.ssh\id_ed25519

# SSH-only gateway hop
RVVLAB_JUMP_HOST=gateway.epcc.ed.ac.uk
RVVLAB_JUMP_PORT=22
RVVLAB_JUMP_USER=gustave
RVVLAB_JUMP_HOST_SHA256=SHA256:<verified-gateway-key>
RVVLAB_JUMP_KEY=C:\Users\YOURUSER\.ssh\id_ed25519
RVVLAB_JUMP_ALLOW_AGENT=1
```

`RVVLAB_SSH_KEY` and `RVVLAB_JUMP_KEY` can be empty if password authentication is permitted; the GUI can prompt for passwords, but **never saves prompted passwords**. If the gateway accepts an SSH agent, set `RVVLAB_JUMP_ALLOW_AGENT=1`; otherwise set it to `0` and provide a key or use an allowed password. Some enterprise SSH setups require interactive MFA/keyboard-interactive flows that Paramiko may not support through this transport; this update **does not guarantee compatibility with every EPCC authentication policy**.

The GUI authenticates to the gateway first and opens a Paramiko **direct-tcpip** SSH jump channel to the specified VM (equivalent in topology to `ssh -J`). It **does not** request an interactive shell on the gateway. It then authenticates to the internal VM and verifies its own pinned host key. **SFTP and benchmark commands use only the internal VM's SSH connection.** Any invalid/missing fingerprint fails closed.

## Running tests on both machines

- **Cloud-V** continues using its original SSH connection and existing local results folder.
- **EPCC** has a **separate results folder** (`~/RVV_Lab_results/EPCC`, on Windows under your user home) and hence separate TestRunner `history.json` PASS markers. A Test 93 completed on Cloud-V will not be marked completed on EPCC.
- To switch target, wait for any active local SSH transfer, local Test Runner queue, or active campaign refresh to finish. Select the other radio option, then **SSH Connect**. Switching closes the previous *local SSH connection*, but does **not** kill detached remote tests.
- For an EPCC target reporting anything other than `riscv64`, Studio allows the SSH console but **blocks native RVV Test Runner tests and RVV launch actions**. It does not pretend an x86 VM is a RISC-V benchmark machine.
- CPU, VLEN, compiler, system load, and memory will differ between machines. Do not compare absolute throughput without documenting system properties; prefer per-machine matched baseline ratios.
- The CLI remains Cloud-V by default unless you explicitly set `RVVLAB_ENV_FILE` to your external `.env.epcc` before invoking it.

## Offline verification

The drop-root update includes `tools/test_dual_ssh_profiles.py`, which simulates direct and jump connections, validates separate host fingerprints, connection teardown, backend parity, and rejection of incomplete/unverified configurations. The installed bundle is **not connected to EPCC** and no remote job is started by this update.

If you have additional changes to `Studio` beyond the provided snapshot, the installer may refuse to overwrite them. In that case, share your latest Lab ZIP rather than forcing an overwrite.
