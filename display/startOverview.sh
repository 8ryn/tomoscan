#!/bin/bash
DISPLAY_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

phoebus -resource "file:$DISPLAY_PATH/overview.bob?P=ADT:USER1:&R=CAM:&M=motorS:&A=axis1&app=display_runtime"
