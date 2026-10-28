---
name: claude-invoices
description: Saves Claude (claude.ai) Pro / Max invoices as PDFs into one folder, named by date so they line up in order, skipping ones already there. Use when the user asks to get, download or file their Claude invoices or receipts.
---

# claude-invoices

Saves every paid claude.ai invoice into one folder:

```
~/Documents/nowork/
├─ 2025-05-30_Anthropic_VLYWGTAO-0001_USD200.00.pdf
├─ 2026-02-04_Anthropic_VLYWGTAO-0002_USD36.85.pdf
└─ 2026-04-30_Anthropic_VLYWGTAO-0005_USD220.00.pdf
```

- Folder: `~/Documents/nowork/`, or `$NOWORK_DIR` when set. Create it if missing.
- Name: `<Date of issue>_Anthropic_<Invoice number>_<Currency><Total>.pdf`, all read from the PDF. Total is tax included, with the currency's usual decimals (`USD220.00`, `JPY3980`).
- The folder is the record. A file already there means that invoice is done.

## Steps

1. **Read the list.** Open https://claude.ai/settings/billing in whichever browser tool you have (the Claude desktop app's built-in browser, or Claude in Chrome). It opens Settings as a dialog. If it shows a sign-in screen instead, ask the user to sign in and wait; never type credentials.
2. Read the **Invoices** table with `read_page` on it (`find` "Invoices table" gives its ref; `get_page_text` does not see the dialog). Each row has date, total, status, and a **Download PDF** link to `https://pay.stripe.com/invoice/.../pdf?s=ap`. That is all the browser is needed for; close the tab.
3. **Skip** rows that are not `Paid`, and rows whose total is zero or negative (credit notes such as `-$86`).
4. **Skip rows already saved.** The list shows dates in the user's time zone, while Stripe dates the invoice in US time, so look one day either side. For a row `Mar 5, 2026 / $200`:
   ```sh
   ls ~/Documents/nowork | grep -E '^(2026-03-04|2026-03-05|2026-03-06)_Anthropic_.*_USD200\.00\.pdf$'
   ```
   Write out the three dates in full (Apr 30 → `2026-04-29|2026-04-30|2026-05-01`). Any match: already saved.
5. **Download each new one** with the shell, not the browser. Quote the link; never write it into a file or your report (anyone with it can open the invoice).
   ```sh
   tmp=$(mktemp -d) && curl -sSLf -o "$tmp/invoice.pdf" '<Download PDF link>' && head -c 5 "$tmp/invoice.pdf"
   ```
   It must print `%PDF-`.
6. **Read the PDF** and take Invoice number, Date of issue and Total. Check that Total equals the row total and Date of issue is within one day of the row date. If not, do not save; tell the user both values.
7. **Save** without overwriting:
   ```sh
   mv -n "$tmp/invoice.pdf" ~/Documents/nowork/2026-03-04_Anthropic_VLYWGTAO-0003_USD200.00.pdf
   ```
   If that name already exists, the invoice was saved before; leave it.
8. **Report** one line per row: saved (with file name), already saved, skipped (why), or mismatch.
