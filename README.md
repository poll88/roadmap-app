Roadmap Timeline (Streamlit)

A simple, mobile-friendly roadmap planner built with Streamlit + [vis-timeline]. Add items, group them by category, color-code them with a pastel palette, and view everything on a clean timeline.

The sidebar is designed to be rock-solid on phones/tablets: you pick which item to edit from a dropdown (or choose “➕ New item”), then edit its fields in one form—no accidental focus jumps, no click-inside-timeline selection.

⸻

Features
	•	Fast, reliable sidebar workflow
	•	Top picker: “➕ New item” or any existing item (drives Edit/Delete).
	•	One form for Title, Subtitle, Start/End dates, Category, Color.
	•	Buttons are stacked vertically: Add, Edit, Delete.
	•	Category inside the form
	•	Dropdown of existing categories.
	•	“+ New…” option reveals an input to create a new category on the fly.
	•	Clean timeline
	•	Item bars show title + subtitle (with text ellipsis).
	•	Initial view is dynamic: focuses on the longest event ± buffer
(buffer = max(14 days, 15% of that event’s length)).
	•	Toolbar buttons: Fit all, Show longest ± buffer, Today.
	•	Selection happens only in the sidebar (timeline clicks are ignored on purpose).
	•	Pastel palette (10 curated light colors).
	•	Import / Export JSON so you can back up or reuse your data.

⸻

Project structure

.
├─ app.py                 # main Streamlit app
└─ lib/
   ├─ styles.py           # global CSS (Montserrat + small tweaks)
   ├─ state.py            # normalize/serialize helpers
   └─ timeline.py         # vis-timeline HTML component

Only these 3 lib/ files are used. If you see other modules (e.g. ids.py, debug.py, sidebar.py), they’re legacy and can be removed.

⸻

Quickstart (local)
	1.	Python 3.9+ recommended.
	2.	Install deps:

pip install streamlit==1.36.0


	3.	Run:

streamlit run app.py


	4.	Open the URL from your terminal (usually http://localhost:8501).

⸻

Deploying on Streamlit Cloud
	1.	Set Main file path → app.py (exactly).
	2.	Ensure your repo contains:
	•	app.py
	•	lib/styles.py, lib/state.py, lib/timeline.py
	•	requirements.txt with:

streamlit==1.36.0


	•	(Optional but recommended) lib/__init__.py as an empty file.

	3.	Reboot the app.
If you ever see a blank page with no logs, it usually means the Main file path is wrong or the app is cached—try a reboot and open the URL in a Private tab (Safari caches aggressively).

⸻

Using the app
	1.	In the sidebar Item picker, choose “➕ New item” (default) to add a new event, or pick an existing one to edit/delete.
	2.	Fill in Title, Subtitle, and Start/End.
	3.	Choose a Category:
	•	Pick an existing category from the dropdown, or
	•	Select “+ New…” and type a name to create it.
	4.	Pick a Color.
	5.	Click Add item.
To modify an existing item, select it in the picker and use Edit item.
To remove it, select and use Delete item.
	6.	Use Export JSON to download all data; later Import JSON to restore.

⸻

JSON export format

Export JSON produces:

{
  "items": [
    {
      "id": "uuid-string",
      "content": "Title",
      "subtitle": "Optional subtitle",
      "start": "YYYY-MM-DD",
      "end": "YYYY-MM-DD",
      "group": "category-id",
      "color": "#HEX"
    }
  ],
  "groups": [
    { "id": "category-id", "content": "Category name", "order": 0 }
  ]
}

You can safely edit this by hand and re-import.

⸻

Customization
	•	Change the initial window logic:
In lib/timeline.py, _window_longest(items) controls the “longest ± buffer” rule.
Tweak BUFFER_PCT and MIN_BUFFER_DAYS, or replace with a dataset span window (earliest start → latest end).
	•	Colors: Edit the PALETTE list in app.py.
	•	Font/Styling: Adjust GLOBAL_CSS in lib/styles.py. Montserrat is loaded via Google Fonts; it falls back to system fonts if blocked.

⸻

Tips & troubleshooting
	•	White page, no logs on Streamlit Cloud
Usually the main file path is wrong or the app shell is cached.
	•	Ensure Main file path = app.py.
	•	Add/commit a small change, Reboot, and open in a Private tab.
	•	CDN access
The timeline uses the vis-timeline CDN (unpkg.com). If your network blocks it, the page still loads (Streamlit UI), but the timeline won’t render. Allowlist unpkg.com or self-host the assets.
	•	Typing loses focus
The form is a single st.form, so keystrokes don’t trigger reruns. If you see focus jumps, check for extra widgets outside the form.

⸻

License

Choose whatever fits your project (e.g., MIT). If none provided, this app is shared “as is” without warranty.

⸻

Credits
	•	Streamlit
	•	vis-timeline

Happy roadmapping! 🗺️
