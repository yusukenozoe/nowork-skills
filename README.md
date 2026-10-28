# nowork-skills

**A collection of skills that makes your life easier.**

nowork-skills is a set of [Agent Skills](https://agentskills.io) for the small, recurring chores of running a business. Each skill is a plain folder with a `SKILL.md`, so it works in Claude and in any other agent that supports the open standard.

The first skill fetches your Claude subscription receipts from claude.ai and files them into a plain folder on your machine.

```
> Get my Claude receipts.

  claude.ai   2 new   10 already saved
  → ~/Documents/nowork/2026/10/
```

## Principles

1. **Accurate** — The date, amount and currency shown on the billing page must match what is read from the saved PDF. Nothing enters the ledger until they agree.
2. **Fast** — Go straight to the billing page by URL, read pages as text, and open only documents that are not saved yet.
3. **Signed in, without passwords** — The skill uses the browser session you already have. When a site asks you to sign in, the agent hands the browser to you and resumes where it left off. It never sees, types or stores credentials.
4. **No duplicates** — Every document is identified by its source and document number. Run it as often as you like; you get each receipt exactly once.

## Skills

| Skill | What it does |
|---|---|
| `receipt-vault` | Saves PDFs into the vault under standard names, keeps the ledger, skips duplicates |
| `claude-ai` | Fetches Claude Pro / Max receipts from claude.ai |

## Repository layout

```
nowork-skills/
├─ README.md
├─ LICENSE
└─ skills/
   ├─ receipt-vault/
   │  ├─ SKILL.md
   │  ├─ scripts/vault.py              checks and saves (Python 3.8+, standard library only)
   │  └─ references/document.schema.json
   └─ claude-ai/
      └─ SKILL.md
```

Domain skills describe only what is unique to one site. Everything about saving lives in `receipt-vault`.

## Vault spec (v1)

Receipts are plain PDFs in plain folders. Anyone can open the vault in a file manager and understand it, with or without an agent.

```
~/Documents/nowork/                 override with NOWORK_VAULT
├─ .nowork/
│  ├─ sources.json
│  └─ documents.jsonl
└─ 2026/
   └─ 10/
      ├─ 2026-10-01_Anthropic_Receipt_USD20.00.pdf
      └─ 2026-10-01_Anthropic_Receipt_USD20.00_2841-3307.pdf
```

- **Folders**: `YYYY/MM/`, by the date on the document
- **File names**: `YYYY-MM-DD_<Vendor>_<Type>_<Currency><Amount>.pdf`
  - Vendor: short brand name, ASCII letters and digits only
  - Type: `Receipt` or `Invoice`
  - Currency: ISO 4217 code
  - Amount: total including tax, in the currency's usual decimals (`USD20.00`, `JPY3980`)
  - Same name twice: the second gets its document number appended (`_2841-3307`), or `_2` when it has none
- **Ledger**: `.nowork/documents.jsonl`, one JSON object per line, append-only

```json
{"id":"claude-ai:2841-3307","source":"claude-ai","vendor":"Anthropic","type":"Receipt","number":"2841-3307","date":"2026-10-01","currency":"USD","amount":"20.00","file":"2026/10/2026-10-01_Anthropic_Receipt_USD20.00.pdf","fetchedAt":"2026-11-03T09:12:00+09:00"}
```

`id` is `<source>:<number>` and is the duplicate key. `amount` is a string so decimals stay exact. `file` is relative to the vault root, so the vault can live anywhere.

## receipt-vault

The agent never writes to the vault by hand. Every check and save goes through `vault.py`.

| Command | What it does |
|---|---|
| `has --source --date --currency --amount` | Prints how many matching documents are saved |
| `latest-download --pattern 'Receipt-*.pdf'` | Prints the newest matching PDF in `~/Downloads` |
| `save <pdf> --source --vendor --type --number --date --currency --amount` | Moves the PDF into `YYYY/MM/` under its standard name and appends one ledger line. Prints `duplicate:` if the number is already saved |
| `list --source --month YYYY-MM` | Lists saved documents |

## claude-ai

Covers Pro and Max plans bought on the web.

| Field | Value |
|---|---|
| source | `claude-ai` |
| vendor | `Anthropic` |
| type | `Receipt` |
| number | Receipt number on the PDF |
| date | Date paid on the PDF |
| amount | Amount paid on the PDF, tax included |

Flow:

1. Open https://claude.ai/settings/billing
2. Signed in when the page shows the current plan and an **Invoices** section. Otherwise hand the tab to the user to sign in
3. Read the Invoices list as text: date, amount, status, **View**
4. Skip rows already saved (`has`)
5. For each new row: **View** → Stripe invoice page → **Download receipt** → `latest-download` → read the PDF and check it against the row → `save`
6. Report how many were saved and how many were already there

## Requirements

- [Claude Code](https://code.claude.com) 2.0.73+ with the [Claude in Chrome](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn) extension 1.0.36+
- Chrome signed in to claude.ai
- `python3` 3.8+

## Install and use

```sh
npx skills add yusukenozoe/nowork-skills --all
claude --chrome
```

```
> Get my Claude receipts for October.
```

## Roadmap

- [ ] **M0** Repository: README, MIT license, `skills/` layout
- [ ] **M1** receipt-vault: `vault.py` (`has` / `save` / `latest-download` / `list`) and `document.schema.json`
- [ ] **M2** claude-ai: one receipt end to end, from the billing page to the vault
- [ ] **M3** A second run saves nothing new; a mismatch is reported, not saved
- [ ] **M4** Publish on GitHub

After the MVP: more domains (platform.claude.com, github.com, vercel.com, …), a skill that drafts new domain skills from a live billing page, then 100 domains and Show HN.

## License

MIT
