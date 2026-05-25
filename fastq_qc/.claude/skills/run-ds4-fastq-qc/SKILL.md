---
name: run-ds4-fastq-qc
description: Build, run, and smoke-test the fastq_qc CLI tool. Use for compile, run, test, verify.
---

# run-ds4-fastq-qc

**Driver:** [run.sh](run.sh) — cross-platform wrapper. Auto-detects Windows/WSL vs native Linux and runs smoke.sh correctly.

All paths below are relative to the repo root.

## Prerequisites

```bash
# Linux / WSL — install build tools
sudo apt-get install -y g++ make zlib1g-dev

# Windows — no native build; run.sh auto-delegates to WSL
```

## Build

```bash
bash .claude/skills/run-ds4-fastq-qc/run.sh build
```

## Run (agent path)

Full smoke suite (builds binary, tests all features):

```bash
bash .claude/skills/run-ds4-fastq-qc/run.sh
```

Single target:

```bash
bash .claude/skills/run-ds4-fastq-qc/run.sh se         # single-end
bash .claude/skills/run-ds4-fastq-qc/run.sh pe         # paired-end
bash .claude/skills/run-ds4-fastq-qc/run.sh json       # JSON output + validation
bash .claude/skills/run-ds4-fastq-qc/run.sh tsv        # TSV output + validation
bash .claude/skills/run-ds4-fastq-qc/run.sh stdin      # stdin pipe
bash .claude/skills/run-ds4-fastq-qc/run.sh gzip       # gzip auto-detection
bash .claude/skills/run-ds4-fastq-qc/run.sh percent    # percent mode + precision
```

### Direct invocation

For checking a single function without the full CLI, compile a test harness snippet against the source:

```bash
g++ -O0 -g -std=c++0x -I. -o /tmp/test_snippet /tmp/test_snippet.cpp fastq_qc.cpp -lz -lpthread
```

(If on Windows, prefix with `wsl bash -c "cd <repo_root> && ..."`.)

## Run (human path)

```bash
make
./fastq_qc -i exmaple/test_single.fastq
```

## Test data

The `exmaple/` directory contains:

| File | Description |
|------|-------------|
| `test_single.fastq` | 5 synthetic reads, 20 bp each |
| `test_paired_R1.fastq` / `test_paired_R2.fastq` | 2 synthetic paired-end reads |
| `healthy12.clean.R1.fq.gz` / `healthy12.clean.R2.fq.gz` | 61,329 real paired-end reads (gzipped, ~8 MB) |

Large files (~1.5 GB each) also present in `exmaple/` but skipped by the smoke script: `260R15336-T_*.fq.gz`, `260R15336T_Clean_*.fq.gz`.

## Gotchas

- **Windows requires WSL to build.** The Makefile produces an ELF binary; MinGW builds fail on missing zlib headers. `run.sh` auto-detects Windows and delegates to WSL.
- **`run.sh` must be called from the repo root** (or the `bash` invocation must use the relative path from repo root) — the script locates the repo root relative to its own directory.
- **Directory typo** — the example directory is `exmaple/`, not `example/`. This is how it's named in the repo.
- **Q40 is zero** on real Illumina data (Q38–Q42 max) — expected, not a bug.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `cannot execute binary file: Exec format error` | Binary was cross-compiled. Run `make clean && make` in WSL. |
| `fatal error: zlib.h: No such file or directory` | `sudo apt-get install zlib1g-dev` |
| `-lpthread` not found | `sudo apt-get install build-essential` |
| Smoke script exits with "FAIL" | Run individual targets to isolate the failure. |
| `run.sh` from Windows fails to find WSL | Ensure a WSL distro is installed and set as default (`wsl --set-default <distro>`). |
