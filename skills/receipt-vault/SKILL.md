---
name: receipt-vault
description: Saves receipt and invoice PDFs into the local nowork vault under standard names, keeps the ledger and skips duplicates. Use whenever a domain skill (such as claude-ai) has a receipt to check or save, or when the user asks what receipts are already saved.
---

# receipt-vault

The vault is a plain folder of PDFs plus an append-only ledger. Never write to it by hand: every check and save goes through `scripts/vault.py`.

- Vault root: `~/Documents/nowork/`, or `$NOWORK_VAULT` when set
- Ledger: `.nowork/documents.jsonl`, one JSON object per line ([schema](references/document.schema.json))
- Duplicate key: `<source>:<number>`

## Commands

Run with `python3 scripts/vault.py <command>` from this skill's folder.

| Command | What it does |
|---|---|
| `has --source --date --currency --amount` | Prints how many matching documents are saved |
| `latest-download --pattern 'Receipt-*.pdf'` | Prints the newest matching PDF in `~/Downloads` |
| `save <pdf> --source --vendor --type --number --date --currency --amount` | Moves the PDF into `YYYY/MM/` under its standard name and appends one ledger line. Prints `duplicate:` if the number is already saved |
| `list --source --month YYYY-MM` | Lists saved documents |

## Rules

1. Before opening a document, ask `has`. Open only documents that are not saved yet.
2. Read the downloaded PDF yourself and check that its date, currency and amount match what the source page showed. If they differ, report the mismatch and do not call `save`.
3. Pass values exactly as printed on the PDF: `date` as `YYYY-MM-DD`, `currency` as an ISO 4217 code, `amount` including tax in the currency's usual decimals (`20.00`, `3980`).
4. `duplicate:` is not an error. Count it as already saved.
