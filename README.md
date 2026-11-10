# Weave Generator

Weave Generator is a **Python desktop application** (Tkinter) for designing handweaving drafts. You edit the **threading**, **tie-up** and **treadling** (or a direct **liftplan**), and the **drawdown** is computed from them, the same model used by professional weaving software such as [WeaveIt](https://www.weaveit.com/).

```text
 [ warp colours ]
 [ threading    ]  [ tie-up    ]
 [ drawdown     ]  [ treadling ]  [ weft colours ]
```

You can:
- Edit **threading**, **tie-up** and **treadling** by clicking or dragging; the **drawdown** updates instantly
- Use several **treadles per pick**, or switch to a direct **liftplan**
- Choose a **rising** or **sinking** shed
- Set up to **400 ends**, **400 picks**, **32 shafts** and **32 treadles**
- Draw with **pencil**, **line**, **curve** and **select** tools; **cut, copy, paste, flip, rotate, repeat** and **wrap** selections
- **Generate** threadings and treadlings (straight, point, advancing, skip) and tie-ups (plain, twill, satin), or start from a **preset** (plain weave, twills, herringbone, diamond, satins)
- **Undo / redo** every edit (Ctrl+Z, Ctrl+Y)
- **Zoom** and scroll large drafts
- Colour every **warp end** and **weft pick** from an unlimited **palette**, with repeating **stripe** sequences
- Switch the drawdown to a shaded **cloth view** that shows the yarns and their colours
- **Open and save WIF** files, the interchange format of weaving software, to share drafts with other programs
- **Export** the whole draft (all panels with numbered rulers) as a PNG (as drawn in the current view), or as a vector **SVG** or **PDF**
- **Print** the draft on A4 or US Letter paper
- Find **long floats** (shaded in red on the drawdown) and work out **yardage** per colour for a project
- Get a warning before you lose **unsaved changes**, reopen **recent files**, and find your zoom, view and other choices remembered next time

---

## Requirements

- **Python**: 3.10+ (tested with Python 3.12)
- **Libraries**: Tkinter (included with standard Python on Windows), Pillow, NumPy

```bash
pip install -r requirements.txt
```

---

## Getting Started

1. **Clone or download** this project, for example into `C:\Users\<you>\Desktop\Weave Generator`.

2. (Optional but recommended) **Create a virtual environment**:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:

   ```bash
   python weave_generator.py
   ```

It opens with a 4-shaft 2/2 twill so you can see how the panels relate.

To make a single `WeaveGenerator.exe` that needs no Python, see [Building a Windows .exe](#building-a-windows-exe-with-pyinstaller) below.

---

## How to Use

### Reading the draft

- **Ends** are numbered **right to left**, **picks** top to bottom, **shafts** bottom to top and **treadles** left to right, as in standard draft notation.
- The **drawdown** is computed and cannot be clicked. Edit the threading, tie-up or treadling instead.
- Hover over any cell to see its end / pick / shaft / treadle in the status bar.

### Editing

| Panel | Click or drag to... |
|---|---|
| **Threading** | Thread an end on a shaft. Click a threaded cell again to unthread it. Dragging threads each end you pass over. |
| **Tie-up** | Toggle which shafts each treadle is tied to. |
| **Treadling** | Toggle which treadles are pressed on each pick (several per pick are allowed). |
| **Liftplan** | (Liftplan mode) Toggle which shafts lift on each pick, replacing the tie-up and treadling. |

A whole press-drag-release is a single undo step.

### Tools

Choose a tool in the **Tool** row:

- **Pencil**: click or drag to set or clear cells (the behavior above). In a colour strip it paints the selected colour. Fast drags are filled in so no cells are skipped.
- **Line**: drag to draw a straight line. Starting on a set cell erases the line instead. In the threading the line threads each end it crosses on the shaft it passes through.
- **Curve**: a smooth curve in two steps. First drag from one end of the curve to the other (the chord). Then move the pointer: a red preview curve bends so that its middle passes through the pointer, and a small circle marks that point. Click to place it (one undo step). A click on the chord's own line gives a straight line. **Esc**, choosing another tool, clicking outside the panel or in another panel, or resizing the draft cancels it without drawing anything, and a plain click without dragging starts nothing. Like the line tool, starting on a set cell erases the curve instead, in a colour strip it paints the selected colour, and in the threading it threads each end the curve crosses on the shaft the curve passes through there, so a steep curve still threads every end once. Any stretch that would swing outside the panel is flattened against its edge. It is handy for threading arcs, tie-up shapes and colour gradients.
- **Select**: drag a rectangle inside one panel; it shows as a dashed outline. Clicking a single cell selects just that cell, which is also how you choose where to paste.

### Edit menu (works on the selection)

| Command | What it does |
|---|---|
| **Cut / Copy / Paste / Delete** | Standard clipboard (Ctrl+X, C, V, Del while the draft has focus). Paste goes at the selection's top-left corner and only into the same kind of panel it came from. In the threading a paste replaces whole ends. |
| **Flip horizontal / vertical** | Mirror the selection left-right or up-down *as you see it on screen*. |
| **Rotate 90 degrees** | Rotate a square selection (not available in the threading). |
| **Repeat selection to the end** | Tile the selected ends (or picks) toward the last end (or pick). |
| **Wrap panel** | Shift the whole panel you last clicked in a direction, wrapping around the edges. |

### Draft menu

- **Generate threading / treadling**: fill the whole panel with *Straight draw*, *Point*, *Point with repeated ends*, *Advancing* (runs of consecutive shafts, each starting further along) or *Skip* (odd shafts then even shafts). The treadling gets one treadle per pick.
- **Tie-up**: *Plain weave*, *Twill* (any up/down, e.g. 2/1, 3/1), *Satin* (any valid move), *Invert*, *Clear*. A satin lifts one shaft per pick, so use a sinking shed for the opposite face.
- **Replace with preset**: plain weave, 2/1, 1/2, 2/2, 3/1 and 1/3 twills, herringbone, diamond, and 5- and 8-shaft satins, at your current number of ends and picks. Your rising/sinking choice is kept.

Every command is a single undo step, and invalid requests (such as a 4/4 twill on 4 shafts) show a message and change nothing. The tie-up and treadling commands are unavailable in liftplan mode, where those panels are hidden.

#### Advanced drafting

These open a window with the options, a live **Result** line (green when the draft can be made, red with the reason when it cannot) and an **Apply** button. Applying replaces the whole draft as one undo step, so Ctrl+Z brings the old one back. Opening the window again reuses it.

- **Block substitution...**: the current draft is the *profile*. Each shaft in its threading stands for a block, and each treadle in its treadling stands for a block. Every profile end and pick is replaced by that block's unit from a structure, and the profile's own tie-up is replaced by the structure's. **Summer and winter** is built in (choose 1 to 15 blocks; the default is the highest block your profile uses), or choose **Custom** and edit the structure text yourself:

  ```text
  shafts 6
  treadles 10
  tieup 1 = 1, 3
  tieup 10 = 3, 4, 5, 6
  block 1 threading = 1 3 2 3
  block 1 treadling = 1 9 2 10
  ```

  Numbers start at 1. `tieup 3 = 1, 4` ties treadle 3 to shafts 1 and 4. A threading unit lists the shafts that replace each end on that block's shaft; a treadling unit lists the treadles that replace each pick on that block's treadle, one pick each. Unthreaded ends and blank picks in the profile are dropped (the Result line says so). A profile pick with more than one treadle cannot be substituted. Thread colours carry over to every end and pick that replaces them.
- **Combine drafts...**: joins this draft with a second one (a preset, a WIF file, or a copy of the current draft). **Interleave** alternates ends and picks of the two drafts, the second one's shafts above the first's; the shorter is repeated to match, and both must have the same shed. **Double weave** weaves the first as the top layer and the second as the bottom: with a rising shed, the second's treadles also lift every shaft of the first; with a sinking shed, the first's treadles also lower every shaft of the second. Palettes are merged. If the result needs more than 32 treadles, or either draft is a liftplan, the result is a liftplan. The drawdown of a double weave shows the shed (what is lifted), not the face of either layer.
- **Network drafting...**: Alice Schlein's method of making a threading and treadling from a *design line* on top of an ordinary twill. Choose the **initial** `k` (for example 4 for a 4-shaft twill): end `e` may only use shafts `s` where `s` and `e` leave the same remainder when divided by `k`. A design line, a list of control points joined by straight lines and repeated across the draft, chooses which one of those shafts each end uses; its numbers are the bottom shaft of a `k`-high ribbon that slides over the shafts. Do the same for the treadling (one treadle per pick). Presets are **level**, **straight**, **point** and **wave**. The tie-up is left alone: with a tie-up that repeats every `k` shafts (such as the twill tie-up in the preset), the cloth keeps the structure of the initial twill whatever the design line, so only the line of the weave changes. The shafts and treadles must both be multiples of the initial. Not available in liftplan mode.
- **Reduce to fewest shafts and treadles**: renumbers the shafts and treadles so the draft uses as few as its cloth needs, keeping the cloth the same. Ends with identical columns share a shaft and picks with identical rows share a treadle.

### Colours and cloth

- The **Colours** row holds your palette. Click a swatch to select it; **Add**, **Edit** and **Remove** change the palette (Edit recolours every thread that uses the colour, Remove reassigns threads to a neighbouring colour; at least one colour always stays). There is no limit on the number of colours.
- The strip above the threading colours the **warp ends**, and the strip to the right of the treadling colours the **weft picks**. Paint them with the pencil, line or curve tool, and use Select, Copy, Paste, Flip, Repeat, Wrap and Delete on them like any other panel. Delete restores the default thread colour.
- **Draft > Colour stripes** colours the whole warp or weft from a repeating sequence of `colour:threads` pairs, for example `1:4, 2:2` is four threads of colour 1 then two of colour 2 (colours are numbered on the swatches).
- The **drawdown** shows each cell in the colour of the thread that is on top: the end's colour where the warp is up, the pick's colour where the weft is.
- The **View** buttons (Drawdown / Cloth): **Cloth** draws rounded, shaded yarns with the lower thread shadowed where it passes under, so floats and colour effects look like woven cloth. **Yarn width %** sets how much of each cell the yarn fills (30 to 100). This is a display choice only: it is not an undo step and never changes the draft.
- Presets and generators change the structure only; your palette and thread colours are kept.

### File menu

- **New** (Ctrl+N): an empty draft. Like opening a file, it is one undo step, so Ctrl+Z brings the old draft back.
- **Open WIF... / Save / Save as WIF...** (Ctrl+O, Ctrl+S, Ctrl+Shift+S): WIF is a text format read and written by most weaving programs. It keeps the size, shed direction, threading, tie-up, treadling (or liftplan), palette and thread colours. Opening a file replaces the draft but is a single undo step, so Ctrl+Z brings your previous draft back. The window title shows the open file and Save writes back to it.
- **Open recent**: the last eight files you opened or saved, newest first. A file that has gone is removed from the list when you try it. **Clear list** empties it.
- **Unsaved changes**: a `*` before the name in the title bar means the draft differs from the saved file (undoing back to the saved state removes it). New, Open, Open recent and Quit ask whether to **save**, **discard** or **cancel** first. Changing the view, zoom or float limit is not a change to the draft.
- **Export PNG / SVG / PDF**: PNG follows the current view (Drawdown or Cloth). SVG and PDF are vector graphics that stay sharp at any size; they always show the flat colour drawdown. The PDF is a single page whose orientation is chosen so the draft prints as large as possible; choose **PDF page size** (A4 or US Letter) first.
- **Import drawdown from image...**: works out a draft from a picture of a drawdown, one pixel per cell (dark pixel = warp up; the left column is the last end; transparent counts as white; images larger than 400 x 400 are refused). Ends with identical columns share a shaft, and picks with identical rows share a treadle; more than 32 different picks gives a liftplan, and more than 32 different ends is an error. Your palette and shed direction are kept. It replaces the draft in one undo step.
- **Print...**: makes a printable PDF and opens it in your PDF viewer, which has the Print command and printer choice. Nothing is sent to a printer directly.

Things to know about WIF: this program allows one shaft per end, so if a file threads an end on several shafts only the lowest is kept and you are warned. Colours, notes, spacing and other extras that WIF can hold but this program has no use for are ignored. In liftplan mode the liftplan is saved instead of the hidden tie-up and treadling. Files that cannot be used (not a WIF, more than 400 ends or picks, more than 32 shafts or treadles, numbers outside the declared size) are reported and leave your draft unchanged.

### Analysis menu

- **Highlight long floats**: shades in red every cell that lies on a float longer than the limit. A *float* is a thread that passes over or under many others in a row without interlacing, which snags and sags in the cloth. Warp floats run down an end, weft floats along a pick, and each can lie on the **face** or the **back** of the cloth; **Floats to show** chooses face, back or both. The shading follows every edit, and it also appears over the cloth view.
- **Float length limit...**: floats *longer than* this many threads are shaded (default 3, so a 5-shaft satin is flagged and a 2/2 twill is not).
- **Float report...**: how many floats are over the limit, the longest float in each place, and where the longest ones are (end and pick numbers start at 1).
- **Yardage...**: enter the finished width and length, the sett (ends per inch or cm), picks per inch or cm, loom waste, warp take-up, weft draw-in and shrinkage. It gives the number of ends and picks, the length of each, and the total yarn in yards (or metres) in all and for each colour. The warp and weft colour strips are repeated to fill the whole project. **Copy** puts the table on the clipboard. Your entries are kept until you close the program.

The float shading is a view only: it does not change the draft or the undo history, and PNG, SVG and PDF exports do not include it.

How yardage is worked out: the loom width is the finished width divided by (1 - width shrinkage), and likewise for length, because finishing shrinks the cloth. Ends = loom width x ends per unit; picks = loom length x picks per unit. Each warp end is the loom length plus warp take-up, plus the loom waste; each weft pick is the loom width plus weft draw-in. Treat the result as a careful estimate and add a margin for sampling and mistakes.

### View menu, shortcuts and help

- **View**: Drawdown or Cloth (Ctrl+K switches), zoom in and out (Ctrl++, Ctrl+-) and back to the standard zoom (Ctrl+0).
- **Edit > Select all** (Ctrl+A) selects the whole panel you last clicked in; **Esc** drops the selection. While the draft has focus, **P**, **L**, **C** and **S** pick the pencil, line, curve and select tools (the letters are left alone in the number boxes).
- **Help > Keyboard shortcuts** (F1) lists every shortcut; **Help > About** shows the version. Hover over a toolbar button for a tip.

### Remembered settings

Zoom, drawdown or cloth view, yarn width, float limit and which floats to show, PDF page size, the yardage window's entries, the window's size and position, the recent files and the last folder you used are saved when you quit and restored next time. They live in `settings.json` in `%APPDATA%\WeaveGenerator` (on other systems `~/.config/weavegen`). Delete that file to go back to the defaults. A damaged file is ignored, and a window position that would be off the screen (a monitor you have unplugged) is replaced by the default.

### Toolbar

- **Ends / Picks / Shafts / Treadles + Apply**: resize the draft, keeping everything that still fits. Ends threaded on a removed shaft become unthreaded.
- **Rising shed**: on is a rising shed, off is a sinking shed (the cloth is inverted).
- **Liftplan**: switches the tie-up and treadling for a direct liftplan. Switching it on converts your current treadling, so the cloth does not change.
- **Undo / Redo / Clear**: clear blanks the threading, tie-up, treadling and liftplan.
- **Zoom** (`-` / `+` or Ctrl + mouse wheel): very large drafts are drawn smaller than the zoom shown so they stay within a workable size.
- **Export PNG**: saves all panels, with rulers, as one image. It follows the current view, so Cloth gives a picture of the woven cloth.

---

## Project Structure

```text
weave_generator.py     launcher (kept for `python weave_generator.py` and PyInstaller)
weavegen/
  settings.py          remembered preferences (JSON file), recent files
  assets/              the application icon (made by tools/make_icon.py)
  core/                toolkit-independent logic (no Tkinter imports)
    draft.py           Draft: threading, tie-up, treadling/liftplan, palette and thread colours, computed drawdown, resize
    history.py         History: undo/redo over draft snapshots
    layout.py          DraftLayout: four-panel geometry, hit-testing, ruler labels
    colors.py          palette helpers (hex -> RGB)
    render.py          draft -> RGB pixel arrays, one per panel, colour-and-weave drawdown
    cloth.py           shaded cloth-view renderer
    selection.py       Rect, and mapping between panel matrices and the screen
    analysis.py        float finder: run lengths, float masks and reports
    yardage.py         yardage sums and report text
    ops.py             copy/cut/paste, flip, rotate, repeat, wrap, invert, lines
    patterns.py        sequence generators, tie-up generators, preset drafts, colour stripes
    blocks.py          block structures (summer and winter, text format) and block substitution
    combine.py         interleaving and double weave of two drafts
    fabric.py          draft from a drawdown, and reduction to the fewest shafts and treadles
    network.py         network drafting: design lines and networked threading/treadling
  io/
    wif.py             WIF reader and writer
    png.py             whole-draft PNG export via Pillow
    scene.py           vector description of the draft (rectangles, lines, labels) shared by SVG and PDF
    svg.py             SVG export
    pdf.py             PDF export (written directly, no extra library) and page placement
    drawdown_image.py  drawdown from an image file
  ui/
    app.py             Tkinter window, canvas, tools, menus, mouse and toolbar handlers
    dialogs.py         the block substitution, combine and network drafting windows
    help.py            keyboard shortcut list, About text, locating bundled files
    tooltip.py         hover tips
    yardage_dialog.py  the yardage calculator window
tools/make_icon.py     draws the icon files
weave_generator.spec   PyInstaller recipe for the Windows .exe
tests/                 pytest suite: core logic, export, and UI driven with synthetic events
                       (UI tests skip themselves when no display is available)
```

The UI is a thin layer over `weavegen.core`, so the logic can be tested without a display and reused if the UI toolkit changes.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m weavegen
```

---

## Building a Windows .exe with PyInstaller

1. Install PyInstaller (inside your environment if you use one):

   ```bash
   pip install pyinstaller
   ```

2. Run PyInstaller from the project directory, using the recipe in the project:

   ```bash
   pyinstaller weave_generator.spec
   ```

3. The program is `dist\WeaveGenerator.exe`: one file, no console window, with the application icon. Other Windows users do not need Python installed. It stores its settings in `%APPDATA%\WeaveGenerator`, the same as when run from source.

The recipe leaves out libraries the program does not use, which keeps the file at about 27 MB. The `build` and `dist` folders are not kept in git.

---

## Notes & Limitations

- Block substitution, combining and network drafting work on the draft in the editor and replace it; drafts are limited to 400 ends and 400 picks and 32 shafts and treadles, so large results are refused with a message. Summer and winter is the only built-in block structure.
- The float finder looks at the draft as drawn: it does not see floats that would form where the draft repeats. Yardage ignores the selvedge and does not convert to yarn weight.
- Each end is threaded on at most one shaft.
- Behavior is tested primarily on **Windows** with Python 3.12. Mouse-wheel scrolling uses the Windows event model.

---

## License

Creative Commons Legal Code

CC0 1.0 Universal

    CREATIVE COMMONS CORPORATION IS NOT A LAW FIRM AND DOES NOT PROVIDE
    LEGAL SERVICES. DISTRIBUTION OF THIS DOCUMENT DOES NOT CREATE AN
    ATTORNEY-CLIENT RELATIONSHIP. CREATIVE COMMONS PROVIDES THIS
    INFORMATION ON AN "AS-IS" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES
    REGARDING THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS
    PROVIDED HEREUNDER, AND DISCLAIMS LIABILITY FOR DAMAGES RESULTING FROM
    THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED
    HEREUNDER.

Statement of Purpose

The laws of most jurisdictions throughout the world automatically confer
exclusive Copyright and Related Rights (defined below) upon the creator
and subsequent owner(s) (each and all, an "owner") of an original work of
authorship and/or a database (each, a "Work").

Certain owners wish to permanently relinquish those rights to a Work for
the purpose of contributing to a commons of creative, cultural and
scientific works ("Commons") that the public can reliably and without fear
of later claims of infringement build upon, modify, incorporate in other
works, reuse and redistribute as freely as possible in any form whatsoever
and for any purposes, including without limitation commercial purposes.
These owners may contribute to the Commons to promote the ideal of a free
culture and the further production of creative, cultural and scientific
works, or to gain reputation or greater distribution for their Work in
part through the use and efforts of others.

For these and/or other purposes and motivations, and without any
expectation of additional consideration or compensation, the person
associating CC0 with a Work (the "Affirmer"), to the extent that he or she
is an owner of Copyright and Related Rights in the Work, voluntarily
elects to apply CC0 to the Work and publicly distribute the Work under its
terms, with knowledge of his or her Copyright and Related Rights in the
Work and the meaning and intended legal effect of CC0 on those rights.

1. Copyright and Related Rights. A Work made available under CC0 may be
protected by copyright and related or neighboring rights ("Copyright and
Related Rights"). Copyright and Related Rights include, but are not
limited to, the following:

  i. the right to reproduce, adapt, distribute, perform, display,
     communicate, and translate a Work;
 ii. moral rights retained by the original author(s) and/or performer(s);
iii. publicity and privacy rights pertaining to a person's image or
     likeness depicted in a Work;
 iv. rights protecting against unfair competition in regards to a Work,
     subject to the limitations in paragraph 4(a), below;
  v. rights protecting the extraction, dissemination, use and reuse of data
     in a Work;
 vi. database rights (such as those arising under Directive 96/9/EC of the
     European Parliament and of the Council of 11 March 1996 on the legal
     protection of databases, and under any national implementation
     thereof, including any amended or successor version of such
     directive); and
vii. other similar, equivalent or corresponding rights throughout the
     world based on applicable law or treaty, and any national
     implementations thereof.

2. Waiver. To the greatest extent permitted by, but not in contravention
of, applicable law, Affirmer hereby overtly, fully, permanently,
irrevocably and unconditionally waives, abandons, and surrenders all of
Affirmer's Copyright and Related Rights and associated claims and causes
of action, whether now known or unknown (including existing as well as
future claims and causes of action), in the Work (i) in all territories
worldwide, (ii) for the maximum duration provided by applicable law or
treaty (including future time extensions), (iii) in any current or future
medium and for any number of copies, and (iv) for any purpose whatsoever,
including without limitation commercial, advertising or promotional
purposes (the "Waiver"). Affirmer makes the Waiver for the benefit of each
member of the public at large and to the detriment of Affirmer's heirs and
successors, fully intending that such Waiver shall not be subject to
revocation, rescission, cancellation, termination, or any other legal or
equitable action to disrupt the quiet enjoyment of the Work by the public
as contemplated by Affirmer's express Statement of Purpose.

3. Public License Fallback. Should any part of the Waiver for any reason
be judged legally invalid or ineffective under applicable law, then the
Waiver shall be preserved to the maximum extent permitted taking into
account Affirmer's express Statement of Purpose. In addition, to the
extent the Waiver is so judged Affirmer hereby grants to each affected
person a royalty-free, non transferable, non sublicensable, non exclusive,
irrevocable and unconditional license to exercise Affirmer's Copyright and
Related Rights in the Work (i) in all territories worldwide, (ii) for the
maximum duration provided by applicable law or treaty (including future
time extensions), (iii) in any current or future medium and for any number
of copies, and (iv) for any purpose whatsoever, including without
limitation commercial, advertising or promotional purposes (the
"License"). The License shall be deemed effective as of the date CC0 was
applied by Affirmer to the Work. Should any part of the License for any
reason be judged legally invalid or ineffective under applicable law, such
partial invalidity or ineffectiveness shall not invalidate the remainder
of the License, and in such case Affirmer hereby affirms that he or she
will not (i) exercise any of his or her remaining Copyright and Related
Rights in the Work or (ii) assert any associated claims and causes of
action with respect to the Work, in either case contrary to Affirmer's
express Statement of Purpose.

4. Limitations and Disclaimers.

 a. No trademark or patent rights held by Affirmer are waived, abandoned,
    surrendered, licensed or otherwise affected by this document.
 b. Affirmer offers the Work as-is and makes no representations or
    warranties of any kind concerning the Work, express, implied,
    statutory or otherwise, including without limitation warranties of
    title, merchantability, fitness for a particular purpose, non
    infringement, or the absence of latent or other defects, accuracy, or
    the present or absence of errors, whether or not discoverable, all to
    the greatest extent permissible under applicable law.
 c. Affirmer disclaims responsibility for clearing rights of other persons
    that may apply to the Work or any use thereof, including without
    limitation any person's Copyright and Related Rights in the Work.
    Further, Affirmer disclaims responsibility for obtaining any necessary
    consents, permissions or other rights required for any use of the
    Work.
 d. Affirmer understands and acknowledges that Creative Commons is not a
    party to this document and has no duty or obligation with respect to
    this CC0 or use of the Work.
