#!/usr/bin/env python3
"""Get sample file information from NCBI SRA.

Usage:
  python run_get_bioinfor_from_NCBI_SRA.py -i SRR8869110 -o ./
"""

import argparse
import csv
import logging
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


EUTILS_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUTILS_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DOWNLOAD_TOOLS = ["wget", "axel", "aria2c", "aws_s3_cp"]
DEFAULT_COLUMNS = [
    "run",
    "cluster",
    "filename",
    "size",
    "date",
    "md5",
    "version",
    "semantic_name",
    "supertype",
    "sratoolkit",
    "url",
    "free_egress",
    "access_type",
    "org",
]


def parse_args():
    """Parse command-line arguments.

    Args:
        None.

    Returns:
        Parsed argparse namespace.
    """
    desc = "Get sample file information from NCBI SRA."
    epilog = """Version: 0.0.5
Email: zhengshimao007@163.com
Create: 2026.05.24
Update: 2026.05.24
Author: Shimao Zheng
Agent:  Codex + GPT5.5
Example: python run_get_bioinfor_from_NCBI_SRA.py -i SRR8869110 -o ./
Example: python run_get_bioinfor_from_NCBI_SRA.py -i PRJNA531644 -o ./
Example: python run_get_bioinfor_from_NCBI_SRA.py -i SRP191521 -o ./
"""
    parser = argparse.ArgumentParser(
        description=desc,
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="SRA run, study, or BioProject ID, e.g. SRR8869110, SRP191521, or PRJNA531644.",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        default="./",
        help="Output directory: an existent directory. (default: %(default)s)",
    )
    return parser.parse_args()


def fetch_url(url, retries=3, timeout=60):
    """Fetch text content from a URL.

    Args:
        url: Request URL.
        retries: Number of request attempts.
        timeout: Request timeout in seconds.

    Returns:
        Response text decoded as UTF-8.
    """
    headers = {"User-Agent": "run_get_bioinfor_from_NCBI_SRA.py/0.0.4"}
    request = urllib.request.Request(url, headers=headers)

    last_error = None
    for attempt in range(1, retries + 1):
        logger.info("Fetching NCBI URL: attempt %s/%s", attempt, retries)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            logger.warning("Fetch attempt failed: %s", exc)
            if attempt < retries:
                time.sleep(2 * attempt)

    raise RuntimeError(f"Failed to fetch URL: {last_error}")


def check_output_dir(output_dir):
    """Check whether an output directory exists and is writable.

    Args:
        output_dir: Output directory path.

    Returns:
        None.
    """
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")
    if not output_dir.is_dir():
        raise FileExistsError(f"Output path is not a directory: {output_dir}")


def fetch_sra_xml(srr, retries=3, timeout=60):
    """Fetch SRA XML from NCBI E-utilities.

    Args:
        srr: SRA run ID, for example SRR8869110.
        retries: Number of request attempts.
        timeout: Request timeout in seconds.

    Returns:
        XML text returned by NCBI.
    """
    params = urllib.parse.urlencode({"db": "sra", "id": srr, "rettype": "xml"})
    url = f"{EUTILS_EFETCH}?{params}"
    return fetch_url(url, retries=retries, timeout=timeout)


def search_sra_uids(query, retmax=100000):
    """Search NCBI SRA and return record UIDs for a query.

    Args:
        query: Search term, for example PRJNA531644 or SRP191521.
        retmax: Maximum UID count to request.

    Returns:
        List of NCBI SRA record UIDs.
    """
    params = urllib.parse.urlencode({"db": "sra", "term": query, "retmax": retmax})
    url = f"{EUTILS_ESEARCH}?{params}"
    xml_text = fetch_url(url)
    root = ET.fromstring(xml_text)
    uids = [node.text for node in root.findall(".//Id") if node.text]
    logger.info("Found SRA record UIDs for %s: %s", query, len(uids))
    return uids


def fetch_sra_xml_by_uids(uids):
    """Fetch SRA XML for NCBI SRA record UIDs.

    Args:
        uids: NCBI SRA record UID list.

    Returns:
        XML text returned by NCBI.
    """
    params = urllib.parse.urlencode({"db": "sra", "id": ",".join(uids), "rettype": "xml"})
    url = f"{EUTILS_EFETCH}?{params}"
    return fetch_url(url)


def parse_run_accessions(xml_text):
    """Parse run accessions from SRA XML.

    Args:
        xml_text: XML text returned by NCBI.

    Returns:
        Sorted list of unique SRR, ERR, or DRR accessions.
    """
    root = ET.fromstring(xml_text)
    runs = set()
    for run_node in root.iter("RUN"):
        accession = run_node.attrib.get("accession", "")
        if accession.startswith(("SRR", "ERR", "DRR")):
            runs.add(accession)
    run_list = sorted(runs)
    logger.info("Parsed run accessions: %s", len(run_list))
    return run_list


def resolve_input_to_runs(input_id):
    """Resolve an input ID to one or more run accessions.

    Args:
        input_id: SRA run, study, or BioProject ID.

    Returns:
        List of SRR, ERR, or DRR accessions.
    """
    if input_id.startswith(("SRR", "ERR", "DRR")):
        return [input_id]

    uids = search_sra_uids(input_id)
    if not uids:
        raise RuntimeError(f"No SRA records found for {input_id}")

    xml_text = fetch_sra_xml_by_uids(uids)
    runs = parse_run_accessions(xml_text)
    if not runs:
        raise RuntimeError(f"No run accessions found for {input_id}")
    return runs


def append_new_keys(columns, record):
    """Append record keys that are not already in the column list.

    Args:
        columns: Output column name list.
        record: Parsed row dictionary.

    Returns:
        None.
    """
    for key in record:
        if key not in columns:
            columns.append(key)


def parse_sra_files(xml_text, srr):
    """Parse SRAFile and Alternatives records from SRA XML.

    Args:
        xml_text: XML text returned by NCBI.
        srr: SRA run ID.

    Returns:
        Tuple of output columns and parsed row dictionaries.
    """
    root = ET.fromstring(xml_text)
    rows = []
    columns = DEFAULT_COLUMNS.copy()

    for sra_file in root.iter("SRAFile"):
        cluster_attrs = dict(sra_file.attrib)
        # Keep Alternatives url because it is the real download URL.
        cluster_attrs.pop("url", None)

        alternatives = list(sra_file.iter("Alternatives"))
        if not alternatives:
            row = {"run": srr}
            row.update(cluster_attrs)
            append_new_keys(columns, row)
            rows.append(row)
            continue

        for alternative in alternatives:
            row = {"run": srr}
            row.update(cluster_attrs)
            row.update(dict(alternative.attrib))
            append_new_keys(columns, row)
            rows.append(row)

    logger.info("Parsed SRAFile rows: %s", len(rows))
    return columns, rows


def read_table(path):
    """Read an existing TSV result file.

    Args:
        path: Input TSV file path.

    Returns:
        Tuple of column names and row dictionaries.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [row for row in reader]
        columns = reader.fieldnames or []
    logger.info("Loaded existing result rows: %s", len(rows))
    return columns, rows


def write_table(path, columns, rows):
    """Write parsed records to a TSV file.

    Args:
        path: Output file path.
        columns: Output column name list.
        rows: Parsed row dictionaries.

    Returns:
        None.
    """
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(column, "") for column in columns])


def merge_columns(rows):
    """Merge default columns and observed row keys.

    Args:
        rows: Parsed row dictionaries.

    Returns:
        Output column name list.
    """
    columns = DEFAULT_COLUMNS.copy()
    for row in rows:
        append_new_keys(columns, row)
    return columns


def get_anonymous_download_rows(rows):
    """Filter anonymous records with downloadable URLs.

    Args:
        rows: Parsed row dictionaries.

    Returns:
        Row dictionaries whose access_type is anonymous and url is present.
    """
    download_rows = []
    for row in rows:
        access_type = row.get("access_type", "")
        url = row.get("url", "")
        if access_type == "anonymous" and url:
            download_rows.append(row)
    logger.info("Anonymous downloadable records: %s", len(download_rows))
    return download_rows


def build_s3_url(url):
    """Build an S3 URL from an S3 or S3 virtual-hosted-style HTTPS URL.

    Args:
        url: Source URL.

    Returns:
        S3 URL string, or None when the URL cannot be represented as a public S3 URL.
    """
    if url.startswith("s3://"):
        return url

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None

    suffix = ".s3.amazonaws.com"
    if parsed.netloc.endswith(suffix):
        bucket = parsed.netloc[: -len(suffix)]
        return urllib.parse.urlunparse(("s3", bucket, parsed.path, "", "", ""))

    return None


def build_download_command(tool, row):
    """Build one shell download command.

    Args:
        tool: Download tool name. Supported values are wget, axel, aria2c, and aws_s3_cp.
        row: One downloadable row dictionary.

    Returns:
        Shell command string, or None when the row does not support the selected tool.
    """
    url = row.get("url", "")
    filename = row.get("filename", "") or Path(urllib.parse.urlparse(url).path).name
    quoted_url = shlex.quote(url)
    quoted_filename = shlex.quote(filename)

    if tool == "wget":
        return f"wget -c -O {quoted_filename} {quoted_url}"
    if tool == "axel":
        return f"axel -a -n 10 -o {quoted_filename} {quoted_url}"
    if tool == "aria2c":
        return f"aria2c -c -x 8 -j 8 -s 8 -o {quoted_filename} {quoted_url}"
    if tool == "aws_s3_cp":
        s3_url = build_s3_url(url)
        if not s3_url:
            return None
        s3_filename = Path(urllib.parse.urlparse(s3_url).path).name
        quoted_s3_url = shlex.quote(s3_url)
        quoted_s3_filename = shlex.quote(s3_filename)
        return f"[[ -f ./{quoted_s3_filename} ]] || aws s3 cp --no-sign-request {quoted_s3_url} ./"
    raise ValueError(f"Unsupported download tool: {tool}")


def write_download_scripts(output_dir, prefix, download_rows):
    """Write one shell download script for each supported download tool.

    Args:
        output_dir: Output directory path.
        prefix: Output file prefix.
        download_rows: Downloadable row dictionaries.

    Returns:
        List of written script paths.
    """
    script_paths = []

    for tool in DOWNLOAD_TOOLS:
        script_path = output_dir / f"{prefix}_download_{tool}.sh"
        with script_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("#!/usr/bin/env bash\n")
            handle.write("set -euo pipefail\n\n")
            handle.write(f"# Download anonymous SRA links for {prefix}\n")
            handle.write("# Generated by run_get_bioinfor_from_NCBI_SRA.py\n\n")
            for row in download_rows:
                command = build_download_command(tool, row)
                if not command:
                    continue
                filename = row.get("filename", "")
                semantic_name = row.get("semantic_name", "")
                handle.write(f"# filename: {filename}; semantic_name: {semantic_name}\n")
                handle.write(command + "\n\n")
        script_path.chmod(0o755)
        script_paths.append(script_path)
        logger.info("Download script written: %s", script_path)

    return script_paths


def write_md5_file(output_dir, prefix, download_rows):
    """Write MD5 checksum file for downloadable records.

    Args:
        output_dir: Output directory path.
        prefix: Output file prefix.
        download_rows: Downloadable row dictionaries.

    Returns:
        Written MD5 file path.
    """
    md5_path = output_dir / f"{prefix}_download_md5.txt"

    with md5_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in download_rows:
            md5 = row.get("md5", "")
            url = row.get("url", "")
            filename = row.get("filename", "") or Path(urllib.parse.urlparse(url).path).name
            if md5 and filename:
                handle.write(f"{md5}  {filename}\n")

    logger.info("MD5 file written: %s", md5_path)
    return md5_path


def process_run(run_id, output_dir):
    """Generate information and download helper files for one SRR.

    Args:
        run_id: SRA run ID.
        output_dir: Output directory path.

    Returns:
        Parsed row dictionaries for this run.
    """
    result_file = output_dir / f"{run_id}_infor.xls"
    if result_file.exists():
        logger.info("Skip: %s", result_file)
        _columns, rows = read_table(result_file)
        download_rows = get_anonymous_download_rows(rows)
        write_download_scripts(output_dir, run_id, download_rows)
        write_md5_file(output_dir, run_id, download_rows)
        return rows

    xml_text = fetch_sra_xml(run_id)
    columns, rows = parse_sra_files(xml_text, run_id)

    if not rows:
        raise RuntimeError(f"No SRAFile records found for {run_id}")

    write_table(result_file, columns, rows)
    logger.info("Output written: %s", result_file)
    download_rows = get_anonymous_download_rows(rows)
    write_download_scripts(output_dir, run_id, download_rows)
    write_md5_file(output_dir, run_id, download_rows)
    return rows


def write_run_list(output_dir, input_id, runs):
    """Write resolved run accessions to a text file.

    Args:
        output_dir: Output directory path.
        input_id: Original input ID.
        runs: Run accession list.

    Returns:
        Written run list path.
    """
    list_path = output_dir / f"{input_id}_run_list.txt"
    with list_path.open("w", encoding="utf-8", newline="\n") as handle:
        for run_id in runs:
            handle.write(f"{run_id}\n")
    logger.info("Run list written: %s", list_path)
    return list_path


def write_project_outputs(output_dir, input_id, all_rows):
    """Write project-level information, download scripts, and MD5 file.

    Args:
        output_dir: Output directory path.
        input_id: Original project or study ID.
        all_rows: Parsed row dictionaries for all runs.

    Returns:
        None.
    """
    if not all_rows:
        raise RuntimeError(f"No run information rows found for {input_id}")

    all_info_path = output_dir / f"{input_id}_all_run_infor.xls"
    columns = merge_columns(all_rows)
    write_table(all_info_path, columns, all_rows)
    logger.info("Project information table written: %s", all_info_path)

    download_rows = get_anonymous_download_rows(all_rows)
    write_download_scripts(output_dir, input_id, download_rows)
    write_md5_file(output_dir, input_id, download_rows)


def main():
    """Run the script workflow."""
    args = parse_args()
    logger.info("Argument values: %s", args.__dict__)
    logger.info("Starting ...")

    input_id = args.input
    output_dir = Path(args.output_dir)

    try:
        check_output_dir(output_dir)
    except (FileNotFoundError, FileExistsError) as exc:
        logger.error("%s", exc)
        return 1

    try:
        runs = resolve_input_to_runs(input_id)
        is_single_run = input_id.startswith(("SRR", "ERR", "DRR"))
        if not is_single_run:
            write_run_list(output_dir, input_id, runs)

        all_rows = []
        for index, run_id in enumerate(runs, start=1):
            logger.info("Processing run %s/%s: %s", index, len(runs), run_id)
            rows = process_run(run_id, output_dir)
            all_rows.extend(rows)

        if not is_single_run:
            write_project_outputs(output_dir, input_id, all_rows)
    except Exception as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
