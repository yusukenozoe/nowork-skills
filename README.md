# nowork-skills

**A collection of skills that makes your life easier.**

nowork-skills is a set of [Agent Skills](https://agentskills.io) for the small, recurring chores of running a business. Each skill is a plain folder with a `SKILL.md`, so it works in Claude and in any other agent that supports the open standard.

The first skill saves your Claude invoices into one folder, in date order.

```
> Get my Claude invoices.

  2026-04-30_Anthropic_VLYWGTAO-0005_USD220.00.pdf   saved
  3 already saved, 1 credit note skipped
```

## Principles

1. **Simple** — One folder of PDFs. The file names are the record; there is no database.
2. **Accurate** — Date, invoice number and total come from the PDF, and the total must match the billing page.
3. **No duplicates** — The invoice number is in the file name, so an invoice already in the folder is skipped.
4. **No passwords** — The agent uses the browser session you already have. When a site asks you to sign in, it waits for you.

## Skills

| Skill | What it does |
|---|---|
| `claude-invoices` | Saves Claude Pro / Max invoices from claude.ai |

## The folder

```
~/Documents/nowork/                 override with NOWORK_DIR
├─ 2025-05-30_Anthropic_VLYWGTAO-0001_USD200.00.pdf
├─ 2026-02-04_Anthropic_VLYWGTAO-0002_USD36.85.pdf
├─ 2026-03-04_Anthropic_VLYWGTAO-0003_USD200.00.pdf
└─ 2026-04-30_Anthropic_VLYWGTAO-0005_USD220.00.pdf
```

`<date>_<vendor>_<invoice number>_<currency><total>.pdf`

- Date: date of issue on the invoice
- Total: tax included, in the currency's usual decimals (`USD220.00`, `JPY3980`)

## How claude-invoices works

1. Opens https://claude.ai/settings/billing and reads the Invoices table: date, total, status, Stripe PDF link
2. Skips unpaid rows, credit notes, and invoices already in the folder
3. Downloads each new PDF directly with `curl`
4. Reads the invoice number, date and total from the PDF and checks the total against the list
5. Saves it under its name without overwriting

The billing page shows dates in your time zone and Stripe uses US time, so the two can differ by a day. The skill allows for that and names the file by the invoice's own date.

## Requirements

- A browser tool for the agent: the built-in browser in the Claude desktop app, or [Claude in Chrome](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) with Claude Code
- Signed in to claude.ai in that browser
- `curl` (preinstalled on macOS)

## Install and use

```sh
npx skills add yusukenozoe/nowork-skills --all
```

```
> Get my Claude invoices.
```

## License

MIT
