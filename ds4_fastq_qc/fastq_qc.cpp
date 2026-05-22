/*
 * fastq_qc - A lightweight FASTQ quality control tool
 *
 * Core QC algorithms extracted and adapted from fastp
 * (https://github.com/OpenGene/fastp)
 *
 * Computes per-cycle quality metrics, base composition, GC content,
 * Q20/Q30/Q40 statistics, and quality score distributions.
 *
 * Supports single-end and paired-end FASTQ files.
 * Handles both plain-text and gzip-compressed FASTQ automatically.
 *
 * Build: g++ -O3 -o fastq_qc fastq_qc.cpp -lz
 * Usage: fastq_qc -i read1.fastq [-I read2.fastq] [-o report.json]
 */

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <ctime>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <iomanip>
#include <unordered_set>
#include <zlib.h>
#include <sys/stat.h>

using namespace std;

// ============================================================
// Fastp uses the last 3 bits of ASCII to encode nucleotides:
//   'A' % 8 = 1, 'T' % 8 = 4, 'C' % 8 = 3, 'G' % 8 = 7, 'N' % 8 = 6
// ============================================================
static inline int base2idx(char base) {
    return base & 0x07;
}

// ============================================================
// Constants
// ============================================================
static const int QUAL_HIST_SIZE = 128;
static const int CYCLE_ARRS = 34;   // 8+8+8+8+1+1 arrays
static const char Q20_CHAR = '5';   // ASCII 53 = Q20
static const char Q30_CHAR = '?';   // ASCII 63 = Q30
static const int MIN_OVERLAP   = 30;    // minimum overlap for insert size

// reverse complement a DNA sequence
static string reverse_complement(const string& seq) {
    string rc(seq.size(), 'N');
    for (size_t i = 0; i < seq.size(); i++) {
        char c;
        switch (seq[seq.size() - 1 - i]) {
            case 'A': c = 'T'; break; case 'T': c = 'A'; break;
            case 'C': c = 'G'; break; case 'G': c = 'C'; break;
            case 'N': c = 'N'; break;
            case 'a': c = 't'; break; case 't': c = 'a'; break;
            case 'c': c = 'g'; break; case 'g': c = 'c'; break;
            case 'n': c = 'n'; break;
            default:  c = 'N'; break;
        }
        rc[i] = c;
    }
    return rc;
}

// FNV-1a 64-bit hash
static uint64_t fnv1a_64(const string& s) {
    uint64_t h = 14695981039346656037ULL;
    for (size_t i = 0; i < s.size(); i++) {
        h ^= (uint64_t)(unsigned char)s[i];
        h *= 1099511628211ULL;
    }
    return h;
}

// find longest exact overlap between suffix of r1 and prefix of rc_r2
static int find_overlap(const string& r1, const string& rc_r2, int min_overlap = MIN_OVERLAP) {
    int max_ov = min((int)r1.length(), (int)rc_r2.length());
    for (int ov = max_ov; ov >= min_overlap; ov--) {
        if (memcmp(r1.data() + r1.size() - ov, rc_r2.data(), ov) == 0)
            return ov;
    }
    return 0;
}

static string fmt_long(long n, bool comma) {
    if (!comma) { char b[32]; sprintf(b, "%ld", n); return b; }
    if (n == 0) return "0";
    bool neg = n < 0; if (neg) n = -n;
    string s;
    int cnt = 0;
    while (n) { if (cnt && cnt % 3 == 0) s = "," + s; s = (char)('0' + n % 10) + s; n /= 10; cnt++; }
    return neg ? "-" + s : s;
}

static string fmt_json_long(long n, bool comma) {
    if (comma) return "\"" + fmt_long(n, true) + "\"";
    char b[32]; sprintf(b, "%ld", n); return b;
}

// ============================================================
// FastqRead: stores one FASTQ record
// ============================================================
struct FastqRead {
    string name;
    string seq;
    string strand;
    string quality;

    int length() const { return (int)seq.length(); }
};

// ============================================================
// FastqReader: reads FASTQ records from a file (or stdin)
//
// Uses a large internal buffer (~4MB) and reads in chunks to
// minimize system calls, similar to fastp's internal circular
// buffer design. Supports both gzip-compressed and plain FASTQ.
//
// Gzip is auto-detected by checking:
//   1. File extension (.gz/.GZ)
//   2. Magic bytes (0x1F 0x8B)
// ============================================================
class FastqReader {
public:
    explicit FastqReader(const string& filename)
        : m_filename(filename)
        , m_file(NULL), m_gz_file(NULL), m_is_gzip(false)
        , m_buf(NULL), m_buf_end(0), m_buf_pos(0), m_eof(false)
    {
        if (filename == "-" || filename == "/dev/stdin") {
            // Use plain FILE* for stdin (no gzip detection needed)
            m_file = stdin;
        } else {
            m_is_gzip = is_gzip_file(filename);
            if (m_is_gzip) {
                m_gz_file = gzopen(filename.c_str(), "rb");
                if (!m_gz_file) {
                    cerr << "Error: cannot open gzip file " << filename << endl;
                    exit(1);
                }
            } else {
                m_file = fopen(filename.c_str(), "rb");
                if (!m_file) {
                    cerr << "Error: cannot open file " << filename << endl;
                    exit(1);
                }
            }
        }

        m_buf = new char[BUF_SIZE];
    }

    ~FastqReader() {
        delete[] m_buf;
        if (m_is_gzip) {
            if (m_gz_file) gzclose(m_gz_file);
        } else {
            if (m_file && m_file != stdin) fclose(m_file);
        }
    }

    // Read one FASTQ record; returns false at EOF
    bool read(FastqRead& r) {
        string name, seq, strand, quality;

        if (!next_line(name))    return false;
        if (!next_line(seq))     return false;
        if (!next_line(strand))  return false;
        if (!next_line(quality)) return false;

        // Basic validation (same as fastp's FastqReader::read)
        if (!name.empty() && name[0] != '@') {
            cerr << "Warning: FASTQ name line does not start with '@': "
                 << name.substr(0, 50) << endl;
        }
        if (!strand.empty() && strand[0] != '+') {
            cerr << "Warning: FASTQ strand line does not start with '+': "
                 << strand.substr(0, 50) << endl;
        }
        if (seq.length() != quality.length()) {
            cerr << "Warning: sequence length (" << seq.length()
                 << ") != quality length (" << quality.length()
                 << ") at: " << name << endl;
        }

        r.name    = name;
        r.seq     = seq;
        r.strand  = strand;
        r.quality = quality;
        return true;
    }

private:
    static const size_t BUF_SIZE = 1 << 22;  // 4MB internal buffer

    string  m_filename;
    FILE*   m_file;      // for plain / stdin
    gzFile  m_gz_file;   // for gzip
    bool    m_is_gzip;

    char*   m_buf;
    size_t  m_buf_end;   // bytes of valid data in buffer
    size_t  m_buf_pos;   // current read offset in buffer
    bool    m_eof;

    // ---- File type detection ----

    static bool has_gz_ext(const string& fn) {
        size_t n = fn.size();
        if (n < 3) return false;
        string ext = fn.substr(n - 3);
        return (ext == ".gz" || ext == ".GZ");
    }

    // Check gzip magic bytes: 0x1F 0x8B
    static bool has_gz_magic(const string& fn) {
        FILE* f = fopen(fn.c_str(), "rb");
        if (!f) return false;
        unsigned char magic[2];
        size_t n = fread(magic, 1, 2, f);
        fclose(f);
        return (n == 2 && magic[0] == 0x1F && magic[1] == 0x8B);
    }

    static bool is_gzip_file(const string& fn) {
        return has_gz_ext(fn) || has_gz_magic(fn);
    }

    // ---- Buffered I/O ----

    // Fill the internal buffer from the underlying file
    bool read_chunk() {
        if (m_eof) return false;

        // Compact remaining unread data to the front
        size_t remaining = m_buf_end - m_buf_pos;
        if (remaining > 0 && m_buf_pos > 0) {
            memmove(m_buf, m_buf + m_buf_pos, remaining);
        }
        m_buf_end = remaining;
        m_buf_pos = 0;

        size_t space = BUF_SIZE - m_buf_end;
        if (space == 0) {
            // Buffer full (possible if BUF_SIZE < line length)
            return m_buf_end > 0;
        }

        int n = 0;
        if (m_is_gzip) {
            n = gzread(m_gz_file, m_buf + m_buf_end, (unsigned int)space);
            if (n < 0) {
                cerr << "Error: gzip read failed on " << m_filename << endl;
                return false;
            }
        } else {
            n = (int)fread(m_buf + m_buf_end, 1, space, m_file);
            if (ferror(m_file)) {
                cerr << "Error: read failed on " << m_filename << endl;
                return false;
            }
        }

        if (n == 0) {
            m_eof = true;
            return m_buf_end > 0;
        }

        m_buf_end += (size_t)n;
        return true;
    }

    // Extract the next line from the internal buffer.
    // Handles lines that span buffer boundaries (important for long reads).
    bool next_line(string& line) {
        line.clear();

        while (true) {
            // Refill if we've exhausted the current buffer content
            if (m_buf_pos >= m_buf_end) {
                if (!read_chunk()) {
                    return !line.empty();
                }
            }

            size_t start = m_buf_pos;
            bool found = false;

            // Scan for newline in the current buffer segment
            for (size_t i = start; i < m_buf_end; i++) {
                if (m_buf[i] == '\n') {
                    line.append(m_buf + start, i - start);
                    m_buf_pos = i + 1;
                    found = true;
                    break;
                }
            }

            if (found) {
                // Strip carriage return if present (Windows line endings)
                if (!line.empty() && line.back() == '\r') {
                    line.pop_back();
                }
                return true;
            }

            // No newline in current chunk; append what we have and continue
            line.append(m_buf + start, m_buf_end - start);
            m_buf_pos = m_buf_end;

            // If EOF, return the accumulated data as the final line
            if (m_eof) {
                return !line.empty();
            }
        }
    }
};

// ============================================================
// QcStats: per-cycle quality metrics
//
// Uses the same data layout as fastp's Stats class:
//   34 arrays of longs, each of length m_buf_len:
//     [0..7]   m_cycle_q30[8]      - per-base Q30 counts per cycle
//     [8..15]  m_cycle_q20[8]      - per-base Q20 counts per cycle
//     [16..23] m_cycle_content[8]  - per-base occurrence counts per cycle
//     [24..31] m_cycle_qual[8]     - sum of quality scores per base per cycle
//     [32]     m_cycle_total_base  - total bases per cycle
//     [33]     m_cycle_total_qual  - total quality sum per cycle
// ============================================================
class QcStats {
public:
    explicit QcStats(int guessed_cycles = 0, int margin = 1024)
        : m_reads(0), m_bases(0), m_cycles(0)
        , m_q20_total(0), m_q30_total(0), m_q40_total(0)
        , m_gc_bases(0), m_len_sum(0), m_summarized(false)
        , m_rate_percent(true), m_decimals(2), m_json_comma(false)
    {
        int buf_len = (guessed_cycles > 0) ? guessed_cycles + margin : 1024;
        m_buf_len = buf_len;

        m_cycle_buf = new long[(long)CYCLE_ARRS * m_buf_len];
        memset(m_cycle_buf, 0, sizeof(long) * CYCLE_ARRS * m_buf_len);
        assign_pointers(m_buf_len);

        memset(m_qual_hist,  0, sizeof(long) * QUAL_HIST_SIZE);
        memset(m_q20_bases,  0, sizeof(long) * 8);
        memset(m_q30_bases,  0, sizeof(long) * 8);
        memset(m_base_counts, 0, sizeof(long) * 8);
    }

    ~QcStats() {
        delete[] m_cycle_buf;
    }

    // ---- Processing ----

    // Process a single read, updating per-cycle statistics
    void process_read(const FastqRead& r) {
        int len = r.length();
        if (len <= 0) return;

        // Grow buffer if needed
        if (m_buf_len < len) {
            int new_len = max(len + 100, (int)(len * 1.5));
            extend_buffer(new_len);
        }

        m_reads++;
        m_len_sum += len;

        const char* seq   = r.seq.c_str();
        const char* qual  = r.quality.c_str();

        for (int i = 0; i < len; i++) {
            char base = seq[i];
            char qc   = qual[i];
            int   b   = base2idx(base);

            // Quality histogram
            m_qual_hist[(unsigned char)qc]++;

            // Q20/Q30 per-base per-cycle
            if (qc >= Q30_CHAR) {
                m_cycle_q30[b][i]++;
                m_cycle_q20[b][i]++;
            } else if (qc >= Q20_CHAR) {
                m_cycle_q20[b][i]++;
            }

            // Base content and quality sum per position
            m_cycle_content[b][i]++;
            m_cycle_qual[b][i] += (qc - 33);

            // Totals per position
            m_cycle_total_base[i]++;
            m_cycle_total_qual[i] += (qc - 33);
        }
    }

    // ---- Summarization ----

    // Compute aggregate metrics from the per-cycle arrays.
    // Must be called before any getter or report method.
    void summarize() {
        if (m_summarized) return;
        m_summarized = true;

        // Determine number of cycles and total bases
        for (int c = 0; c < m_buf_len; c++) {
            m_bases += m_cycle_total_base[c];
            if (m_cycle_total_base[c] == 0) {
                m_cycles = c;
                break;
            }
            m_cycles = c + 1;
        }

        // Aggregate per-base statistics across all cycles
        for (int b = 0; b < 8; b++) {
            for (int c = 0; c < m_cycles; c++) {
                m_q20_bases[b]   += m_cycle_q20[b][c];
                m_q30_bases[b]   += m_cycle_q30[b][c];
                m_base_counts[b] += m_cycle_content[b][c];
            }
            m_q20_total += m_q20_bases[b];
            m_q30_total += m_q30_bases[b];
        }

        // Q40: base quality >= 40 + 33 = 73 ('I')
        for (int q = 40; q < QUAL_HIST_SIZE - 33; q++) {
            m_q40_total += m_qual_hist[q + 33];
        }

        // GC bases
        m_gc_bases = m_base_counts['G' & 0x07] + m_base_counts['C' & 0x07];

        // ---- Build curves ----

        // Mean quality curve
        m_mean_qual_curve.resize(m_cycles);
        for (int c = 0; c < m_cycles; c++) {
            m_mean_qual_curve[c] = (m_cycle_total_base[c] > 0)
                ? (double)m_cycle_total_qual[c] / m_cycle_total_base[c]
                : 0.0;
        }

        // Per-base quality and content curves (A, T, C, G, N)
        const char bases[5] = { 'A', 'T', 'C', 'G', 'N' };
        for (int bi = 0; bi < 5; bi++) {
            int idx = base2idx(bases[bi]);
            vector<double> qc(m_cycles), cc(m_cycles);
            for (int c = 0; c < m_cycles; c++) {
                if (m_cycle_content[idx][c] == 0)
                    qc[c] = m_mean_qual_curve[c];
                else
                    qc[c] = (double)m_cycle_qual[idx][c] / m_cycle_content[idx][c];

                cc[c] = (m_cycle_total_base[c] > 0)
                    ? (double)m_cycle_content[idx][c] / m_cycle_total_base[c]
                    : 0.0;
            }
            m_qual_curves[string(1, bases[bi])]    = qc;
            m_content_curves[string(1, bases[bi])] = cc;
        }

        // GC content curve
        int g_idx = 'G' & 0x07;
        int c_idx = 'C' & 0x07;
        m_gc_curve.resize(m_cycles);
        for (int c = 0; c < m_cycles; c++) {
            m_gc_curve[c] = (m_cycle_total_base[c] > 0)
                ? (double)(m_cycle_content[g_idx][c] + m_cycle_content[c_idx][c])
                  / m_cycle_total_base[c]
                : 0.0;
        }
    }

    // ---- Accessors (auto-summarize) ----

    long    total_reads()  const { return m_reads; }
    long    total_bases()        { if (!m_summarized) summarize(); return m_bases; }
    int     total_cycles()       { if (!m_summarized) summarize(); return m_cycles; }
    long    total_q20()          { if (!m_summarized) summarize(); return m_q20_total; }
    long    total_q30()          { if (!m_summarized) summarize(); return m_q30_total; }
    long    total_q40()          { if (!m_summarized) summarize(); return m_q40_total; }
    long    total_gc()           { if (!m_summarized) summarize(); return m_gc_bases; }
    long    mean_length()        { if (m_reads == 0) return 0; return m_len_sum / m_reads; }
    long*   qual_histogram()     { return m_qual_hist; }

    double  gc_content()         { if (!m_summarized) summarize(); return (m_bases > 0) ? (m_rate_percent?100.0:1.0) * m_gc_bases / m_bases : 0.0; }
    double  q20_rate()           { if (!m_summarized) summarize(); return (m_bases > 0) ? (m_rate_percent?100.0:1.0) * m_q20_total / m_bases : 0.0; }
    double  q30_rate()           { if (!m_summarized) summarize(); return (m_bases > 0) ? (m_rate_percent?100.0:1.0) * m_q30_total / m_bases : 0.0; }

    // Q20+ rate at the 20th sequencing cycle (position 20, 0-based index 19)
    double cycle20_rate() {
        if (!m_summarized) summarize();
        int c = 19;
        if (c >= m_cycles || m_cycle_total_base[c] == 0) return 0.0;
        long q20b = 0;
        for (int b = 0; b < 8; b++) q20b += m_cycle_q20[b][c];
        double ratio = (double)q20b / m_cycle_total_base[c];
        return m_rate_percent ? 100.0 * ratio : ratio;
    }

    double q40_rate() {
        if (!m_summarized) summarize();
        return (m_bases > 0) ? (m_rate_percent?100.0:1.0) * m_q40_total / m_bases : 0.0;
    }

    void set_rate_percent(bool p) { m_rate_percent = p; }
    void set_decimals(int d)      { m_decimals = d; }
    void set_json_comma(bool c)   { m_json_comma = c; }

    static string format_double(double v, int d) {
        ostringstream oss;
        oss << fixed << setprecision(d) << v;
        return oss.str();
    }

    // ---- Merge ----

    // Merge another QcStats into this one (used for combining R1 and R2)
    void merge(const QcStats& other) {
        if (m_buf_len < other.m_buf_len) {
            extend_buffer(other.m_buf_len);
        }

        m_reads   += other.m_reads;
        m_len_sum += other.m_len_sum;

        for (int b = 0; b < 8; b++) {
            for (int c = 0; c < other.m_buf_len; c++) {
                m_cycle_q30[b][c]     += other.m_cycle_q30[b][c];
                m_cycle_q20[b][c]     += other.m_cycle_q20[b][c];
                m_cycle_content[b][c] += other.m_cycle_content[b][c];
                m_cycle_qual[b][c]    += other.m_cycle_qual[b][c];
            }
        }
        for (int c = 0; c < other.m_buf_len; c++) {
            m_cycle_total_base[c] += other.m_cycle_total_base[c];
            m_cycle_total_qual[c] += other.m_cycle_total_qual[c];
        }
        for (int i = 0; i < QUAL_HIST_SIZE; i++) {
            m_qual_hist[i] += other.m_qual_hist[i];
        }

        m_summarized = false;
    }

    // ---- Reports ----

    // Output a text summary to stderr
    void print() {
        if (!m_summarized) summarize();
        const char* pct = m_rate_percent ? " %" : "";

        ostringstream gc_s, q20_s, q30_s, q40_s;
        gc_s  << fixed << setprecision(m_decimals) << gc_content() << pct;
        q20_s << fixed << setprecision(m_decimals) << q20_rate()   << pct;
        q30_s << fixed << setprecision(m_decimals) << q30_rate()   << pct;
        q40_s << fixed << setprecision(m_decimals) << q40_rate()   << pct;
        string gc_str  = gc_s.str();
        string q20_str = q20_s.str();
        string q30_str = q30_s.str();
        string q40_str = q40_s.str();

        string tro = fmt_long(m_reads, true);
        string tba = fmt_long(m_bases, true);
        string tml = fmt_long(mean_length(), true);
        string tq2 = fmt_long(m_q20_total, true);
        string tq3 = fmt_long(m_q30_total, true);
        string tq4 = fmt_long(m_q40_total, true);
        string tcy = fmt_long(m_cycles, true);

        printf( "=== QC Summary ===\n");
        printf( "  %-20s %12s\n",     "Total reads:",   tro.c_str());
        printf( "  %-20s %12s\n",     "Total bases:",   tba.c_str());
        printf( "  %-20s %12s bp\n",  "Mean length:",   tml.c_str());
        printf( "  %-20s %12s\n",      "GC content:",    gc_str.c_str());
        printf( "  %-20s %12s  (%s)\n", "Q20 bases:",   tq2.c_str(), q20_str.c_str());
        printf( "  %-20s %12s  (%s)\n", "Q30 bases:",   tq3.c_str(), q30_str.c_str());
        printf( "  %-20s %12s  (%s)\n", "Q40 bases:",   tq4.c_str(), q40_str.c_str());
        printf( "  %-20s %12s\n",      "Total cycles:",  tcy.c_str());
        ostringstream c20_s;
        c20_s << fixed << setprecision(m_decimals) << cycle20_rate() << pct;
        string c20_str = c20_s.str();
        printf( "  %-20s %12s\n",      "Cycle 20 Q20 rate:", c20_str.c_str());

        printf( "\n  Per-cycle mean quality (sampled):\n");
        printf( "    Cycle   MeanQual\n");
        int step = max(1, m_cycles / 25);
        for (int c = 0; c < m_cycles; c += step) {
            printf( "    %5d   %7.2f\n", c + 1, m_mean_qual_curve[c]);
        }
    }

    // Output a JSON object representing these stats.
    // If label is non-empty, wraps with '"label": {...}'.
    void report_json(ostream& os, const string& padding = "",
                     const string& label = "")
    {
        if (!m_summarized) summarize();

        string p = padding;
        string indent = padding + "\t";

        if (!label.empty()) {
            os << p << "\"" << label << "\": ";
        }
        os << p << "{" << endl;

        // Summary fields
        os << indent << "\"total_reads\": "  << fmt_json_long(m_reads, m_json_comma)     << "," << endl;
        os << indent << "\"total_bases\": "  << fmt_json_long(m_bases, m_json_comma)     << "," << endl;
        os << indent << "\"mean_length\": "  << fmt_json_long(mean_length(), m_json_comma) << "," << endl;
        os << indent << "\"total_cycles\": " << fmt_json_long(m_cycles, m_json_comma)    << "," << endl;
        os << indent << "\"q20_bases\": "    << fmt_json_long(m_q20_total, m_json_comma) << "," << endl;
        os << indent << "\"q20_rate\": "     << format_double(q20_rate(), m_decimals)  << "," << endl;
        os << indent << "\"q30_bases\": "    << fmt_json_long(m_q30_total, m_json_comma) << "," << endl;
        os << indent << "\"q30_rate\": "     << format_double(q30_rate(), m_decimals)  << "," << endl;
        os << indent << "\"q40_bases\": "    << fmt_json_long(m_q40_total, m_json_comma) << "," << endl;
        os << indent << "\"q40_rate\": "     << format_double(q40_rate(), m_decimals)  << "," << endl;
        os << indent << "\"gc_bases\": "     << fmt_json_long(m_gc_bases, m_json_comma)  << "," << endl;
        os << indent << "\"gc_content\": "   << format_double(gc_content(), m_decimals) << "," << endl;
        os << indent << "\"cycle20_rate\": "   << format_double(cycle20_rate(), m_decimals) << "," << endl;

        // ---- Quality curves ----
        os << indent << "\"quality_curves\": {" << endl;
        const char* qnames[5] = { "A", "T", "C", "G", "mean" };
        for (int i = 0; i < 5; i++) {
            vector<double>& curve = (i < 4)
                ? m_qual_curves[string(qnames[i])]
                : m_mean_qual_curve;

            os << indent << "\t\"" << qnames[i] << "\":[";
            for (int c = 0; c < m_cycles; c++) {
                if (c > 0) os << ",";
                os << curve[c];
            }
            os << "]";
            if (i < 4) os << ",";
            os << endl;
        }
        os << indent << "}," << endl;

        // ---- Content curves ----
        os << indent << "\"content_curves\": {" << endl;
        map<string, vector<double>*> cmap;
        cmap["A"]  = &m_content_curves["A"];
        cmap["T"]  = &m_content_curves["T"];
        cmap["C"]  = &m_content_curves["C"];
        cmap["G"]  = &m_content_curves["G"];
        cmap["N"]  = &m_content_curves["N"];
        cmap["GC"] = &m_gc_curve;

        const char* cnames[6] = { "A", "T", "C", "G", "N", "GC" };
        for (int i = 0; i < 6; i++) {
            vector<double>& curve = *cmap[string(cnames[i])];
            os << indent << "\t\"" << cnames[i] << "\":[";
            for (int c = 0; c < m_cycles; c++) {
                if (c > 0) os << ",";
                os << curve[c];
            }
            os << "]";
            if (i < 5) os << ",";
            os << endl;
        }
        os << indent << "}," << endl;

        // ---- Quality histogram ----
        os << indent << "\"quality_histogram\": {" << endl;
        bool first = true;
        for (int i = 0; i < QUAL_HIST_SIZE; i++) {
            if (m_qual_hist[i] > 0) {
                if (!first) os << "," << endl;
                first = false;
                os << indent << "\t\"" << i << "\": " << m_qual_hist[i];
            }
        }
        if (!first) os << endl;
        os << indent << "}" << endl;

        os << p << "}";
    }

    // Export per-cycle curves as TSV
    void write_cycles_tsv(ostream& os) {
        if (!m_summarized) summarize();
        os << "cycle\tmean_qual\tA_qual\tT_qual\tC_qual\tG_qual"
           << "\tA_content\tT_content\tC_content\tG_content\tN_content\tGC_content" << endl;
        const char* bases[4] = { "A", "T", "C", "G" };
        for (int c = 0; c < m_cycles; c++) {
            os << (c + 1);
            os << "\t" << m_mean_qual_curve[c];
            for (int b = 0; b < 4; b++)
                os << "\t" << m_qual_curves[bases[b]][c];
            for (int b = 0; b < 4; b++)
                os << "\t" << m_content_curves[bases[b]][c];
            os << "\t" << m_content_curves["N"][c];
            os << "\t" << m_gc_curve[c];
            os << endl;
        }
    }

private:
    // ---- Memory management ----

    void assign_pointers(int buf_len) {
        for (int i = 0; i < 8; i++) {
            m_cycle_q30[i]     = m_cycle_buf + (0*8 + i) * (long)buf_len;
            m_cycle_q20[i]     = m_cycle_buf + (1*8 + i) * (long)buf_len;
            m_cycle_content[i] = m_cycle_buf + (2*8 + i) * (long)buf_len;
            m_cycle_qual[i]   = m_cycle_buf + (3*8 + i) * (long)buf_len;
        }
        m_cycle_total_base = m_cycle_buf + 32 * (long)buf_len;
        m_cycle_total_qual = m_cycle_buf + 33 * (long)buf_len;
    }

    void extend_buffer(int new_len) {
        if (new_len <= m_buf_len) return;

        long* new_buf = new long[(long)CYCLE_ARRS * new_len];
        memset(new_buf, 0, sizeof(long) * CYCLE_ARRS * new_len);

        for (int a = 0; a < CYCLE_ARRS; a++) {
            memcpy(new_buf + a * (long)new_len,
                   m_cycle_buf + a * (long)m_buf_len,
                   sizeof(long) * m_buf_len);
        }

        delete[] m_cycle_buf;
        m_cycle_buf = new_buf;
        assign_pointers(new_len);
        m_buf_len = new_len;
    }

    // ---- Data members ----

    long  m_reads;
    long  m_bases;
    int   m_cycles;
    int   m_buf_len;

    // Single allocation for all cycle arrays
    long* m_cycle_buf;
    long* m_cycle_q30[8];
    long* m_cycle_q20[8];
    long* m_cycle_content[8];
    long* m_cycle_qual[8];
    long* m_cycle_total_base;
    long* m_cycle_total_qual;

    // Global aggregates
    long m_q20_bases[8];
    long m_q30_bases[8];
    long m_base_counts[8];
    long m_q20_total;
    long m_q30_total;
    long m_q40_total;
    long m_gc_bases;
    long m_qual_hist[QUAL_HIST_SIZE];
    long m_len_sum;

    // Curves (computed during summarization)
    vector<double> m_mean_qual_curve;
    map<string, vector<double>> m_qual_curves;     // "A","T","C","G"
    map<string, vector<double>> m_content_curves;  // "A","T","C","G","N"
    vector<double> m_gc_curve;

    bool m_summarized;
    bool m_rate_percent;
    int  m_decimals;
    bool m_json_comma;
};


// ============================================================
// DupCounter: hash-based exact duplicate detection
//
// Uses FNV-1a 64-bit hash + unordered_set. For paired-end reads,
// R1 and R2 hashes are combined via boost::hash_combine.
// ============================================================
class DupCounter {
public:
    DupCounter() : m_total(0), m_dup(0) {}

    void add_read(const FastqRead& r) {
        m_total++;
        uint64_t h = fnv1a_64(r.seq);
        if (m_seen.count(h)) m_dup++;
        else                 m_seen.insert(h);
    }

    void add_pair(const FastqRead& r1, const FastqRead& r2) {
        m_total++;
        uint64_t h1 = fnv1a_64(r1.seq);
        uint64_t h2 = fnv1a_64(r2.seq);
        // boost::hash_combine
        uint64_t h = h1 ^ (h2 + 0x9e3779b97f4a7c15ULL + (h1 << 6) + (h1 >> 2));
        if (m_seen.count(h)) m_dup++;
        else                 m_seen.insert(h);
    }

    long   total()    const { return m_total; }
    long   dup_count() const { return m_dup; }
    double dup_rate()  const { return m_total > 0 ? (double)m_dup / m_total : 0.0; }

    void print(bool as_percent, int decimals) const {
        double val = as_percent ? dup_rate() * 100.0 : dup_rate();
        ostringstream oss;
        oss << fixed << setprecision(decimals) << val;
        if (as_percent) oss << " %";
        string s = oss.str();
        printf( "  %-20s %12s\n", "Duplication rate:", s.c_str());
    }

    void report_json(ostream& os, const string& indent, bool as_percent, int decimals) {
        double val = as_percent ? dup_rate() * 100.0 : dup_rate();
        os << indent << "\"duplication\": {" << endl;
        os << indent << "\t\"rate\": " << format_val(val, decimals) << endl;
        os << indent << "}";
    }

private:
    unordered_set<uint64_t> m_seen;
    long m_total;
    long m_dup;

    static string format_val(double v, int d) {
        ostringstream oss;
        oss << fixed << setprecision(d) << v;
        return oss.str();
    }
};


// ============================================================
// InsertSizeStats: overlap-based insert size estimation (PE only)
//
// Reverse-complements R2, finds longest exact overlap with R1
// suffix, computes insert_size = len(R1) + len(R2) - overlap.
// Tracks histogram and finds the peak (mode).
// ============================================================
class InsertSizeStats {
public:
    explicit InsertSizeStats(int max_size = 512)
        : m_max_size(max_size), m_total(0), m_unknown(0), m_json_comma(false)
    {
        m_hist.resize(max_size + 1, 0);
    }

    void process_pair(const FastqRead& r1, const FastqRead& r2) {
        m_total++;
        string rc_r2 = reverse_complement(r2.seq);
        int overlap = find_overlap(r1.seq, rc_r2);
        if (overlap > 0) {
            int isize = r1.length() + r2.length() - overlap;
            if (isize >= m_max_size)
                m_hist[m_max_size]++;
            else if (isize > 0)
                m_hist[isize]++;
            else
                m_unknown++;
        } else {
            m_unknown++;
        }
    }

    int  peak()    const {
        int  pk = 0;
        long mx = -1;
        for (int i = 0; i < m_max_size; i++) {
            if (m_hist[i] > mx) { pk = i; mx = m_hist[i]; }
        }
        return pk;
    }
    long total()   const { return m_total; }
    long unknown() const { return m_unknown; }

    void print() const {
        int pk = peak();
        string spk = fmt_long(pk, true);
        string sun = fmt_long(m_unknown, true);
        printf( "  %-20s %12s\n",   "Insert size peak:", spk.c_str());
        printf( "  %-20s %12s\n",  "Unknown pairs:",   sun.c_str());
    }

    void set_json_comma(bool c) { m_json_comma = c; }

    void report_json(ostream& os, const string& indent) {
        os << indent << "\"insert_size\": {" << endl;
        os << indent << "\t\"peak\": " << fmt_json_long(peak(), m_json_comma) << "," << endl;
        os << indent << "\t\"unknown\": " << fmt_json_long(m_unknown, m_json_comma) << "," << endl;
        os << indent << "\t\"histogram\": [";
        for (int i = 0; i <= m_max_size; i++) {
            if (i > 0) os << ",";
            os << fmt_json_long(m_hist[i], m_json_comma);
        }
        os << "]" << endl;
        os << indent << "}";
    }

private:
    vector<long> m_hist;
    int  m_max_size;
    long m_total;
    long m_unknown;
    bool m_json_comma;
};


// ============================================================
// Configuration & CLI
// ============================================================
struct QcConfig {
    string read1_file;
    string read2_file;   // Empty => single-end
    string output_file;  // Empty => no JSON output
    bool   rate_percent;
    int    decimals;
    int    insert_size_max;
    string tsv_prefix;
    string sample_id;
    bool   tsv_comma;
    bool   json_comma;

    QcConfig() : rate_percent(true), decimals(2), insert_size_max(512), tsv_comma(false), json_comma(false) {}
};

static void print_usage(const char* prog) {
    printf(
        "Usage: %s [options] -i <read1.fastq> [-I <read2.fastq>]\n"
        "\n"
        "Options:\n"
        "  -i <file>     Input FASTQ file (R1 for paired-end). Use '-' for stdin.\n"
        "                 Gzip auto-detected by .gz extension or magic bytes.\n"
        "  -I <file>     Input R2 FASTQ file (enables paired-end mode).\n"
        "  -o <file>     Output JSON report to file (omitted = no JSON output).\n"
        "  -no-percent   Output rate values as decimals (0.0-1.0) instead of percentages.\n"
        "  -d <n>        Set decimal places for rate values (default: 2).\n"
        "  -is <n>       Max insert size (default: 512). Paired-end only.\n"
        "  -p <prefix>   Export TSV tables (summary + per-cycle) with this prefix.\n"
        "  -s <id>       Sample ID for TSV output (default: derived from filename).\n"
        "  --tsv-comma   Add thousands separators in TSV output.\n"
        "  --json-comma  Add thousands separators in JSON output (as strings).\n"
        "  -h            Show this help.\n"
        "\n"
        "Examples:\n"
        "  %s -i sample_R1.fastq -I sample_R2.fastq -o qc_report.json\n"
        "  %s -i sample.fastq.gz -o qc_report.json\n"
        "  %s -i sample.fastq -t\n",
        prog, prog, prog, prog);
}

static bool parse_args(int argc, char* argv[], QcConfig& config) {
    for (int i = 1; i < argc; i++) {
        string arg = argv[i];
        if (arg == "-i") {
            if (++i >= argc) { cerr << "Error: -i requires an argument" << endl; return false; }
            config.read1_file = argv[i];
        } else if (arg == "-I") {
            if (++i >= argc) { cerr << "Error: -I requires an argument" << endl; return false; }
            config.read2_file = argv[i];
        } else if (arg == "-o") {
            if (++i >= argc) { cerr << "Error: -o requires an argument" << endl; return false; }
            config.output_file = argv[i];
        } else if (arg == "-no-percent") {
            config.rate_percent = false;
        } else if (arg == "-d") {
            if (++i >= argc) { cerr << "Error: -d requires an argument" << endl; return false; }
            config.decimals = atoi(argv[i]);
        } else if (arg == "-is") {
            if (++i >= argc) { cerr << "Error: -is requires an argument" << endl; return false; }
            config.insert_size_max = atoi(argv[i]);
        } else if (arg == "-p") {
            if (++i >= argc) { cerr << "Error: -p requires an argument" << endl; return false; }
            config.tsv_prefix = argv[i];
        } else if (arg == "-s") {
            if (++i >= argc) { cerr << "Error: -s requires an argument" << endl; return false; }
            config.sample_id = argv[i];
        } else if (arg == "--tsv-comma") {
            config.tsv_comma = true;
        } else if (arg == "--json-comma") {
            config.json_comma = true;
        } else if (arg == "-h") {
            print_usage(argv[0]);
            exit(0);
        } else {
            cerr << "Error: unknown option " << arg << endl;
            return false;
        }
    }
    if (config.read1_file.empty()) {
        cerr << "Error: input file (-i) is required" << endl;
        return false;
    }
    return true;
}

static string basename_noext(const string& path) {
    size_t slash = path.find_last_of("/\\");
    string name = (slash == string::npos) ? path : path.substr(slash + 1);
    // Strip .gz then .fastq/.fq
    if (name.size() > 3 && (name.compare(name.size()-3, 3, ".gz") == 0
                         || name.compare(name.size()-3, 3, ".GZ") == 0))
        name = name.substr(0, name.size()-3);
    if (name.size() > 6 && name.compare(name.size()-6, 6, ".fastq") == 0)
        name = name.substr(0, name.size()-6);
    else if (name.size() > 3 && name.compare(name.size()-3, 3, ".fq") == 0)
        name = name.substr(0, name.size()-3);
    return name.empty() ? "sample" : name;
}

// ============================================================
// Main
// ============================================================
int main(int argc, char* argv[]) {
    QcConfig config;
    if (!parse_args(argc, argv, config)) {
        print_usage(argv[0]);
        return 1;
    }

    bool paired = !config.read2_file.empty();

    // Quick file existence check (skip for stdin)
    if (config.read1_file != "-") {
        struct stat st;
        if (stat(config.read1_file.c_str(), &st) != 0) {
            cerr << "Error: cannot access " << config.read1_file << endl; return 1;
        }
    }
    if (paired && config.read2_file != "-") {
        struct stat st;
        if (stat(config.read2_file.c_str(), &st) != 0) {
            cerr << "Error: cannot access " << config.read2_file << endl; return 1;
        }
    }

    // Prepare readers
    FastqReader reader1(config.read1_file);
    FastqReader* reader2 = paired ? new FastqReader(config.read2_file) : NULL;

    time_t start_t = time(NULL);

    // Per-read statistics
    QcStats stats1, stats2;
    stats1.set_rate_percent(config.rate_percent);
    stats1.set_decimals(config.decimals); stats1.set_json_comma(config.json_comma);
    stats2.set_rate_percent(config.rate_percent);
    stats2.set_decimals(config.decimals); stats2.set_json_comma(config.json_comma);

    // Duplication and insert size
    DupCounter dup_counter;
    InsertSizeStats* isize_stats = paired ? new InsertSizeStats(config.insert_size_max) : NULL;
    if (isize_stats) isize_stats->set_json_comma(config.json_comma);

    FastqRead r1, r2;
    long read_count = 0;

    fprintf(stderr, "Processing %s FASTQ data...\n", paired ? "paired-end" : "single-end");

    while (reader1.read(r1)) {
        if (paired) {
            if (!reader2->read(r2)) {
                cerr << "Warning: R1 has more reads than R2 at read " << (read_count + 1) << endl;
                break;
            }
            stats2.process_read(r2);
            dup_counter.add_pair(r1, r2);
            isize_stats->process_pair(r1, r2);
        } else {
            dup_counter.add_read(r1);
        }

        stats1.process_read(r1);

        read_count++;
        if (read_count % 500000 == 0) {
            fprintf(stderr, "  Processed %s reads...\n", fmt_long(read_count, true).c_str());
        }
    }

    // Check for extra reads in R2
    if (paired) {
        FastqRead extra;
        if (reader2->read(extra)) {
            cerr << "Warning: R2 has more reads than R1" << endl;
        }
    }

    delete reader2;

    fprintf(stderr, "Total reads processed: %ld\n", read_count);

    // ---- Reporting ----

    if (paired) {
        printf("\n>>>> Read 1 <<<<\n");
    }
    stats1.print();

    if (paired) {
        printf("\n>>>> Read 2 <<<<\n");
        stats2.print();

        // Combined stats
        QcStats combined;
        combined.set_rate_percent(config.rate_percent);
        combined.set_decimals(config.decimals); combined.set_json_comma(config.json_comma);
        combined.merge(stats1);
        combined.merge(stats2);
        printf("\n>>>> Combined <<<<\n");
        combined.print();
    }

    printf("\n=== Duplication ===\n");
    dup_counter.print(config.rate_percent, config.decimals);

    if (paired) {
        printf("\n=== Insert Size ===\n");
        isize_stats->print();
    }

    if (!config.output_file.empty()) {
        ofstream out_file(config.output_file.c_str());
        if (!out_file.is_open()) {
            cerr << "Error: cannot open output file " << config.output_file << endl;
            return 1;
        }

        if (paired) {
            out_file << "{" << endl;
            stats1.report_json(out_file, "\t", "read1");
            out_file << "," << endl;
            stats2.report_json(out_file, "\t", "read2");
            out_file << endl;
            // Combined summary
            QcStats combined;
            combined.set_rate_percent(config.rate_percent);
            combined.set_decimals(config.decimals); combined.set_json_comma(config.json_comma);
            combined.merge(stats1);
            combined.merge(stats2);
            combined.summarize();
            out_file << "," << endl;
            out_file << "\t\"total_reads\": " << fmt_json_long(combined.total_reads(), config.json_comma) << "," << endl;
            out_file << "\t\"total_bases\": " << fmt_json_long(combined.total_bases(), config.json_comma) << "," << endl;
            out_file << "\t\"q20_rate\": "    << QcStats::format_double(combined.q20_rate(), config.decimals)    << "," << endl;
            out_file << "\t\"q30_rate\": "    << QcStats::format_double(combined.q30_rate(), config.decimals)    << "," << endl;
            out_file << "\t\"gc_content\": "  << QcStats::format_double(combined.gc_content(), config.decimals)  << "," << endl;
            dup_counter.report_json(out_file, "\t", config.rate_percent, config.decimals);
            out_file << "," << endl;
            isize_stats->report_json(out_file, "\t");
            out_file << endl << "}" << endl;
        } else {
            out_file << "{" << endl;
            stats1.report_json(out_file, "\t", "read1");
            out_file << "," << endl;
            dup_counter.report_json(out_file, "\t", config.rate_percent, config.decimals);
            out_file << endl << "}" << endl;
        }

        fprintf(stderr, "JSON report written to: %s\n", config.output_file.c_str());
    }

    // ---- TSV export ----
    if (!config.tsv_prefix.empty()) {
        string sample = config.sample_id.empty() ? basename_noext(config.read1_file) : config.sample_id;
        double mult  = config.rate_percent ? 100.0 : 1.0;

        string sum_hdr = "sample\ttotal_reads\ttotal_bases\tmean_length"
                         "\tgc_content\tq20_rate\tq30_rate\tq40_bases\tq40_rate\tcycle20_rate\tdup_rate";
        string sum_pe_ext = "\tinsert_size_peak\tinsert_size_unknown";

        if (paired) {
            // R1 summary
            string r1_sum = config.tsv_prefix + "_R1_summary.tsv";
            ofstream r1s(r1_sum.c_str());
            if (r1s.is_open()) {
                r1s << sum_hdr << sum_pe_ext << endl;
                r1s << sample
                    << "\t" << fmt_long(stats1.total_reads(), config.tsv_comma)
                    << "\t" << fmt_long(stats1.total_bases(), config.tsv_comma)
                    << "\t" << fmt_long(stats1.mean_length(), config.tsv_comma)
                    << "\t" << fixed << setprecision(config.decimals) << stats1.gc_content()
                    << "\t" << fixed << setprecision(config.decimals) << stats1.q20_rate()
                    << "\t" << fixed << setprecision(config.decimals) << stats1.q30_rate()
                    << "\t" << fmt_long(stats1.total_q40(), config.tsv_comma)
                    << "\t" << fixed << setprecision(config.decimals) << stats1.q40_rate()
                    << "\t" << fixed << setprecision(config.decimals) << stats1.cycle20_rate()
                    << "\t" << fixed << setprecision(config.decimals) << (mult * dup_counter.dup_rate())
                    << "\t" << fmt_long(isize_stats->peak(), config.tsv_comma)
                    << "\t" << fmt_long(isize_stats->unknown(), config.tsv_comma)
                    << endl;
                r1s.close();
                fprintf(stderr, "TSV summary R1 written to: %s\n", r1_sum.c_str());
            }

            // R2 summary
            string r2_sum = config.tsv_prefix + "_R2_summary.tsv";
            ofstream r2s(r2_sum.c_str());
            if (r2s.is_open()) {
                r2s << sum_hdr << sum_pe_ext << endl;
                r2s << sample
                    << "\t" << fmt_long(stats2.total_reads(), config.tsv_comma)
                    << "\t" << fmt_long(stats2.total_bases(), config.tsv_comma)
                    << "\t" << fmt_long(stats2.mean_length(), config.tsv_comma)
                    << "\t" << fixed << setprecision(config.decimals) << stats2.gc_content()
                    << "\t" << fixed << setprecision(config.decimals) << stats2.q20_rate()
                    << "\t" << fixed << setprecision(config.decimals) << stats2.q30_rate()
                    << "\t" << fmt_long(stats2.total_q40(), config.tsv_comma)
                    << "\t" << fixed << setprecision(config.decimals) << stats2.q40_rate()
                    << "\t" << fixed << setprecision(config.decimals) << stats2.cycle20_rate()
                    << "\t" << fixed << setprecision(config.decimals) << (mult * dup_counter.dup_rate())
                    << "\t" << fmt_long(isize_stats->peak(), config.tsv_comma)
                    << "\t" << fmt_long(isize_stats->unknown(), config.tsv_comma)
                    << endl;
                r2s.close();
                fprintf(stderr, "TSV summary R2 written to: %s\n", r2_sum.c_str());
            }

            // Combined R1+R2 summary
            QcStats combined;
            combined.set_rate_percent(config.rate_percent);
            combined.set_decimals(config.decimals);
            combined.merge(stats1);
            combined.merge(stats2);
            combined.summarize();
            string comb_sum = config.tsv_prefix + "_combined_summary.tsv";
            ofstream cs(comb_sum.c_str());
            if (cs.is_open()) {
                cs << "sample\ttotal_reads\ttotal_bases\tmean_length"
                   << "\tgc_content\tq20_rate\tq30_rate\tq40_bases\tq40_rate\tdup_rate"
                   << sum_pe_ext << endl;
                cs << sample
                   << "\t" << fmt_long(combined.total_reads(), config.tsv_comma)
                   << "\t" << fmt_long(combined.total_bases(), config.tsv_comma)
                   << "\t" << fmt_long(combined.mean_length(), config.tsv_comma)
                   << "\t" << fixed << setprecision(config.decimals) << combined.gc_content()
                   << "\t" << fixed << setprecision(config.decimals) << combined.q20_rate()
                   << "\t" << fixed << setprecision(config.decimals) << combined.q30_rate()
                   << "\t" << fmt_long(combined.total_q40(), config.tsv_comma)
                   << "\t" << fixed << setprecision(config.decimals) << combined.q40_rate()
                   << "\t" << fixed << setprecision(config.decimals) << (mult * dup_counter.dup_rate())
                   << "\t" << fmt_long(isize_stats->peak(), config.tsv_comma)
                   << "\t" << fmt_long(isize_stats->unknown(), config.tsv_comma)
                   << endl;
                cs.close();
                fprintf(stderr, "TSV combined summary written to: %s\n", comb_sum.c_str());
            }
        } else {
            // Single-end summary
            string sum_file = config.tsv_prefix + "_summary.tsv";
            ofstream sum_out(sum_file.c_str());
            if (sum_out.is_open()) {
                sum_out << sum_hdr << endl;
                sum_out << sample
                        << "\t" << fmt_long(stats1.total_reads(), config.tsv_comma)
                        << "\t" << fmt_long(stats1.total_bases(), config.tsv_comma)
                        << "\t" << fmt_long(stats1.mean_length(), config.tsv_comma)
                        << "\t" << fixed << setprecision(config.decimals) << stats1.gc_content()
                        << "\t" << fixed << setprecision(config.decimals) << stats1.q20_rate()
                        << "\t" << fixed << setprecision(config.decimals) << stats1.q30_rate()
                        << "\t" << fmt_long(stats1.total_q40(), config.tsv_comma)
                        << "\t" << fixed << setprecision(config.decimals) << stats1.q40_rate()
                        << "\t" << fixed << setprecision(config.decimals) << stats1.cycle20_rate()
                        << "\t" << fixed << setprecision(config.decimals) << (mult * dup_counter.dup_rate())
                        << endl;
                sum_out.close();
                fprintf(stderr, "TSV summary written to: %s\n", sum_file.c_str());
            }
        }

        // Cycles TSV
        string r1_cycles = config.tsv_prefix + "_R1_cycles.tsv";
        ofstream cyc1(r1_cycles.c_str());
        if (cyc1.is_open()) {
            stats1.write_cycles_tsv(cyc1);
            fprintf(stderr, "TSV cycles R1 written to: %s\n", r1_cycles.c_str());
        }

        if (paired) {
            string r2_cycles = config.tsv_prefix + "_R2_cycles.tsv";
            ofstream cyc2(r2_cycles.c_str());
            if (cyc2.is_open()) {
                stats2.write_cycles_tsv(cyc2);
                fprintf(stderr, "TSV cycles R2 written to: %s\n", r2_cycles.c_str());
            }
        }
    }

    delete isize_stats;

    time_t end_t = time(NULL);
    long elapsed = (long)(end_t - start_t);
    fprintf(stderr, "Elapsed time: %ld sec (%ld min %ld sec)\n",
            elapsed, elapsed / 60, elapsed % 60);

    return 0;
}
