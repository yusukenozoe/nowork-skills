"""Tests for skills/receipt-vault/scripts/vault.py. Run: python3 -m unittest discover tests"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

VAULT_PY = os.path.join(os.path.dirname(__file__), "..", "skills", "receipt-vault", "scripts", "vault.py")

PDF = b"%PDF-1.4\n% test receipt\n%%EOF\n"


class VaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(self.tmp.name, "vault")
        self.downloads = os.path.join(self.tmp.name, "Downloads")
        os.makedirs(self.downloads)

    def tearDown(self):
        self.tmp.cleanup()

    def run_vault(self, *args):
        env = dict(os.environ, NOWORK_VAULT=self.vault, NOWORK_DOWNLOADS=self.downloads)
        return subprocess.run(
            [sys.executable, VAULT_PY] + list(args),
            env=env, capture_output=True, text=True,
        )

    def download(self, name, content=PDF):
        path = os.path.join(self.downloads, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def save(self, pdf, number="2841-3307", date="2026-10-01", currency="USD", amount="20.00"):
        return self.run_vault(
            "save", pdf, "--source", "claude-ai", "--vendor", "Anthropic", "--type", "Receipt",
            "--number", number, "--date", date, "--currency", currency, "--amount", amount,
        )

    def ledger(self):
        with open(os.path.join(self.vault, ".nowork", "documents.jsonl")) as f:
            return [json.loads(line) for line in f]

    # --- save -----------------------------------------------------------

    def test_save_moves_pdf_and_writes_ledger(self):
        pdf = self.download("Receipt-2841-3307.pdf")
        r = self.save(pdf)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("saved: claude-ai:2841-3307", r.stdout)

        rel = "2026/10/2026-10-01_Anthropic_Receipt_USD20.00.pdf"
        self.assertTrue(os.path.isfile(os.path.join(self.vault, rel)))
        self.assertFalse(os.path.exists(pdf))

        (doc,) = self.ledger()
        self.assertEqual(doc["id"], "claude-ai:2841-3307")
        self.assertEqual(doc["amount"], "20.00")
        self.assertEqual(doc["file"], rel)
        self.assertRegex(doc["fetchedAt"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
        self.assertEqual(os.listdir(os.path.join(self.vault, "2026", "10")), [os.path.basename(rel)])

    def test_save_duplicate_number_is_skipped_and_pdf_kept(self):
        self.save(self.download("Receipt-a.pdf"))
        pdf = self.download("Receipt-b.pdf")
        r = self.save(pdf)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("duplicate: claude-ai:2841-3307"))
        self.assertTrue(os.path.exists(pdf))
        self.assertEqual(len(self.ledger()), 1)

    def test_same_name_gets_number_then_counter(self):
        self.save(self.download("a.pdf", PDF + b"a"), number="1111")
        self.save(self.download("b.pdf", PDF + b"b"), number="2222")
        self.save(self.download("c.pdf", PDF + b"c"), number="2222-x")
        files = [d["file"] for d in self.ledger()]
        self.assertEqual(files, [
            "2026/10/2026-10-01_Anthropic_Receipt_USD20.00.pdf",
            "2026/10/2026-10-01_Anthropic_Receipt_USD20.00_2222.pdf",
            "2026/10/2026-10-01_Anthropic_Receipt_USD20.00_2222-x.pdf",
        ])
        self.save(self.download("d.pdf", PDF + b"d"), number="2222")  # duplicate id
        self.save(self.download("e.pdf", PDF + b"e"), number="2222 x")  # suffix "2222-x" taken
        self.assertEqual(self.ledger()[-1]["file"], "2026/10/2026-10-01_Anthropic_Receipt_USD20.00_2.pdf")

    def test_save_reuses_file_left_by_interrupted_save(self):
        folder = os.path.join(self.vault, "2026", "10")
        os.makedirs(folder)
        with open(os.path.join(folder, "2026-10-01_Anthropic_Receipt_USD20.00.pdf"), "wb") as f:
            f.write(PDF)
        r = self.save(self.download("Receipt.pdf"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ledger()[0]["file"], "2026/10/2026-10-01_Anthropic_Receipt_USD20.00.pdf")
        self.assertEqual(len(os.listdir(folder)), 1)

    def test_zero_decimal_currency(self):
        r = self.save(self.download("r.pdf"), currency="JPY", amount="3980")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.ledger()[0]["file"], "2026/10/2026-10-01_Anthropic_Receipt_JPY3980.pdf")

    def test_invalid_input_is_rejected(self):
        cases = [
            dict(amount="20"),
            dict(amount="20.0"),
            dict(amount="$20.00"),
            dict(amount="1,020.00"),
            dict(currency="JPY", amount="3980.00"),
            dict(currency="usd"),
            dict(date="2026-13-01"),
            dict(date="2026/10/01"),
            dict(number="  "),
        ]
        for kwargs in cases:
            pdf = self.download("r.pdf")
            r = self.save(pdf, **kwargs)
            self.assertEqual(r.returncode, 2, kwargs)
            self.assertIn("error:", r.stderr)
            self.assertTrue(os.path.exists(pdf))
        self.assertFalse(os.path.exists(os.path.join(self.vault, ".nowork", "documents.jsonl")))

    def test_bad_vendor_and_non_pdf_are_rejected(self):
        r = self.run_vault(
            "save", self.download("r.pdf"), "--source", "claude-ai", "--vendor", "Anthropic PBC",
            "--type", "Receipt", "--number", "1", "--date", "2026-10-01", "--currency", "USD", "--amount", "20.00",
        )
        self.assertEqual(r.returncode, 2)
        r = self.save(self.download("r.html", b"<html>"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a PDF", r.stderr)

    # --- has / list -----------------------------------------------------

    def test_has_counts_matches(self):
        self.assertEqual(self.run_vault("has", "--source", "claude-ai", "--date", "2026-10-01",
                                        "--currency", "USD", "--amount", "20.00").stdout.strip(), "0")
        self.save(self.download("a.pdf", PDF + b"a"), number="1")
        self.save(self.download("b.pdf", PDF + b"b"), number="2")
        self.save(self.download("c.pdf", PDF + b"c"), number="3", amount="100.00")
        r = self.run_vault("has", "--source", "claude-ai", "--date", "2026-10-01", "--currency", "USD", "--amount", "20.00")
        self.assertEqual(r.stdout.strip(), "2")

    def test_list_filters_by_source_and_month(self):
        self.save(self.download("a.pdf", PDF + b"a"), number="1", date="2026-11-01")
        self.save(self.download("b.pdf", PDF + b"b"), number="2", date="2026-10-01")
        r = self.run_vault("list", "--source", "claude-ai", "--month", "2026-10")
        docs = [json.loads(line) for line in r.stdout.splitlines()]
        self.assertEqual([d["number"] for d in docs], ["2"])
        r = self.run_vault("list")
        self.assertEqual([json.loads(line)["number"] for line in r.stdout.splitlines()], ["2", "1"])
        self.assertEqual(self.run_vault("list", "--month", "2026-13").returncode, 2)

    # --- latest-download ------------------------------------------------

    def test_latest_download_picks_newest_match(self):
        old = self.download("Receipt-old.pdf")
        os.utime(old, (time.time() - 100, time.time() - 100))
        new = self.download("Receipt-new.pdf")
        self.download("Invoice-other.pdf")
        r = self.run_vault("latest-download", "--pattern", "Receipt-*.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), new)

    def test_latest_download_respects_max_age_and_partial_downloads(self):
        old = self.download("Receipt-old.pdf")
        os.utime(old, (time.time() - 100, time.time() - 100))
        r = self.run_vault("latest-download", "--pattern", "Receipt-*.pdf", "--max-age", "30")
        self.assertEqual(r.returncode, 1)
        self.download("Receipt-new.pdf")
        self.download("Receipt-new.pdf.crdownload")
        r = self.run_vault("latest-download", "--pattern", "Receipt-*.pdf", "--max-age", "30")
        self.assertEqual(r.returncode, 1)

    def test_latest_download_waits(self):
        env = dict(os.environ, NOWORK_VAULT=self.vault, NOWORK_DOWNLOADS=self.downloads)
        proc = subprocess.Popen(
            [sys.executable, VAULT_PY, "latest-download", "--pattern", "Receipt-*.pdf", "--wait", "10"],
            env=env, stdout=subprocess.PIPE, text=True,
        )
        time.sleep(1)
        path = self.download("Receipt-late.pdf")
        out, _ = proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(out.strip(), path)


if __name__ == "__main__":
    unittest.main()
