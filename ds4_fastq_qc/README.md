# fastq_qc · 轻量 FASTQ 质控工具

[![C++](https://img.shields.io/badge/C%2B%2B-11-blue)](https://en.cppreference.com/w/cpp/11)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![fastp](https://img.shields.io/badge/algorithm-fastp%20v1.3.3-orange)](https://github.com/OpenGene/fastp/archive/refs/tags/v1.3.3.zip)

[English](#english) | [中文](#中文)

---

## 中文

### 简介

**轻量 FASTQ 质量控制工具** — 核心质控算法提取并改写自 [fastp v1.3.3](https://github.com/OpenGene/fastp/archive/refs/tags/v1.3.3.zip)（[GitHub](https://github.com/OpenGene/fastp)）。

支持单端/双端 FASTQ，自动识别 gzip 压缩，输出文本摘要、JSON 报告、TSV 表格。

### 特性

- **单文件 C++** — 除 zlib 外零运行时依赖
- **兼容 fastp** — 相同的 34 数组 per-cycle 统计引擎
- **gzip 透明** — 通过 `.gz` 扩展名和 magic bytes 自动检测
- **多格式输出** — 文本摘要 (stdout)、JSON 报告 (`-o`)、TSV 表格 (`-p`)
- **双端感知** — 分读长/合并摘要，插入片段大小估算
- **千分位分隔** — 文本/TSV/JSON 各自独立控制

### 编译

**依赖**：g++ ≥ 4.6，zlib（`libz-dev` / `zlib-devel`）。Windows 建议在 **WSL** 中编译。

```bash
cd fastq_qc
make
```

### 快速开始

```bash
# 单端：文本摘要输出到 stdout
./fastq_qc -i sample.fq.gz

# 单端 + JSON 报告
./fastq_qc -i sample.fq.gz -o qc_report.json

# 双端 + JSON + TSV 表格
./fastq_qc -i R1.fq.gz -I R2.fq.gz -o report.json -p sample1

# 百分比模式 + 自定义精度 + 千分位 (默认输出小数 0.0-1.0)
./fastq_qc -i R1.fq.gz -I R2.fq.gz -o report.json -p sample1 \
    -s sample1 -percent -d 2 --tsv-comma --json-comma

# 多线程加速
./fastq_qc -i R1.fq.gz -I R2.fq.gz -t 4 -o report.json

# 从 stdin 读取
cat sample.fastq | ./fastq_qc -i -
```

> 反斜杠 `\` 为 bash 续行符，可将长命令拆分为多行，也可写在同一行。

### 选项

| 选项 | 参数 | 默认 | 说明 |
|--------|-----|---------|-------------|
| `-i` | `<file>` | — | **必选**。输入 FASTQ（双端时为 R1），`-` 表示 stdin |
| `-I` | `<file>` | — | R2 FASTQ，启用双端模式 |
| `-o` | `<file>` | — | JSON 报告路径（不指定则不输出 JSON） |
| `-p` | `<prefix>` | — | TSV 前缀。单端：`_summary.tsv` + cycles；双端：`_R1_summary`、`_R2_summary`、`_combined_summary` + cycles |
| `-s` | `<id>` | 文件名 | TSV 中使用的样本 ID |
| `-percent` | — | off | 百分比模式：rate 以 0–100 输出；**默认小数** (0.0–1.0, 6dp) |
| `-d` | `<n>` | `6` | rate 值保留的小数位数 |
| `-is` | `<n>` | `512` | 最大插入片段大小（仅双端） |
| `-t` | `<n>` | `1` | Worker 线程数；>1 时启用批处理多线程 |
| `--tsv-comma` | — | off | TSV 数值加千分位分隔符 |
| `--json-comma` | — | off | JSON 长整数加千分位（以字符串输出） |
| `-h` | — | — | 显示帮助 |

### 输出参考

#### 文本摘要 (stdout)

```
=== QC Summary ===
  Total reads:               61,329
  Total bases:           15,999,479
  Mean length:                  260 bp
  GC bases:               8,486,112  (0.530399)
  Q20 bases:             15,593,674  (0.974636)
  Q30 bases:             14,726,729  (0.920451)
  Q40 bases:                      0  (0.000000)
  Total cycles:                 301
  Cycle 20 Q20:              61,266  (0.998973)

=== Duplication ===
  Duplication rate:        0.058602

=== Insert Size ===
  Insert size peak:             259
  Unknown pairs:                  0
```

#### JSON 报告 (`-o`)

```json
{
  "read1": {
    "total_reads": 61329, "total_bases": 15999479,
    "mean_length": 260, "total_cycles": 301,
    "q20_bases": 15593674, "q20_rate": 0.974636,
    "q30_bases": 14726729, "q30_rate": 0.920451,
    "q40_bases": 0, "q40_rate": 0.000000,
    "gc_bases": 8486112, "gc_content": 0.530399,
    "cycle20_bases": 61266, "cycle20_rate": 0.998973,
    "quality_curves": { "A":[...], "T":[...], "C":[...], "G":[...], "mean":[...] },
    "content_curves": { "A":[...], "T":[...], "C":[...], "G":[...], "N":[...], "GC":[...] },
    "quality_histogram": { "33":221, "34":522, ..., "71":10499889 }
  },
  "read2": { ... },
  "total_reads": 122658, "total_bases": 31995914,
  "cycle20_bases": 121919, "cycle20_rate": 0.993975,
  "duplication": { "rate": 0.058602 },
  "insert_size": { "peak": 259, "unknown": 0, "histogram": [...] }
}
```

#### TSV 表格 (`-p`)

| 模式 | 文件 | 列 |
|------|------|---------|
| 单端 | `_summary.tsv` | sample, total_reads, total_bases, total_cycles, mean_length, gc_bases, gc_content, q20_bases, q20_rate, q30_bases, q30_rate, q40_bases, q40_rate, cycle20_bases, cycle20_rate, dup_rate |
| 双端 | `_R1_summary.tsv` | + insert_size_peak, insert_size_unknown |
| 双端 | `_R2_summary.tsv` | R2 独立指标 + 全局 dup/insert |
| 双端 | `_combined_summary.tsv` | R1+R2 合并指标 |
| 通用 | `_R1_cycles.tsv` | cycle, mean_qual, A/T/C/G_qual, A/T/C/G/N_content, GC_content |
| 双端 | `_R2_cycles.tsv` | 同上 per-cycle 列 |

#### stderr 日志

```
Processing paired-end FASTQ data...
Total reads processed: 61,329
JSON report written to: report.json
TSV summary R1 written to: sample1_R1_summary.tsv
TSV summary R2 written to: sample1_R2_summary.tsv
TSV combined summary written to: sample1_combined_summary.tsv
TSV cycles R1 written to: sample1_R1_cycles.tsv
TSV cycles R2 written to: sample1_R2_cycles.tsv
Elapsed time: 2 sec (0 min 2 sec)
```

### 架构

#### 类结构

| 类 | 职责 |
|-------|------|
| `FastqRead` | 存储一条 FASTQ 记录（name, seq, strand, quality） |
| `FastqReader` | 以 4 MB 内部缓冲读取 FASTQ；通过扩展名和 magic bytes 自动检测 gzip |
| `QcStats` | 核心质量统计引擎 — 与 fastp 相同的 34 数组 per-cycle 布局 |
| `DupCounter` | FNV-1a 64-bit 哈希 + `unordered_set` 精确去重 |
| `InsertSizeStats` | 基于重叠分析的插入片段大小估算（仅双端） |

#### 处理流程

```
命令行解析 → FastqReader (gzip 检测) → 逐条读取循环：
  ├─ QcStats::process_read()    → per-cycle 质量/含量/GC 计数
  ├─ DupCounter::add_read/pair() → 哈希去重
  └─ InsertSizeStats::process_pair() → 重叠 → 插入大小 (仅 PE)

→ QcStats::summarize() → 曲线 + 聚合指标
→ stdout: 文本摘要
→ -o: JSON 报告
→ -p: TSV 表格
→ stderr: 运行时间
```

### 算法

#### Per-Cycle 质量统计

采用与 fastp 相同的 **34 数组单次分配** 布局：

```
m_cycle_buffer = new long[34 × bufLen]

  [ 0..7]  — m_cycle_q30[8]       每种碱基 Q30 次数/cycle
  [ 8..15] — m_cycle_q20[8]       每种碱基 Q20 次数/cycle
  [16..23] — m_cycle_content[8]   每种碱基出现次数/cycle
  [24..31] — m_cycle_qual[8]      每种碱基质量值总和/cycle
  [32]     — m_cycle_total_base   每 cycle 总碱基数
  [33]     — m_cycle_total_qual   每 cycle 总质量值
```

**碱基编码**：`base & 0x07` 映射 A→1, T→4, C→3, G→7, N→6（利用 ASCII % 8 性质）。

#### 重复检测

每条 read 序列做 FNV-1a 64-bit 哈希，存入 `unordered_set<uint64_t>`。双端时通过 `boost::hash_combine` 合并 R1 和 R2 哈希。哈希值已存在即为重复。

#### 插入片段大小（仅双端）

1. R2 反向互补
2. 在 R1 后缀与 RC-R2 前缀之间寻找最长精确重叠（≥ 30 bp），通过 `memcmp` 实现
3. `insert_size = len(R1) + len(R2) - overlap`
4. 跟踪直方图；peak = 众数

#### cycle20_rate 定义

> **重要**："cycle20" 在不同 QC 工具中含义不同。

本工具中 `cycle20_rate` 为**第 20 个测序循环（即 reads 第 20 个碱基位置，0-based 索引 19）处，质量值 ≥ Q20 的碱基占比**：

```
cycle20_rate = Σ m_cycle_q20[b][19] / m_cycle_total_base[19]
```

常见歧义（本工具不使用）：

| 上下文 | cycle20 含义 |
|---------|----------------|
| **fastq_qc** | reads 位置 20 处 Q20+ 比率 |
| 某些 QC 报告 | Phred 20 质量阈值 (ASCII `'5'`) |
| 某些 QC 报告 | 平均质量首次降至 Q20 以下的 cycle 编号 |

如需全局 Q20+ 比率请使用 `q20_rate`。Q20 阈值为 Phred 20（Phred+33 编码下 ASCII `'5'`）。

### 注意事项

- **内存**：去重使用 256 MB 固定大小的 Bloom Filter，内存不随数据量增长。多线程模式下线程间共享（mutex 保护）。
- **Q40**：`q40_bases` 为 0 是正常的——多数 Illumina 数据质量上限为 Q38–Q42，Q40 需要 ASCII `'I'` (73)。
- **单端重复率**可能高于双端——哈希信息更少导致碰撞概率更高，与 fastp 行为一致。
- **TSV 千分位**：开启 `--tsv-comma` 后数值列包含逗号（如 `61,329`），部分解析器可能需要预处理。
- **JSON 千分位**：开启 `--json-comma` 后长整数以 JSON 字符串输出（如 `"61,329"`），而非数字。
- **插入片段大小**：算法移植自 fastp v1.3.3，容错 overlap（≤5 mismatch 或 20%），双向搜索，unknown = hist[max]。
- **gzip 检测**：同时检查 `.gz` 扩展名和 gzip magic bytes `0x1F 0x8B`。无 `.gz` 扩展名但内容为 gzip 的文件也能正确处理。

### 与 fastp v1.3.3 的差异

| 对比项 | fastp v1.3.3 | fastq_qc |
|--------|-------------|----------|
| 去重算法 | Bloom Filter + SIMD 素数哈希, 1G–32G | Bloom Filter + FNV-1a, **固定 256 MB** |
| 去重率 (RNA001) | 53.58% | **53.67%** (+0.09%) |
| insert_size unknown | 在原始 reads 上计算 overlap (含 adapter) | 在最终 reads 上计算 |
| 多线程 | Reader×2 + Worker×N + Writer×N, SPSC 队列 | 批处理: 500K reads/批 → N 线程并行 |
| 速率格式 | JSON 百分比 (0–100) | **默认小数** (0.0–1.0, 6dp), `-percent` 切百分比 |
| 核心 QC 指标 | identical | identical (total_reads/bases/cycles/q20/q30/q40 完全一致) |

**基准测试** (RNA001 Clean, 2000 万 PE reads):

| 指标 | fastp (after) | fastq_qc | 差异 |
|------|-------------|----------|------|
| R1 total_reads | 20,007,861 | 20,007,861 | 0 |
| R1 total_bases | 2,987,954,103 | 2,987,954,103 | 0 |
| R1 q20_bases | 2,923,704,980 | 2,923,704,980 | 0 |
| Duplication rate | 0.535827 | 0.536722 | +0.000895 |
| Insert size peak | 268 | 268 | 0 |
| Insert size unknown | 866,263 | 10,444,537 | 见上表说明 |

---

## English

### Overview

**Lightweight FASTQ Quality Control Tool** — core QC algorithms extracted and adapted from [fastp v1.3.3](https://github.com/OpenGene/fastp/archive/refs/tags/v1.3.3.zip) ([GitHub](https://github.com/OpenGene/fastp)).

Supports single-end and paired-end FASTQ, auto-detects gzip compression, and outputs text summaries, JSON reports, and TSV tables.

### Features

- **Single-file C++** — zero runtime dependencies beyond zlib
- **fastp-compatible** — same 34-array per-cycle statistics engine
- **Gzip transparent** — auto-detection via `.gz` extension *and* magic bytes
- **Multi-format output** — text summary (stdout), JSON report (`-o`), TSV tables (`-p`)
- **Paired-end aware** — per-read and combined summaries, insert-size estimation
- **Thousands separators** — independently controlled for text, TSV, and JSON

### Build

**Requirements**: g++ ≥ 4.6, zlib (`libz-dev` / `zlib-devel`). On Windows, build inside **WSL**.

```bash
cd fastq_qc
make
```

### Quick Start

```bash
# Single-end: text summary to stdout
./fastq_qc -i sample.fq.gz

# Single-end + JSON report
./fastq_qc -i sample.fq.gz -o qc_report.json

# Paired-end + JSON + TSV tables
./fastq_qc -i R1.fq.gz -I R2.fq.gz -o report.json -p sample1

# Percentage mode with custom precision and comma separators (default: decimal 0.0-1.0)
./fastq_qc -i R1.fq.gz -I R2.fq.gz -o report.json -p sample1 \
    -s TCR001 -percent -d 2 --tsv-comma --json-comma

# Multi-threaded
./fastq_qc -i R1.fq.gz -I R2.fq.gz -t 4 -o report.json

# From stdin
cat sample.fastq | ./fastq_qc -i -
```

> The backslash `\` is bash line-continuation syntax.

### Options

| Option | Arg | Default | Description |
|--------|-----|---------|-------------|
| `-i` | `<file>` | — | **Required**. Input FASTQ (R1 for paired-end). Use `-` for stdin |
| `-I` | `<file>` | — | R2 FASTQ — enables paired-end mode |
| `-o` | `<file>` | — | JSON report output path (omitted = no JSON) |
| `-p` | `<prefix>` | — | TSV output prefix. SE: `_summary.tsv` + cycles. PE: `_R1_summary`, `_R2_summary`, `_combined_summary` + cycles |
| `-s` | `<id>` | filename | Sample ID used in TSV output |
| `-percent` | — | off | Output rates as percentages (0–100); **default: decimal** (0.0–1.0, 6dp) |
| `-d` | `<n>` | `6` | Decimal places for rate values |
| `-is` | `<n>` | `512` | Maximum insert size (paired-end only) |
| `-t` | `<n>` | `1` | Number of worker threads; >1 enables batch multi-threading |
| `--tsv-comma` | — | off | Add thousands separators to TSV numeric columns |
| `--json-comma` | — | off | Add thousands separators to JSON long values (output as strings) |
| `-h` | — | — | Show help |

### Output Reference

See the Chinese section above for formatted examples. Key outputs:

- **stdout**: aligned text summary with QC Summary, Duplication, and Insert Size sections
- **`-o` JSON**: full per-cycle curves, quality histogram, duplication rate, insert size
- **`-p` TSV**: summary table + per-cycle tables (`_R1_cycles.tsv`, `_R2_cycles.tsv`)
- **stderr**: progress, file paths, and elapsed time

### Architecture

| Class | Role |
|-------|------|
| `FastqRead` | Stores one FASTQ record (name, seq, strand, quality) |
| `FastqReader` | Reads FASTQ with 4 MB internal buffer; auto-detects gzip |
| `QcStats` | Core QC engine — 34-array per-cycle layout matching fastp |
| `DupCounter` | Bloom Filter (256 MB fixed) + FNV-1a hash, thread-safe via mutex |
| `InsertSizeStats` | Mismatch-tolerant overlap analysis ported from fastp v1.3.3 (PE only) |

### Algorithms

#### Per-Cycle Statistics

Uses the same **34-array single-allocation** layout as fastp. Base encoding via `base & 0x07`.

#### Duplication

Fixed-size Bloom Filter (256 MB, 4 hash functions) with FNV-1a hash. Thread-safe via shared mutex. Paired-end hashes combined via `hash_combine`.

#### Insert Size (PE only)

Ported from fastp v1.3.3: mismatch-tolerant overlap search (≤5 mismatches or 20%), forward + reverse direction. Overlap computed on reverse-complemented R2 vs R1. Unknown = `hist[max_size]`.

#### cycle20_rate / cycle20_bases

`cycle20_rate` = proportion of bases ≥ Q20 at read position 20 (0-based index 19). `cycle20_bases` = absolute Q20+ base count at that position.

### Notes

- **Memory**: DupCounter uses 256 MB fixed Bloom Filter. Memory does not grow with data size.
- **Q40**: `q40_bases` of 0 is normal — typical Illumina max quality is Q38–Q42.
- **Single-end duplication** may be higher than paired-end (less hash information).
- **TSV commas**: `--tsv-comma` outputs `61,329` — not all parsers handle this.
- **JSON commas**: `--json-comma` outputs `"61,329"` as a *string*, not a number.
- **Insert size**: Ported from fastp v1.3.3 — mismatch-tolerant overlap, bidirectional search, unknown = hist[max].
- **Gzip detection**: checks `.gz` extension and magic bytes `0x1F 0x8B`.

### Comparison with fastp v1.3.3

| Metric | fastp | fastq_qc |
|--------|-------|----------|
| Dedup algorithm | Bloom Filter + SIMD prime hash, 1G–32G | Bloom Filter + FNV-1a, **fixed 256 MB** |
| Dedup rate (RNA001) | 53.58% | **53.67%** (+0.09%) |
| Insert size unknown | Computed on original reads (pre-trim) | Computed on final reads |
| Threading | Full pipeline: Reader×2 + Worker×N + Writer×N | Batch: 500K reads/batch → N threads |
| Rate format | JSON percentages (0–100) | **Default decimal** (0.0–1.0, 6dp), `-percent` for % |
| Core QC metrics | identical | identical (reads/bases/cycles/q20/q30/q40) |

> See the Chinese section for detailed benchmark results.

### License

Core algorithms adapted from [fastp v1.3.3](https://github.com/OpenGene/fastp/archive/refs/tags/v1.3.3.zip) by Shifu Chen et al. (MIT License).
