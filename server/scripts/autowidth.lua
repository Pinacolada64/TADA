-- pandoc filter for md_to_pdf.sh: size each table's columns by their
-- contents, as a browser lays out an auto-width table.
--
-- Without this, pandoc gives a pipe table either no widths (every row fits
-- in 72 characters of source: plain `l` columns that never wrap, so a long
-- cell runs off the page) or widths in proportion to the dashes in its
-- |---|---| line (any row is longer), which wastes room on short columns
-- and squeezes long ones. Instead: if every column fits on one line, each
-- gets its natural width (the table can be narrower than the page);
-- otherwise each gets at least its longest word, and the room left over
-- goes to the columns in proportion to how much more they'd need to fit.
-- Widths are estimated from the font's character widths, in ems of the 10pt
-- body font.
-- A heading counts as one long word, so "Merge commit" stays on one line;
-- when even the longest words don't all fit, the headings are kept on one
-- line first and the long words (branch names, code) are what wrap.
--
-- Adapted from ImageBBS3's tools/pandoc/docbook-latex.lua (the widths) and
-- docs/extensions/table-heading-widths.rb (the headings).
--
-- Usage: pandoc --lua-filter=scripts/autowidth.lua ... (md_to_pdf.sh does)

local TEXT_WIDTH = 46.975 -- US Letter less 1in margins: 469.75pt
local TABCOLSEP = 0.6     -- 6pt each side of a column
-- room to spare in every column, so that rounding (pandoc writes each
-- column's share to 4 decimals) can't leave a word a hair too wide for its
-- column, which TeX would then break at a hyphen: -drive8type as - drive8type
local SLACK = 0.2
local EM_TEXT = 0.5       -- a character not in EM_CHAR (accented, emoji)
local EM_SPACE = 0.333    -- interword space in Latin Modern Roman
local EM_CODE = 0.525     -- every character in Latin Modern Mono

-- printable ASCII in Latin Modern Roman 10pt, by code point (from cmr10.tfm,
-- whose glyphs LM copies; < > _ | have other glyphs in cmr10's OT1 slots)
local EM_CHAR = {
  [33]=0.278, [34]=0.5, [35]=0.833, [36]=0.5, [37]=0.833, [38]=0.778,
  [39]=0.278, [40]=0.389, [41]=0.389, [42]=0.5, [43]=0.778, [44]=0.278,
  [45]=0.333, [46]=0.278, [47]=0.5, [48]=0.5, [49]=0.5, [50]=0.5, [51]=0.5,
  [52]=0.5, [53]=0.5, [54]=0.5, [55]=0.5, [56]=0.5, [57]=0.5, [58]=0.278,
  [59]=0.278, [60]=0.778, [61]=0.778, [62]=0.778, [63]=0.472, [64]=0.778,
  [65]=0.75, [66]=0.708, [67]=0.722, [68]=0.764, [69]=0.681, [70]=0.653,
  [71]=0.785, [72]=0.75, [73]=0.361, [74]=0.514, [75]=0.778, [76]=0.625,
  [77]=0.917, [78]=0.75, [79]=0.778, [80]=0.681, [81]=0.778, [82]=0.736,
  [83]=0.556, [84]=0.722, [85]=0.75, [86]=0.75, [87]=1.028, [88]=0.75,
  [89]=0.75, [90]=0.611, [91]=0.278, [92]=0.5, [93]=0.278, [94]=0.5,
  [95]=0.5, [96]=0.278, [97]=0.5, [98]=0.556, [99]=0.444, [100]=0.556,
  [101]=0.444, [102]=0.306, [103]=0.5, [104]=0.556, [105]=0.278,
  [106]=0.306, [107]=0.528, [108]=0.278, [109]=0.833, [110]=0.556,
  [111]=0.5, [112]=0.556, [113]=0.528, [114]=0.392, [115]=0.394,
  [116]=0.389, [117]=0.556, [118]=0.528, [119]=0.722, [120]=0.528,
  [121]=0.528, [122]=0.444, [123]=0.5, [124]=0.278, [125]=0.5, [126]=0.5
}

local measure_blocks

-- natural (one-line) and minimum (longest word) width of some inlines
local function measure_inlines(inlines)
  local lines, line, word, min = {}, 0, 0, 0
  local function end_word() min = math.max(min, word); word = 0 end
  local function end_line() end_word(); lines[#lines + 1] = line; line = 0 end
  local function add(text, code)
    for _, c in utf8.codes(text) do
      if c == 32 then
        end_word()
        line = line + (code and EM_CODE or EM_SPACE)
      else
        local em = code and EM_CODE or EM_CHAR[c] or EM_TEXT
        word, line = word + em, line + em
      end
    end
  end
  pandoc.Inlines(inlines):walk({
    Str = function(s) add(s.text, false) end,
    Code = function(c) add(c.text, true) end,
    Space = function() add(' ', false) end,
    SoftBreak = function() add(' ', false) end,
    LineBreak = end_line,
  })
  end_line()
  return math.max(table.unpack(lines)), min
end

-- every cell of a table, with the column it starts in
local function cells(tbl)
  local rows = {}
  for _, r in ipairs(tbl.head.rows) do rows[#rows + 1] = r end
  for _, body in ipairs(tbl.bodies) do
    for _, r in ipairs(body.head) do rows[#rows + 1] = r end
    for _, r in ipairs(body.body) do rows[#rows + 1] = r end
  end
  for _, r in ipairs(tbl.foot.rows) do rows[#rows + 1] = r end
  local result = {}
  for n, row in ipairs(rows) do
    local col = 1
    for _, cell in ipairs(row.cells) do
      result[#result + 1] = { col = col, cell = cell, head = n <= #tbl.head.rows }
      col = col + cell.col_span
    end
  end
  return result
end

-- natural and minimum widths of each column, and of its heading
local function measure_columns(tbl)
  local nat, min, head = {}, {}, {}
  for i = 1, #tbl.colspecs do nat[i], min[i], head[i] = 0, 0, 0 end
  for _, c in ipairs(cells(tbl)) do
    if c.cell.col_span == 1 then
      local n, m = measure_blocks(c.cell.contents)
      nat[c.col] = math.max(nat[c.col], n)
      min[c.col] = math.max(min[c.col], m)
      if c.head then head[c.col] = math.max(head[c.col], n) end
    end
  end
  return nat, min, head
end

function measure_blocks(blocks)
  local nat, min = 0, 0
  for _, b in ipairs(blocks) do
    local n, m = 0, 0
    if b.t == 'Para' or b.t == 'Plain' then
      n, m = measure_inlines(b.content)
    elseif b.t == 'CodeBlock' then
      for line in (b.text .. '\n'):gmatch('(.-)\n') do
        n = math.max(n, utf8.len(line) * EM_CODE)
      end
      m = n
    elseif b.content then
      n, m = measure_blocks(b.content)
    end
    nat, min = math.max(nat, n), math.max(min, m)
  end
  return nat, min
end

-- Three widths per column, each at least the one before: its heading on one
-- line, its longest word (or heading) on one line, and everything on one
-- line. Each column gets the widest of these that all the columns can have
-- at once, plus a share of what's left toward the next, in proportion to
-- how much more it needs.
function Table(tbl)
  local nat, min, head = measure_columns(tbl)
  local room = TEXT_WIDTH - 2 * TABCOLSEP * (#nat - 1)
  local levels = { head, min, nat }
  for i = 1, #nat do
    nat[i] = math.max(nat[i], 1) + SLACK
    min[i] = math.min(math.max(min[i], head[i], 1) + SLACK, nat[i])
    head[i] = math.min(math.max(head[i], 1) + SLACK, min[i])
  end
  local totals = {}
  for l, widths in ipairs(levels) do
    totals[l] = 0
    for i = 1, #nat do totals[l] = totals[l] + widths[i] end
  end
  for i, spec in ipairs(tbl.colspecs) do
    local w
    if totals[3] <= room then
      w = nat[i]
    elseif totals[1] >= room then
      w = head[i] * room / totals[1]
    else
      local l = totals[2] <= room and 2 or 1
      local lo, hi = levels[l], levels[l + 1]
      w = lo[i] + (hi[i] - lo[i]) * (room - totals[l]) / (totals[l + 1] - totals[l])
    end
    tbl.colspecs[i] = { spec[1], w / room }
  end
  return tbl
end
