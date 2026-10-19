# RVV Lab — Unexpected Disk Free-Space Increase

**Incident report ID:** RVV-STORAGE-2026-10-13-01  
**Date of observation:** 2026-10-13 (UTC)  
**System:** `bpf3-16G-2` (RISC-V Linux)  
**Affected workload:** RVV Lab Test 92 — Adaptive Composition Exploration (8-hour run)  
**Campaign:** `night-20261013T011722Z-d61b0f`  
**Status:** Observed and verified; root cause not established  
**Priority:** Investigation recommended; no demonstrated data loss or immediate service failure

## Executive summary

During RVV Lab Test 92, the reported free space on the workload's filesystem increased abruptly from **2.421 GiB at 08:19:31 UTC** to **25.365 GiB at 08:49:51 UTC** on **October 13, 2026**. This represents a net increase of approximately **22.945 GiB** in 30 minutes. The rise occurred in two observed steps: first to **3.969 GiB** at 08:34:32 UTC, then to **25.365 GiB** at 08:49:51 UTC.

The free-space increase is **not merely a Studio display error**: subsequent server-side `df` confirmed approximately **26 GiB available** on the root `ext4` filesystem. RVV Lab's current campaign directory resides on `/dev/mmcblk0p6`, a partition of the `SC64G` SD device (`mmcblk0`). A separate **116.5 GiB** device (`mmcblk2`) is visible but is **not the mounted filesystem used by RVV Lab**.

**The cause has not been proven.** A cleanup or release of previously allocated files on the shared root filesystem is plausible, but no command output identifies the responsible process, account, files, or administrative action. The user cannot view system-wide journals. The free capacity should **not** be assumed to constitute an increase in the user's authorized storage allocation.

## 1. Incident timeline and measured delta

Source: Test 92 campaign archive, `metadata.json`, `disk_monitor_15m` (free-space samples recorded in MiB and converted to GiB using 1,024 MiB/GiB).

| Time (UTC), 2026-10-13 | Free space | Change from previous listed sample | Observation |
|---|---:|---:|---|
| 01:17:45 | 2.543 GiB | — | Early Test 92 measurement |
| 08:04:20 | 2.483 GiB | — | Near pre-anomaly level |
| **08:19:31** | **2.421 GiB** | −0.063 GiB | Last pre-increase measurement |
| **08:34:32** | **3.969 GiB** | **+1.549 GiB** | First observed increase |
| **08:49:51** | **25.365 GiB** | **+21.396 GiB** | Second observed increase |
| 09:04:52 | 25.365 GiB | ~0 GiB | Level remained stable in final sample |

**Net change (08:19:31–08:49:51): +22.945 GiB.** Because samples were taken approximately every 15 minutes, the precise times and number of underlying filesystem operations are unknown.

Test 92's result export subsequently completed. Its log reported **17,591 observations**, a `stopped` state after the allotted run time, and a final **PASS** for the runner. No loss of this exported result set has been demonstrated in the materials reviewed. This does not establish that unrelated files on the server were unaffected.

## 2. Server-side evidence

The following findings are taken from SSH commands executed after the event.

### 2.1 Filesystem identity and capacity

```text
$ hostname
bpf3-16G-2
$ uname -r
6.6.63
$ df -hT "$HOME/rvvlab-v5/results"
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/mmcblk0p6 ext4   58G   31G   26G  55% /
$ findmnt -T "$HOME/rvvlab-v5/night-runs"
TARGET SOURCE         FSTYPE OPTIONS
/      /dev/mmcblk0p6 ext4   rw,noatime,errors=remount-ro
$ cat /sys/block/mmcblk0/device/type
SD
$ cat /sys/block/mmcblk0/device/name
SC64G
```

- The current RVV Lab `night-runs` directory is on the **root ext4 filesystem**, `/dev/mmcblk0p6`.
- `lsblk` showed `mmcblk0` (59.5 GiB) with `/` on `mmcblk0p6`, and a separate `mmcblk2` (116.5 GiB) with **no mountpoint shown**.
- The root filesystem has **26 GiB available** according to Linux, approximately matching Studio's **25.3 GiB** display; rounding and collection times can explain the displayed difference.
- No evidence in the supplied post-incident mount information supports a switch of RVV Lab to `mmcblk2`.
- Historical mount-device identity was **not independently logged at each Test 92 free-space sample**, so a complete device-history proof cannot be reconstructed from these samples alone.

### 2.2 Directory usage

```text
$ du -h -d 1 "$HOME/rvvlab-v5"
141M  /home/users/gleblanc/rvvlab-v5/sources
4.0K  /home/users/gleblanc/rvvlab-v5/incoming
212K  /home/users/gleblanc/rvvlab-v5/explorers
4.0K  /home/users/gleblanc/rvvlab-v5/results
706M  /home/users/gleblanc/rvvlab-v5/night-runs
847M  /home/users/gleblanc/rvvlab-v5
$ du -h -d 1 "$HOME"
2.1G  /home/users/gleblanc/cloudv-simdjson-rvv-v5
847M  /home/users/gleblanc/rvvlab-v5
1.6G  /home/users/gleblanc/cloudv-simdjson-rvv
4.5G  /home/users/gleblanc
```

The current RVV Lab tree is **847 MiB**, including **706 MiB** in `night-runs`. Six campaign directories remained visible there. The current size of the project **does not account for a 22.945 GiB free-space increase**; nevertheless, current directory sizes alone cannot prove which historical files, if any, were deleted.

The root filesystem's **31 GiB used** greatly exceeds the **4.5 GiB** accounted for in this user's home directory. Therefore, the relevant change could have originated elsewhere on the shared filesystem. Differences between filesystem-level and directory-level space accounting must also be considered.

### 2.3 Inodes and limits

```text
$ df -i /
Filesystem      Inodes  IUsed   IFree IUse% Mounted on
/dev/mmcblk0p6 5179872 575375 4604497   12% /
$ quota -s
-bash: quota: command not found
$ ulimit -f
unlimited
```

- Inode availability was high (approximately **88% free**); this does not indicate inode exhaustion.
- The `quota` utility is absent; **user or group storage quotas were not verified**.
- `ulimit -f` being unlimited is a file-size resource limit, **not evidence of unrestricted storage entitlement**.
- The account belongs to the `external_users` group; a shared filesystem's unused capacity should not be assumed to belong exclusively to this user.

## 3. Journal and reboot checks

```text
$ journalctl --list-boots --no-pager
Hint: You are currently not seeing messages from other users and the system.
Users in groups 'adm', 'systemd-journal' can see all messages.
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
  0 aa6a792733d944b8a3ac17cf3cb623fb Wed 2026-10-07 ... Tue 2026-10-13 ...

$ journalctl --since "2026-10-13 08:15:00 UTC" \
    --until "2026-10-13 08:55:00 UTC" --no-pager
-- No entries --
```

The accessible journal lists one boot covering the incident interval. This **provides no indication of an intervening reboot** in the accessible history. However, the journal explicitly warns that the account cannot read messages from other users or the system. Accordingly, **`-- No entries --` must not be interpreted as proof that no cleanup or maintenance occurred**.

## 4. Assessment and hypotheses

| Hypothesis | Assessment | Supporting / missing evidence |
|---|---|---|
| Studio miscomputed free space | **Unlikely** | Server-side `df` independently reported ~26 GiB available. |
| RVV Lab moved to the 116.5 GiB device | **Not supported** | Current run path is mounted on root `/dev/mmcblk0p6`, not `mmcblk2`. |
| Files were deleted or cleaned elsewhere on the shared filesystem | **Plausible, unconfirmed** | Sudden stepwise free-space rise; current home usage is only 4.5 GiB. No deletion audit. |
| Space was released when open-but-deleted files were closed | **Possible, unconfirmed** | Consistent with a sudden free-space change; no relevant process/file-handle history. |
| Storage quota or administrative allocation changed | **Unknown** | Quota inspection tool unavailable; administrative policies not provided. |
| Filesystem size was increased | **Not supported by current evidence** | Current partition reports an ordinary 58 GiB filesystem; historical capacity snapshots are unavailable. |

**Working hypothesis:** a large amount of allocation on the shared root filesystem was released while Test 92 ran, potentially by an external cleanup or another workload. **No actor or mechanism has been established.**

## 5. Impact and risk

**Observed impact:** RVV Lab reported substantially more free disk capacity during Test 92. The campaign completed its result export, and existing campaign folders were still listed in `night-runs`. No disk-full condition or direct loss of the Test 92 result packet is shown.

**Outstanding risks:**

1. **Authorization and capacity planning:** 25–26 GiB of *system-wide* free capacity is not equivalent to a guaranteed per-user allocation.
2. **Shared-environment volatility:** free space may decrease if other users or system processes consume the same root partition.
3. **Benchmark consistency:** unchanged current device identity does not establish unchanged storage latency or throughput; no before/after I/O benchmark exists in the supplied evidence.
4. **Incomplete observability:** absence of privileged filesystem and journal history prevents root-cause attribution.

**Related, separate UI finding:** Studio's **Server Storage** panel displayed `0 campaigns`, while `~/rvvlab-v5/night-runs` visibly contained **six campaign directories**. The displayed count therefore does not represent the actual campaigns in `night-runs`. Investigate and align Studio's campaign discovery path; this UI discrepancy is **not shown to have caused the disk-space event**.

## 6. Requested administrator verification

Please ask the server administrator or hosting provider to confirm:

1. Whether scheduled cleanup, temporary-file removal, log rotation, account-level cleanup, or maintenance ran on **`bpf3-16G-2` between 2026-10-13 08:19 and 08:49 UTC** (**13:19–13:49 PKT**).
2. Whether a large file deletion, release of deleted-but-open files, change to storage accounting, or mount/device operation explains the **~22.945 GiB** free-space increase on `/dev/mmcblk0p6`.
3. Whether the user `gleblanc` / group `external_users` has a **documented quota or usage policy**, and what capacity can safely be reserved for sustained RVV Lab workloads.
4. Whether there was any relevant storage maintenance or performance event affecting the SD device `mmcblk0` / `SC64G`.

**Do not request privilege escalation or attempt to inspect other users' private data.** Aggregate administrative confirmation is sufficient.

## 7. Recommended RVV Lab follow-up

- **Do not purge or relocate campaign files** as part of this investigation; preserve Test 92 metadata and exported results.
- Keep conservative **per-campaign storage budgets**, free-space alerts, and safe stops on insufficient capacity regardless of the unexpectedly high current free-space reading.
- Record alongside every disk-space sample: UTC timestamp, `df` available/used/total values, resolved mountpoint, filesystem type, and device identifier. This allows future changes to be attributed to usage versus mount/capacity changes.
- Update Studio **Server Storage** to enumerate actual `night-runs` campaigns, and show total/used/free storage with mountpoint information.
- After CPU performance testing finishes, optionally run a **small, bounded I/O benchmark** on the existing authorized work directory. Measure without disrupting running experiments and compare only against an equivalent historical test, if one exists.

## 8. Closure criteria

The incident can be considered **explained** when the administrator confirms the cause of the large release or provides equivalent auditable system evidence. Independently, RVV Lab can consider the **operational risk contained** when approved storage limits, monitoring, and campaign listing are corrected. These are separate criteria; confirmation of today's free space alone does not establish root cause or permission to consume it.

---

## Evidence references

- `night-20261013T011722Z-d61b0f.zip` → `metadata.json` → `disk_monitor_15m`: Test 92 timestamps and free MiB; source for the calculated 22.945 GiB increase.
- Test 92 runner log supplied by the user: test identifier, run completion, packet retrieval, observations, and PASS status.
- SSH console transcript supplied by the user: `hostname`, `uname -r`, `df -hT`, `findmnt`, `lsblk`, `/sys/block/mmcblk0/device/*`, `du`, `df -i`, `id`, `quota`, `ulimit`, `journalctl`.
- Studio storage panel text supplied by the user: `25.3 Gio libres / 57.9 Gio au total. 0 campaigns.`

**Evidence limitations:** Post-incident directory listings and unprivileged journal access do not reveal historical deletions; no administrative log, historical mount inventory, per-user quota record, or before/after disk-throughput measurement has been provided.
