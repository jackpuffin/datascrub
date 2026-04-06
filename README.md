# DataScrub — CSV & Excel Cleaner

A lightweight web app that cleans messy CSV and Excel files automatically. Upload a file, get back a clean one with a full audit report.

## What it does

- Removes duplicate rows (case-insensitive — catches duplicates where one row is all-caps)
- Strips leading/trailing whitespace from all cells
- Collapses internal whitespace (e.g. `"John  Smith"` → `"John Smith"`)
- Replaces nullish strings (`N/A`, `none`, `null`, `-`, `unknown`) with proper empty values
- Normalizes column names to `snake_case`
- Lowercases email addresses before deduplication
- Coerces currency/percentage columns to numeric values (strips `$`, `%`, `,`)
- Optionally applies smart title case (preserves abbreviations like USA, UK, LLC)
- Outputs a full JSON audit report of every action taken

## Live demo

[datascrub.onrender.com](https://datascrub.onrender.com)

## Run locally

```bash
git clone https://github.com/yourusername/datascrub.git
cd datascrub
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`

## Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — click Deploy

Free tier is sufficient for a portfolio demo.

## Tech stack

- Python 3.11
- Flask
- pandas
- Deployed on Render
