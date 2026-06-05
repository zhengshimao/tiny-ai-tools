# fastq_check

<p>
  <img src="https://img.shields.io/badge/language-Rust-orange" alt="Rust">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

[中文](#中文说明) | [English](#english-readme)

`fastq_check` 是一个 Rust 编写的 FASTQ/FASTQ.GZ 格式检查工具，支持单端和双端测序数据检查、双端 read ID 一致性检查、质量字符 ASCII 范围统计、平台推测、JSON 报告、Rayon 并行 batch 处理，以及可选 pigz 多线程解压。

> **🎯 适用范围：无法获得测序 FASTQ 文件原始 MD5 时**，本工具可通过格式检查、质量统计、平台推测等替代手段验证 FASTQ 文件的完整性与正确性。

## 目录

- [中文说明](#中文说明)
  - [功能特性](#功能特性)
  - [安装与编译](#安装与编译)
  - [快速使用](#快速使用)
  - [参数说明](#参数说明)
  - [输入文件](#输入文件)
  - [输出结果](#输出结果)
  - [示例](#示例)
  - [注意事项](#注意事项)
- [English README](#english-readme)
  - [Features](#features)
  - [Build](#build)
  - [Quick Start](#quick-start)
  - [Options](#options)
  - [Input Files](#input-files)
  - [Output](#output)
  - [Examples](#examples)
  - [Notes](#notes)

## 功能特性

- 支持单端 FASTQ 检查：只提供 `--read1`。
- 支持双端 FASTQ 检查：同时提供 `--read1` 和 `--read2`。
- 支持 `.fq`、`.fastq`、`.fq.gz`、`.fastq.gz`。
- 检查 FASTQ 基本格式：header、plus 行、sequence/quality 长度一致性。
- 可选严格碱基检查：`--strict-bases`，仅允许 `A/C/G/T/N`。
- 可选质量字符范围统计：`--detect-quality`。
- 可选测序平台推测：`--infer-platform`。
- 支持平台：`Illumina`、`BGI/MGI`、`PacBio`、`Oxford Nanopore`、`Unknown`。
- 双端模式输出 `pairs_checked`、`name_mismatches`、`unpaired_reads`。
- 使用 Rayon、Crossbeam channel、batch 处理、线程局部统计和 reduce，减少锁竞争。
- 可选外部 `pigz` 多线程解压 gzip 文件。
- 支持 pretty JSON 报告。

## 安装与编译

需要 Rust 工具链。

```bash
cargo build --release
```

编译后的程序位于：

```bash
target/release/fastq_check
```

Windows 下为：

```powershell
target\release\fastq_check.exe
```

预编译的 Linux 和 Windows 可执行文件已上传至 [bin/](bin/) 目录，可直接下载使用。

## 快速使用

单端：

```bash
target/release/fastq_check \
  --read1 example/CRR947772_part.fastq \
  --infer-platform \
  --detect-quality \
  --json-report single_report.json
```

双端：

```bash
target/release/fastq_check \
  --read1 example/illumina_R1.fq \
  --read2 example/illumina_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report illumina_report.json
```

gzip 文件使用 pigz：

```bash
target/release/fastq_check \
  --read1 input_R1.fq.gz \
  --read2 input_R2.fq.gz \
  --pigz \
  --pigz-path /path/to/pigz \
  --pigz-threads 8 \
  --threads 8 \
  --json-report report.json
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--read1`, `-1` | 必填 | R1 FASTQ/FASTQ.GZ；单端数据只需提供该参数 |
| `--read2`, `-2` | 无 | R2 FASTQ/FASTQ.GZ；提供后启用双端检查 |
| `--threads` | `0` | Rayon worker 线程数；`0` 表示自动选择 |
| `--batch-size` | `8192` | 每个 batch 的 FASTQ records 数，不是文件数 |
| `--pigz` | `false` | 对 `.gz` 输入使用外部 pigz 解压 |
| `--pigz-threads` | `8` | 传给 pigz 的线程数 |
| `--pigz-path` | `pigz` | pigz 可执行文件路径 |
| `--strict-bases` | `false` | 仅允许大写 `A/C/G/T/N` |
| `--detect-quality` | `false` | 统计 quality ASCII 范围并推测 Phred 编码 |
| `--infer-platform` | `false` | 根据 header 推测测序平台 |
| `--platform-sample-size` | `10000` | 每个文件用于平台推测的 reads 数 |
| `--json-report` | 无 | 输出 pretty JSON 报告 |

## 输入文件

FASTQ record 为四行结构：

```text
@header
sequence
+
quality
```

示例：

```text
@A00459:371:H25C5DSX5:2:1101:9064:1000 1:N:0:GAACCTTAGC+ACGTCACAGA
CNAAGGCTTGCTGATTAATTTTATCCATCACAACTGGCCCTCTCTTCTGCGACATCGTTTTCTGGAGGAATTTATCACTCCCATTGTAAAGGTATCTAAAAACAAGCAAGAAATGGCATTTTACAGCCTTCCTGAATTTGAAGAGTGGAA
+
F#FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:FFFFFFFFFFFF:FFFFFFFFF:FFFFFFFFFFFFFFFFFFF:FF:FF:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
```

## 输出结果

标准输出示例：

```text
Total reads: 50
Total bases: 7500
Errors: 0
Elapsed seconds: 0.030
example/illumina_R1.fq: reads=25, bases=3750, errors=0
example/illumina_R1.fq: quality=Phred33
example/illumina_R1.fq: platform=Illumina confidence=1.000 sampled_reads=25
```

JSON 输出示例：

```json
{
  "read1": {
    "path": "example/illumina_R1.fq",
    "total_reads": 25,
    "total_bases": 3750,
    "min_read_len": 150,
    "max_read_len": 150,
    "min_qual_ascii": 35,
    "max_qual_ascii": 70,
    "phred_detected": "Phred33",
    "platform_inferred": "Illumina",
    "platform_confidence": 1.0,
    "platform_reads_sampled": 25,
    "errors": 0
  },
  "read2": {
    "path": "example/illumina_R2.fq",
    "total_reads": 25,
    "total_bases": 3750,
    "min_read_len": 150,
    "max_read_len": 150,
    "min_qual_ascii": 44,
    "max_qual_ascii": 70,
    "phred_detected": "Phred33",
    "platform_inferred": "Illumina",
    "platform_confidence": 1.0,
    "platform_reads_sampled": 25,
    "errors": 0
  },
  "paired": {
    "pairs_checked": 25,
    "name_mismatches": 0,
    "unpaired_reads": 0,
    "errors": 0
  },
  "total_reads": 50,
  "total_bases": 7500,
  "errors": 0,
  "elapsed_seconds": 0.03
}
```

## 示例

Illumina 示例：

```bash
target/release/fastq_check \
  --read1 example/illumina_R1.fq \
  --read2 example/illumina_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report example_illumina_report.json \
  --threads 4 \
  --batch-size 128
```

MGI 示例：

```bash
target/release/fastq_check \
  --read1 example/MGI_R1.fq \
  --read2 example/MGI_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report example_mgi_report.json \
  --threads 4 \
  --batch-size 128
```

## 注意事项

- `--batch-size` 的单位是 FASTQ records/reads，不是文件数量。`8192 records = 32768 lines`。
- `min_qual_ascii` 和 `max_qual_ascii` 是 quality 字符的 ASCII 编码范围，不是解码后的 Phred Q 值。
- `--platform-sample-size` 只控制平台推测采样 reads 数；FASTQ 完整性检查仍扫描完整文件。
- `--infer-platform` 是基于 header 的启发式推测，不应作为强制平台判定。
- `--pigz` 需要系统可执行 `pigz`，也可以用 `--pigz-path` 指定完整路径。
- 程序发现错误时退出码为 `1`；无错误时退出码为 `0`。

---

<a id="english-readme"></a>

# fastq_check

<p>
  <img src="https://img.shields.io/badge/language-Rust-orange" alt="Rust">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License">
</p>

[中文](#中文说明) | [English](#english-readme)

`fastq_check` is a Rust-based FASTQ/FASTQ.GZ validator for single-end and paired-end sequencing data. It supports paired read ID consistency checks, quality ASCII range reporting, sequencing platform inference, pretty JSON reports, Rayon-based batch parallelism, and optional pigz-powered gzip decompression.

> **🎯 Scope: When original FASTQ MD5 checksums are unavailable**, this tool provides format validation, quality statistics, platform inference, and other alternative integrity checks for FASTQ files.

## Features

- Single-end FASTQ validation with `--read1`.
- Paired-end FASTQ validation with `--read1` and `--read2`.
- Supports `.fq`, `.fastq`, `.fq.gz`, and `.fastq.gz`.
- Checks FASTQ header, plus line, sequence/quality length consistency, truncation, and gzip read errors.
- Optional strict base validation with `--strict-bases`.
- Optional quality ASCII range detection with `--detect-quality`.
- Optional platform inference with `--infer-platform`.
- Supported inferred platforms: `Illumina`, `BGI/MGI`, `PacBio`, `Oxford Nanopore`, and `Unknown`.
- Paired-end report fields: `pairs_checked`, `name_mismatches`, `unpaired_reads`.
- Rayon workers, Crossbeam channels, batch processing, thread-local statistics, and reduce-style aggregation.
- Optional external `pigz` decompression for gzip FASTQ files.
- Pretty JSON report output.

## Build

Install Rust, then run:

```bash
cargo build --release
```

Executable:

```bash
target/release/fastq_check
```

On Windows:

```powershell
target\release\fastq_check.exe
```

Pre-compiled Linux and Windows executables are available in the [bin/](bin/) directory for direct download.

## Quick Start

Single-end:

```bash
target/release/fastq_check \
  --read1 example/CRR947772_part.fastq \
  --infer-platform \
  --detect-quality \
  --json-report single_report.json
```

Paired-end:

```bash
target/release/fastq_check \
  --read1 example/illumina_R1.fq \
  --read2 example/illumina_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report illumina_report.json
```

Use pigz for gzip input:

```bash
target/release/fastq_check \
  --read1 input_R1.fq.gz \
  --read2 input_R2.fq.gz \
  --pigz \
  --pigz-path /path/to/pigz \
  --pigz-threads 8 \
  --threads 8 \
  --json-report report.json
```

## Options

| Option | Default | Description |
|---|---:|---|
| `--read1`, `-1` | required | R1 FASTQ/FASTQ.GZ; provide only this for single-end data |
| `--read2`, `-2` | none | R2 FASTQ/FASTQ.GZ; enables paired-end checks |
| `--threads` | `0` | Rayon worker threads; `0` lets Rayon choose |
| `--batch-size` | `8192` | FASTQ records per worker batch |
| `--pigz` | `false` | Use external pigz for `.gz` input |
| `--pigz-threads` | `8` | Threads passed to pigz |
| `--pigz-path` | `pigz` | Path to pigz executable |
| `--strict-bases` | `false` | Allow only uppercase `A/C/G/T/N` |
| `--detect-quality` | `false` | Report quality ASCII range and infer Phred encoding |
| `--infer-platform` | `false` | Infer sequencing platform from FASTQ headers |
| `--platform-sample-size` | `10000` | Reads sampled per file for platform inference |
| `--json-report` | none | Write a pretty JSON report |

## Input Files

A FASTQ record has four lines:

```text
@header
sequence
+
quality
```

Example:

```text
@E250122340L1C001R00100012764/1
GGGGGGTAAGGCGAGGTTAGCGAGGCTTGCTAGAAGTCATCAAAAAGGTATTAGTGGGAGTAGAGTTTGAAGTCCTTGAGAGAGGATTATGATGCGACTGTGAGTGCGTTCGTAGTTTGAGTTTGCTAGGAAGAGTAGTAATGAGGATGT
+
DDDDDDDDDDDDDDDDDDDDDDD9DDDDD9DDDDDD,DDDDDDDDDD,DDDDD,D,D,,D,DDDDDDDDDDDD,DDDDD9DDD,9DDDDDD,DDDDDDD,DDDD9D9DD9DD,DDD9D9D9DDDD,DDD,,DDD,D9DDDD,DD,9,DDD
```

## Output

Standard output example:

```text
Total reads: 50
Total bases: 7500
Errors: 0
Elapsed seconds: 0.019
example/MGI_R1.fq: reads=25, bases=3750, errors=0
example/MGI_R1.fq: quality=Phred33
example/MGI_R1.fq: platform=BGI/MGI confidence=1.000 sampled_reads=25
```

JSON report example:

```json
{
  "read1": {
    "path": "example/MGI_R1.fq",
    "total_reads": 25,
    "total_bases": 3750,
    "min_read_len": 150,
    "max_read_len": 150,
    "min_qual_ascii": 33,
    "max_qual_ascii": 68,
    "phred_detected": "Phred33",
    "platform_inferred": "BGI/MGI",
    "platform_confidence": 1.0,
    "platform_reads_sampled": 25,
    "errors": 0
  },
  "read2": {
    "path": "example/MGI_R2.fq",
    "total_reads": 25,
    "total_bases": 3750,
    "min_read_len": 150,
    "max_read_len": 150,
    "min_qual_ascii": 33,
    "max_qual_ascii": 68,
    "phred_detected": "Phred33",
    "platform_inferred": "BGI/MGI",
    "platform_confidence": 1.0,
    "platform_reads_sampled": 25,
    "errors": 0
  },
  "paired": {
    "pairs_checked": 25,
    "name_mismatches": 0,
    "unpaired_reads": 0,
    "errors": 0
  },
  "total_reads": 50,
  "total_bases": 7500,
  "errors": 0,
  "elapsed_seconds": 0.019
}
```

## Examples

Illumina example:

```bash
target/release/fastq_check \
  --read1 example/illumina_R1.fq \
  --read2 example/illumina_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report example_illumina_report.json \
  --threads 4 \
  --batch-size 128
```

MGI example:

```bash
target/release/fastq_check \
  --read1 example/MGI_R1.fq \
  --read2 example/MGI_R2.fq \
  --infer-platform \
  --detect-quality \
  --strict-bases \
  --json-report example_mgi_report.json \
  --threads 4 \
  --batch-size 128
```

## Notes

- `--batch-size` is measured in FASTQ records/reads, not file count. `8192 records = 32768 lines`.
- `min_qual_ascii` and `max_qual_ascii` are ASCII byte ranges from the quality line, not decoded Phred Q scores.
- `--platform-sample-size` only controls reads sampled for platform inference. FASTQ integrity checks still scan the entire file.
- `--infer-platform` is heuristic and should not be treated as a strict platform validator.
- `--pigz` requires an executable `pigz`; use `--pigz-path` when it is not available in `PATH`.
- Exit code is `0` when no errors are found and `1` when validation errors are detected.

---

[回到顶端中文说明版本](#中文说明)
