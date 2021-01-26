#!/bin/bash
#
# Process data.
#
# Usage:
#   ./process_data.sh <SUBJECT> <PATH_GRADCORR_FILE>
#
# Manual segmentations or labels should be located under:
# PATH_DATA/derivatives/labels/SUBJECT/anat/
#
# Authors: Sandrine Bédard, Julien Cohen-Adad

set -x
# Immediately exit if error
set -e -o pipefail

# Exit if user presses CTRL+C (Linux) or CMD+C (OSX)
trap "echo Caught Keyboard Interrupt within script. Exiting now.; exit" INT

# Retrieve input params
SUBJECT=$1
PATH_GRADCORR_FILE=$2 #to remove

# get starting time:
start=`date +%s`

# FUNCTIONS
# ==============================================================================

# Check if manual label already exists. If it does, copy it locally. If it does
# not, perform labeling.
label_if_does_not_exist(){
  local file="$1"
  local file_seg="$2"
  # Update global variable with segmentation file name
  FILELABEL="${file}_labels"
  FILELABELMANUAL="${PATH_DATA}/derivatives/labels/${SUBJECT}/anat/${FILELABEL}-manual.nii.gz"
  echo "Looking for manual label: $FILELABELMANUAL"
  if [[ -e $FILELABELMANUAL ]]; then
    echo "Found! Using manual labels."
    rsync -avzh $FILELABELMANUAL ${FILELABEL}.nii.gz
  else
    echo "Not found. Proceeding with automatic labeling."
    # Generate labeled segmentation
    sct_label_vertebrae -i ${file}.nii.gz -s ${file_seg}.nii.gz -c t1
    # Create label at the C2-C3 intervertebral disc
    sct_label_utils -i ${file_seg}_labeled_discs.nii.gz -keep 3 -o ${FILELABEL}.nii.gz
  fi
}

# Check if manual segmentation already exists. If it does, copy it locally. If it does not, perform segmentation.
segment_if_does_not_exist(){
  local file="$1"
  local contrast="$2"
  folder_contrast="anat"

  # Update global variable with segmentation file name
  FILESEG="${file}_seg"
  FILESEGMANUAL="${PATH_DATA}/derivatives/labels/${SUBJECT}/${folder_contrast}/${FILESEG}-manual.nii.gz"
  echo
  echo "Looking for manual segmentation: $FILESEGMANUAL"
  if [[ -e $FILESEGMANUAL ]]; then
    echo "Found! Using manual segmentation."
    rsync -avzh $FILESEGMANUAL ${FILESEG}.nii.gz
    sct_qc -i ${file}.nii.gz -s ${FILESEG}.nii.gz -p sct_deepseg_sc -qc ${PATH_QC} -qc-subject ${SUBJECT}
  else
    echo "Not found. Proceeding with automatic segmentation."
    # Segment spinal cord
    sct_deepseg_sc -i ${file}.nii.gz -c $contrast -qc ${PATH_QC} -qc-subject ${SUBJECT}
  fi
}

# SCRIPT STARTS HERE
# ==============================================================================
# Display useful info for the log, such as SCT version, RAM and CPU cores available
sct_check_dependencies -short

# Go to folder where data will be copied and processed
cd ${PATH_DATA_PROCESSED}
# Copy list of participants in processed data folder
if [[ ! -f "participants.tsv" ]]; then
  rsync -avzh $PATH_DATA/participants.tsv .
fi
# Copy list of participants in resutls folder
if [[ ! -f $PATH_RESULTS/"participants.tsv" ]]; then
  rsync -avzh $PATH_DATA/participants.tsv $PATH_RESULTS/"participants.tsv"
fi
# Copy source images
rsync -avzh $PATH_DATA/$SUBJECT .
# Go to anat folder where all structural data are located
cd ${SUBJECT}/anat/

# T1w
# ------------------------------------------------------------------------------
file_t1="${SUBJECT}_T1w"

# Segment spinal cord (only if it does not exist)
segment_if_does_not_exist $file_t1 "t1"
file_t1_seg=$FILESEG

# Create label at the C2-C3 intervertebral disc (only if it does not exist) 
label_if_does_not_exist ${file_t1} ${file_t1_seg}

file_label=$FILELABEL
# Register to PAM50 template
sct_register_to_template -i ${file_t1}.nii.gz -s ${file_t1_seg}.nii.gz -ldisc ${file_label}.nii.gz -c t1 -param step=1,type=seg,algo=centermassrot:step=2,type=seg,algo=syn,slicewise=1,smooth=0,iter=5:step=3,type=im,algo=syn,slicewise=1,smooth=0,iter=3 -qc ${PATH_QC} -qc-subject ${SUBJECT}
# Rename warping fields for clarity
mv warp_template2anat.nii.gz warp_template2T1w.nii.gz
mv warp_anat2template.nii.gz warp_T1w2template.nii.gz
# Warp template without the white matter atlas (we don't need it at this point)
sct_warp_template -d ${file_t1}.nii.gz -w warp_template2T1w.nii.gz -a 0 -ofolder label_T1w
# Generate QC report to assess vertebral labeling
sct_qc -i ${file_t1}.nii.gz -s label_T1w/template/PAM50_levels.nii.gz -p sct_label_vertebrae -qc ${PATH_QC} -qc-subject ${SUBJECT}
# Flatten scan along R-L direction (to make nice figures)
sct_flatten_sagittal -i ${file_t1}.nii.gz -s ${file_t1_seg}.nii.gz
# Compute average cord CSA between C2 and C3
sct_process_segmentation -i ${file_t1_seg}.nii.gz -vert 2:3 -vertfile label_T1w/template/PAM50_levels.nii.gz -o ${PATH_RESULTS}/csa-SC_T1w.csv -append 1

# T2
# ------------------------------------------------------------------------------
file_t2="${SUBJECT}_T2w"

# Segment spinal cord (only if it does not exist)
# Note: we specify the "t1" contrast for the automatic segmentation because the T2-FLAIR contrast is more similar to the T1 MPRAGE (this is due to the inversion recovery 'IR' in 'FLAIR' pulse which nulls the CSF signal)
segment_if_does_not_exist $file_t2 "t1"
file_t2_seg=$FILESEG
# Flatten scan along R-L direction (to make nice figures) 
sct_flatten_sagittal -i ${file_t2}.nii.gz -s ${file_t2_seg}.nii.gz

# Dilate t2 cord segmentation to use as mask for registration
file_t2_mask="${file_t2_seg}_dil"
ImageMath 3 ${file_t2_mask}.nii.gz MD ${file_t2_seg}.nii.gz 40

# Register T1w image to T2w FLAIR (rigid)
isct_antsRegistration -d 3 -m CC[ ${file_t2}.nii.gz , ${file_t1}.nii.gz , 1, 4] -t Rigid[0.5] -c 50x20x10 -f 8x4x2 -s 0x0x0 -o [_rigid, ${file_t1}_reg.nii.gz] -v 1 -x ${file_t2_mask}.nii.gz

# Apply transformation to T1w vertebral level
isct_antsApplyTransforms -i label_T1w/template/PAM50_levels.nii.gz -r ${file_t2}.nii.gz -t _rigid0GenericAffine.mat -o PAM50_levels2${file_t2}.nii.gz -n NearestNeighbor

# Generate QC report to assess T1w registration to T2w
sct_qc -i ${file_t1}_reg_mask.nii.gz -s PAM50_levels2${file_t2}.nii.gz -d ${file_t2}.nii.gz -p sct_register_multimodal -qc ${PATH_QC} -qc-subject ${SUBJECT}

# Generate QC report to assess T2w vertebral labeling
sct_qc -i ${file_t2}.nii.gz -s PAM50_levels2${file_t2}.nii.gz -p sct_label_vertebrae -qc ${PATH_QC} -qc-subject ${SUBJECT}

# Compute average cord CSA between C2 and C3
sct_process_segmentation -i ${file_t2_seg}.nii.gz -vert 2:3 -vertfile PAM50_levels2${file_t2}.nii.gz -o ${PATH_RESULTS}/csa-SC_T2w.csv -append 1

# Verify presence of output files and write log file if error
# ------------------------------------------------------------------------------
FILES_TO_CHECK=(
  "${SUBJECT}_T1w_seg.nii.gz" 
  "${SUBJECT}_T2w_seg.nii.gz"
  "${SUBJECT}_T1w_labels.nii.gz"
  "label_T1w/template/PAM50_levels.nii.gz"
  "PAM50_levels2${SUBJECT}_T2w.nii.gz"
  
)
pwd
for file in ${FILES_TO_CHECK[@]}; do
  if [[ ! -e $file ]]; then
    echo "${SUBJECT}/anat/${file} does not exist" >> $PATH_LOG/_error_check_output_files.log
  fi
done

# Display useful info for the log
end=`date +%s`
runtime=$((end-start))
echo
echo "~~~"
echo "SCT version: `sct_version`"
echo "Ran on:      `uname -nsr`"
echo "Duration:    $(($runtime / 3600))hrs $((($runtime / 60) % 60))min $(($runtime % 60))sec"
echo "~~~"
