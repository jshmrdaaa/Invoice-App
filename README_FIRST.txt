ADAEL CONSTRUCTION INVOICE APP - HOW TO BUILD THE REAL PROGRAM
=================================================================

WHAT'S IN THIS FOLDER
----------------------
adael_desktop.py              -> the app itself (you won't need to open this)
build_desktop_app.bat         -> double-click this ONE TIME to build the program
requirements_desktop.txt      -> tells the computer what to install (automatic)
logo_grayblue_transparent.png -> the logo that prints on invoices (placeholder for now -
                                  see "SWAPPING THE LOGO" below)
customers.json, drafts.json, invoice_history.json, estimate_history.json,
invoice_counter.txt, estimate_counter.txt
                               -> your existing saved customers, invoice numbers,
                                  and history, carried over from before

STEP 1: BUILD THE PROGRAM (only needs to be done once)
--------------------------------------------------------
1. Unzip this whole folder somewhere on the HP laptop, like the Desktop.
2. Double-click "build_desktop_app.bat"
3. A black window will pop up and do its thing for a few minutes
   (it's downloading and installing what it needs - this requires internet).
4. When it's done, you'll see a new file appear in this same folder:
        "TA Invoices and Estimates.exe"
   That's the real program.

If the window says "Python was not found" - Python needs to be reinstalled
with the "Add python.exe to PATH" box checked during setup.

If it says "The desktop app did not build correctly" - take a screenshot/photo
of the window and send it over so we can fix it.

STEP 2: ONE MORE THING - INSTALL wkhtmltopdf (only needs to be done once)
----------------------------------------------------------------------------
The app needs a free little tool called "wkhtmltopdf" to actually create the
PDF invoices. Download and install it from:
        https://wkhtmltopdf.org/downloads.html
(pick the Windows installer). Just click through the installer with defaults.

STEP 3: USE THE PROGRAM
-------------------------
Double-click "TA Invoices and Estimates.exe" any time you want to make an
invoice or estimate. You can drag it to the Desktop or pin it to the
taskbar like any other program.

SWAPPING THE LOGO LATER
-------------------------
Right now "logo_grayblue_transparent.png" is just a stand-in placeholder.
Whenever you have the real company logo:
1. Save it as a PNG with that exact same name: logo_grayblue_transparent.png
2. Drop it into this folder, replacing the old one.
3. Double-click "build_desktop_app.bat" again to rebuild the program with the
   new logo.


AUTO-UPDATES (so your dad never has to do anything to get changes)
======================================================================
The app now checks, every time it opens, whether you've published a newer
version online - if so, it quietly downloads it and restarts itself with
the update already applied. Your dad does nothing; he just opens the app
like normal. (If there's no internet connection at that moment, it just
skips the check and opens normally - it never gets stuck.)

To turn this on, you need a free place online to publish new versions.
The easiest is GitHub Releases (free, no server needed). One-time setup:

1. Go to github.com and make a free account if you don't have one.
2. Click "New repository". Name it anything, e.g. "adael-invoice-app".
   Public is fine - it only ever holds the program file, never your
   customer data or invoices (those stay only on your dad's laptop).
3. Open adael_desktop.py in a text editor and find this line near the top:
        UPDATE_FEED_URL = "https://api.github.com/repos/YOUR-GITHUB-USERNAME/YOUR-REPO-NAME/releases/latest"
   Replace YOUR-GITHUB-USERNAME and YOUR-REPO-NAME with your actual GitHub
   username and the repo name you just created.
4. Re-run build_desktop_app.bat to build the exe with that change baked in.
5. On your GitHub repo's page, click "Releases" -> "Create a new release".
   - Tag it "v1.0.0" (matches CURRENT_VERSION in the code right now)
   - Upload the "TA Invoices and Estimates.exe" you just built as the
     release file
   - Click "Publish release"
6. Give your dad THIS exe (the one you just uploaded) to start with.

PUSHING A NEW UPDATE LATER (after the one-time setup above):
1. Make your code changes in adael_desktop.py.
2. Near the top, bump the version, e.g. change:
        CURRENT_VERSION = "1.0.0"
   to:
        CURRENT_VERSION = "1.0.1"
3. Run build_desktop_app.bat to rebuild.
4. On GitHub, create another new release - tag it "v1.0.1" (matching the
   version you just set) and upload the freshly built exe.
5. That's it. Next time your dad's laptop has internet and he opens the
   app, it will see "v1.0.1" is newer, download it, and restart itself
   automatically with the update applied - no action needed from him.

