#!/usr/bin/env Rscript


suppressWarnings(suppressMessages(library(argparser))) #https://github.com/cran/argparser

# 参数设置
p <- arg_parser("e.g.: Rscript run_get_bioinfo_from_NCBI_SRA.r -i SRR9054070 # 3个reads 的 run\n
e.g.: Rscript run_get_bioinfo_from_NCBI_SRA.r -i SRR8869110 # 10X cellranger bam\n
Function: Get sample information from NCBI SRA.\n
Author: Shimao Zheng, zhengshimao007@163.com\n
Create: 2024.05.20\n
Update: -\n
Version: 0.0.1\n
Notes:  Follow my WeChat public account 'The_Elder_Student'\n
conda install conda-forge::r-rentrez conda-forge::r-magrittr conda-forge::r-stringr conda-forge::r-dplyr conda-forge::r-argparser\n
  ")

p <- add_argument(p, "--input", help="input: run ID of SRA", type="character")
#p <- add_argument(p, "--pattern", help="limit pattern of input files using regular expression in R language",type="character",default = "_gene_level.count$")
p <- add_argument(p, "--output_dir", help="output directory: an existent directory", type="character", default = "./")
#p <- add_argument(p, "--prefix", help="give the file of output matrix a prefix like '<output_prefix>_genes.*'", type="character",default = "result_gene",short = "-f")
#p <- add_argument(p, "--id", help="colname of gene or transcript in results.", type="character",default = "gene_id",short = "-f")

# 参数解析与定义
argv <- parse_args(p)
srr <- argv$input
output_dir <- argv$output_dir

# 参数处理
if(is.na(srr)) {
  system(command = "run_get_bioinfo_from_NCBI_SRA.R -h")
  quit(save = "no", status = 1)
}

result_file <- paste0(output_dir,"/",srr,"_infor.xls")

# 测试用
# srr <- "SRR9054070" # SRR9054070 多个reads(单细胞)  # SRR8869110 一个bam多个地址

# 加载R包
suppressWarnings(suppressMessages(library(rentrez)))
suppressWarnings(suppressMessages(library(magrittr)))
# library(XML)
suppressWarnings(suppressMessages(library(stringr)))
suppressWarnings(suppressMessages(library(dplyr)))

# 测试结果文件 
## 如果结果文件已存在，则跳出
if(file.exists(result_file)) {
  cat("Skip: ",result_file,"\n")
  quit(save = "no", status = 0)
}

# 代码主体
ef <- entrez_fetch(db = "sra", id = srr, rettype = "xml") 

# xml <- ef %>% xmlTreeParse()
# xml # 利用xml查看提取的区块

# 按<SRAFile cluster> 到</SRAFile>分模块处理

srafiles <- str_extract_all(ef, "<SRAFile cluster.*</SRAFile>")[[1]]

srafiles_list <- str_split(srafiles,"</SRAFile>")[[1]]
srafiles_list <- srafiles_list[!srafiles_list %in% ""] # 去除最后一个空值

file_list <- list()

for (x in seq_along(srafiles_list)) {
  #tmp_list <- list(cluster=c(), url = c())
  sra_tmp <- srafiles_list[x] # 向量
  
  # part1 
  sra_cluster <- str_extract_all(sra_tmp,"<SRAFile cluster.*?>")[[1]] %>% str_remove("<") %>% str_remove_all("/>") # SRAFile cluster 每个模块只有一个。
  name_cluster <- str_extract_all(sra_cluster, " \\S+?=")[[1]] %>% str_remove_all("[ =]")
  mat_cluster <- sra_cluster %>% str_extract_all("\".*?\"",simplify = TRUE)
  mat_cluster <- apply(mat_cluster, 2, function(x){str_remove_all(x, "\\\"")})
  names(mat_cluster) <- name_cluster
  mat_cluster <- t(mat_cluster) # matrix，单行
  # tmp_list[["cluster"]] <- mat_cluster# append(mat_cluster)
  
  # part2
  sra_url <- str_extract_all(sra_tmp,"<Alternatives url.*?>")[[1]] %>% str_remove("<") %>% str_remove_all("/>")
  url <- lapply(sra_url, function(y){
    name_url <- str_extract_all(y, " \\S+?=")[[1]] %>% str_remove_all("[ =]")
    mat_url <-  str_extract_all(y, "\".*?\"")[[1]]
    #mat_url <- apply(mat_url, 2, function(y){str_remove_all(y, "\\\"")})
    mat_url <- str_remove_all(mat_url, "\\\"")
    names(mat_url) <- name_url
    return(mat_url)
  })
  url <- do.call(rbind,url) # matrix
  # tmp_list[["url"]] <- url
  
  # part3
  # cluster和url有重复列，如url列
  # cluster中列是重复的，由于后面nrow(url) >1重复该列的url并不是实际的地址，因此去掉cluter中的列。
  name_cluster <- colnames(mat_cluster)[!(colnames(mat_cluster) %in% c("url"))] # 去除url部分。
  mat_cluster <- mat_cluster[!(colnames(mat_cluster) %in% c("url"))]
  mat_cluster <- mat_cluster %>% as.matrix() %>% t()
  colnames(mat_cluster) <- name_cluster
  
  # part4
  # 合并cluster和url
  if(nrow(url) >1){
    mat_cluster <- mat_cluster[rep(1, nrow(url)),]
    # mat_cluster <- mat_cluster[,!(colnames(mat_cluster) %in% c("url"))]
    file_list[[x]] <- cbind(mat_cluster,url) %>% as.data.frame()
  }else{
    
    file_list[[x]] <- cbind(mat_cluster,url) %>% as.data.frame()
  }
  
}
# 每个元素的列名
# lapply(file_list, function(x){
#   colnames(x)
# })
# 每个元素的列名
# [1] "cluster"       "filename"      "size"          "date"          "md5"           "version"       "semantic_name" "supertype"    
# [9] "sratoolkit"    "url"           "free_egress"   "access_type"   "org" 

df <- do.call(rbind, file_list) %>% mutate(run = srr, .before = 1)

if(nrow(df) > 0){
  write.table(df,file = result_file, sep = "\t", na = "", quote = F, row.names = F, col.names = T)
  cat("OK: ",result_file,"\n")
  quit(save = "no", status = 0)
}else{
  quit(save = "no", status = 1)
}





