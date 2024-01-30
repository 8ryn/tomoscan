#!/bin/bash
DISPLAY_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

phoebus -resource "file:$DISPLAY_PATH/overview.bob?P=TA1:CT_CAM:&R=cam1:&M=TA1:SMC100:&A=m1&app=display_runtime"
