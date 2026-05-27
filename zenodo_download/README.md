<a id="中文说明"></a>

# Zenodo Download Script Generator

[中文说明](#中文说明) | [English](#english)

`run_download_zenodo.py` generates `wget`, `axel`, and `aria2c` download scripts for files in a Zenodo record. It also extracts MD5 checksums, download URLs, and a manifest table.

## 目录

- [元信息](#元信息)
- [功能概述](#功能概述)
- [运行环境](#运行环境)
- [快速开始](#快速开始)
- [--record 支持格式](#--record-支持格式)
- [输出文件](#输出文件)
- [下载与校验](#下载与校验)
- [脚本处理流程](#脚本处理流程)
- [注意事项](#注意事项)
- [English](#english)

## 功能概述

该项目用于从 Zenodo record 页面或 DOI 自动解析 record ID，并通过 Zenodo API 获取文件列表，生成批量下载所需的脚本和校验文件。

主要功能：

- 支持 Zenodo record ID、Zenodo URL、Zenodo API URL、DOI URL、DOI 字符串作为输入。
- 生成 `wget`、`axel`、`aria2c` 三种下载脚本。
- 每个文件一条下载命令，便于查看、修改和单独重跑。
- 自动提取 Zenodo `md5:` 校验值，生成 `md5sum -c` 可用的校验文件。
- 输出 manifest 表格，包含文件名、易读大小、原始字节数、MD5 和下载 URL。
- 网络请求支持重试机制。

## 运行环境

- Python 3.6+
- 仅使用 Python 标准库，无需安装第三方 Python 包。
- 生成的 `.sh` 下载脚本建议在 Linux 或 WSL 中执行。
- 下载工具按需安装：
  - `wget`
  - `axel`
  - `aria2c`

## 快速开始

查看帮助：

```bash
python run_download_zenodo.py -h
```

为 Zenodo record `15596052` 生成下载脚本：

```bash
python run_download_zenodo.py -r 15596052 -o scripts
```

使用 DOI URL：

```bash
python run_download_zenodo.py -r https://doi.org/10.5281/zenodo.15596052 -o scripts
```

使用 DOI 字符串：

```bash
python run_download_zenodo.py -r 10.5281/zenodo.15596052 -o scripts
```

## --record 支持格式

| 输入类型 | 示例 | 解析结果 |
|---|---|---|
| Zenodo record ID | `15596052` | `15596052` |
| Zenodo 页面 URL | `https://zenodo.org/records/15596052` | `15596052` |
| Zenodo API URL | `https://zenodo.org/api/records/15596052` | `15596052` |
| DOI URL | `https://doi.org/10.5281/zenodo.15596052` | `15596052` |
| DOI 字符串 | `10.5281/zenodo.15596052` | `15596052` |
| 带前缀 DOI | `doi:10.5281/zenodo.15596052` | `15596052` |

## 输出文件

以以下命令为例：

```bash
python run_download_zenodo.py -r 15596052 -o scripts
```

会生成：

| 文件 | 用途 |
|---|---|
| `scripts/zenodo_15596052_wget.sh` | 使用 `wget -c` 下载所有文件 |
| `scripts/zenodo_15596052_axel.sh` | 使用 `axel --insecure -c -n 20` 下载所有文件 |
| `scripts/zenodo_15596052_aria2c.sh` | 使用 `aria2c -c -j 16 -x 16 -s 1` 下载所有文件 |
| `scripts/zenodo_15596052_md5.txt` | MD5 校验文件，可用于 `md5sum -c` |
| `scripts/zenodo_15596052_urls.txt` | 一行一个下载 URL |
| `scripts/zenodo_15596052_manifest.tsv` | 文件清单，包含文件名、大小、MD5 和 URL |

manifest 示例：

```text
filename	size	size_bytes	md5	url
damha_reference.fasta	92 B	92	35daa62f4d9d52cc6a355efd6e9b6d57	https://zenodo.org/api/records/15596052/files/damha_reference.fasta/content
flair_sep	1.40 KiB	1436	7f4e5fc662df47069325a8f6bd32a857	https://zenodo.org/api/records/15596052/files/flair_sep/content
```

## 下载与校验

任选一种下载脚本执行即可：

```bash
bash scripts/zenodo_15596052_wget.sh
```

或：

```bash
bash scripts/zenodo_15596052_axel.sh
```

或：

```bash
bash scripts/zenodo_15596052_aria2c.sh
```

下载完成后校验：

```bash
md5sum -c scripts/zenodo_15596052_md5.txt
```

## 脚本处理流程

1. 解析命令行参数。
2. 从 `--record` 输入中解析 Zenodo record ID。
3. 请求 `https://zenodo.org/api/records/<record_id>`。
4. 从 JSON 中提取文件名、下载 URL、文件大小和 MD5。
5. 生成三种下载脚本。
6. 写出 MD5、URL 列表和 manifest 表格。

## 注意事项

- 该脚本只生成下载脚本，不直接下载数据文件。
- 生成的 `.sh` 文件建议在 Linux 或 WSL 中执行。
- 大型 Zenodo 数据集下载前请确认磁盘空间充足。
- 推荐下载完成后使用 `md5sum -c` 校验文件完整性。
- 若 Zenodo API 返回 HTTP `429` 或 `5xx`，脚本会自动重试。
- 非 `429` 的 `4xx` 错误通常表示输入 record 无效或访问权限受限。

---

<a id="english"></a>

# Zenodo Download Script Generator

[中文说明](#中文说明) | [English](#english)

`run_download_zenodo.py` generates `wget`, `axel`, and `aria2c` download scripts for files in a Zenodo record. It also writes MD5 checksums, download URLs, and a manifest table.

## Table of Contents

- [Metadata](#metadata)
- [Overview](#overview)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Supported --record Formats](#supported---record-formats)
- [Output Files](#output-files)
- [Download and Checksum](#download-and-checksum)
- [Workflow](#workflow)
- [Notes](#notes)
- [Back to Chinese Section](#中文说明)

## Overview

This repository provides a small Python script for generating reproducible download helper files from Zenodo record metadata.

Key features:

- Accepts Zenodo record IDs, Zenodo URLs, Zenodo API URLs, DOI URLs, and DOI strings.
- Generates download scripts for `wget`, `axel`, and `aria2c`.
- Writes one download command per file.
- Extracts Zenodo `md5:` checksum values into an `md5sum -c` compatible file.
- Writes a manifest table with file name, human-readable size, byte size, MD5, and download URL.
- Retries temporary network failures when fetching Zenodo metadata.

## Requirements

- Python 3.6+
- No third-party Python package is required.
- The generated `.sh` scripts are intended for Linux or WSL.
- Install at least one download tool as needed:
  - `wget`
  - `axel`
  - `aria2c`

## Quick Start

Show help:

```bash
python run_download_zenodo.py -h
```

Generate scripts for Zenodo record `15596052`:

```bash
python run_download_zenodo.py -r 15596052 -o scripts
```

Use a DOI URL:

```bash
python run_download_zenodo.py -r https://doi.org/10.5281/zenodo.15596052 -o scripts
```

Use a DOI string:

```bash
python run_download_zenodo.py -r 10.5281/zenodo.15596052 -o scripts
```

## Supported --record Formats

| Input type | Example | Parsed record ID |
|---|---|---|
| Zenodo record ID | `15596052` | `15596052` |
| Zenodo record URL | `https://zenodo.org/records/15596052` | `15596052` |
| Zenodo API URL | `https://zenodo.org/api/records/15596052` | `15596052` |
| DOI URL | `https://doi.org/10.5281/zenodo.15596052` | `15596052` |
| DOI string | `10.5281/zenodo.15596052` | `15596052` |
| DOI with prefix | `doi:10.5281/zenodo.15596052` | `15596052` |

## Output Files

For this command:

```bash
python run_download_zenodo.py -r 15596052 -o scripts
```

The script writes:

| File | Purpose |
|---|---|
| `scripts/zenodo_15596052_wget.sh` | Download all files using `wget -c` |
| `scripts/zenodo_15596052_axel.sh` | Download all files using `axel --insecure -c -n 20` |
| `scripts/zenodo_15596052_aria2c.sh` | Download all files using `aria2c -c -j 16 -x 16 -s 1` |
| `scripts/zenodo_15596052_md5.txt` | MD5 checksum file compatible with `md5sum -c` |
| `scripts/zenodo_15596052_urls.txt` | One download URL per line |
| `scripts/zenodo_15596052_manifest.tsv` | Manifest table with file name, size, MD5, and URL |

Manifest example:

```text
filename	size	size_bytes	md5	url
damha_reference.fasta	92 B	92	35daa62f4d9d52cc6a355efd6e9b6d57	https://zenodo.org/api/records/15596052/files/damha_reference.fasta/content
flair_sep	1.40 KiB	1436	7f4e5fc662df47069325a8f6bd32a857	https://zenodo.org/api/records/15596052/files/flair_sep/content
```

## Download and Checksum

Run one of the generated scripts:

```bash
bash scripts/zenodo_15596052_wget.sh
```

or:

```bash
bash scripts/zenodo_15596052_axel.sh
```

or:

```bash
bash scripts/zenodo_15596052_aria2c.sh
```

Verify downloaded files:

```bash
md5sum -c scripts/zenodo_15596052_md5.txt
```

## Workflow

1. Parse command-line arguments.
2. Parse a Zenodo record ID from the `--record` value.
3. Fetch `https://zenodo.org/api/records/<record_id>`.
4. Extract file names, download URLs, file sizes, and MD5 checksums from JSON.
5. Generate three download scripts.
6. Write MD5, URL list, and manifest files.

## Notes

- This script only generates download scripts. It does not download data files directly.
- Run the generated `.sh` files in Linux or WSL.
- Check available disk space before downloading large Zenodo datasets.
- Always verify downloaded files with `md5sum -c` when possible.
- HTTP `429` and `5xx` errors are retried when fetching Zenodo metadata.
- Non-`429` `4xx` errors usually mean an invalid record value or restricted access.

---

[返回中文说明版本顶端](#中文说明)
