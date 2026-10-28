---
name: claude-ai
description: Fetches Claude Pro / Max invoices and receipts from claude.ai and files them into the nowork vault. Use when the user asks to get, download or file their Claude (claude.ai) receipts or invoices. Requires Claude in Chrome and the receipt-vault skill.
---

# claude-ai

Covers Pro and Max plans bought on the web. Billing runs on Stripe. Each paid row gives two documents, and both are saved through `receipt-vault`:

| Field | Invoice | Receipt |
|---|---|---|
| source | `claude-ai` | `claude-ai` |
| vendor | `Anthropic` | `Anthropic` |
| type | `Invoice` | `Receipt` |
| number | Invoice number (`VLYWGTAO-0005`) | Receipt number (`2359-3323-9793`) |
| date | Date of issue | Date paid |
| amount | **Total**, tax included | **Amount paid** (Total minus any applied balance) |

The invoice is the qualified invoice for Japan JCT; the receipt proves what was actually charged. They can differ when a credit balance was applied.

## Flow

Work in one tab. Never click **Download PDF** in the claude.ai list: it opens a tab outside your tab group.

1. Navigate to https://claude.ai/settings/billing. It redirects to `/new#settings/billing` and opens Settings as a dialog. That is expected.
2. Signed in when the dialog shows the current plan and an **Invoices** table. Otherwise hand the tab to the user to sign in, and wait. Never type or read credentials.
3. Read the table with `read_page` on the `Invoices` table (`find` "Invoices table" gives its ref). `get_page_text` does not see the dialog. Each row gives date, total, status and a **Download PDF** link to `https://pay.stripe.com/invoice/<acct>/<id>/pdf?s=ap`.
4. Skip, and count as skipped:
   - rows whose status is not `Paid`
   - rows whose total is zero or negative (credit notes, e.g. `-$86`)
5. For every remaining row, check the vault before opening anything. `$` is `USD`; write the total with two decimals.
   ```
   has --source claude-ai --type Invoice --date 2026-04-30 --date-tolerance 1 --currency USD --amount 220.00
   has --source claude-ai --type Receipt --date 2026-04-30 --date-tolerance 1
   ```
   Both `1` or more: already saved. Only open rows where either is `0`.
6. For each row to fetch, navigate the same tab to the link **without** `/pdf?s=ap`. It lands on `invoice.stripe.com/i/...`. Read it with `get_page_text`: invoice number, date paid, amount paid. The page follows the browser language; the two buttons are **Download invoice** / **Download receipt** (Japanese: 請求書をダウンロード / 領収書をダウンロード).
7. Invoice (skip if its `has` was not `0`):
   1. `find` the download invoice button and click it.
   2. `latest-download --pattern 'Invoice-*.pdf' --max-age 120 --wait 30`
   3. Read the PDF. Invoice number must equal the page, Total must equal the row total, Date of issue must be within one day of the row date (see Dates).
   4. `save <pdf> --source claude-ai --vendor Anthropic --type Invoice --number <Invoice number> --date <Date of issue> --currency <from PDF> --amount <Total>`
8. Receipt (skip if its `has` was not `0`):
   1. Click the download receipt button.
   2. `latest-download --pattern 'Receipt-*.pdf' --max-age 120 --wait 30`
   3. Read the PDF. Invoice number must equal the page, Amount paid and Date paid must equal the page.
   4. `save <pdf> --source claude-ai --vendor Anthropic --type Receipt --number <Receipt number> --date <Date paid> --currency <from PDF> --amount <Amount paid>`
9. Report per row: saved, already saved, skipped (and why), or mismatch (with both values). Then close your tab.

If any check in 7 or 8 fails, do not save; leave the PDF in `~/Downloads` and report the mismatch.

## Dates

claude.ai shows dates in the user's time zone; Stripe pages and PDFs use US time. The same charge can read `Mar 5, 2026` in the list and `March 4, 2026` on the PDF. So:

- Always save the date printed on the PDF.
- Compare the list date with the PDF date allowing one day either way. Amounts and the invoice number must still match exactly, and the Stripe page and the PDF must agree on the date.
- Always pass `--date-tolerance 1` to `has` with a list date.

## Notes

- Do not write the Stripe links anywhere (ledger, report, files). Anyone with the link can open the invoice.
- Click the download buttons one at a time, each in its own tool call. A download briefly leaves the page, and a batched second click fails.
- If the receipt was paid more than a day after the invoice, the `has --type Receipt` check misses it and the receipt is fetched again. `save` then prints `duplicate:`, which is fine.
