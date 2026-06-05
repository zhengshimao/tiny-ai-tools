# tiny-ai-tools 🤖🧬

> AI-generated tiny utilities for bioinformatics tasks

一个存放由 AI（ChatGPT / DeepSeek 等）生成的小巧、实用的生物信息学工具集合。每个工具独立、开箱即用，解决日常数据分析中的小痛点。

---

## 📦 工具列表

| 工具                                        | 描述                                                         | 主要功能                                                     | coding agent |
| ------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------ |
| [fastq_qc](./fastq_qc/)                     | 基于 fastp v1.3.3 的轻量 FASTQ 质控工具，单文件 C++，支持单双端、gzip 自动识别、多格式输出 | per-cycle 质量/含量/GC 统计 · Q20/Q30/Q40 检测 · 重复率 · 插入片段峰值 · 文本/JSON/TSV 输出。 | [1](#coding-agent) |
| [sra_infor_download](./sra_infor_download/) | 从 NCBI SRA 获取 run / BioProject / Study 文件信息，并生成多工具下载脚本的 Python 工具 | SRA XML 解析 · run 列表生成 · TSV 信息表 · wget/axel/aria2c/aws s3 cp 下载脚本 · MD5 校验清单。 | [2](#coding-agent) |
| [gsa_infor_download](./gsa_infor_download/) | 从 GSA/GSA-human 项目获取 metadata、md5 信息，并生成多工具下载脚本的 Python 工具 | GSA/GSA-human metadata 下载 · md5sum 解析 · MD5 校验清单 · aspera/axel/aria2c 下载脚本。 | [2](#coding-agent) |
| [zenodo_download](./zenodo_download/)       | 从 Zenodo record 或 DOI 获取文件信息，并生成多工具下载脚本的 Python 工具 | Zenodo record/URL/DOI 解析 · manifest 文件清单 · URL 列表 · MD5 校验清单 · wget/axel/aria2c 下载脚本。 | [2](#coding-agent) |
| [fastq_check](./fastq_check/)               | 基于 Rust 的 FASTQ/FASTQ.GZ 格式检查工具，支持单双端、质量检测、平台推测、JSON 报告 | 格式检查 · 双端 ID 一致性 · 质量 ASCII 范围 · 平台推测 · JSON 报告 · Rayon 并行 · pigz 解压。 | [3](#coding-agent) + [2](#coding-agent) |

### coding agent

| 编号 | coding agent |
| ---- | ------------ |
| 1 | Claude code + DeepSeek V4 |
| 2 | Codex + GPT5.5 |
| 3 | ChatGPT free 2026.02  + me |

*更多工具持续添加中…*

---

## 🚀 使用方式

每个工具均包含详细的README.md和html文档。

```bash
# 克隆仓库
git clone https://github.com/zhengshimao/tiny-ai-tools.git

# 进入对应工具目录，打开 html说明文档查看工具说明
