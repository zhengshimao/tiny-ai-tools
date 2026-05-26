#!/usr/bin/env python3
"""Generate GSA/GSA-human metadata and download helper scripts.

Usage:
  python run_get_gsa_infor.py -p HRA000425
  python run_get_gsa_infor.py -p CRA000112
  python run_get_gsa_infor.py -p https://download.cncb.ac.cn/gsa/CRA000112/
"""

import argparse
import logging
import os
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request

logging.basicConfig(
    level=logging.INFO,  # 设置日志级别为INFO
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',  # 指定时间格式
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept": "*/*",
}


def check_file(file):
    """检查输入文件是否存在且可读。

    参数:
        file (str): 要检查的文件路径。
                     例如: "/path/to/input.txt", "CRA000112.xlsx"

    返回:
        None。如果文件不存在、不是普通文件或不可读，直接抛出异常。

    异常:
        FileNotFoundError: 文件不存在
        FileExistsError: 路径不是普通文件，或文件不可读

    示例:
        check_file("md5sum.txt")      # 检查当前目录下的 md5sum.txt
        check_file("data/sample.fq")  # 检查子目录中的文件
    """
    if not os.path.exists(file):
        raise FileNotFoundError(f"File {file} does not exist!")
    if not os.path.isfile(file):
        raise FileExistsError(f"File {file} is not a file!")
    if not os.access(file, os.R_OK):
        raise FileExistsError(f"File {file} is not readable!")


def parse_args():
    """解析命令行参数。

    输入:
        从 sys.argv 读取用户传入的命令行参数。

    返回:
        argparse.Namespace，包含以下属性:
            - project (str): 项目 ID 或下载 URL，例如 "CRA000112", "HRA000425",
                             "https://download.cncb.ac.cn/gsa/CRA000112/"
            - outdir (str 或 None): 输出目录路径，None 表示使用默认目录
            - force (bool): 是否强制重新下载已缓存的文件

    命令行参数:
        -p, --project : 必需。项目 ID（以 HRA/CRA 开头）或完整 URL
        -o, --outdir  : 可选。输出目录，默认生成 gsa_info_sample_<项目名>
        --force       : 可选。重新下载已缓存的 HTML/Excel/md5sum 文件

    示例:
        python run_get_gsa_infor.py -p CRA000112
        python run_get_gsa_infor.py -p HRA000425 -o ./my_output --force
    """
    desc = "Download GSA/GSA-human metadata and generate download helper scripts."
    epilog = """Version: 0.1.0
Email: zhengshimao007@163.com
Create: 2026.05.26
Update: -
Author: Shimao Zheng
Example:
  python run_get_gsa_infor.py -p HRA000425
  python run_get_gsa_infor.py -p CRA000112
  python run_get_gsa_infor.py -p https://download.cncb.ac.cn/gsa/CRA000112/
"""
    parser = argparse.ArgumentParser(
        description=desc,
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Project ID or download URL. It must start with HRA, CRA, or http.",
    )
    parser.add_argument(
        "-o",
        "--outdir",
        default=None,
        help="Output directory. Default: gsa_info_sample_<project_basename> under current directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload cached HTML, metadata Excel, and md5sum.txt.",
    )
    return parser.parse_args()


def project_basename(project):
    """从项目 ID 或 URL 中提取稳定的项目基名。

    参数:
        project (str): 项目 ID 或 URL。
                        例如: "CRA000112", "HRA000425",
                              "https://download.cncb.ac.cn/gsa/CRA000112/"

    返回:
        str: 项目基名（去掉了末尾的斜杠后取 basename）。
             例如: "CRA000112"（从 ID 或 URL 中提取）

    示例:
        project_basename("CRA000112")                                    # → "CRA000112"
        project_basename("https://download.cncb.ac.cn/gsa/CRA000112/")   # → "CRA000112"
    """
    return os.path.basename(project.rstrip("/"))


def validate_project(project):
    """验证项目 ID 或 URL 的前缀是否合法。

    参数:
        project (str): 项目 ID 或 URL。
                        例如: "CRA000112", "HRA000425",
                              "https://download.cncb.ac.cn/gsa/CRA000112/"

    返回:
        None。如果前缀不合法，抛出 ValueError 异常。

    异常:
        ValueError: 项目 ID 不以 HRA/CRA/http 开头时抛出

    示例:
        validate_project("CRA000112")  # 通过
        validate_project("HRA000425")  # 通过
        validate_project("ABC000001")  # 抛出 ValueError
    """
    if re.search(r"^[HC]RA", project) or project.startswith("http"):
        return
    raise ValueError(
        "The project id must start with 'HRA', 'CRA', or 'http', "
        "e.g. HRA000425, CRA000112."
    )


def ensure_dir(path):
    """创建目录（如果不存在）。

    参数:
        path (str): 要创建的目录路径。
                    例如: "gsa_info_sample_CRA000112", "./output/data"

    返回:
        None。如果目录已存在也不会报错（等价于 mkdir -p）。

    示例:
        ensure_dir("gsa_info_sample_CRA000112")  # 创建输出目录
        ensure_dir("./downloads/samples")        # 创建多级子目录
    """
    os.makedirs(path, exist_ok=True)


def is_nonempty_file(path):
    """检查路径是否为非空文件。

    参数:
        path (str): 要检查的文件路径。
                    例如: "md5sum.txt", "CRA000112.xlsx"

    返回:
        bool: True 表示文件存在且大小大于 0，否则返回 False。

    示例:
        is_nonempty_file("md5sum.txt")     # → True（文件存在且有内容）
        is_nonempty_file("empty.txt")      # → False（空文件）
        is_nonempty_file("not_exist.txt")  # → False（文件不存在）
    """
    return os.path.isfile(path) and os.path.getsize(path) > 0


def fetch_url(url, output_file, method="GET", data=None, headers=None, force=False):
    """下载 URL 内容到本地文件。

    参数:
        url (str): 要下载的 URL 地址。
                   例如: "https://ngdc.cncb.ac.cn/gsa/browse/CRA000112"
        output_file (str): 保存路径。
                           例如: "gsa_info_sample_CRA000112/index.html"
        method (str): HTTP 方法，默认 "GET"。
                      例如: "GET", "POST"
        data (dict, 可选): POST 表单数据字典。
                           例如: {"type": "3", "dlAcession": "CRA000112"}
        headers (dict, 可选): 额外的 HTTP 请求头。
                              例如: {"Content-Type": "application/x-www-form-urlencoded"}
        force (bool): 如果为 True，即使本地已有非空文件也重新下载。

    返回:
        None。下载内容直接写入 output_file。

    异常:
        RuntimeError: 下载失败或下载的文件为空时抛出

    示例:
        fetch_url("https://ngdc.cncb.ac.cn/gsa/browse/CRA000112", "index.html")
        fetch_url("https://example.com/api", "data.json",
                  method="POST", data={"key": "value"}, force=True)
    """
    if is_nonempty_file(output_file) and not force:
        logger.info("OK: %s", output_file)
        return

    encoded_data = None
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    if data is not None:
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    request = urllib.request.Request(url, data=encoded_data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ERROR: failed to download '{url}': {exc}") from exc

    with open(output_file, "wb") as out_handle:
        out_handle.write(content)

    if not is_nonempty_file(output_file):
        raise RuntimeError(f"ERROR: downloaded file is empty: {output_file}")
    logger.info("OK: %s", output_file)


def read_text(path):
    """以 UTF-8 编码读取文本文件（遇到非法字节时自动替换）。

    参数:
        path (str): 要读取的文件路径。
                    例如: "gsa_info_sample_CRA000112/index.html",
                          "gsa_info_sample_CRA000112/md5sum.txt"

    返回:
        str: 文件完整内容字符串。

    示例:
        html = read_text("index.html")     # 读取 HTML 文件内容
        text = read_text("md5sum.txt")     # 读取 md5 校验文件内容
    """
    with open(path, encoding="utf-8", errors="replace") as in_handle:
        return in_handle.read()


def download_html(project, workdir, force=False):
    """下载 CRA 或 HRA 项目的 browse 页面 HTML。

    参数:
        project (str): 项目 ID。例如: "CRA000112", "HRA000425"
        workdir (str): 输出目录路径。
                       例如: "gsa_info_sample_CRA000112"
        force (bool): 是否忽略本地缓存、强制重新下载。

    返回:
        str: 下载的 HTML 文件路径。
             例如: "gsa_info_sample_CRA000112/index.html"

    行为:
        - CRA 项目: 从 https://ngdc.cncb.ac.cn/gsa/browse/<project> 下载
        - HRA 项目: 从 https://ngdc.cncb.ac.cn/gsa-human/browse/<project> 下载
        - 其他格式: 直接返回文件路径（不下载）
        - HRA 受控访问项目: 检测到 "Controlled access" 后直接退出

    示例:
        download_html("CRA000112", "gsa_info_sample_CRA000112")
        # → 下载页面到 gsa_info_sample_CRA000112/index.html
    """
    html_file = os.path.join(workdir, "index.html")
    if re.match(r"^CRA[0-9]{6}$", project):
        browse_url = f"https://ngdc.cncb.ac.cn/gsa/browse/{project}"
    elif re.match(r"^HRA[0-9]{6}$", project):
        browse_url = f"https://ngdc.cncb.ac.cn/gsa-human/browse/{project}"
    else:
        return html_file

    logger.info("browse_url: %s", browse_url)
    fetch_url(browse_url, html_file, force=force)
    if project.startswith("HRA") and "Controlled access" in read_text(html_file):
        logger.warning("%s: %s is Controlled access.", project, browse_url)
        raise SystemExit(0)
    return html_file


def download_meta_gsa(project, workdir, force=False):
    """下载 GSA（CRA 项目）的元数据 Excel 文件。

    参数:
        project (str): CRA 项目 ID。例如: "CRA000112", "CRA001234"
        workdir (str): 输出目录路径。
                       例如: "gsa_info_sample_CRA000112"
        force (bool): 是否忽略本地缓存、强制重新下载。

    返回:
        None。Excel 文件保存到 <workdir>/<project>.xlsx。
             例如: "gsa_info_sample_CRA000112/CRA000112.xlsx"

    说明:
        通过 POST 请求向 GSA 接口提交 project ID 来获取元数据 Excel。

    示例:
        download_meta_gsa("CRA000112", "gsa_info_sample_CRA000112")
        # → 生成 gsa_info_sample_CRA000112/CRA000112.xlsx
    """
    if not re.match(r"^CRA[0-9]{6}$", project):
        raise ValueError(f"ERROR: failed to download {project} metadata excel file")
    excel_file = os.path.join(workdir, f"{project}.xlsx")
    fetch_url(
        "https://ngdc.cncb.ac.cn/gsa/file/exportExcelFile",
        excel_file,
        method="POST",
        data={"type": "3", "dlAcession": project},
        force=force,
    )


def find_hra_study_id(html_text):
    """从 GSA-human browse 页面 HTML 中提取 study_id，为下载HRA开头ID的信息表作准备。

    参数:
        html_text (str): browse 页面的 HTML 内容。
                         通常来自 read_text("index.html")。

    返回:
        str: 提取到的 study_id 数字字符串。
             例如: "12345", "67890"

    异常:
        RuntimeError: 无法从 HTML 中找到 study_id 时抛出

    示例:
        html = read_text("gsa_info_sample_HRA000425/index.html")
        study_id = find_hra_study_id(html)  # → "12345"
    """
    match = re.search(r"study_id[^0-9]*([0-9]+)", html_text)
    if not match:
        raise RuntimeError("ERROR: cannot find study_id from index.html")
    return match.group(1)


def download_meta_gsa_human(project, workdir, force=False):
    """下载 GSA-human（HRA 项目）的元数据 Excel 文件。

    参数:
        project (str): HRA 项目 ID。例如: "HRA000425", "HRA001234"
        workdir (str): 输出目录路径。
                       例如: "gsa_info_sample_HRA000425"
        force (bool): 是否忽略本地缓存、强制重新下载。

    返回:
        None。Excel 文件保存到 <workdir>/<project>.xlsx。
             例如: "gsa_info_sample_HRA000425/HRA000425.xlsx"

    说明:
        需要先下载 browse 页面并从中提取 study_id，
        然后用 study_id 拼接出 Excel 文件的下载地址。

    示例:
        download_meta_gsa_human("HRA000425", "gsa_info_sample_HRA000425")
        # → 先下载 index.html，再生成 HRA000425.xlsx
    """
    if not re.match(r"^HRA[0-9]{6}$", project):
        raise ValueError(f"ERROR: failed to download {project} metadata excel file")
    html_file = download_html(project, workdir, force=force)
    study_id = find_hra_study_id(read_text(html_file))
    excel_file = os.path.join(workdir, f"{project}.xlsx")
    excel_url = (
        f"https://ngdc.cncb.ac.cn/gsa-human/file/exportExcelFile?"
        f"fileName=/webdb/gsagroup/webApplications/gsa_human_20200410/"
        f"gsa-human/batchExcel/human/{project}/{project}.xlsx&study_id={study_id}&requestFlag=0"
    )
    fetch_url(
        excel_url,
        excel_file,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        force=force,
    )


def load_cached_url(url_file):
    """从 url.txt 缓存文件中读取之前保存的下载 URL。

    参数:
        url_file (str): url.txt 缓存文件路径。
                        例如: "gsa_info_sample_CRA000112/url.txt"

    返回:
        str 或 None: 成功读取则返回 URL 字符串，文件不存在或为空则返回 None。
                     例如: "https://download.cncb.ac.cn/gsa/CRA000112"

    说明:
        url.txt 内容为纯文本 URL 链接（无引号包裹，无赋值语法）。

    示例:
        url = load_cached_url("gsa_info_sample_CRA000112/url.txt")
        # → "https://download.cncb.ac.cn/gsa/CRA000112"
    """
    if not is_nonempty_file(url_file):
        return None
    return read_text(url_file).strip()


def write_cached_url(url_file, url):
    """将下载 URL 以纯文本格式写入缓存文件。

    参数:
        url_file (str): 缓存文件路径（通常为 url.txt）。
                        例如: "gsa_info_sample_CRA000112/url.txt"
        url (str): 要缓存的下载 URL。
                   例如: "https://download.cncb.ac.cn/gsa/CRA000112"

    返回:
        None。写入格式即为 URL 本身。

    示例:
        write_cached_url("url.txt", "https://download.cncb.ac.cn/gsa/CRA000112")
        # → url.txt 内容为: https://download.cncb.ac.cn/gsa/CRA000112
    """
    with open(url_file, "w", encoding="utf-8") as out_handle:
        out_handle.write(f"{url}\n")


def find_download_url_from_html(project, html_text):
    """从 CRA browse 页面 HTML 中提取唯一的下载 URL。

    参数:
        project (str): CRA 项目 ID。例如: "CRA000112"
        html_text (str): browse 页面的 HTML 内容。
                         通常来自 read_text("index.html")。

    返回:
        str: 提取到的下载 URL。
             例如: "https://download.cncb.ac.cn/gsa/CRA000112"

    异常:
        RuntimeError: 找不到唯一下载 URL（0 个或 2+ 个匹配）时抛出

    说明:
        在 HTML 中搜索包含项目名且含 "download" 字样的所有 URL，
        去重后应该只有一个匹配。

    示例:
        html = read_text("gsa_info_sample_CRA000112/index.html")
        url = find_download_url_from_html("CRA000112", html)
        # → "https://download.cncb.ac.cn/gsa/CRA000112"
    """
    urls = sorted(set(re.findall(rf"http[^< =]+{re.escape(project)}", html_text)))
    urls = [url for url in urls if "download" in url]
    if len(urls) != 1:
        raise RuntimeError(f"ERROR: cannot find a unique download URL for {project}")
    return urls[0]


def get_download_url(project, workdir, force=False):
    """获取最终的数据下载 URL(ftp站点)。

    参数:
        project (str): 项目 ID 或完整 URL。
                       例如: "CRA000112", "HRA000425",
                             "https://download.cncb.ac.cn/gsa/CRA000112/"
        workdir (str): 工作目录路径（用于缓存 url.txt）。
                       例如: "gsa_info_sample_CRA000112"
        force (bool): 是否忽略本地 url.txt 缓存，重新解析。

    返回:
        str: 最终的数据下载 URL（末尾无斜杠）。
             例如: "https://download.cncb.ac.cn/gsa/CRA000112"

    说明:
        - 如果已有缓存的 url.txt 且不强制刷新，直接读取缓存
        - 直接输入 URL → 直接返回该 URL
        - HRA 项目 → 拼接下载域名
        - CRA 项目 → 先下载 HTML 页面，再从中解析下载 URL

    示例:
        url = get_download_url("CRA000112", "gsa_info_sample_CRA000112")
        # → "https://download.cncb.ac.cn/gsa/CRA000112"
    """
    url_file = os.path.join(workdir, "url.txt")
    cached_url = None if force else load_cached_url(url_file)
    if cached_url:
        logger.info("OK: %s", url_file)
        return cached_url.rstrip("/")

    if project.startswith("http"):
        url = project.rstrip("/")
    elif re.match(r"^HRA[0-9]{6}$", project):
        url = f"https://download.cncb.ac.cn/gsa-human/{project}"
    elif re.match(r"^CRA[0-9]{6}$", project):
        html_file = download_html(project, workdir, force=force)
        url = find_download_url_from_html(project, read_text(html_file))
    else:
        raise ValueError(f"ERROR: unsupported project type: {project}")

    write_cached_url(url_file, url)
    logger.info("OK: %s", url_file)
    return url.rstrip("/")


def parse_md5sum(md5sum_file, project_base):
    """解析 md5sum.txt 文件中的校验条目。

    参数:
        md5sum_file (str): md5sum.txt 文件路径。
                           例如: "gsa_info_sample_CRA000112/md5sum.txt"
        project_base (str): 项目基名，用于去除路径中的项目前缀。
                            例如: "CRA000112"

    返回:
        list[tuple[str, str]]: 列表，每个元素为 (md5校验值, 相对路径)。
             例如: [
                 ("8e017f9d...", "CRA000112/CRD015678.gz"),
                 ("caeaaf41...", "CRA000112/CRD015679.gz"),
             ]
             其中项目基名 "CRA000112/" 前缀会被去除。

    说明:
        md5sum.txt 每行格式为: <md5>  <路径>
        函数会过滤掉格式不正确的行（不是恰好两列）。

    示例:
        entries = parse_md5sum("gsa_info_sample_CRA000112/md5sum.txt", "CRA000112")
        # → [("8e017f9d...", "CRD015678.gz"), ("caeaaf41...", "CRD015679.gz")]
    """
    entries = []
    with open(md5sum_file, encoding="utf-8", errors="replace") as in_handle:
        for line in in_handle:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            checksum, path = parts
            marker = project_base + "/"
            if marker in path:
                path = path.split(marker, 1)[1]
            entries.append((checksum, path))
    return entries


def write_md5_file(entries, output_file):
    """将 MD5 条目写入校验文件（第二列仅保留文件名，不包含路径）。

    参数:
        entries (list[tuple[str, str]]): (md5, 路径) 元组列表。
             例如: [("8e017f9d...", "CRD015678.gz"), ...]
        output_file (str): 输出文件路径。
                           例如: "gsa_info_sample_CRA000112/MD5_all.txt"

    返回:
        None。写入格式为每行 "<md5>\t<文件名>"。
             例如: "8e017f9d...\tCRD015678.gz"

    说明:
        输出文件可直接用于 `md5sum -c` 校验：
        将 MD5_all.txt 与数据文件放在同一目录，运行 md5sum -c MD5_all.txt 即可。

    示例:
        write_md5_file(entries, "MD5_all.txt")
        # → MD5_all.txt 内容:
        #   8e017f9d...	CRD015678.gz
        #   caeaaf41...	CRD015679.gz
    """
    with open(output_file, "w", encoding="utf-8", newline="") as out_handle:
        for checksum, path in entries:
            out_handle.write(f"{checksum}\t{os.path.basename(path)}\n")
    logger.info("OK: %s", output_file)


def aspera_base_url(url):
    """将 HTTPS 下载根 URL 转换为 Aspera 远程路径格式。

    参数:
        url (str): HTTPS 下载根 URL。
                   例如: "https://download.cncb.ac.cn/gsa/CRA000112"

    返回:
        str: Aspera 远程根路径。
             例如: "download.cncb.ac.cn:gsa/CRA000112"

    说明:
        转换规则:
        1. 去掉 "https://" 前缀
        2. 将第一个 ".ac.cn/" 替换为 ".ac.cn:"
        最终格式为 "主机:路径"，供 ascp 命令使用。

    示例:
        aspera_base_url("https://download.cncb.ac.cn/gsa/CRA000112")
        # → "download.cncb.ac.cn:gsa/CRA000112"
    """
    value = re.sub(r"^https://", "", url.rstrip("/"))
    value = re.sub(r"\.ac\.cn/", ".ac.cn:", value, count=1)
    return value


def make_executable(path):
    """为脚本文件添加可执行权限（平台支持的情况下）。

    参数:
        path (str): 脚本文件路径。
                    例如: "gsa_info_sample_CRA000112/run_download_all_files_using_axel.sh"

    返回:
        None。修改文件的权限位，添加 owner/group/others 的执行权限。

    说明:
        在 Windows 上可能不支持 chmod，此时会记录警告但不中断流程。

    示例:
        make_executable("run_download_all_files_using_axel.sh")
        # → 文件添加 +x 权限
    """
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as exc:
        logger.warning("Failed to chmod +x %s: %s", path, exc)


def write_download_scripts(entries, url, workdir, prefix):
    """生成 aspera、axel、aria2c 三种下载工具的辅助脚本。

    参数:
        entries (list[tuple[str, str]]): (md5, 相对路径) 元组列表。
             例如: [("8e017f9d...", "CRD015678.gz"), ...]
        url (str): HTTPS 下载根 URL。
                   例如: "https://download.cncb.ac.cn/gsa/CRA000112"
        workdir (str): 脚本输出目录。
                       例如: "gsa_info_sample_CRA000112"
        prefix (str): 脚本文件名前缀。
                      例如: "run_download_fastq" → 生成:
                            - run_download_fastq_using_aspera.sh
                            - run_download_fastq_using_axel.sh
                            - run_download_fastq_using_aria2c.sh

    返回:
        None。生成三个 shell 脚本文件，内容分别为:

        aspera 脚本每行格式:
            [[ -f ./<文件名> ]] && echo Skip: <文件名> || \
            ascp -vQT -l 500m -P33001 -k 1 -i ~/.aspera/connect/etc/aspera01.openssh \
            aspera01@<远程路径>/<相对路径> ./

        axel 脚本每行格式:
            axel --no-clobber -n 20 <URL>/<相对路径>

        aria2c 脚本每行格式:
            aria2c -c -j 16 -x 16 -s 16 <URL>/<相对路径>

        同时检查 aspera keyfile (~/.aspera/connect/etc/aspera01.openssh) 是否存在，
        如果不存在则打印下载提示。

    示例:
        write_download_scripts(entries, url, workdir, "run_download_all_files")
        # → 生成 run_download_all_files_using_{aspera,axel,aria2c}.sh
    """
    paths = [path for _, path in entries]
    aspera_file = os.path.join(workdir, f"{prefix}_using_aspera.sh")
    axel_file = os.path.join(workdir, f"{prefix}_using_axel.sh")
    aria2c_file = os.path.join(workdir, f"{prefix}_using_aria2c.sh")
    remote_root = aspera_base_url(url)

    keyfile = os.path.expanduser("~/.aspera/connect/etc/aspera01.openssh")
    if not os.path.isfile(keyfile):
        logger.error(
            "FILE not exist: %s. Please download it: wget --no-clobber -c -O %s "
            "https://ngdc.cncb.ac.cn/gsa-human/file/fileId000003/downFile",
            keyfile,
            keyfile,
        )

    with open(aspera_file, "w", encoding="utf-8", newline="\n") as out_handle:
        for path in paths:
            basename = os.path.basename(path)
            out_handle.write(
                f"[[ -f ./{basename} ]] && echo Skip: {basename} || "
                f"ascp -vQT -l 500m -P33001 -k 1 -i "
                f"~/.aspera/connect/etc/aspera01.openssh "
                f"aspera01@{remote_root}/{path} ./\n"
            )

    with open(axel_file, "w", encoding="utf-8", newline="\n") as out_handle:
        for path in paths:
            out_handle.write(f"axel --no-clobber -n 20 {url}/{path}\n")

    with open(aria2c_file, "w", encoding="utf-8", newline="\n") as out_handle:
        for path in paths:
            out_handle.write(f"aria2c -c -j 16 -x 16 -s 16 {url}/{path}\n")

    for script in (aspera_file, axel_file, aria2c_file):
        make_executable(script)
        logger.info("OK: %s", script)


def run_workflow(args):
    """执行脚本的主工作流程。

    参数:
        args (argparse.Namespace): 命令行参数对象，包含:
            - args.project (str): 项目 ID 或 URL
            - args.outdir (str 或 None): 输出目录
            - args.force (bool): 是否强制重新下载

    返回:
        None。

    工作流程说明:
        1. 验证项目 ID 格式是否合法
        2. 创建输出目录
        3. 下载元数据 Excel（CRA 用 GSA 接口，HRA 用 GSA-human 接口）
        4. 下载 browse 页面 HTML
        5. 获取最终的数据下载 URL
        6. 下载 md5sum.txt 校验文件
        7. 解析 md5sum.txt，统计全部文件和 FASTQ 文件数量
        8. 如果有 FASTQ 文件: 生成 MD5.txt 和 fastq 下载脚本
        9. 生成全部文件的 MD5_all.txt 和下载脚本

    输出文件:
        <workdir>/<project>.xlsx           - GSA 元数据 Excel
        <workdir>/index.html               - browse 页面 HTML
        <workdir>/url.txt                   - 缓存的下载 URL
        <workdir>/md5sum.txt               - 原始 md5 校验文件
        <workdir>/MD5_all.txt              - 全部文件的 MD5（可直接 md5sum -c）
        <workdir>/MD5.txt                  - 仅 FASTQ 的 MD5（如有 FASTQ）
        <workdir>/run_download_all_files_using_*.sh  - 全部文件下载脚本
        <workdir>/run_download_fastq_using_*.sh      - FASTQ 下载脚本（如有）

    示例:
        args = parse_args()       # 从命令行解析参数
        run_workflow(args)        # 执行完整工作流
    """
    project = args.project.strip()
    validate_project(project)

    base = project_basename(project)
    workdir = args.outdir or os.path.join(os.getcwd(), f"gsa_info_sample_{base}")
    ensure_dir(workdir)

    logger.info("Argument values: %s", vars(args))
    logger.info("Starting ...")

    if re.match(r"^CRA[0-9]{6}$", project):
        download_meta_gsa(project, workdir, force=args.force)
    elif re.match(r"^HRA[0-9]{6}$", project):
        download_meta_gsa_human(project, workdir, force=args.force)

    if re.match(r"^[CH]RA[0-9]{6}$", project):
        download_html(project, workdir, force=args.force)

    url = get_download_url(project, workdir, force=args.force)
    logger.info("Final URL: %s", url)

    md5sum_file = os.path.join(workdir, "md5sum.txt")
    fetch_url(f"{url}/md5sum.txt", md5sum_file, force=args.force)

    all_entries = parse_md5sum(md5sum_file, base)
    fastq_entries = [(checksum, path) for checksum, path in all_entries if path.endswith("q.gz")]
    logger.info("Loaded md5 entries: all=%d, fastq=%d", len(all_entries), len(fastq_entries))

    if fastq_entries:
        write_md5_file(fastq_entries, os.path.join(workdir, "MD5.txt"))
        write_download_scripts(fastq_entries, url, workdir, "run_download_fastq")
    else:
        logger.info("No fastq files found, skip generating fastq scripts")

    write_md5_file(all_entries, os.path.join(workdir, "MD5_all.txt"))
    write_download_scripts(all_entries, url, workdir, "run_download_all_files")

    logger.info("Output directory: %s", workdir)
    logger.info("Done")


def main():
    """主函数入口。

    输入:
        从命令行读取参数（由 parse_args 处理）。

    输出:
        int: 返回值。
             0 表示成功，1 表示发生错误。

    说明:
        捕获 OSError、RuntimeError、ValueError 三种异常，
        记录错误日志后返回 1，避免程序崩溃。

    示例:
        if __name__ == "__main__":
            sys.exit(main())
    """
    args = parse_args()
    try:
        run_workflow(args)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
