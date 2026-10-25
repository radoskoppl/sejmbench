#!/bin/bash
# Full-text druki pipeline: download PDFs, extract text, push to Hub. Resumable.
cd ~/sejmbench
PY=~/sejm-venv/bin/python3
until $PY ~/download_druki.py && $PY ~/extract_druki.py; do
  echo "RESTART $(date)" >> /home/porwat/druki-pipeline.log
  sleep 60
done
echo "PIPELINE COMPLETE $(date)" >> /home/porwat/druki-pipeline.log
