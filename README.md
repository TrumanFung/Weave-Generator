### README.md (copy-paste ready)

```markdown
# Weave Generator MVP

Weave Generator is a simple **Python desktop application** built with **Tkinter** that lets you design basic over/under weave patterns on a grid and export them as PNG images.

You can:
- Define the **grid size** (warp x weft)
- **Click cells** to toggle between “under” and “over”
- **Pick two colors** for the weave
- **Download** the final pattern as a **PNG** using a file dialog

---

## Requirements

- **Python**: 3.10+ (tested with Python 3.12)
- **Libraries**:
  - Tkinter (included with standard Python on Windows)
  - Pillow (PIL fork) for image export

Install Pillow with:

```bash
pip install pillow
```

---

## Getting Started

1. **Clone or download** this project into a folder, for example:

   ```text
   C:\Users\<you>\Desktop\Weave Generator
   ```

2. (Optional but recommended) **Create a virtual environment**:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install pillow
   ```

4. **Run the application**:

   ```bash
   python weave_generator.py
   ```

This should open a desktop window titled **“Weave Generator MVP”**.

---

## How to Use

### 1. Set grid size

- At the **top** of the window, enter:
  - **Warp** (columns)
  - **Weft** (rows)
- Default is **16 x 16**.
- Click **Generate** to create a new blank grid.
- The grid is clamped to a maximum of **40 x 40** to stay responsive.

### 2. Edit the weave pattern

- Click on any **cell** in the grid:
  - `0` (under) switches to `1` (over)
  - `1` (over) switches back to `0` (under)
- The canvas **updates immediately** after each click.

### 3. Choose thread colors

- At the **bottom**, you’ll see:
  - **Over color** (left) with a color swatch and **Pick** button
  - **Under color** (right) with a color swatch and **Pick** button
- Click **Pick** to open the color chooser, then select any color.
- The pattern redraws with the new colors.

### 4. Download the pattern as PNG

- Click the **“Download Pattern”** button at the bottom.
- A standard **Save As** dialog appears:
  - Choose the folder and filename (e.g. `weave_pattern.png`)
  - Click **Save**
- The app renders the pattern using **Pillow** and saves a **PNG image** to the chosen path.

---

## Project Structure

This MVP is intentionally small and simple:

- `weave_generator.py` – the **entire application**:
  - Tkinter window setup
  - Canvas rendering
  - Grid logic (0/1 states for under/over)
  - Color pickers
  - PNG export via Pillow

No database, no authentication, and no advanced textile simulation are used.

---

## Building a Windows .exe with PyInstaller

You can package the app into a single `.exe` file using **PyInstaller**.

1. Install PyInstaller (inside your environment if you’re using one):

   ```bash
   pip install pyinstaller
   ```

2. Run PyInstaller from the project directory:

   ```bash
   pyinstaller --onefile --windowed weave_generator.py
   ```

3. After it finishes:
   - Look in the `dist` folder
   - You should see `weave_generator.exe`

You can distribute that `.exe` to other Windows users (they don’t need Python installed).

---

## Notes & Limitations

- Designed for grids up to **40 x 40** for reasonable performance and usability.
- This is an **MVP**:
  - No fabric physics, yarn thickness simulation, or advanced textile modeling.
  - The pattern is purely a graphical over/under grid.
- Behavior is tested primarily on **Windows** with Python 3.12.

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

```
