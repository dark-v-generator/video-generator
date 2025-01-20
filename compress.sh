#!/bin/bash

path=$1
output_folder="output"
mkdir -p "$output_folder"

for filepath in $path/*.mp4; do
    filename=$(basename $filepath)
    ffmpeg -i "$filepath" -vcodec libx265 -crf 28 "$output_folder/$filename"
done