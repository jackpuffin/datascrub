# DataScrub — CSV & Excel Cleaner

A lightweight web app that cleans messy CSV and Excel files automatically. Upload a file, get back a clean one with a full audit report of every change made.

## Live Demo

[datascrub-cy6g.onrender.com](https://datascrub-cy6g.onrender.com)

*(Free tier — may take ~30 seconds to wake up after inactivity)*

## What it does

| Step | Action |
|------|--------|
| 1 | Renames columns to `snake_case` |
| 2 | Removes fully empty rows |
| 3 | Strips leading/trailing whitespace from all cells |
| 4 | Collapses internal whitespace (`"John  Smith"` → `"John Smith"`) |
| 5 | Replaces nullish strings (`N/A`, `none`, `null`, `-`, `unknown`) with proper empty values |
| 6 | Lowercases email addresses before deduplication |
| 7 | Removes duplicate rows (case-insensitive) |
| 8 | Removes blank-dominant duplicates (rows that match another row on all populated fields but have more empty cells) |
| 9 | Coerces currency/percentage columns to numeric (strips `$`, `%`, `,`) |
| 10 | Optionally applies smart title case (preserves abbreviations like USA, UK, LLC) |

Every action is logged in the audit report with a count of rows or cells affected.

## Assumptions & Limitations

This tool makes reasonable default assumptions that suit most use cases. Before using output in production, review the audit log to confirm the rules applied correctly for your dataset.

**Duplicate detection** matches rows by value across all columns. This works well for contact lists, customer records, and similar data — but in transactional datasets (e.g. order histories), two rows with the same customer and amount may be legitimate separate orders, not duplicates. Always review the "Removed duplicate rows" count in the report.

**Blank-dominant duplicate removal** drops a row if another row matches it on all populated fields but has more data. For example, if Bob Brown appears twice — once with an order amount and once without — the incomplete row is dropped. This is appropriate for most record-keeping datasets but may not be right for every use case.

**Numeric coercion** is applied when more than 60% of a column's values contain digits. Columns that look numeric but shouldn't be converted (e.g. zip codes, phone numbers) may be affected. Review numeric columns in the output.

**Title case** is optional and applied only to columns you specify (or auto-detected name/location columns). Known abbreviations (USA, UK, LLC, etc.) are preserved.

## Run Locally

```bash
git clone https://github.com/jackpuffin/datascrub.git
cd datascrub
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`

## Deploy to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo — Render auto-detects `render.yaml`
4. Click Deploy

## Tech Stack

- Python 3 / Flask
- pandas
- Deployed on Render (free tier)
