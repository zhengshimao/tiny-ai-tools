#!/usr/bin/env bash
set -euo pipefail

# damha_reference.fasta (92 B)
wget -c --content-disposition -O 'damha_reference.fasta' 'https://zenodo.org/api/records/15596052/files/damha_reference.fasta/content'
# flair_sep (1.40 KiB)
wget -c --content-disposition -O 'flair_sep' 'https://zenodo.org/api/records/15596052/files/flair_sep/content'
# NL43_GFP_R2R.fasta (9.60 KiB)
wget -c --content-disposition -O 'NL43_GFP_R2R.fasta' 'https://zenodo.org/api/records/15596052/files/NL43_GFP_R2R.fasta/content'
# damha_m6A_synthesizedFragment.tar.xz (43.91 MiB)
wget -c --content-disposition -O 'damha_m6A_synthesizedFragment.tar.xz' 'https://zenodo.org/api/records/15596052/files/damha_m6A_synthesizedFragment.tar.xz/content'
# 11CI_Jurkats_HIV-GFP_cART.tar.xz (4.56 GiB)
wget -c --content-disposition -O '11CI_Jurkats_HIV-GFP_cART.tar.xz' 'https://zenodo.org/api/records/15596052/files/11CI_Jurkats_HIV-GFP_cART.tar.xz/content'
# P5S2_PLWH_CD4.tar.xz (2.04 MiB)
wget -c --content-disposition -O 'P5S2_PLWH_CD4.tar.xz' 'https://zenodo.org/api/records/15596052/files/P5S2_PLWH_CD4.tar.xz/content'
# 7C_Jurkats_HIV-GFP.tar.xz (2.96 GiB)
wget -c --content-disposition -O '7C_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/7C_Jurkats_HIV-GFP.tar.xz/content'
# 11BH_Jurkats_HIV-GFP.tar.xz (4.41 GiB)
wget -c --content-disposition -O '11BH_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/11BH_Jurkats_HIV-GFP.tar.xz/content'
# 11BH_RnaseH_Jurkats_HIV-GFP.tar.xz (33.28 MiB)
wget -c --content-disposition -O '11BH_RnaseH_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/11BH_RnaseH_Jurkats_HIV-GFP.tar.xz/content'
# P6S_PLWH_CD4.tar.xz (1.71 MiB)
wget -c --content-disposition -O 'P6S_PLWH_CD4.tar.xz' 'https://zenodo.org/api/records/15596052/files/P6S_PLWH_CD4.tar.xz/content'
# 13B_P8C_HIV.tar.xz (33.28 MiB)
wget -c --content-disposition -O '13B_P8C_HIV.tar.xz' 'https://zenodo.org/api/records/15596052/files/13B_P8C_HIV.tar.xz/content'
# 14H_CD4_HIV_Supernatant.tar.xz (1.67 GiB)
wget -c --content-disposition -O '14H_CD4_HIV_Supernatant.tar.xz' 'https://zenodo.org/api/records/15596052/files/14H_CD4_HIV_Supernatant.tar.xz/content'
# damha_unmodified_synthesizedFragment.tar.xz (175.08 MiB)
wget -c --content-disposition -O 'damha_unmodified_synthesizedFragment.tar.xz' 'https://zenodo.org/api/records/15596052/files/damha_unmodified_synthesizedFragment.tar.xz/content'
# STM2457_0uM_Jurkats_HIV-GFP.tar.xz (1.28 GiB)
wget -c --content-disposition -O 'STM2457_0uM_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/STM2457_0uM_Jurkats_HIV-GFP.tar.xz/content'
# Jurkat_antisense.tar.xz (4.43 MiB)
wget -c --content-disposition -O 'Jurkat_antisense.tar.xz' 'https://zenodo.org/api/records/15596052/files/Jurkat_antisense.tar.xz/content'
# t7inVitro_fullm5C.tar.xz (40.19 MiB)
wget -c --content-disposition -O 't7inVitro_fullm5C.tar.xz' 'https://zenodo.org/api/records/15596052/files/t7inVitro_fullm5C.tar.xz/content'
# t7inVitro_fullm6A.tar.xz (2.12 GiB)
wget -c --content-disposition -O 't7inVitro_fullm6A.tar.xz' 'https://zenodo.org/api/records/15596052/files/t7inVitro_fullm6A.tar.xz/content'
# t7inVitro_fullPsi.tar.xz (554.90 MiB)
wget -c --content-disposition -O 't7inVitro_fullPsi.tar.xz' 'https://zenodo.org/api/records/15596052/files/t7inVitro_fullPsi.tar.xz/content'
# t7inVitro_unmodified.tar.xz (1006.23 MiB)
wget -c --content-disposition -O 't7inVitro_unmodified.tar.xz' 'https://zenodo.org/api/records/15596052/files/t7inVitro_unmodified.tar.xz/content'
# 11BH_PAS_Jurkats_HIV-GFP.tar.xz (4.40 GiB)
wget -c --content-disposition -O '11BH_PAS_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/11BH_PAS_Jurkats_HIV-GFP.tar.xz/content'
# STM2457_30uM_Jurkats_HIV-GFP.tar.xz (5.84 GiB)
wget -c --content-disposition -O 'STM2457_30uM_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/STM2457_30uM_Jurkats_HIV-GFP.tar.xz/content'
# modkit_process_dorado1.0 (4.54 KiB)
wget -c --content-disposition -O 'modkit_process_dorado1.0' 'https://zenodo.org/api/records/15596052/files/modkit_process_dorado1.0/content'
# NL43_AF324493.2_R2R.fasta (8.98 KiB)
wget -c --content-disposition -O 'NL43_AF324493.2_R2R.fasta' 'https://zenodo.org/api/records/15596052/files/NL43_AF324493.2_R2R.fasta/content'
# 11E_Jurkats_HIV-GFP.tar.xz (375.56 MiB)
wget -c --content-disposition -O '11E_Jurkats_HIV-GFP.tar.xz' 'https://zenodo.org/api/records/15596052/files/11E_Jurkats_HIV-GFP.tar.xz/content'
# 10D_CD4_HIV.tar.xz (864.42 MiB)
wget -c --content-disposition -O '10D_CD4_HIV.tar.xz' 'https://zenodo.org/api/records/15596052/files/10D_CD4_HIV.tar.xz/content'
# 11F_Jurkats_HIV-GFP_cART.tar.xz (350.61 MiB)
wget -c --content-disposition -O '11F_Jurkats_HIV-GFP_cART.tar.xz' 'https://zenodo.org/api/records/15596052/files/11F_Jurkats_HIV-GFP_cART.tar.xz/content'
# 7E_Jurkats_HIV-GFP_cART.tar.xz (611.82 MiB)
wget -c --content-disposition -O '7E_Jurkats_HIV-GFP_cART.tar.xz' 'https://zenodo.org/api/records/15596052/files/7E_Jurkats_HIV-GFP_cART.tar.xz/content'
