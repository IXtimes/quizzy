PRIMARY = "#d8220e"
PRIMARY_HOVER = "#8c1309"
SECONDARY = "#858e96"
SECONDARY_HOVER = "#5c646b"
SUCCESS = "#469307"
SUCCESS_HOVER = "#2d6505"
INFO = "#0099ce"
INFO_HOVER = "#006b9c"
PARTIAL = "#285cc4"
PARTIAL_HOVER = "#1a4081"
WARNING = "#d88220"
WARNING_HOVER = "#a75c19"
DANGER = "#9a479e"
DANGER_HOVER = "#73377a"
FLAG_HIGHLIGHT = "#fff187"
FLAG_HIGHLIGHT_HOVER = "#edda47"
LIGHT = "#f2f2f2"
DARK = "#3b3d3f"
BG = "#fcfcfc"
BG_HOVER = "#f0f0f0"
FG = "#3b3d3f"
SELECT_BG = "#a9afb6"
SELECT_BG_HOVER = "#989da3"
SELECT_FG = "#ffffff"
BORDER = "#858e96"
INPUT_FG = "#3b3d3f"
INPUT_BG = "#fcfcfc"
GRADE_COLOR_SCALE = (PRIMARY, PRIMARY, PRIMARY, PRIMARY, PRIMARY, PRIMARY, DANGER, WARNING, SUCCESS, INFO)

FONT = 'Tahoma'
CODE_FONT = 'Consolas'
SMALL_FONT_SIZE = 9
NORMAL_FONT_SIZE = 12
TITLE_FONT_SIZE = 24
HEADER_FONT_SIZE = 60

import sys
import os

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)