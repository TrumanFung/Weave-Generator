# Weave Generator

Weave Generator is a **Python desktop application** (Tkinter) for designing handweaving drafts. You edit the **threading**, **tie-up** and **treadling** (or a direct **liftplan**), and the **drawdown** is computed from them, the same model used by professional weaving software such as [WeaveIt](https://www.weaveit.com/).

```text
 [ threading ]  [ tie-up    ]
 [ drawdown  ]  [ treadling ]
```

You can:
- Edit **threading**, **tie-up** and **treadling** by clicking or dragging; the **drawdown** updates instantly
- Use several **treadles per pick**, or switch to a direct **liftplan**
- Choose a **rising** or **sinking** shed
- Set up to **400 ends**, **400 picks**, **32 shafts** and **32 treadles**
- **Undo / redo** every edit (Ctrl+Z, Ctrl+Y)
- **Zoom** and scroll large drafts
- Pick **warp** and **weft** colors
- **Export** the whole draft (all four panels with numbered rulers) as a PNG

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

### Toolbar

- **Ends / Picks / Shafts / Treadles + Apply**: resize the draft, keeping everything that still fits. Ends threaded on a removed shaft become unthreaded.
- **Rising shed**: on is a rising shed, off is a sinking shed (the cloth is inverted).
- **Liftplan**: switches the tie-up and treadling for a direct liftplan. Switching it on converts your current treadling, so the cloth does not change.
- **Undo / Redo / Clear**: clear blanks the threading, tie-up, treadling and liftplan.
- **Zoom** (`-` / `+` or Ctrl + mouse wheel): very large drafts are drawn smaller than the zoom shown so they stay within a workable size.
- **Warp / Weft**: the colors of warp-on-top and weft-on-top cells in the drawdown.
- **Export PNG**: saves all panels, with rulers, as one image.

---

## Project Structure

```text
weave_generator.py     launcher (kept for `python weave_generator.py` and PyInstaller)
weavegen/
  core/                toolkit-independent logic (no Tkinter imports)
    draft.py           Draft: threading, tie-up, treadling/liftplan, computed drawdown, resize
    history.py         History: undo/redo over draft snapshots
    layout.py          DraftLayout: four-panel geometry, hit-testing, ruler labels
    render.py          draft -> RGB pixel arrays, one per panel
  io/
    png.py             whole-draft PNG export via Pillow
  ui/
    app.py             Tkinter window, canvas, mouse and toolbar handlers
tests/                 pytest suite for core and export
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

2. Run PyInstaller from the project directory:

   ```bash
   pyinstaller --onefile --windowed weave_generator.py
   ```

3. The executable is `dist\weave_generator.exe`. Other Windows users do not need Python installed.

---

## Notes & Limitations

- Not yet implemented: drawing tools (line, curve, select, copy/paste), pattern generators, per-thread colors, WIF import/export, printing, float finder and yardage, network drafting and double weave.
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
