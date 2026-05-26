#!/usr/bin/bash

# 2024.04.08
# v0.1.1 修改从md5文件中抓取fastq文件的后缀

# https://ngdc.cncb.ac.cn/gsa-human/file/exportExcelFile?fileName=/webdb/gsagroup/webApplications/gsa_human_20200410/gsa-human/batchExcel/human/HRA000425/HRA000425.xlsx&study_id=394&requestFlag=0

# https://download.cncb.ac.cn/gsa-human/HRA000425/


# https://ngdc.cncb.ac.cn/gsa-human/file/exportExcelFile?fileName=/webdb/gsagroup/webApplications/gsa_human_20200410/gsa-human/batchExcel/human/HRA005386/HRA005386.xlsx&study_id=7684&requestFlag=0

# https://download.cncb.ac.cn/gsa/CRA000228

# 检查网页可及性
# wget -q --spider --timeout=5 --tries=3  -o /dev/null  https://download.cncb.ac.cn/gsa-human/HRA005386

# grep 并不能通过管道符获取200状态。

# https://download.cncb.ac.cn/gsa/CRA000112/

# 2025.06.10
# v0.2.1 修改从md5文件中抓取fastq文件的后缀
# 脚本升级思路： 通过爬取搜索界面
# https://ngdc.cncb.ac.cn/gsa/browse/CRA021305 # https://ngdc.cncb.ac.cn/ettrans?filePath=/gsa2/CRA021305
# 抓取： 将结果放入到数组中，检查数组长度为1。
# wget -O- https://ngdc.cncb.ac.cn/gsa/browse/CRA021305 -q |grep -Po 'http[^< ]+CRA021305' |grep 'download' | sort |uniq # 2个结果，需要去重一下
# wget -O- https://ngdc.cncb.ac.cn/gsa/browse/CRA021305 -q |grep -Po 'http[^< =]+CRA021305' | sort |uniq

# 2025.10.25
# v0.2.2 添加excel表格的下载
# 下载保存了GSA的搜索界面网页源码，并从中提取ftp链接。
# 下载保存了GSA-human的搜索界面网页源码，只从中提取了study_id来下载信息表，并未从中提取ftp链接。
# 将GSA与GSA-human的ftp链接保存到了url.sh，如果该文件已经存在，则直接source url.sh。变量的赋值为url
# 利用curl POST下载GSA数据（CRA开头编号）库信息表；
# 利用curl POST下载GSA-human数据库（HRA开头编号）信息表，还要从index.html中捕获study_id=部分。
# 对于受控数据，如HRA000150，如果检测到'Controlled access'，则会打印'Warning'信息，跳出脚本。此时跳出脚本返回值为0.


function usage(){
	echo -e "Usage:bash $0 HRA000425\nThe project id must start with 'HRA' or 'CRA' or 'XD[AB]',e.g.HRA000425, CRA000112";
	echo -e "Usage:bash $0 https://download.cncb.ac.cn/gsa/CRA000112/";
	echo -e "Usage:bash $0 CRA001180 # for test, 2 samples # gsa2: CRA021305 # Controlled access: HRA000150";
	exit 1;
}

[[ $# -eq 1 ]] || usage # 无参数输入

project=$1

thisdir=$PWD
workdir=${thisdir}/gsa_info_sample_$(basename $project)
mkdir -p ${workdir} && cd ${workdir}

echo $project |grep '^[HC]RA' > /dev/null || echo $project |grep '^http' > /dev/null || echo $project | grep '^XD[AB]' > /dev/null
#echo $project |grep '^[HC]RA' > /dev/dull || echo $project |grep '^http' > /dev/dull
[[ $? -eq 0 ]] || usage

# -------------- start: 00. function --------------
function download_html(){
	# 下载到${workdir}/index.html
	project=$1
	workdir=${2:-"${workdir}"}
	[[ $project =~ ^CRA[0-9]{6}$ ]] && {
		browse_url=https://ngdc.cncb.ac.cn/gsa/browse/${project}
		echo "browse_url: ${browse_url}"
		##- 下载网页到本地 20251025
		# [[ -s ${workdir}/index.html ]] || wget -c --tries=3 -q ${browse_url} -O ${workdir}/index.html
		##- wget下载网页容易失败，改为20251225
		[[ -s ${workdir}/index.html ]] || curl -s ${browse_url} -o ${workdir}/index.html
		[[ -s ${workdir}/index.html ]] && echo "OK: ${workdir}/index.html" || { echo "ERROR: download html: 'curl -s ${browse_url} -o ${workdir}/index.html'" && exit 1; }
	}

	[[ $project =~ ^HRA[0-9]{6}$ ]] && {
		browse_url=https://ngdc.cncb.ac.cn/gsa-human/browse/${project}
		# echo "browse_url: ${browse_url}"
		##- 下载网页到本地 20251025
		# [[ -s ${workdir}/index.html ]] || wget -c --tries=3 -q ${browse_url} -O ${workdir}/index.html
		##- wget下载网页容易失败，改为20251225
		[[ -s ${workdir}/index.html ]] || curl -s ${browse_url} -o ${workdir}/index.html
		[[ -s ${workdir}/index.html ]] && echo "OK: ${workdir}/index.html" || { echo "ERROR: download html: 'curl -s ${browse_url} -o ${workdir}/index.html'" && exit 1; }
		##- 申请数据 对于需要申请的数据，跳过下载。只有index.html和excel信息表 返回值为0
		cat ${workdir}/index.html |grep 'Controlled access' > /dev/null && echo "Waring: ${project}: ${browse_url} is Controlled access." && exit 0;
	}
	# [[ ! -f ${workdir}/index.html ]] || echo "OK: ${workdir}/index.html"
}

# -------------- end:   00. function --------------


# -------------- start: 00. GSA meta excel --------
function dowload_meta_gsa(){
	project=$1 # CRA000112
	workdir=${2:-"${workdir}"}
	[[ $project =~ ^CRA[0-9]{6}$ ]] && {
		[[ -f ${workdir}/${project}.xlsx ]] && echo "OK: ${workdir}/${project}.xlsx" || \
		curl --silent 'https://ngdc.cncb.ac.cn/gsa/file/exportExcelFile' \
  		-X POST \
  		--data "type=3&dlAcession=${project}" \
  		-o ${workdir}/${project}.xlsx
	} || { echo "ERROR: failed to download ${project} metadata excel file" && exit 1; }

}

##- GSA-human中每个项目的study_id= 20251025
##- 通过下载搜索网页界面抓取链接和study_id=部分
function dowload_meta_gsa_human(){
	project=$1 # HRA006030
	workdir=${2:-"${workdir}"}
	##- 下载网页界面 20251025
	download_html ${project} ${workdir} ##- 结果 ${workdir}/index.html 20251025
	[[ $project =~ ^HRA[0-9]{6}$ ]] && {
		study_id=$(cat ${workdir}/index.html |grep 'study_id'  |grep -Po '[0-9]+') ##- HRA000425 394 # 这是HRA编号对应的study_id
		[[ -s ${workdir}/${project}.xlsx ]] && echo "OK: ${workdir}/${project}.xlsx" || \
		curl --silent -L "https://ngdc.cncb.ac.cn/gsa-human/file/exportExcelFile?fileName=/webdb/gsagroup/webApplications/gsa_human_20200410/gsa-human/batchExcel/human/${project}/${project}.xlsx&study_id=${study_id}&requestFlag=0" \
		-H 'Content-Type: application/x-www-form-urlencoded' \
  		-X POST \
  		-o ${workdir}/${project}.xlsx
	} || { echo "ERROR: failed to download ${project} metadata excel file" && exit 1; }

}

# -------------- end:   00. GSA meta excel --------
# echo ${project}
[[ ${project} =~ ^CRA[0-9]{6}$ ]] && dowload_meta_gsa ${project} ${workdir} || true;
[[ ${project} =~ ^HRA[0-9]{6}$ ]] && dowload_meta_gsa_human ${project} ${workdir} || true;

# -------------- start: 01. GSA url ---------------
# 获取项目url

## 获取ftp链接方式一：
# ## 当项目编号为http链接
# { echo $project | grep '^http' > /dev/null && url=$project; } || \
# 
# ## 当项目编号为HRA开头时
# { echo $project | grep '^HRA' > /dev/null && url="https://download.cncb.ac.cn/gsa-human/${project}"; } || \
# 
# 
# ## 当项目编号为PRJCA/CRA/XD[AB]开头时 # 过度依赖网络
# { 	{ echo $project | grep '^PRJCA' > /dev/null || echo $project | grep '^CRA' > /dev/null || echo $project | grep '^XD[AB]' > /dev/null ; } && \
# 	# 下载gsa项目编号
#   	{
# 		{ gsa=$(wget -q --tries=3 --timeout=5 -O -  https://download.cncb.ac.cn/gsa/ |grep -P -o ">\w+\/\<" |sed -e 's/>//g' -e 's/\/<//g') || \
# 			{ echo "ERROR: download GSA project ID from https://download.cncb.ac.cn/gsa/" >&2 && exit 1; } && 
# 			echo $gsa |grep "$project" > /dev/null && url="https://download.cncb.ac.cn/gsa/${project}"; } ||  \
#      	{ gsa2=$(wget -q --tries=3 --timeout=5 -O -  https://download.cncb.ac.cn/gsa2/ |grep -P -o ">\w+\/\<" |sed -e 's/>//g' -e 's/\/<//g') || \
# 			{ echo "ERROR: download GSA project ID from https://download.cncb.ac.cn/gsa2/" >&2 && exit 1;} && \
# 			echo $gsa2 |grep "$project" > /dev/null && url="https://download.cncb.ac.cn/gsa2/${project}"; } || \
# 		{ gsa3=$(wget -q --tries=3 --timeout=5 -O -  https://download.cncb.ac.cn/gsa3/ |grep -P -o ">\w+\/\<" |sed -e 's/>//g' -e 's/\/<//g') || \
# 			{ echo "ERROR: download GSA project ID from https://download.cncb.ac.cn/gsa3/" >&2 && exit 1;} && \
# 			echo $gsa3 |grep "$project" > /dev/null && url="https://download.cncb.ac.cn/gsa3/${project}"; } || \
# 		# 未检索到该编号时
# 		echo "ERROR: cannot find the project id from https://download.cncb.ac.cn/gsa/\thttps://download.cncb.ac.cn/gsa2/\thttps://download.cncb.ac.cn/gsa3/";
# 	};
#    
# } || \
# ## 当项目ID有问题，报错时
# echo "The project ID has an error!"


## 获取ftp链接方式二：
## 当项目编号为http链接
##- 保存数据的ftp链接网址到 20251025
##- 如果下载了 index.html 和 url.sh, 但是中间单独删了index.html，这里会跳过index.html下载，造成无index.html。 20251025
[[ ${project} =~ ^[CH]RA[0-9]{6}$ ]] && download_html ${project} ${workdir}; ##- 加一次下载，防止有单独删除index.html的情况

{ [[ -s ${workdir}/url.sh ]] && echo "OK: ${workdir}/url.sh" && source ${workdir}/url.sh; } || \
{

	{ echo $project | grep '^http' > /dev/null && url=$project && echo "url='${url}'" > ${workdir}/url.sh; } || \

	## 当项目编号为HRA开头时 ##- 目前还是直接可以拼接链接的。如果后续有改动，需要从index.html中提取更加稳健。
	{ echo $project | grep '^HRA' > /dev/null && url="https://download.cncb.ac.cn/gsa-human/${project}" && echo "url='${url}'" > ${workdir}/url.sh;  } || \

	## 当项目编号为CRA开头时
	{
		# browse_url=https://ngdc.cncb.ac.cn/gsa/browse/${project}
		##- 下载网页到本地 20251025
		# [[ -f ${workdir}/index.html ]] && wget -q ${browse_url} -O ${workdir}/index.html || { echo "ERROR: download html: 'wget -q ${browse_url} -O ${workdir}/index.html'" && exit 1; }
		download_html $project $workdir ##- 结果 $workdir/index.html 20251025
		arr_url=$(cat ${workdir}/index.html |grep -Po "http[^< =]+${project}" | sort |uniq)
		# echo "arr_url: ${arr_url[@]}"
		[[ ${#arr_url[@]} == 1 ]] || { echo "Not Find url in '${browse_url}'" && usage; }
		
		url=${arr_url[0]}
		echo "url='${arr_url[@]}'" > ${workdir}/url.sh
	}
}

echo Final URL: $url

#-------------- end: 01. GSA url ------------------

#-------------- start: 02.md5sum.txt --------------
md5sum=$url/md5sum.txt

md5sum_file=${workdir}/md5sum.txt
md5_file=${workdir}/MD5.txt
##- wget 方法不能使用了 20251225
# [[ -s ${md5sum_file} ]] && echo "OK: md5sum.txt exists!" || \
# { wget -c -q --tries=3 --timeout=5 -O ${md5sum_file}  $url/md5sum.txt && echo "OK: download md5sum.txt successfully!" || \
# 	{ echo "ERROR: failed to download 'md5sum.txt' " && exit 1; };
# }

##- wget 方法不能使用了,改为curl下载 20251225
[[ -s ${md5sum_file} ]] && echo "OK: md5sum.txt exists!" || \
{ curl -s -o ${md5sum_file}  $url/md5sum.txt && echo "OK: download md5sum.txt successfully!" || \
	{ echo "ERROR: failed to download 'md5sum.txt' " && exit 1; };
}

# all fastq # 抓取全部fastq # 用于下载的链接拼接部分
# declare -A all_fastq=$( cat ${md5_file} | awk -F "\t" '{print $2}' |tr '\n' ' ' ) && \
declare -A all_fastq=$(cat ${md5sum_file} | awk '{if(NF == 2) print $2}' |grep "q.gz$" |sed "s/.*$(basename ${project})\///g" |tr '\n' ' ' ) # && \
# echo ${all_fastq[@]}
# 最终用于校验的MD5文件MD5.txt
cat ${md5sum_file} |awk '{if(NF == 2) print $0}' |grep "q.gz$" |sed "s/\t.*\//\t/g" > ${md5_file}

# echo ${md5_file} 

#-------------- end: 02.md5sum.txt --------------

#-------------- start: 03.download fastq --------
## aspera fastq
# ascp -vQT -l 500m -P33001 -k 1 -i /home/zheng/.aspera/connect/etc/aspera01.openssh aspera01@download.cncb.ac.cn:gsa-human/HRA000425/HRR165457/HRR165457_f1.fastq.gz ./ 
keyfile=$HOME/.aspera/connect/etc/aspera01.openssh
[[ -f ${keyfile}  ]] && \
{
	for i in ${all_fastq[@]};do
		echo "[[ -f ./$(basename $i)  ]] && echo Skip: $(basename $i) || ascp -vQT -l 500m -P33001 -k 1 -i ~/.aspera/connect/etc/aspera01.openssh aspera01@$(echo $url |sed -e 's/https:\/\///g' -e 's/.ac.cn\//.ac.cn:/g' )/$i  ./"
	done > ${workdir}/run_download_fastq_using_aspera.sh
} || \
echo -e "ERROR: FILE not exist: ${keyfile}\nPlease download it: wget --no-clobber -c -O ${keyfile} https://ngdc.cncb.ac.cn/gsa-human/file/fileId000003/downFile"
# wget --no-clobber -c -O ${keyfile} https://ngdc.cncb.ac.cn/gsa-human/file/fileId000003/downFile

## axel fastq
for i in ${all_fastq[@]};do
	echo "axel --no-clobber -n 20 $url/$i"
done > ${workdir}/run_download_fastq_using_axel.sh

## aria2c
for i in ${all_fastq[@]};do
	echo "aria2c -c -j 16 -x 16 -s 16 $url/$i"
done > ${workdir}/run_download_fastq_using_aria2c.sh

## 增加可执行权限
chmod +x ${workdir}/run_download_fastq_using_aspera.sh
chmod +x ${workdir}/run_download_fastq_using_axel.sh
chmod +x ${workdir}/run_download_fastq_using_aria2c.sh


#-------------- end: 03.download ----------------

#-------------- start: 04.download -------------
# 最终用于校验全部文件的MD5文件 MD5_all.txt
md5_file_all=${workdir}/MD5_all.txt
cat ${md5sum_file} |awk '{if(NF == 2) print $0}' |sed "s/\t.*\//\t/g" > ${md5_file_all}
# 下载全部内容
declare -A all_files=$(cat ${md5sum_file} | awk '{if(NF == 2) print $2}' |sed "s/.*$(basename ${project})\///g" |tr '\n' ' ' ) # && \
# echo ${all_files[@]}
# 最终用于校验的MD5文件即为md5sum.txt
keyfile=$HOME/.aspera/connect/etc/aspera01.openssh
[[ -f ${keyfile}  ]] && \
{
	for i in ${all_files[@]};do
		echo "[[ -f ./$(basename $i)  ]] && echo Skip: $(basename $i) || ascp -vQT -l 500m -P33001 -k 1 -i ~/.aspera/connect/etc/aspera01.openssh aspera01@$(echo $url |sed -e 's/https:\/\///g' -e 's/.ac.cn\//.ac.cn:/g' )/$i  ./"
	done > ${workdir}/run_download_all_files_using_aspera.sh
} || \
echo -e "ERROR: FILE not exist: ${keyfile}\nPlease download it: wget --no-clobber -c -O ${keyfile} https://ngdc.cncb.ac.cn/gsa-human/file/fileId000003/downFile"
# wget --no-clobber -c -O ${keyfile} https://ngdc.cncb.ac.cn/gsa-human/file/fileId000003/downFile

## axel fastq
for i in ${all_files[@]};do
	echo "axel --no-clobber -n 20 $url/$i"
done > ${workdir}/run_download_all_files_using_axel.sh

## aria2c
for i in ${all_files[@]};do
	echo "aria2c -c -j 16 -x 16 -s 16 $url/$i"
done > ${workdir}/run_download_all_files_using_aria2c.sh

## 增加可执行权限
chmod +x ${workdir}/run_download_all_files_using_aspera.sh
chmod +x ${workdir}/run_download_all_files_using_axel.sh
chmod +x ${workdir}/run_download_all_files_using_aria2c.sh


#-------------- end: 04.download ----------------
cd $thisdir
exit 0
