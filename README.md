# EU Public Tender Finder (TED)

Find public procurement tenders from all EU and EEA countries in seconds. This Actor searches **TED (Tenders Electronic Daily)**, the official journal where every EU public buyer above the EU thresholds must publish, and returns clean, flat rows you can drop straight into a spreadsheet, CRM or AI agent.

Use it to:

- **Find tenders you can bid on** in your sector and countries, filtered by keyword, CPV code, value and deadline.
- **Get a daily tender alert.** Turn on monitoring, schedule the Actor, and each run returns only tenders you have not seen yet.
- **Research competitors and buyers.** Switch to contract awards to see who won which contracts.
- **Feed AI agents** with structured procurement data (title, buyer, deadline, value, CPV codes, links).

## What you get

Each result is one tender notice:

| Field | Example |
|---|---|
| `title` | Denmark – Supply services of personnel including temporary staff – ... |
| `buyerName` | Region Hovedstaden |
| `buyerCountry` | DNK |
| `submissionDeadline` | 2026-12-17 |
| `estimatedValue`, `currency` | 224000000, DKK |
| `cpvCodes` | ["79620000", "85311000"] |
| `procedureType` | open |
| `description` | Short description of the work, in your preferred language when available |
| `lotTitles` | Titles of the individual lots |
| `placeOfPerformance` | NUTS region codes, for example DK042 |
| `tenderDocumentsUrl` | Link to the buyer's tender documents |
| `tedUrl`, `pdfUrl` | Official notice on TED |
| `publicationDate`, `noticeId`, `noticeType`, `buyerEmail` | |

## How to use

1. Add **keywords** (any EU language, for example `software`, `cleaning`, `rengøring`) and/or **CPV codes** (short codes match whole families: `72` IT services, `45` construction, `90910000` cleaning, `33` medical equipment).
2. Pick **buyer countries** (`DK`, `SE`, `NO`, `FI`, `DE`, ... or leave empty for all of Europe).
3. Choose the **notice type**: open calls (default), upcoming tenders, or contract awards.
4. Run. Export as JSON, CSV or Excel, or call it from the API, Make, Zapier, n8n or an AI agent.

### Daily tender alert

Set **Only new notices since the last run** to on, give the search a **monitor name**, and add a daily schedule in Apify. Each run returns only new tenders, and you only pay for those. Connect the dataset to email, Slack or Google Sheets with an Apify integration.

## Pricing

Pay per result: you pay a small fee for each tender notice delivered, plus nothing else. Monitoring runs that find no new tenders cost close to nothing.

## Data source and reliability

Data comes from the official TED Search API published by the Publications Office of the European Union. It is public, free to reuse, and updated every working day. No scraping, no login, no proxies, so runs are fast and stable. Notices are returned as published by the buyer; the Actor only cleans and flattens them and picks your preferred language when a translation exists.

## Tips

- TED publishes Monday to Friday, so a one-day window on a weekend returns nothing.
- Many notices do not state an estimated value. Setting a minimum value skips those.
- Titles on TED are machine-translated into all EU languages; descriptions are often only in the buyer's language.

## Feedback

Missing a filter or field? Open an issue on the Actor page and it will be added.
