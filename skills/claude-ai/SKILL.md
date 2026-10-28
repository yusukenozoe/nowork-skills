---
name: claude-ai
description: Fetches Claude Pro / Max subscription receipts from claude.ai and files them into the nowork vault. Use when the user asks to get, download or file their Claude (claude.ai) receipts or invoices. Requires Claude in Chrome and the receipt-vault skill.
---

# claude-ai

Covers Pro and Max plans bought on the web. Saving is done by the `receipt-vault` skill.

| Field | Value |
|---|---|
| source | `claude-ai` |
| vendor | `Anthropic` |
| type | `Receipt` |
| number | Receipt number on the PDF |
| date | Date paid on the PDF |
| amount | Amount paid on the PDF, tax included |

## Flow

1. Open https://claude.ai/settings/billing
2. Signed in when the page shows the current plan and an **Invoices** section. Otherwise hand the tab to the user to sign in, and wait. Never type or read credentials.
3. Read the Invoices list as text: date, amount, status, **View**
4. Skip rows already saved (`has`). If several rows share a date and amount, compare the count `has` prints with the number of such rows.
5. For each new row: **View** → Stripe invoice page → **Download receipt** → `latest-download --pattern 'Receipt-*.pdf' --max-age 120 --wait 30` → read the PDF and check it against the row → `save`
6. Report how many were saved and how many were already there
