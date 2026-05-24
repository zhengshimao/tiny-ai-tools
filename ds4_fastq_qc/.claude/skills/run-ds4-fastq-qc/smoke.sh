#!/bin/bash
# smoke.sh — fastq_qc driver script
# Runs in WSL. Call from repo root, e.g.:
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh
#
# Also callable individually with target names:
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh build
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh se
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh pe
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh json
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh tsv
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh stdin
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh gzip
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh percent
#   wsl bash .claude/skills/run-ds4-fastq-qc/smoke.sh all

set -euo pipefail
BIN="./fastq_qc"
EX="exmaple"
TMPDIR="${TMPDIR:-/tmp}"

red()   { echo -e "\033[31mFAIL\033[0m $*"; exit 1; }
green() { echo -e "\033[32mPASS\033[0m $*"; }

need_binary() {
  if [ ! -x "$BIN" ]; then
    echo "Building fastq_qc..."
    make clean >/dev/null 2>&1
    make
  fi
}

test_build() {
  echo "=== Build ==="
  make clean >/dev/null 2>&1
  make
  [ -x "$BIN" ] || red "binary not created"
  green "Binary built successfully"
}

test_se() {
  echo "=== Single-end ==="
  out=$("$BIN" -i "$EX/test_single.fastq" 2>&1) || red "SE exit code $?"
  echo "$out" | grep -q "Total reads:.*5" || red "SE: missing Total reads"
  echo "$out" | grep -q "GC bases:.*50" || red "SE: missing GC bases"
  echo "$out" | grep -q "Duplication rate" || red "SE: missing Duplication"
  green "Single-end summary correct"
}

test_pe() {
  echo "=== Paired-end ==="
  out=$("$BIN" -i "$EX/test_paired_R1.fastq" -I "$EX/test_paired_R2.fastq" 2>&1) || red "PE exit code $?"
  echo "$out" | grep -q "Read 1" || red "PE: missing Read 1 section"
  echo "$out" | grep -q "Read 2" || red "PE: missing Read 2 section"
  echo "$out" | grep -q "Combined" || red "PE: missing Combined section"
  echo "$out" | grep -q "Insert Size" || red "PE: missing Insert Size"
  green "Paired-end summary correct"
}

test_json() {
  echo "=== JSON output ==="
  jf="$TMPDIR/fastq_qc_smoke_test.json"
  "$BIN" -i "$EX/test_single.fastq" -o "$jf" >/dev/null 2>&1 || red "JSON exit code $?"
  [ -f "$jf" ] || red "JSON file not created"
  python3 -c "import json; json.load(open('$jf'))" 2>/dev/null || red "JSON parse failed"
  python3 -c "
import json
d = json.load(open('$jf'))
assert d['read1']['total_reads'] == 5
assert d['read1']['total_bases'] == 100
assert 'quality_curves' in d['read1']
assert 'content_curves' in d['read1']
assert 'quality_histogram' in d['read1']
assert d['duplication']['rate'] == 0.8
" 2>/dev/null || red "JSON content mismatch"
  rm -f "$jf"
  green "JSON output correct"
}

test_tsv() {
  echo "=== TSV output ==="
  prefix="$TMPDIR/fastq_qc_smoke"
  "$BIN" -i "$EX/test_single.fastq" -p "$prefix" -s SMOKE >/dev/null 2>&1 || red "TSV exit code $?"
  [ -f "${prefix}_summary.tsv" ] || red "TSV summary not created"
  [ -f "${prefix}_R1_cycles.tsv" ] || red "TSV cycles not created"
  head -1 "${prefix}_summary.tsv" | grep -q "sample" || red "TSV: missing header"
  grep -q "SMOKE" "${prefix}_summary.tsv" || red "TSV: missing sample ID"
  rm -f "${prefix}_summary.tsv" "${prefix}_R1_cycles.tsv"
  green "TSV output correct"
}

test_stdin() {
  echo "=== Stdin ==="
  out=$(cat "$EX/test_single.fastq" | "$BIN" -i - 2>&1) || red "stdin exit code $?"
  echo "$out" | grep -q "Total reads:.*5" || red "stdin: missing Total reads"
  green "Stdin input works"
}

test_gzip() {
  echo "=== Gzip ==="
  out=$("$BIN" -i "$EX/healthy12.clean.R1.fq.gz" -I "$EX/healthy12.clean.R2.fq.gz" 2>&1) || red "gzip exit code $?"
  echo "$out" | grep -q "Total reads:.*61,329" || red "gzip: missing Total reads"
  echo "$out" | grep -q "Insert Size" || red "gzip: missing Insert Size"
  green "Gzip paired-end correct"
}

test_percent() {
  echo "=== Percent mode ==="
  out=$("$BIN" -i "$EX/test_single.fastq" -percent -d 2 2>&1) || red "percent exit code $?"
  echo "$out" | grep -q "%" || red "percent: missing % sign"
  echo "$out" | grep -q "80.00 %" || red "percent: missing expected percentage"
  green "Percent mode correct"
}

test_all() {
  need_binary
  test_se
  test_pe
  test_json
  test_tsv
  test_stdin
  test_gzip
  test_percent
  echo ""
  echo "All tests passed."
}

# Run named target(s), or all by default.
if [ $# -eq 0 ]; then
  test_all
else
  need_binary
  for t in "$@"; do
    case "$t" in
      build)   test_build ;;
      se)      test_se ;;
      pe)      test_pe ;;
      json)    test_json ;;
      tsv)     test_tsv ;;
      stdin)   test_stdin ;;
      gzip)    test_gzip ;;
      percent) test_percent ;;
      all)     test_all ;;
      *)       echo "Unknown target: $t"; echo "Targets: build se pe json tsv stdin gzip percent all"; exit 1 ;;
    esac
  done
fi
