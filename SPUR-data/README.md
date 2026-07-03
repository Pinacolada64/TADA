`convert_from_gbbs_tool.py`: A first attempt (with some help from Claude AI) at a utility which works with [GBBS Message Tool](https://github.com/bernstbj/gbbs/blob/main/gbbsmsgtool.py) to turn a subdirectory of uncompressed room data files into JSON.

`gbbsmsgtool.py` itself lives in `server/tools/gbbsmsgtool.py`.

`python3 ../server/tools/gbbsmsgtool.py extract ROOM.LEVEL1 --output-dir level-1/
`

Suggested command-line:

`python3 convert_from_gbbs_tool.py --output level-1/level-1.json level-1/`

* sets output directory to `level-1/` and filename to `level-1.json`