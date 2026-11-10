# Weave Generator User Guide

This guide walks through every button, menu and tool in Weave Generator, then shows how to do common jobs step by step. For installation and developer notes, see the [README](../README.md).

Contents

1. [The window at a glance](#1-the-window-at-a-glance)
2. [Reading a draft](#2-reading-a-draft)
3. [The top bars](#3-the-top-bars)
4. [Drawing tools](#4-drawing-tools)
5. [Selections and the Edit menu](#5-selections-and-the-edit-menu)
6. [Draft menu](#6-draft-menu)
7. [Colours and the cloth view](#7-colours-and-the-cloth-view)
8. [File menu: saving, opening and exporting](#8-file-menu-saving-opening-and-exporting)
9. [View menu](#9-view-menu)
10. [Analysis menu](#10-analysis-menu)
11. [Keyboard shortcuts](#11-keyboard-shortcuts)
12. [How-to recipes](#12-how-to-recipes)
13. [Troubleshooting and limits](#13-troubleshooting-and-limits)

---

## 1. The window at a glance

```text
 Row 1   Ends  Picks  Shafts  Treadles  [Apply]   [x] Rising shed  [ ] Liftplan
 Row 2   [Undo] [Redo] [Clear]   Zoom [-] 100% [+]                [Export PNG]
 Row 3   Tool:  [Pencil] [Line] [Curve] [Select]   (hint for the chosen tool)
 Row 4   Colours: [swatches] [Add] [Edit] [Remove]   View: [Drawdown] [Cloth]   Yarn width %
 Canvas  the draft itself
 Status  hover and message line
```

The canvas holds the draft:

```text
          [ warp colours ]
          [ threading    ]   [ tie-up    ]
          [ drawdown     ]   [ treadling ]   [ weft colours ]
```

The menu bar has **File, Edit, View, Draft, Analysis** and **Help**. The title bar shows the file name (or *Untitled*) and a `*` when you have unsaved changes.

## 2. Reading a draft

- **Ends** (warp threads) are numbered **right to left** along the top.
- **Picks** (weft shots) are numbered **top to bottom**.
- **Shafts** are numbered **bottom to top**; **treadles** **left to right**.
- The **threading** says which shaft each end is threaded on (one shaft per end).
- The **tie-up** says which shafts each treadle lifts.
- The **treadling** says which treadle(s) you press on each pick.
- The **drawdown** is computed from the other three and shows the cloth. You cannot click it; change the threading, tie-up or treadling instead.
- Hover over any cell and the **status bar** names it (end, pick, shaft or treadle).
- With **Liftplan** on, the tie-up and treadling are replaced by a **liftplan**: for each pick you mark the shafts that lift directly.

## 3. The top bars

### Size row

| Control | What it does |
|---|---|
| **Ends / Picks / Shafts / Treadles** | Type or step the size you want. Limits: 400 ends, 400 picks, 32 shafts, 32 treadles. |
| **Apply** (or Enter in a box) | Resizes the draft, keeping everything that still fits. Ends threaded on a shaft that no longer exists become unthreaded. One undo step. |
| **Rising shed** | Checked = rising shed (a lifted shaft raises its ends, so the warp shows on top). Unchecked = sinking shed, which inverts the cloth. The threading, tie-up and treadling are not changed. |
| **Liftplan** | Switches between tie-up + treadling and a direct liftplan. Turning it on converts your treadling so the cloth stays the same. |

### Edit row

| Control | What it does |
|---|---|
| **Undo / Redo** | Step back and forward through every edit. A whole press-drag-release is one step. |
| **Clear** | Blanks the threading, tie-up, treadling and liftplan (colours and size stay). Undo brings it back. |
| **Zoom - / +** | Change the cell size. Very large drafts are drawn smaller than the zoom shown so they stay workable. Also Ctrl + mouse wheel. |
| **Export PNG** | Saves **only the woven cloth** as a PNG (see [section 8](#8-file-menu-saving-opening-and-exporting)). |

### Tool row

Choose **Pencil, Line, Curve** or **Select** (or press P, L, C, S while the draft has focus). A grey hint beside the buttons reminds you how the chosen tool works. Hover a button for a tip.

### Colour row

See [section 7](#7-colours-and-the-cloth-view).

## 4. Drawing tools

Every tool works in any panel: threading, tie-up, treadling, liftplan and the two colour strips. Cells outside the panel you start in are ignored.

### Pencil

- **Click** a cell to set it; click a set cell to clear it.
- **Drag** to paint a run of cells. The first cell you touch decides whether the whole stroke sets or clears. Fast drags are filled in so no cell is skipped.
- **Threading**: setting a cell threads that end on that shaft, replacing any other shaft it had. Dragging threads each end you pass.
- **Colour strips**: paints the colour selected in the Colours row.

### Line

Drag from one cell to another to draw a straight line. Starting on a set cell **erases** along the line instead. In the threading, each end the line crosses is threaded on the shaft the line passes through. In a colour strip it paints the selected colour.

### Curve

A smooth curve in two steps:

1. **Drag** from one end of the curve to the other. A guide appears, and the status bar prompts you to bend it.
2. **Move the pointer.** A red preview curve bends so its **middle passes through the pointer**, marked with a small circle. **Click** to place it (one undo step).

Notes:

- Put the pointer on the straight line between the ends and you get a straight line.
- **Esc**, picking another tool, clicking outside the panel or in another panel, or resizing the draft cancels the curve without drawing.
- A plain click without dragging starts nothing.
- Like the line tool: starting on a set cell erases; colour strips get the selected colour; in the threading every end the curve crosses is threaded once, on the shaft the curve passes through there.
- Any stretch that would swing outside the panel is flattened against its edge.
- Good for threading arcs, tie-up shapes and colour gradients.

### Select

Drag a rectangle inside one panel (dashed outline). A single click selects one cell, which is also how you pick where to paste. **Esc** drops the selection.

## 5. Selections and the Edit menu

Most commands act on the current selection. If a command needs a selection and there is none, the status bar says so.

| Command | Shortcut | What it does |
|---|---|---|
| **Undo / Redo** | Ctrl+Z / Ctrl+Y | Step back / forward. Ctrl+Shift+Z also redoes. |
| **Cut / Copy / Paste** | Ctrl+X / C / V | Standard clipboard. Paste puts the block's top-left corner at the selected cell, and only into the same kind of panel it came from. In the threading a paste replaces whole ends. Shortcuts work while the draft has focus. |
| **Delete** | Del | Clears the selected cells (in a colour strip, restores the default thread colour). |
| **Select all** | Ctrl+A | Selects the whole panel you last clicked in. |
| **Flip horizontal / vertical** | | Mirrors the selection left-right or up-down *as you see it on screen*. |
| **Rotate 90 degrees** | | Rotates a **square** selection. Not available in the threading or colour strips. |
| **Repeat selection to the end** | | Tiles the selected ends (or picks) toward the last end (or pick). |
| **Wrap panel > Left / Right / Up / Down** | | Shifts the whole panel you last clicked in by one cell, wrapping around the edges. |

## 6. Draft menu

Every command here is a single undo step. If a request is invalid (for example a 4/4 twill on 4 shafts), a message explains why and the draft is unchanged.

### Generate threading / Generate treadling

Fill the whole panel from a pattern:

| Option | Result |
|---|---|
| **Straight draw** | 1, 2, 3 ... up to the last shaft (or treadle), repeating. |
| **Point** | Up to the last shaft and back down, repeating. |
| **Point, repeated ends** | Like Point, but the turning shafts are used twice. |
| **Advancing...** | Runs of consecutive shafts, each run starting further along. Asks for the *threads in each run* and the *shafts to advance after each run*. |
| **Skip** | Odd shafts, then even shafts. |

The treadling gets one treadle per pick. Unavailable in liftplan mode (treadling).

### Tie-up

| Option | Result |
|---|---|
| **Plain weave** | Alternating tie-up for plain weave. |
| **Twill...** | Asks for *up* and *down* (for example 2 and 1 for a 2/1 twill). |
| **Satin...** | Asks for the move number. One shaft lifts per pick, so use a sinking shed for the opposite face. |
| **Invert tie-up** | Swaps set and empty cells. |
| **Clear tie-up** | Empties the tie-up. |

Unavailable in liftplan mode, where the tie-up is hidden.

### Colour stripes > Warp stripes... / Weft stripes...

Colours the whole warp or weft from a repeating sequence of `colour:threads` pairs. Colours are numbered as on the swatches. Example: `1:4, 2:2` is four threads of colour 1, then two of colour 2, repeated.

### Replace with preset

Replaces the structure with a ready-made draft at your current number of ends and picks: plain weave, 2/1, 1/2, 2/2, 3/1 and 1/3 twills, 2/2 herringbone, 2/2 diamond, 5-shaft satin and 8-shaft satin. Your palette, thread colours and rising/sinking choice are kept.

### Block substitution...

Treats the current draft as a *profile* in which each shaft and treadle stands for a block, and replaces each with a unit from a structure. **Summer and winter** is built in (choose the number of blocks), or choose **Custom** and type your own structure:

```text
shafts 6
treadles 10
tieup 1 = 1, 3
tieup 10 = 3, 4, 5, 6
block 1 threading = 1 3 2 3
block 1 treadling = 1 9 2 10
```

The window shows a live **Result** line (green when it can be made, red with the reason when it cannot). **Apply** replaces the draft; **Close** leaves without changes. Ctrl+Z undoes the replacement.

### Combine drafts...

Joins the current draft (A) with a second one (B), chosen from a preset, a WIF file (**Browse...**) or a copy of the current draft.

- **Interleave** alternates the ends and picks of A and B; B's shafts sit above A's. Both must have the same shed direction.
- **Double weave** weaves A as the top layer and B as the bottom layer.

Palettes are merged. If the result needs more than 32 treadles, it becomes a liftplan.

### Network drafting...

Builds a threading and treadling from a *design line* over an ordinary twill (Alice Schlein's method).

1. Set **Initial** (for example 4 for a 4-shaft twill). Shafts and treadles must be multiples of it.
2. For the threading and for the treadling choose a **Shape** (level, straight, point, wave) and **Cycles**, or edit the **Control points** directly.
3. Watch the **Result** line, then **Apply**.

The tie-up is left alone; use a tie-up that repeats every *k* shafts (the twill presets do).

### Reduce to fewest shafts and treadles

Renumbers shafts and treadles so the draft uses as few as the cloth needs, without changing the cloth.

## 7. Colours and the cloth view

### The palette

| Control | What it does |
|---|---|
| **Swatches** | Click one to make it the selected colour (the one the drawing tools paint with in the colour strips). Swatches are numbered for use in colour stripes. |
| **Add** | Opens a colour chooser and adds a new colour to the palette. |
| **Edit** | Recolours the selected swatch everywhere it is used. |
| **Remove** | Removes the selected colour; threads using it move to a neighbouring colour. At least one colour always stays. |

### Colouring threads

- The strip **above the threading** colours each **warp end**.
- The strip **right of the treadling** colours each **weft pick**.
- Paint them with Pencil, Line or Curve, and use Select, Copy, Paste, Flip, Repeat, Wrap and Delete on them like any panel.
- **Draft > Colour stripes** does whole-warp or whole-weft stripe sequences.
- The drawdown shows each cell in the colour of the thread on top: the end's colour where the warp is up, the pick's colour where the weft is.

### Drawdown and Cloth views

| Control | What it does |
|---|---|
| **View: Drawdown** | Flat coloured squares. |
| **View: Cloth** | Rounded, shaded yarns with the lower thread shadowed where it passes under, so floats and colour effects look like real cloth. |
| **Yarn width %** | How much of each cell the yarn fills (30 to 100). Lower shows more gap between threads. |

The view is a display choice only: it is not an undo step and never changes the draft. **Ctrl+K** switches views. The PNG export follows the current view.

## 8. File menu: saving, opening and exporting

| Command | What it does |
|---|---|
| **New** (Ctrl+N) | An empty draft. One undo step, so Ctrl+Z brings the old draft back. |
| **Open WIF...** (Ctrl+O) | Opens a WIF file, the exchange format of weaving software. One undo step. |
| **Open recent** | The last eight files you opened or saved. **Clear list** empties it. A file that has gone is removed when you try it. |
| **Save** (Ctrl+S) | Writes back to the open file (asks for a name if the draft is new). |
| **Save as WIF...** (Ctrl+Shift+S) | Saves under a new name. |
| **Import drawdown from image...** | Works out a draft from a picture of a drawdown (see recipes). |
| **Export PNG (weave only)...** | Saves **just the woven cloth**: no threading, tie-up, treadling, colour strips, rulers or grid lines. It follows the current view (Drawdown or Cloth) at 12 pixels per cell. The toolbar's **Export PNG** button does the same. |
| **Export PNG (full draft)...** | Saves every panel with numbered rulers, as it appears on screen (in the current view). |
| **Export SVG...** | Vector picture of the whole draft; sharp at any size. Always shows the flat drawdown. |
| **Export PDF...** | One-page vector PDF of the whole draft. Pick the paper with **PDF page size** first. |
| **PDF page size** | A4 or US Letter, used by Export PDF and Print. |
| **Print...** (Ctrl+P) | Makes a printable PDF and opens it in your PDF viewer, which has the Print command and printer choice. Nothing is sent to a printer directly. |
| **Quit** (Ctrl+Q) | Closes the program. |

**Unsaved changes:** a `*` in the title bar means the draft differs from the saved file (undoing back to the saved state removes it). New, Open, Open recent and Quit ask whether to **save**, **discard** or **cancel** first. Changing the view, zoom or float limit does not count as a change.

**WIF notes:** WIF keeps the size, shed direction, threading, tie-up, treadling (or liftplan), palette and thread colours. If a file threads an end on several shafts, only the lowest is kept and you are warned. Unusable files are reported and leave your draft unchanged.

## 9. View menu

- **Drawdown / Cloth**: same as the View buttons.
- **Switch view** (Ctrl+K): toggles between them.
- **Zoom in / Zoom out** (Ctrl++, Ctrl+-): same as the zoom buttons.
- **Standard zoom** (Ctrl+0): back to the default cell size.

## 10. Analysis menu

| Command | What it does |
|---|---|
| **Highlight long floats** | Shades in red every cell on a float longer than the limit. A float is a thread that passes over or under many others in a row without interlacing. Follows every edit and shows over the cloth view. Not included in exports. |
| **Float length limit...** | Floats *longer than* this many threads are shaded. Default 3, so a 5-shaft satin is flagged and a 2/2 twill is not. |
| **Floats to show** | **Face and back**, **Face only** or **Back only**. |
| **Float report...** | Counts floats over the limit and lists where the longest are (end and pick numbers start at 1). |
| **Yardage...** | Yarn calculator: enter finished width and length, sett (ends per inch or cm), picks per inch or cm, loom waste, warp take-up, weft draw-in and shrinkage. It shows the ends and picks, the length of each, and total yarn in yards (or metres) overall and per colour. **Copy** puts the table on the clipboard. Treat the result as an estimate and add a margin. |

## 11. Keyboard shortcuts

Press **F1** (or Help > Keyboard shortcuts) for the list inside the program.

| Keys | Action |
|---|---|
| Ctrl+N / O / S / Shift+S / P / Q | New, Open, Save, Save as, Print, Quit |
| Ctrl+Z, Ctrl+Y (or Ctrl+Shift+Z) | Undo, Redo |
| Ctrl+C / X / V, Delete | Copy, cut, paste, clear the selected cells (draft has focus) |
| Ctrl+A | Select the whole panel you last clicked in |
| Esc | Cancel a curve in progress, otherwise drop the selection |
| P, L, C, S | Pencil, Line, Curve, Select (draft has focus) |
| Ctrl++, Ctrl+-, Ctrl+0, Ctrl+mouse wheel | Zoom in, out, standard, zoom with the wheel |
| Ctrl+K | Switch between Drawdown and Cloth |
| Mouse wheel / Shift+wheel | Scroll up-down / left-right |
| F1 | Keyboard shortcuts |

The tool letters only work while the draft has focus (click the canvas), so typing in the size boxes is not affected.

## 12. How-to recipes

### Make a simple twill from scratch

1. **Draft > Replace with preset > 2/2 twill**.
2. Set **Ends** and **Picks** (for example 48 and 48) and click **Apply**, then pick the preset again so it fills the new size.
3. Switch **View** to **Cloth** to see it as fabric.

### Build a draft by hand

1. Set the size and click **Apply**.
2. With **Pencil**, click the threading cells, for example 1 to 4 along the bottom diagonal. Or use **Draft > Generate threading > Straight draw**.
3. Click the tie-up to say which shafts each treadle lifts, or use **Draft > Tie-up > Twill...**.
4. Click the treadling, or use **Draft > Generate treadling**.
5. Check the drawdown. Press **Ctrl+Z** to undo any slip.

### Make a pointed (diamond-like) design

1. **Draft > Generate threading > Point** and **Generate treadling > Point**.
2. **Draft > Tie-up > Twill...** with 2 and 2.

### Add stripes of colour

1. Click **Add** twice to create two colours.
2. **Draft > Colour stripes > Warp stripes...** and enter, for example, `1:6, 2:2`.
3. Do the same for the weft. Switch to **Cloth** view to judge the look.

Or paint by hand: select a swatch, choose the Pencil, and drag across the strip above the threading (warp) or beside the treadling (weft).

### Draw a smooth arc in the threading

1. Choose **Curve** (press C).
2. Drag from the first end's shaft to the last end's shaft.
3. Move the pointer up or down to bend the arc, and **click**. **Esc** cancels.

### Save only the picture of the cloth

1. Choose **Cloth** or **Drawdown** view (the export follows it).
2. Click **Export PNG** in the toolbar (or **File > Export PNG (weave only)...**).
3. Pick a name. The image contains only the fabric, nothing used for editing.

Want everything, including the threading, tie-up and treadling with their rulers? Use **File > Export PNG (full draft)...** (or **Export PDF**/**SVG** for printable vector copies).

### Print a draft

1. **File > PDF page size** to choose A4 or US Letter.
2. **File > Print...** (Ctrl+P). The PDF opens in your viewer; use its Print command.

Or **File > Export PDF...** to keep the file.

### Share a draft with other weaving software

**File > Save as WIF...** and send the `.wif` file. To use a draft from other software, **File > Open WIF...**.

### Work from a picture of a drawdown

1. Prepare an image with **one pixel per cell**: dark pixel = warp up, light pixel = weft up; the left column is the last end. Up to 400 x 400.
2. **File > Import drawdown from image...** and choose the file. A threading, tie-up and treadling are worked out (more than 32 different picks gives a liftplan).
3. Use **Draft > Reduce to fewest shafts and treadles** if you want it tidier.

### Check for loose floats

1. **Analysis > Highlight long floats**. Red cells are floats over the limit.
2. Change **Float length limit...** or **Floats to show** if needed.
3. **Float report...** gives the counts and positions.

### Estimate how much yarn to buy

1. Finish the draft and give each thread its colour.
2. **Analysis > Yardage...**, fill in the project figures, and read the total per colour. Click **Copy** to paste the table into a note.

### Try a structure with blocks (summer and winter)

1. Draw a small *profile* draft, with each shaft and treadle standing for a block.
2. **Draft > Block substitution...**, leave **Summer and winter**, choose the number of blocks, check the green **Result** line and click **Apply**.
3. Not happy? **Ctrl+Z**.

### Combine two drafts into a double weave

1. Make draft A (the top layer) in the editor.
2. **Draft > Combine drafts...**, choose a preset or WIF file for B, choose **Double weave**, **Apply**.
3. The drawdown then shows the shed, not the face of either layer.

### Recover from a mistake

- **Ctrl+Z** undoes any edit, including New, Open, presets and the advanced commands.
- If you close with unsaved changes, the program asks to **save**, **discard** or **cancel**.

### Reset remembered settings

Settings (zoom, view, window position, recent files and so on) are saved in `settings.json` in `%APPDATA%\WeaveGenerator`. Delete that file to return to the defaults.

## 13. Troubleshooting and limits

| Problem | What to do |
|---|---|
| A menu item is greyed out or a message says it is unavailable | Tie-up and treadling commands are unavailable in **Liftplan** mode; network drafting is too. Turn Liftplan off. |
| "The selection is outside the panel" or a command does nothing | Make a selection with the Select tool inside one panel first. |
| A paste does nothing | Paste only goes into the same kind of panel it was copied from. Click the destination cell first. |
| Drawdown looks inverted | Check **Rising shed**: unchecking it gives a sinking shed, which flips the cloth. |
| A file will not open | It may not be a WIF, or exceeds 400 ends or picks or 32 shafts or treadles. The message says which; your draft is not changed. |
| Windows warns about the program | The `.exe` is unsigned. Choose **More info > Run anyway**. |
| Cloth view looks coarse | Zoom in, or raise **Yarn width %** to fill more of each cell. |

Limits: 400 ends, 400 picks, 32 shafts, 32 treadles; one shaft per end. The float finder does not look across the repeat edge, and yardage ignores the selvedge.
