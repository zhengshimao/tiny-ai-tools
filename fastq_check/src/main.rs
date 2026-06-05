use clap::Parser;
use crossbeam::channel::{bounded, unbounded, Receiver, Sender};
use flate2::read::MultiGzDecoder;
use rayon::ThreadPoolBuilder;
use regex::Regex;
use serde::Serialize;
use std::fs::File;
use std::io::{self, BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::thread;
use std::time::Instant;

const HELP_INFO: &str = "Version: 0.0.1
Email: zhengshimao007@163.com
Create: 2026.06.05
Update: -
Author: Shimao Zheng
Agent: ChatGPT + me and Codex + GPT5.5

Example:
  fastq_check.exe --read1 input_R1.fq.gz --read2 input_R2.fq.gz --infer-platform --detect-quality --strict-bases --json-report report.json";

const READ_BUFFER_SIZE: usize = 1024 * 1024;

#[derive(Parser, Clone)]
#[command(
    author,
    version,
    about = "Check single-end or paired-end FASTQ/FASTQ.GZ files",
    long_about = "Check single-end or paired-end FASTQ/FASTQ.GZ files for format errors, sequence/quality length mismatches, optional base validation, optional quality encoding detection, platform inference, and paired-end read-name consistency.",
    after_help = HELP_INFO
)]
struct Args {
    /// Read 1 FASTQ/FASTQ.GZ file. For single-end data, provide only this option.
    #[arg(short = '1', long = "read1")]
    read1: String,

    /// Read 2 FASTQ/FASTQ.GZ file. Provide this option for paired-end data.
    #[arg(short = '2', long = "read2")]
    read2: Option<String>,

    /// Worker threads. Use 0 to let Rayon choose.
    #[arg(long, default_value_t = 0)]
    threads: usize,

    /// FASTQ records per batch sent to workers.
    #[arg(long = "batch-size", default_value_t = 8192)]
    batch_size: usize,

    /// Use external pigz to decompress .gz FASTQ files.
    #[arg(long = "pigz")]
    pigz: bool,

    /// Threads passed to pigz when --pigz is enabled.
    #[arg(long = "pigz-threads", default_value_t = 8)]
    pigz_threads: usize,

    /// Path to pigz executable when --pigz is enabled.
    #[arg(long = "pigz-path", default_value = "pigz")]
    pigz_path: String,

    /// Require sequence bases to be uppercase A/C/G/T/N only.
    #[arg(long = "strict-bases")]
    strict_bases: bool,

    /// Report quality encoding from observed ASCII range.
    #[arg(long = "detect-quality", alias = "check-phred")]
    check_phred: bool,

    /// Infer sequencing platform from FASTQ header patterns.
    #[arg(long = "infer-platform")]
    infer_platform: bool,

    /// Number of reads sampled per file when inferring sequencing platform.
    #[arg(long = "platform-sample-size", default_value_t = 10000)]
    platform_sample_size: u64,

    /// Write a machine-readable JSON summary to this file.
    #[arg(long = "json-report")]
    json_report: Option<String>,
}

#[derive(Serialize)]
struct Report {
    read1: FileStats,
    read2: Option<FileStats>,
    paired: Option<PairedStats>,
    total_reads: u64,
    total_bases: u64,
    errors: u64,
    elapsed_seconds: f64,
}

#[derive(Default, Serialize, Clone)]
struct FileStats {
    path: String,
    total_reads: u64,
    total_bases: u64,
    min_read_len: Option<usize>,
    max_read_len: Option<usize>,
    min_qual_ascii: Option<u8>,
    max_qual_ascii: Option<u8>,
    phred_detected: Option<String>,
    platform_inferred: Option<String>,
    platform_confidence: Option<f64>,
    platform_reads_sampled: Option<u64>,
    #[serde(skip)]
    platform_counts: PlatformCounts,
    errors: u64,
}

#[derive(Default, Serialize, Clone)]
struct PairedStats {
    pairs_checked: u64,
    name_mismatches: u64,
    unpaired_reads: u64,
    errors: u64,
}

#[derive(Default, Clone)]
struct PlatformCounts {
    sampled: u64,
    illumina: u64,
    bgi_mgi: u64,
    pacbio: u64,
    oxford_nanopore: u64,
}

#[derive(Default)]
struct FileLocalStats {
    total_reads: u64,
    total_bases: u64,
    min_read_len: Option<usize>,
    max_read_len: Option<usize>,
    min_qual_ascii: Option<u8>,
    max_qual_ascii: Option<u8>,
    platform_counts: PlatformCounts,
    errors: u64,
}

#[derive(Default)]
struct PairLocalStats {
    read1: FileLocalStats,
    read2: FileLocalStats,
    paired: PairedStats,
}

struct Record {
    index: u64,
    line: u64,
    header: Vec<u8>,
    seq: Vec<u8>,
    plus: Vec<u8>,
    qual: Vec<u8>,
}

type Batch = Vec<Record>;
type PairBatch = Vec<(Option<Record>, Option<Record>)>;

struct FastqReader {
    path: String,
    reader: Box<dyn BufRead + Send>,
    child: Option<Child>,
    next_line: u64,
    records: u64,
    errors: u64,
}

enum ReadStatus {
    Record(Record),
    End,
    Error,
}

fn main() -> io::Result<()> {
    let started_at = Instant::now();
    let args = Arc::new(Args::parse());
    if args.batch_size == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "--batch-size must be greater than 0",
        ));
    }
    if args.pigz && args.pigz_threads == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "--pigz-threads must be greater than 0",
        ));
    }

    let pool = build_thread_pool(args.threads)?;
    let platform_re = Arc::new(PlatformRegexes::new(args.infer_platform));

    let mut report = pool.install(|| {
        if let Some(read2) = args.read2.as_deref() {
            check_pair(&args.read1, read2, args.clone(), platform_re.clone())
        } else {
            let stats = check_single(&args.read1, args.clone(), platform_re.clone())?;
            Ok(make_report(vec![stats], None))
        }
    })?;
    report.elapsed_seconds = round_seconds(started_at.elapsed().as_secs_f64());

    println!("Total reads: {}", report.total_reads);
    println!("Total bases: {}", report.total_bases);
    println!("Errors: {}", report.errors);
    println!("Elapsed seconds: {:.3}", report.elapsed_seconds);

    print_file_summary(&report.read1);
    if let Some(read2) = &report.read2 {
        print_file_summary(read2);
    }

    if let Some(path) = &args.json_report {
        let json = serde_json::to_string_pretty(&report).expect("report serialization failed");
        std::fs::write(path, json)?;
    }

    if report.errors > 0 {
        std::process::exit(1);
    }

    Ok(())
}

fn build_thread_pool(threads: usize) -> io::Result<rayon::ThreadPool> {
    let mut builder = ThreadPoolBuilder::new();
    if threads > 0 {
        builder = builder.num_threads(threads);
    }
    builder
        .build()
        .map_err(|err| io::Error::new(io::ErrorKind::Other, err.to_string()))
}

fn print_file_summary(file: &FileStats) {
    println!(
        "{}: reads={}, bases={}, errors={}",
        file.path, file.total_reads, file.total_bases, file.errors
    );
    if let Some(phred) = &file.phred_detected {
        println!("{}: quality={}", file.path, phred);
    }
    if let Some(platform) = &file.platform_inferred {
        let confidence = file.platform_confidence.unwrap_or(0.0);
        let sampled = file.platform_reads_sampled.unwrap_or(0);
        println!(
            "{}: platform={} confidence={:.3} sampled_reads={}",
            file.path, platform, confidence, sampled
        );
    }
}

fn check_single(
    path: &str,
    args: Arc<Args>,
    platform_re: Arc<Option<PlatformRegexes>>,
) -> io::Result<FileStats> {
    let (batch_tx, batch_rx) = bounded::<Batch>(args.threads.max(1) * 2);
    let (stats_tx, stats_rx) = unbounded::<FileLocalStats>();
    let producer_args = args.clone();
    let producer_path = path.to_string();

    let producer =
        thread::spawn(move || produce_single_batches(&producer_path, producer_args, batch_tx));

    rayon::scope(|scope| {
        let worker_count = rayon::current_num_threads();
        for _ in 0..worker_count {
            let rx = batch_rx.clone();
            let tx = stats_tx.clone();
            let args = args.clone();
            let platform_re = platform_re.clone();
            scope.spawn(move |_| {
                let local = consume_single_batches(rx, &args, platform_re.as_ref().as_ref());
                let _ = tx.send(local);
            });
        }
        drop(stats_tx);
    });

    let reader_errors = join_reader(producer)?;
    let mut local = FileLocalStats::default();
    for worker_stats in stats_rx {
        local.merge(worker_stats);
    }
    local.errors += reader_errors;

    let mut stats = local.into_file_stats(path.to_string());
    finish_file_stats(&mut stats, args.check_phred);
    finish_platform_stats(&mut stats, args.infer_platform);
    Ok(stats)
}

fn check_pair(
    read1: &str,
    read2: &str,
    args: Arc<Args>,
    platform_re: Arc<Option<PlatformRegexes>>,
) -> io::Result<Report> {
    let (batch_tx, batch_rx) = bounded::<PairBatch>(args.threads.max(1) * 2);
    let (stats_tx, stats_rx) = unbounded::<PairLocalStats>();
    let producer_args = args.clone();
    let left_path = read1.to_string();
    let right_path = read2.to_string();

    let producer = thread::spawn(move || {
        produce_pair_batches(&left_path, &right_path, producer_args, batch_tx)
    });

    rayon::scope(|scope| {
        let worker_count = rayon::current_num_threads();
        for _ in 0..worker_count {
            let rx = batch_rx.clone();
            let tx = stats_tx.clone();
            let args = args.clone();
            let platform_re = platform_re.clone();
            scope.spawn(move |_| {
                let local = consume_pair_batches(rx, &args, platform_re.as_ref().as_ref());
                let _ = tx.send(local);
            });
        }
        drop(stats_tx);
    });

    let (left_reader_errors, right_reader_errors) = join_pair_reader(producer)?;
    let mut local = PairLocalStats::default();
    for worker_stats in stats_rx {
        local.merge(worker_stats);
    }

    local.read1.errors += left_reader_errors;
    local.read2.errors += right_reader_errors;
    local.paired.errors = local.paired.name_mismatches + local.paired.unpaired_reads;

    let mut left_stats = local.read1.into_file_stats(read1.to_string());
    let mut right_stats = local.read2.into_file_stats(read2.to_string());
    finish_file_stats(&mut left_stats, args.check_phred);
    finish_file_stats(&mut right_stats, args.check_phred);
    finish_platform_stats(&mut left_stats, args.infer_platform);
    finish_platform_stats(&mut right_stats, args.infer_platform);

    Ok(make_report(
        vec![left_stats, right_stats],
        Some(local.paired),
    ))
}

fn produce_single_batches(path: &str, args: Arc<Args>, tx: Sender<Batch>) -> io::Result<u64> {
    let mut reader = FastqReader::open(path, &args)?;
    let mut batch = Vec::with_capacity(args.batch_size);

    loop {
        match reader.next_record() {
            Ok(ReadStatus::Record(record)) => {
                batch.push(record);
                if batch.len() == args.batch_size {
                    let full_batch = std::mem::take(&mut batch);
                    if tx.send(full_batch).is_err() {
                        break;
                    }
                    batch = Vec::with_capacity(args.batch_size);
                }
            }
            Ok(ReadStatus::End) => break,
            Ok(ReadStatus::Error) => break,
            Err(err) => {
                reader.errors += 1;
                eprintln!(
                    "{}\tline {}\tread error: {}",
                    reader.path,
                    reader.current_line(),
                    err
                );
                break;
            }
        }
    }

    if !batch.is_empty() {
        let _ = tx.send(batch);
    }
    Ok(reader.errors)
}

fn produce_pair_batches(
    read1: &str,
    read2: &str,
    args: Arc<Args>,
    tx: Sender<PairBatch>,
) -> io::Result<(u64, u64)> {
    let mut left = FastqReader::open(read1, &args)?;
    let mut right = FastqReader::open(read2, &args)?;
    let mut batch = Vec::with_capacity(args.batch_size);

    loop {
        let l = read_next_or_log(&mut left);
        let r = read_next_or_log(&mut right);

        match (l, r) {
            (ReadStatus::End, ReadStatus::End) => break,
            (ReadStatus::Error, ReadStatus::End) | (ReadStatus::End, ReadStatus::Error) => break,
            (ReadStatus::Error, _) => {
                drain_pair_side(&mut right, false, &mut batch, args.batch_size, &tx)?;
                break;
            }
            (_, ReadStatus::Error) => {
                drain_pair_side(&mut left, true, &mut batch, args.batch_size, &tx)?;
                break;
            }
            (left_status, right_status) => {
                batch.push((
                    status_to_record(left_status),
                    status_to_record(right_status),
                ));
                if batch.len() == args.batch_size {
                    let full_batch = std::mem::take(&mut batch);
                    if tx.send(full_batch).is_err() {
                        break;
                    }
                    batch = Vec::with_capacity(args.batch_size);
                }
            }
        }
    }

    if !batch.is_empty() {
        let _ = tx.send(batch);
    }
    Ok((left.errors, right.errors))
}

fn drain_pair_side(
    reader: &mut FastqReader,
    is_left: bool,
    batch: &mut PairBatch,
    batch_size: usize,
    tx: &Sender<PairBatch>,
) -> io::Result<()> {
    loop {
        match read_next_or_log(reader) {
            ReadStatus::Record(record) => {
                if is_left {
                    batch.push((Some(record), None));
                } else {
                    batch.push((None, Some(record)));
                }
                if batch.len() == batch_size {
                    let mut next = Vec::with_capacity(batch_size);
                    std::mem::swap(batch, &mut next);
                    if tx.send(next).is_err() {
                        break;
                    }
                }
            }
            ReadStatus::End | ReadStatus::Error => break,
        }
    }
    Ok(())
}

fn read_next_or_log(reader: &mut FastqReader) -> ReadStatus {
    match reader.next_record() {
        Ok(status) => status,
        Err(err) => {
            reader.errors += 1;
            eprintln!(
                "{}\tline {}\tread error: {}",
                reader.path,
                reader.current_line(),
                err
            );
            ReadStatus::Error
        }
    }
}

fn status_to_record(status: ReadStatus) -> Option<Record> {
    match status {
        ReadStatus::Record(record) => Some(record),
        ReadStatus::End | ReadStatus::Error => None,
    }
}

fn consume_single_batches(
    rx: Receiver<Batch>,
    args: &Args,
    platform_re: Option<&PlatformRegexes>,
) -> FileLocalStats {
    let mut local = FileLocalStats::default();
    for batch in rx {
        for record in batch {
            validate_record(&record, &mut local, args, platform_re);
        }
    }
    local
}

fn consume_pair_batches(
    rx: Receiver<PairBatch>,
    args: &Args,
    platform_re: Option<&PlatformRegexes>,
) -> PairLocalStats {
    let mut local = PairLocalStats::default();
    for batch in rx {
        for (left, right) in batch {
            match (left, right) {
                (Some(l), Some(r)) => {
                    validate_record(&l, &mut local.read1, args, platform_re);
                    validate_record(&r, &mut local.read2, args, platform_re);
                    local.paired.pairs_checked += 1;

                    if normalized_read_id_bytes(&l.header) != normalized_read_id_bytes(&r.header) {
                        local.paired.name_mismatches += 1;
                        eprintln!(
                            "PAIR\trecord {}\tread names differ: '{}' vs '{}'",
                            local.paired.pairs_checked,
                            String::from_utf8_lossy(&l.header),
                            String::from_utf8_lossy(&r.header)
                        );
                    }
                }
                (Some(l), None) => {
                    validate_record(&l, &mut local.read1, args, platform_re);
                    local.paired.unpaired_reads += 1;
                    eprintln!(
                        "PAIR\trecord {}\tread1 has extra records after read2 ended",
                        l.index
                    );
                }
                (None, Some(r)) => {
                    validate_record(&r, &mut local.read2, args, platform_re);
                    local.paired.unpaired_reads += 1;
                    eprintln!(
                        "PAIR\trecord {}\tread2 has extra records after read1 ended",
                        r.index
                    );
                }
                (None, None) => {}
            }
        }
    }
    local.paired.errors = local.paired.name_mismatches + local.paired.unpaired_reads;
    local
}

fn validate_record(
    rec: &Record,
    stats: &mut FileLocalStats,
    args: &Args,
    platform_re: Option<&PlatformRegexes>,
) {
    let header = rec.header.as_slice();
    let seq = rec.seq.as_slice();
    let plus = rec.plus.as_slice();
    let qual = rec.qual.as_slice();

    stats.total_reads += 1;
    stats.total_bases += seq.len() as u64;
    stats.min_read_len = Some(stats.min_read_len.map_or(seq.len(), |v| v.min(seq.len())));
    stats.max_read_len = Some(stats.max_read_len.map_or(seq.len(), |v| v.max(seq.len())));

    if !header.starts_with(b"@") {
        stats.errors += 1;
        eprintln!(
            "record {}\tline {}\theader must start with '@': {}",
            rec.index,
            rec.line,
            String::from_utf8_lossy(header)
        );
    }
    if seq.is_empty() {
        stats.errors += 1;
        eprintln!("record {}\tline {}\tsequence is empty", rec.index, rec.line);
    }
    if !plus.starts_with(b"+") {
        stats.errors += 1;
        eprintln!(
            "record {}\tline {}\tplus line must start with '+': {}",
            rec.index,
            rec.line,
            String::from_utf8_lossy(plus)
        );
    }
    if seq.len() != qual.len() {
        stats.errors += 1;
        eprintln!(
            "record {}\tline {}\tsequence/quality length mismatch: {} vs {}",
            rec.index,
            rec.line,
            seq.len(),
            qual.len()
        );
    }
    if args.strict_bases && !seq.iter().all(|&base| is_strict_base(base)) {
        stats.errors += 1;
        eprintln!(
            "record {}\tline {}\tsequence contains bases outside A/C/G/T/N",
            rec.index, rec.line
        );
    }

    update_platform_counts(header, stats, args, platform_re);

    if args.check_phred {
        for &b in qual {
            if !(33..=126).contains(&b) {
                stats.errors += 1;
                eprintln!(
                    "record {}\tline {}\tquality contains non-printable ASCII byte {}",
                    rec.index, rec.line, b
                );
            }
            stats.min_qual_ascii = Some(stats.min_qual_ascii.map_or(b, |v| v.min(b)));
            stats.max_qual_ascii = Some(stats.max_qual_ascii.map_or(b, |v| v.max(b)));
        }
    }
}

fn finish_file_stats(stats: &mut FileStats, check_phred: bool) {
    if check_phred {
        stats.phred_detected = Some(match (stats.min_qual_ascii, stats.max_qual_ascii) {
            (Some(min), Some(max)) => detect_phred(min, max),
            _ => "No qualities observed".to_string(),
        });
    }
}

fn finish_platform_stats(stats: &mut FileStats, enabled: bool) {
    if !enabled {
        return;
    }

    let counts = &stats.platform_counts;
    stats.platform_reads_sampled = Some(counts.sampled);

    if counts.sampled == 0 {
        stats.platform_inferred = Some("Unknown".to_string());
        stats.platform_confidence = Some(0.0);
        return;
    }

    let candidates = [
        ("Illumina", counts.illumina),
        ("BGI/MGI", counts.bgi_mgi),
        ("PacBio", counts.pacbio),
        ("Oxford Nanopore", counts.oxford_nanopore),
    ];
    let (platform, hits) = candidates
        .into_iter()
        .max_by_key(|(_, hits)| *hits)
        .expect("platform candidate list must not be empty");
    let confidence = hits as f64 / counts.sampled as f64;

    if confidence >= 0.8 {
        stats.platform_inferred = Some(platform.to_string());
    } else {
        stats.platform_inferred = Some("Unknown".to_string());
    }
    stats.platform_confidence = Some(round_confidence(confidence));
}

fn make_report(files: Vec<FileStats>, paired: Option<PairedStats>) -> Report {
    let total_reads = files.iter().map(|s| s.total_reads).sum();
    let total_bases = files.iter().map(|s| s.total_bases).sum();
    let file_errors: u64 = files.iter().map(|s| s.errors).sum();
    let pair_errors = paired.as_ref().map_or(0, |s| s.errors);
    let read1 = files
        .first()
        .expect("report must contain read1 stats")
        .clone();
    let read2 = files.get(1).cloned();

    Report {
        read1,
        read2,
        paired,
        total_reads,
        total_bases,
        errors: file_errors + pair_errors,
        elapsed_seconds: 0.0,
    }
}

impl FileLocalStats {
    fn merge(&mut self, other: Self) {
        self.total_reads += other.total_reads;
        self.total_bases += other.total_bases;
        self.min_read_len = merge_min(self.min_read_len, other.min_read_len);
        self.max_read_len = merge_max(self.max_read_len, other.max_read_len);
        self.min_qual_ascii = merge_min(self.min_qual_ascii, other.min_qual_ascii);
        self.max_qual_ascii = merge_max(self.max_qual_ascii, other.max_qual_ascii);
        self.platform_counts.merge(other.platform_counts);
        self.errors += other.errors;
    }

    fn into_file_stats(self, path: String) -> FileStats {
        FileStats {
            path,
            total_reads: self.total_reads,
            total_bases: self.total_bases,
            min_read_len: self.min_read_len,
            max_read_len: self.max_read_len,
            min_qual_ascii: self.min_qual_ascii,
            max_qual_ascii: self.max_qual_ascii,
            platform_counts: self.platform_counts,
            errors: self.errors,
            ..Default::default()
        }
    }
}

impl PairLocalStats {
    fn merge(&mut self, other: Self) {
        self.read1.merge(other.read1);
        self.read2.merge(other.read2);
        self.paired.pairs_checked += other.paired.pairs_checked;
        self.paired.name_mismatches += other.paired.name_mismatches;
        self.paired.unpaired_reads += other.paired.unpaired_reads;
        self.paired.errors += other.paired.errors;
    }
}

impl PlatformCounts {
    fn merge(&mut self, other: Self) {
        self.sampled += other.sampled;
        self.illumina += other.illumina;
        self.bgi_mgi += other.bgi_mgi;
        self.pacbio += other.pacbio;
        self.oxford_nanopore += other.oxford_nanopore;
    }
}

impl FastqReader {
    fn open(path: &str, args: &Args) -> io::Result<Self> {
        let input = open_fastq(path, args)?;
        Ok(Self {
            path: path.to_string(),
            reader: input.reader,
            child: input.child,
            next_line: 1,
            records: 0,
            errors: 0,
        })
    }

    fn next_record(&mut self) -> io::Result<ReadStatus> {
        let header = match self.read_line()? {
            Some(line) => line,
            None => return Ok(ReadStatus::End),
        };
        let record_line = self.next_line - 1;

        let seq = match self.read_line()? {
            Some(line) => line,
            None => return Ok(self.log_truncated(record_line, "sequence")),
        };
        let plus = match self.read_line()? {
            Some(line) => line,
            None => return Ok(self.log_truncated(record_line, "plus")),
        };
        let qual = match self.read_line()? {
            Some(line) => line,
            None => return Ok(self.log_truncated(record_line, "quality")),
        };

        self.records += 1;
        Ok(ReadStatus::Record(Record {
            index: self.records,
            line: record_line,
            header,
            seq,
            plus,
            qual,
        }))
    }

    fn read_line(&mut self) -> io::Result<Option<Vec<u8>>> {
        let mut line = Vec::with_capacity(256);
        let n = self.reader.read_until(b'\n', &mut line).map_err(|err| {
            io::Error::new(
                err.kind(),
                format!(
                    "{}: failed to read near line {}: {}",
                    self.path, self.next_line, err
                ),
            )
        })?;
        if n == 0 {
            return Ok(None);
        }
        trim_newline(&mut line);
        self.next_line += 1;
        Ok(Some(line))
    }

    fn current_line(&self) -> u64 {
        self.next_line.saturating_sub(1)
    }

    fn log_truncated(&mut self, record_line: u64, missing: &str) -> ReadStatus {
        self.errors += 1;
        eprintln!(
            "{}\trecord starting line {}\ttruncated FASTQ: missing {} line",
            self.path, record_line, missing
        );
        ReadStatus::Error
    }
}

impl Drop for FastqReader {
    fn drop(&mut self) {
        if let Some(child) = self.child.as_mut() {
            let _ = child.wait();
        }
    }
}

struct PlatformRegexes {
    illumina: Regex,
    bgi_mgi: Regex,
    pacbio: Regex,
    oxford_nanopore: Regex,
}

impl PlatformRegexes {
    fn new(enabled: bool) -> Option<Self> {
        enabled.then(|| Self {
            illumina: Regex::new(
                r"^@[^:\s]+:\d+:[^:\s]+:\d+:\d+:\d+:\d+(?:\s+[12]:[YN]:\d+:[A-Za-z0-9+_-]+)?$",
            )
            .expect("Illumina platform regex must compile"),
            bgi_mgi: Regex::new(
                r"^@(?:V\d+|CL\d+|E\d+|MGI|DNBSEQ|BGI)[A-Za-z0-9_-]*(?:[/:#\s].*)?$",
            )
            .expect("BGI/MGI platform regex must compile"),
            pacbio: Regex::new(r"^@[^/\s]+/\d+/\d+_\d+(?:\s.*)?$")
                .expect("PacBio platform regex must compile"),
            oxford_nanopore: Regex::new(
                r"^@[A-Za-z0-9-]+(?:\s+\S+=\S+)*\s+runid=[0-9a-fA-F-]+(?:\s+\S+=\S+)*\s+ch=\d+(?:\s+\S+=\S+)*\s+start_time=\S+",
            )
            .expect("Oxford Nanopore platform regex must compile"),
        })
    }
}

fn update_platform_counts(
    header: &[u8],
    stats: &mut FileLocalStats,
    args: &Args,
    platform_re: Option<&PlatformRegexes>,
) {
    let Some(re) = platform_re else {
        return;
    };
    if stats.platform_counts.sampled >= args.platform_sample_size {
        return;
    }

    let Ok(header_text) = std::str::from_utf8(header) else {
        stats.platform_counts.sampled += 1;
        return;
    };

    stats.platform_counts.sampled += 1;
    if re.illumina.is_match(header_text) {
        stats.platform_counts.illumina += 1;
    }
    if re.bgi_mgi.is_match(header_text) {
        stats.platform_counts.bgi_mgi += 1;
    }
    if re.pacbio.is_match(header_text) {
        stats.platform_counts.pacbio += 1;
    }
    if re.oxford_nanopore.is_match(header_text) {
        stats.platform_counts.oxford_nanopore += 1;
    }
}

fn join_reader(handle: thread::JoinHandle<io::Result<u64>>) -> io::Result<u64> {
    handle
        .join()
        .map_err(|_| io::Error::new(io::ErrorKind::Other, "reader thread panicked"))?
}

fn join_pair_reader(handle: thread::JoinHandle<io::Result<(u64, u64)>>) -> io::Result<(u64, u64)> {
    handle
        .join()
        .map_err(|_| io::Error::new(io::ErrorKind::Other, "reader thread panicked"))?
}

fn merge_min<T: Ord + Copy>(left: Option<T>, right: Option<T>) -> Option<T> {
    match (left, right) {
        (Some(a), Some(b)) => Some(a.min(b)),
        (Some(a), None) => Some(a),
        (None, Some(b)) => Some(b),
        (None, None) => None,
    }
}

fn merge_max<T: Ord + Copy>(left: Option<T>, right: Option<T>) -> Option<T> {
    match (left, right) {
        (Some(a), Some(b)) => Some(a.max(b)),
        (Some(a), None) => Some(a),
        (None, Some(b)) => Some(b),
        (None, None) => None,
    }
}

fn trim_newline(line: &mut Vec<u8>) {
    if line.ends_with(b"\n") {
        line.pop();
        if line.ends_with(b"\r") {
            line.pop();
        }
    }
}

fn round_confidence(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

fn round_seconds(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

fn is_strict_base(base: u8) -> bool {
    matches!(base, b'A' | b'C' | b'G' | b'T' | b'N')
}

fn normalized_read_id_bytes(header: &[u8]) -> &[u8] {
    let header = header.strip_prefix(b"@").unwrap_or(header);
    let first_field_end = header
        .iter()
        .position(|&b| b == b' ' || b == b'\t')
        .unwrap_or(header.len());
    let first = &header[..first_field_end];
    if first.ends_with(b"/1") || first.ends_with(b"/2") {
        &first[..first.len() - 2]
    } else {
        first
    }
}

fn detect_phred(min: u8, max: u8) -> String {
    if min >= 33 && max <= 74 {
        "Phred33".into()
    } else if min >= 64 && max <= 104 {
        "Phred64".into()
    } else {
        format!("Unknown (ASCII {}-{})", min, max)
    }
}

struct OpenedFastq {
    reader: Box<dyn BufRead + Send>,
    child: Option<Child>,
}

fn open_fastq<P: AsRef<Path>>(path: P, args: &Args) -> io::Result<OpenedFastq> {
    if args.pigz && is_gzip_path(path.as_ref()) {
        return open_fastq_with_pigz(path.as_ref(), args);
    }

    let file = File::open(&path)?;
    let reader: Box<dyn BufRead + Send> = if is_gzip_path(path.as_ref()) {
        let decoder = MultiGzDecoder::new(file);
        Box::new(BufReader::with_capacity(READ_BUFFER_SIZE, decoder))
    } else {
        Box::new(BufReader::with_capacity(READ_BUFFER_SIZE, file))
    };

    Ok(OpenedFastq {
        reader,
        child: None,
    })
}

fn open_fastq_with_pigz(path: &Path, args: &Args) -> io::Result<OpenedFastq> {
    println!(
        "Using pigz: path={}, threads={}, input={}",
        args.pigz_path,
        args.pigz_threads,
        path.display()
    );

    let mut child = Command::new(&args.pigz_path)
        .arg("-dc")
        .arg("-p")
        .arg(args.pigz_threads.to_string())
        .arg(path)
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .map_err(|err| {
            io::Error::new(
                err.kind(),
                format!(
                    "failed to start '{}' for '{}': {}. Install pigz, pass --pigz-path, or run without --pigz",
                    args.pigz_path,
                    path.display(),
                    err
                ),
            )
        })?;

    let stdout = child.stdout.take().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::Other,
            format!("failed to capture pigz stdout for '{}'", path.display()),
        )
    })?;

    Ok(OpenedFastq {
        reader: Box::new(BufReader::with_capacity(READ_BUFFER_SIZE, stdout)),
        child: Some(child),
    })
}

fn is_gzip_path(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map_or(false, |e| e.eq_ignore_ascii_case("gz"))
}

#[allow(dead_code)]
fn windows_to_wsl_path(path: &Path) -> String {
    let path = PathBuf::from(path);
    let text = path.to_string_lossy().replace('\\', "/");
    if text.len() >= 3 && text.as_bytes()[1] == b':' {
        let drive = text.as_bytes()[0] as char;
        format!("/mnt/{}/{}", drive.to_ascii_lowercase(), &text[3..])
    } else {
        text
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_phred_ranges() {
        assert_eq!(detect_phred(33, 74), "Phred33");
        assert_eq!(detect_phred(64, 104), "Phred64");
        assert_eq!(detect_phred(10, 120), "Unknown (ASCII 10-120)");
    }

    #[test]
    fn normalizes_common_pair_suffixes() {
        assert_eq!(normalized_read_id_bytes(b"@READ001/1 extra"), b"READ001");
        assert_eq!(normalized_read_id_bytes(b"@READ001/2 extra"), b"READ001");
        assert_eq!(
            normalized_read_id_bytes(b"@A00123:1:H7:1:1101:1000:1000 1:N:0:ACGT"),
            b"A00123:1:H7:1:1101:1000:1000"
        );
    }

    #[test]
    fn recognizes_gzip_extension_case_insensitively() {
        assert!(is_gzip_path(Path::new("sample.fastq.gz")));
        assert!(is_gzip_path(Path::new("sample.FQ.GZ")));
        assert!(!is_gzip_path(Path::new("sample.fastq")));
    }

    #[test]
    fn validates_strict_bases() {
        for base in b"ACGTN" {
            assert!(is_strict_base(*base));
        }
        assert!(!is_strict_base(b'a'));
        assert!(!is_strict_base(b'R'));
    }
}
