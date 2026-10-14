# Test 94 — EPCC LLVM 16 RVV lookup compatibility hotfix

EPCC login has LLVM 16's RVV intrinsics v0.11; the Test94 compiler probe and
C++ linking passed, but building simdjson failed in
`engine/include/simdjson/rvv/intrinsics.h`:

- Clang16's `__riscv_vcreate_v_u8m1_u8m2` signature is incompatible with two `u8m1` arguments.
- `__riscv_vcreate_v_u8m1_u8m4` is not available on that compiler.

Only when compiling using Clang 16 or older, the 16-entry lookup functions use
`__riscv_vlmul_ext_v_u8m1_u8m2` / `_u8m4` to widen the register group and
`__riscv_vrgather_vv_u8m2` / `_u8m4` to gather in the target group. All indices
in these two lookup helpers must be in 0..15; both helpers already required
that precondition. LLVM 16's RVV headers support these intrinsics.

On GCC and newer Clang, the previously used create/get assembly is **unchanged**.
No benchmark duration, compiler flags, existing Test91-93 code or output settings
were altered. The EPCC source snapshot SHA256 changes. Keep track of the Cloud-V
and EPCC source hashes when comparing results.

Test locally (with a suitable Clang):

    python tools/test94_rvv_lookup_clang16.py

Run Test94 from Studio, as before. The EPCC cross-build and native JSON
correctness have **not** been validated on the live EPCC machine. Do not
consider a successful compile alone a correctness or performance result; wait
for the Slurm job ID and validation outputs.
