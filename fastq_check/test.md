## 适用情况

- 无法获得测序fastq文件MD5时适用。

## 注意

- 一般看标准输或者json文件中`errors` 部分即可，不为0即为文件有问题。其它结果内容都是辅助。

- 平台推断考虑的情况种类并不多。尤其是对于三代测序来说，下机数据可能不是fastq形式，另外很多分析程序都会修改header部分，造成无法识别。
- 选项中一般指定好文件选项和启用`--pigz`加上多线程即可。
- 如果一定要测试`--infer-platform` 建议去国内GSA平台下载原始数据。

## 时间测试

- 测试设备比较老了

### 命令1

```sh
cargo run --release -- --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 0
    Finished `release` profile [optimized] target(s) in 0.09s
     Running `target\release\fastq_check.exe --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 0`
Total reads: 40018826
Total bases: 6002823900
Errors: 0
Elapsed seconds: 82.768
example/260R15336-T_L1_1.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_1.fq.gz: quality=Phred33
example/260R15336-T_L1_1.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
example/260R15336-T_L1_2.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_2.fq.gz: quality=Phred33
example/260R15336-T_L1_2.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
```

### 命令2

```sh
cargo run --release -- --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 8
    Finished `release` profile [optimized] target(s) in 0.09s
     Running `target\release\fastq_check.exe --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 8`
Total reads: 40018826
Total bases: 6002823900
Errors: 0
Elapsed seconds: 77.431
example/260R15336-T_L1_1.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_1.fq.gz: quality=Phred33
example/260R15336-T_L1_1.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
example/260R15336-T_L1_2.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_2.fq.gz: quality=Phred33
example/260R15336-T_L1_2.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
```

### 命令3：比较快

```sh
cargo run --release -- --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 8 --pigz --batch-size 81920
    Finished `release` profile [optimized] target(s) in 0.11s
     Running `target\release\fastq_check.exe --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 8 --pigz --batch-size 81920`
Using pigz: path=pigz, threads=8, input=example/260R15336-T_L1_1.fq.gz
Using pigz: path=pigz, threads=8, input=example/260R15336-T_L1_2.fq.gz
Total reads: 40018826
Total bases: 6002823900
Errors: 0
Elapsed seconds: 58.032
example/260R15336-T_L1_1.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_1.fq.gz: quality=Phred33
example/260R15336-T_L1_1.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
example/260R15336-T_L1_2.fq.gz: reads=20009413, bases=3001411950, errors=0
example/260R15336-T_L1_2.fq.gz: quality=Phred33
example/260R15336-T_L1_2.fq.gz: platform=BGI/MGI confidence=1.000 sampled_reads=80000
```


## illumina数据测试

```sh
cargo run --release -- --read1 illumina_R1.fq --read2 illumina_R2.fq --detect-quality --strict-bases --json-report illumina_report.json --infer-platform
```



```sh
cargo run --release -- --read1 example/222R0096-T_L2_1.fq.gz --read2 example/222R0096-T_L2_2.fq.gz --detect-quality --strict-bases --json-report 222R0096-T_report.json --infer-platform --threads 0

cargo run --release -- --read1 example/222R0096-T_L2_1.fq.gz --read2 example/222R0096-T_L2_2.fq.gz --detect-quality --strict-bases --json-report 222R0096-T_report.json --infer-platform --threads 0 --pigz --batch-size 81920
```

## MGI测序

```sh
cargo run --release -- --read1 MGI_R1.fq --read2 MGI_R2.fq --detect-quality --strict-bases --json-report MGI_report.json --infer-platform
```



```sh
cargo run --release -- --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 0

cargo run --release -- --read1 example/260R15336-T_L1_1.fq.gz --read2 example/260R15336-T_L1_2.fq.gz --detect-quality --strict-bases --json-report 260R15336-T_report.json --infer-platform --threads 8 --pigz --batch-size 81920
```

**未推断的测序仪：**

- Ion Torrent：header 格式变化较多，容易误判
- 454 / SOLiD：老平台，格式不统一，实际使用少
- Element / Ultima / Singular 等新平台：FASTQ header 没有足够稳定的公开通用特征时，推断可靠性有限

## ONT测序

```sh
cargo run --release -- --read1 CRR947772_part.fastq --detect-quality --strict-bases --json-report  CRR947772_part_report.json --infer-platform
```

## PacBio测序

- fastq经过处理，校验 平台失败。

```sh
cargo run --release -- --read1 CRR1667053_part.fq --detect-quality --strict-bases --json-report  CRR1667053_part_report.json --infer-platform
```

- 

```sh
cargo run --release -- --read1 CRR730507_part.fq --detect-quality --strict-bases --json-report  CRR730507_part_report.json --infer-platform
```

