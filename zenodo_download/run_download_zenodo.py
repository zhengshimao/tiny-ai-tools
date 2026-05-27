#!/usr/bin/env python3
"""Generate download scripts and MD5 file for a Zenodo record.

Usage:
  python run_download_zenodo.py -r 15596052 -o scripts
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为INFO
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',  # 指定时间格式
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


USER_AGENT = "Mozilla/5.0 (compatible; zenodo-download-script-generator/0.0.1)"


def check_output_dir(path):
    """创建并检查输出目录。

    Args:
        path: 输出目录路径。目录不存在时会自动创建。
            示例: "scripts" 或 "./download_scripts"。

    Returns:
        None。函数只负责目录创建和权限校验，不返回路径。

    示例:
        check_output_dir("scripts")
    """
    os.makedirs(path, exist_ok=True)
    if not os.path.isdir(path):
        raise FileExistsError(f"Output path {path} is not a directory!")
    if not os.access(path, os.W_OK):
        raise PermissionError(f"Output directory {path} is not writable!")


def parse_record_id(record):
    """从 Zenodo ID、记录链接或 DOI 中解析 record ID。

    Args:
        record: 用户通过 --record 输入的记录标识。
            支持纯数字 ID、Zenodo 页面链接、Zenodo API 链接、DOI 链接和 DOI 字符串。
            示例: "15596052"。
            示例: "https://zenodo.org/records/15596052"。
            示例: "https://doi.org/10.5281/zenodo.15596052"。
            示例: "10.5281/zenodo.15596052"。

    Returns:
        Zenodo record ID 字符串。
            示例: "15596052"。
    """
    record = str(record).strip()
    record = re.sub(r"^doi:\s*", "", record, flags=re.IGNORECASE)
    if re.fullmatch(r"\d+", record):
        return record

    # 支持 https://zenodo.org/records/15596052 和 https://zenodo.org/api/records/15596052
    match = re.search(r"/records/(\d+)", record)
    if match:
        return match.group(1)

    # 支持 https://doi.org/10.5281/zenodo.15596052 和 10.5281/zenodo.15596052
    match = re.search(r"10\.5281/zenodo\.(\d+)", record, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    raise ValueError(f"Cannot parse a Zenodo record ID from {record}!")


def fetch_json(url, timeout, retries=3, retry_delay=5):
    """从网络地址下载 JSON 数据，并对临时网络错误进行重试。

    Args:
        url: Zenodo API 地址。
            示例: "https://zenodo.org/api/records/15596052"。
        timeout: 单次请求超时时间，单位为秒。
            示例: 60。
        retries: 最大尝试次数，包括第一次请求。
            示例: 3 表示最多请求 3 次。
        retry_delay: 重试基础等待秒数。第 attempt 次失败后等待 retry_delay * attempt 秒。
            示例: retry_delay=5 时，第一次失败等待 5 秒，第二次失败等待 10 秒。

    Returns:
        解析后的 JSON 对象，通常是 dict。
            示例: 返回对象包含 "files"、"metadata"、"links" 等字段。
    """
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            if exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"HTTP error while fetching {url}: {exc.code} {exc.reason}") from exc
            logger.warning(
                "Fetch attempt %s/%s failed with HTTP %s: %s",
                attempt,
                retries,
                exc.code,
                exc.reason,
            )
        except URLError as exc:
            last_error = exc
            logger.warning("Fetch attempt %s/%s failed: %s", attempt, retries, exc.reason)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response from {url}: {exc}") from exc

        if attempt < retries:
            time.sleep(retry_delay * attempt)

    if isinstance(last_error, HTTPError):
        raise RuntimeError(
            f"HTTP error while fetching {url} after {retries} attempts: "
            f"{last_error.code} {last_error.reason}"
        ) from last_error
    if isinstance(last_error, URLError):
        raise RuntimeError(
            f"Network error while fetching {url} after {retries} attempts: {last_error.reason}"
        ) from last_error
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def extract_files(record_data):
    """从 Zenodo record JSON 中提取下载所需的文件信息。

    Args:
        record_data: fetch_json() 返回的 Zenodo 记录元数据。
            输入中通常包含 record_data["files"] 列表。
            示例文件项包含 key、size、checksum、links.self 等字段。

    Returns:
        文件信息列表。每个元素是 OrderedDict，包含:
            name: 文件名，例如 "NL43_GFP_R2R.fasta"。
            url: 下载链接，例如 Zenodo content API 链接。
            size: 原始字节数，例如 9826。
            md5: MD5 字符串，例如 "322729b2775cd916841c4f3e21e8d22f"。
    """
    files = []
    for item in record_data.get("files", []):
        name = item.get("key")
        url = item.get("links", {}).get("self")
        checksum = item.get("checksum", "")
        size = item.get("size", 0)
        if not name or not url:
            logger.warning("Skipping a file without name or URL: %s", item)
            continue
        md5 = ""
        if checksum.startswith("md5:"):
            md5 = checksum.split(":", 1)[1]
        files.append(
            OrderedDict(
                [
                    ("name", name),
                    ("url", url),
                    ("size", size),
                    ("md5", md5),
                ]
            )
        )

    if not files:
        raise ValueError("No downloadable files were found in the Zenodo record!")
    return files


def sh_quote(text):
    """对字符串进行 POSIX shell 单引号转义。

    Args:
        text: 需要写入 bash 脚本命令行的字符串。
            示例: "file name's test.tar.xz"。

    Returns:
        可安全用于 shell 命令的单引号字符串。
            示例: "'file name'\"'\"'s test.tar.xz'"。
    """
    return "'" + text.replace("'", "'\"'\"'") + "'"


def format_size(size):
    """将字节数转换为易读大小。

    Args:
        size: 文件大小，单位为字节。可以是 int 或能转换为 float 的数值。
            示例: 4893001644。

    Returns:
        易读大小字符串。
            示例: 92 -> "92 B"。
            示例: 1436 -> "1.40 KiB"。
            示例: 4893001644 -> "4.56 GiB"。
    """
    size = float(size)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024


def write_lines(path, lines):
    """将多行文本写入 UTF-8 文件。

    Args:
        path: 输出文件路径。
            示例: "scripts/zenodo_15596052_wget.sh"。
        lines: 不带换行符的文本行可迭代对象。
            示例: ["#!/usr/bin/env bash", "set -euo pipefail"]。

    Returns:
        None。函数会覆盖已有文件内容。
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")


def write_manifest(path, files):
    """写出文件清单 TSV，包含文件名、易读大小、字节数、MD5 和下载链接。

    Args:
        path: manifest TSV 输出路径。
            示例: "scripts/zenodo_15596052_manifest.tsv"。
        files: extract_files() 返回的文件信息列表。
            每个元素需要包含 name、size、md5、url 字段。

    Returns:
        None。输出表头为 filename、size、size_bytes、md5、url。

    示例:
        输入 item["size"] 为 4893001644 时，size 列写为 "4.56 GiB"，
        size_bytes 列写为 "4893001644"。
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["filename", "size", "size_bytes", "md5", "url"])
        for item in files:
            writer.writerow([item["name"], format_size(item["size"]), item["size"], item["md5"], item["url"]])


def build_axel_script(files):
    """构建 axel 下载脚本内容。

    Args:
        files: extract_files() 返回的文件信息列表。
            每个文件会生成两行: 一行注释显示文件名和易读大小，一行 axel 命令。

    Returns:
        bash 脚本文本行列表。
            示例命令: axel --insecure -c -n 20 -o 'file.tar.xz' 'https://.../content'。
    """
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for item in files:
        lines.append(f"# {item['name']} ({format_size(item['size'])})")
        lines.append(f"axel --insecure -c -n 20 -o {sh_quote(item['name'])} {sh_quote(item['url'])}")
    return lines


def build_wget_script(files):
    """构建 wget 下载脚本内容。

    Args:
        files: extract_files() 返回的文件信息列表。
            每个文件会生成两行: 一行注释显示文件名和易读大小，一行 wget 命令。

    Returns:
        bash 脚本文本行列表。
            示例命令: wget -c --content-disposition -O 'file.tar.xz' 'https://.../content'。
    """
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for item in files:
        lines.append(f"# {item['name']} ({format_size(item['size'])})")
        lines.append(f"wget -c --content-disposition -O {sh_quote(item['name'])} {sh_quote(item['url'])}")
    return lines


def build_aria2c_script(files):
    """构建 aria2c 下载脚本内容。

    Args:
        files: extract_files() 返回的文件信息列表。
            每个文件会生成两行: 一行注释显示文件名和易读大小，一行 aria2c 命令。

    Returns:
        bash 脚本文本行列表。
            示例命令: aria2c -c -j 16 -x 16 -s 1 --out='file.tar.xz' 'https://.../content'。
    """
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for item in files:
        lines.append(f"# {item['name']} ({format_size(item['size'])})")
        lines.append(f"aria2c -c -j 16 -x 16 -s 1 --out={sh_quote(item['name'])} {sh_quote(item['url'])}")
    return lines


def write_scripts(files, outdir, prefix):
    """写出下载脚本、MD5 文件、URL 列表和 manifest 表格。

    Args:
        files: extract_files() 返回的文件信息列表。
        outdir: 输出目录。
            示例: "scripts"。
        prefix: 输出文件名前缀。
            示例: "zenodo_15596052"。

    Returns:
        输出类型到文件路径的字典。
            示例: {"wget": "scripts/zenodo_15596052_wget.sh", "md5": "..."}。
    """
    outputs = {
        "axel": os.path.join(outdir, f"{prefix}_axel.sh"),
        "wget": os.path.join(outdir, f"{prefix}_wget.sh"),
        "aria2c": os.path.join(outdir, f"{prefix}_aria2c.sh"),
        "md5": os.path.join(outdir, f"{prefix}_md5.txt"),
        "urls": os.path.join(outdir, f"{prefix}_urls.txt"),
        "manifest": os.path.join(outdir, f"{prefix}_manifest.tsv"),
    }

    write_lines(outputs["axel"], build_axel_script(files))
    write_lines(outputs["wget"], build_wget_script(files))
    write_lines(outputs["aria2c"], build_aria2c_script(files))
    write_lines(outputs["md5"], [f"{item['md5']}  {item['name']}" for item in files if item["md5"]])
    write_lines(outputs["urls"], [item["url"] for item in files])
    write_manifest(outputs["manifest"], files)

    return outputs


def parse_args():
    """解析命令行参数。

    Args:
        None。参数来自 sys.argv，由 argparse 自动读取。

    Returns:
        argparse.Namespace 对象，包含 record、outdir、prefix、timeout 等属性。
            示例: args.record == "15596052"。
    """
    desc = "Generate axel, wget, aria2c download scripts and an MD5 file for a Zenodo record."
    epilog = """Version: 0.0.1
Email: zhengshimao007@163.com
Create: 2026.05.27
Update: -
Author: Shimao Zheng
Agent:  Codex + GPT5.5
Example:
  python run_download_zenodo.py -r 15596052 -o scripts
  python run_download_zenodo.py -r https://zenodo.org/records/15596052 -o scripts
  python run_download_zenodo.py -r https://doi.org/10.5281/zenodo.15596052 -o scripts
  python run_download_zenodo.py -r 10.5281/zenodo.15596052 -o scripts
"""
    parser = argparse.ArgumentParser(
        description=desc,
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-r",
        "--record",
        required=True,
        help=(
            "Zenodo record URL, API URL, numeric ID, DOI URL, or DOI string."
        ),
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=".",
        help="Output directory for generated scripts and checksum files. Default: current directory.",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        default=None,
        help="Output filename prefix. Default: zenodo_<record_id>.",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=60,
        help="Network timeout in seconds. Default: 60.",
    )
    return parser.parse_args()


def main():
    """执行完整脚本流程。"""
    args = parse_args()
    logger.info("Argument values: %s", args.__dict__)
    logger.info("Starting ...")

    if args.timeout < 1:
        raise ValueError("Timeout must be a positive integer!")

    record_id = parse_record_id(args.record)
    prefix = args.prefix if args.prefix else f"zenodo_{record_id}"
    api_url = f"https://zenodo.org/api/records/{record_id}"
    check_output_dir(args.outdir)

    logger.info("Fetching Zenodo record metadata: %s", api_url)
    record_data = fetch_json(api_url, args.timeout)
    files = extract_files(record_data)
    total_size = sum(item["size"] for item in files)
    logger.info(
        "Loaded files: count=%s total_size=%s (%s bytes)",
        len(files),
        format_size(total_size),
        total_size,
    )

    outputs = write_scripts(files, args.outdir, prefix)
    for label, path in sorted(outputs.items()):
        logger.info("Wrote %s: %s", label, path)
    logger.info("Done")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
