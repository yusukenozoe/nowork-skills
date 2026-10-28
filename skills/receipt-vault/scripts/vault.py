#!/usr/bin/env python3
"""nowork vault: check and save receipt PDFs. Python 3.8+, standard library only.

Vault root is ~/Documents/nowork, or $NOWORK_VAULT when set.
Downloads folder is ~/Downloads, or $NOWORK_DOWNLOADS when set.

Exit codes: 0 ok, 1 nothing found, 2 invalid input or vault error.
"""

import argparse
import datetime
import filecmp
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import time

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

LEDGER = os.path.join(".nowork", "documents.jsonl")
LOCK = os.path.join(".nowork", "lock")

TYPES = ("Receipt", "Invoice")

# ISO 4217 minor units that differ from the usual 2.
MINOR_UNITS = {
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0, "KMF": 0,
    "KRW": 0, "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0, "VND": 0, "VUV": 0,
    "XAF": 0, "XOF": 0, "XPF": 0,
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3, "TND": 3,
}

SOURCE_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
VENDOR_RE = re.compile(r"^[A-Za-z0-9]+$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class VaultError(Exception):
    pass


def vault_root():
    return os.path.expanduser(os.environ.get("NOWORK_VAULT") or "~/Documents/nowork")


def downloads_dir():
    return os.path.expanduser(os.environ.get("NOWORK_DOWNLOADS") or "~/Downloads")


# --- validation -------------------------------------------------------------

def check_source(value):
    if not SOURCE_RE.match(value):
        raise VaultError("source must be lowercase letters, digits, '.' or '-': %r" % value)
    return value


def check_vendor(value):
    if not VENDOR_RE.match(value):
        raise VaultError("vendor must be ASCII letters and digits only: %r" % value)
    return value


def check_type(value):
    if value not in TYPES:
        raise VaultError("type must be one of %s: %r" % (", ".join(TYPES), value))
    return value


def check_number(value):
    value = value.strip()
    if not value or any(c in value for c in "\r\n"):
        raise VaultError("number must be a non-empty single line: %r" % value)
    return value


def check_date(value):
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise VaultError("date must be YYYY-MM-DD: %r" % value)
    if len(value) != 10:
        raise VaultError("date must be YYYY-MM-DD: %r" % value)
    return value


def check_currency(value):
    if not CURRENCY_RE.match(value):
        raise VaultError("currency must be an ISO 4217 code such as USD: %r" % value)
    return value


def check_amount(value, currency):
    decimals = MINOR_UNITS.get(currency, 2)
    pattern = r"^(0|[1-9]\d*)" + (r"\.\d{%d}" % decimals if decimals else "") + "$"
    if not re.match(pattern, value):
        example = "3980" if decimals == 0 else "20." + "0" * decimals
        raise VaultError(
            "amount for %s must have %d decimals and no separators (e.g. %s): %r"
            % (currency, decimals, example, value)
        )
    return value


def check_month(value):
    if not MONTH_RE.match(value) or not 1 <= int(value[5:]) <= 12:
        raise VaultError("month must be YYYY-MM: %r" % value)
    return value


# --- ledger -----------------------------------------------------------------

def read_ledger(root):
    path = os.path.join(root, LEDGER)
    if not os.path.exists(path):
        return []
    docs = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                docs.append(json.loads(line))
            except ValueError:
                raise VaultError("ledger line %d is not valid JSON: %s" % (lineno, path))
    return docs


def append_ledger(root, doc):
    path = os.path.join(root, LEDGER)
    line = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


class Lock:
    """Exclusive lock on the vault so two saves never interleave."""

    def __init__(self, root):
        os.makedirs(os.path.join(root, ".nowork"), exist_ok=True)
        self.path = os.path.join(root, LOCK)

    def __enter__(self):
        self.f = open(self.path, "a")
        if fcntl:
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if fcntl:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# --- commands ---------------------------------------------------------------

def cmd_has(args):
    if args.amount is not None and args.currency is None:
        raise VaultError("--amount needs --currency")
    wanted = {"source": check_source(args.source)}
    if args.type is not None:
        wanted["type"] = check_type(args.type)
    if args.number is not None:
        wanted["number"] = check_number(args.number)
    dates = None
    if args.date is not None:
        day = datetime.date.fromisoformat(check_date(args.date))
        if args.date_tolerance < 0:
            raise VaultError("--date-tolerance must be 0 or more")
        dates = {
            (day + datetime.timedelta(days=n)).isoformat()
            for n in range(-args.date_tolerance, args.date_tolerance + 1)
        }
    elif args.date_tolerance:
        raise VaultError("--date-tolerance needs --date")
    if args.currency is not None:
        wanted["currency"] = check_currency(args.currency)
    if args.amount is not None:
        wanted["amount"] = check_amount(args.amount, args.currency)
    count = sum(
        1
        for d in read_ledger(vault_root())
        if all(d.get(k) == v for k, v in wanted.items())
        and (dates is None or d.get("date") in dates)
    )
    print(count)
    return 0


def find_download(pattern, max_age):
    if os.sep in pattern or "/" in pattern:
        raise VaultError("pattern must be a file name pattern, not a path: %r" % pattern)
    now = time.time()
    best = None
    for path in glob.glob(os.path.join(downloads_dir(), pattern)):
        if not os.path.isfile(path) or os.path.exists(path + ".crdownload"):
            continue
        mtime = os.path.getmtime(path)
        if max_age is not None and now - mtime > max_age:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, path)
    if best is None:
        return None
    # Make sure the browser has finished writing it.
    size = os.path.getsize(best[1])
    time.sleep(0.3)
    if os.path.getsize(best[1]) != size or size == 0:
        return None
    return best[1]


def cmd_latest_download(args):
    deadline = time.time() + max(args.wait, 0)
    while True:
        path = find_download(args.pattern, args.max_age)
        if path:
            print(path)
            return 0
        if time.time() >= deadline:
            print("not found: no %s in %s" % (args.pattern, downloads_dir()), file=sys.stderr)
            return 1
        time.sleep(0.5)


def is_pdf(path):
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def place_file(src, folder, base, number):
    """Copy src into folder under a free standard name and return the name.

    The copy is written to a temp file and linked into place, so a name is
    never overwritten and a half-written PDF never appears in the vault.
    """
    suffix = re.sub(r"[^A-Za-z0-9-]+", "-", number).strip("-")
    candidates = [base + ".pdf"]
    if suffix:
        candidates.append("%s_%s.pdf" % (base, suffix))
    candidates += ["%s_%d.pdf" % (base, n) for n in range(2, 1000)]

    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".saving-", suffix=".pdf")
    os.close(fd)
    # mkstemp creates 0600; give the PDF the same mode as any new file.
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(tmp, 0o666 & ~umask)
    try:
        shutil.copyfile(src, tmp)
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        for name in candidates:
            dest = os.path.join(folder, name)
            try:
                os.link(tmp, dest)
                return name
            except FileExistsError:
                # Same bytes already here: an earlier save stopped before the
                # ledger line was written. Reuse that file.
                if filecmp.cmp(src, dest, shallow=False):
                    return name
        raise VaultError("no free file name for %s in %s" % (base, folder))
    finally:
        os.unlink(tmp)


def cmd_save(args):
    source = check_source(args.source)
    vendor = check_vendor(args.vendor)
    doc_type = check_type(args.type)
    number = check_number(args.number)
    date = check_date(args.date)
    currency = check_currency(args.currency)
    amount = check_amount(args.amount, currency)

    src = os.path.expanduser(args.pdf)
    if not os.path.isfile(src):
        raise VaultError("no such file: %s" % src)
    if not is_pdf(src):
        raise VaultError("not a PDF: %s" % src)

    root = vault_root()
    doc_id = "%s:%s" % (source, number)
    with Lock(root):
        for d in read_ledger(root):
            if d.get("id") == doc_id:
                print("duplicate: %s %s" % (doc_id, d.get("file")))
                return 0

        rel_dir = os.path.join(date[:4], date[5:7])
        folder = os.path.join(root, rel_dir)
        os.makedirs(folder, exist_ok=True)
        base = "%s_%s_%s_%s%s" % (date, vendor, doc_type, currency, amount)
        name = place_file(src, folder, base, number)
        rel_file = "%s/%s/%s" % (date[:4], date[5:7], name)

        append_ledger(root, {
            "id": doc_id,
            "source": source,
            "vendor": vendor,
            "type": doc_type,
            "number": number,
            "date": date,
            "currency": currency,
            "amount": amount,
            "file": rel_file,
            "fetchedAt": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        })

    os.unlink(src)
    print("saved: %s %s" % (doc_id, rel_file))
    return 0


def cmd_list(args):
    source = check_source(args.source) if args.source else None
    month = check_month(args.month) if args.month else None
    docs = [
        d
        for d in read_ledger(vault_root())
        if (source is None or d.get("source") == source)
        and (month is None or str(d.get("date", "")).startswith(month + "-"))
    ]
    docs.sort(key=lambda d: (d.get("date", ""), d.get("id", "")))
    for d in docs:
        print(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    return 0


# --- cli --------------------------------------------------------------------

def parser():
    p = argparse.ArgumentParser(prog="vault.py", description="Check and save receipt PDFs in the nowork vault.")
    sub = p.add_subparsers(dest="command", metavar="command")
    sub.required = True

    has = sub.add_parser("has", help="print how many matching documents are saved")
    has.add_argument("--source", required=True)
    has.add_argument("--type", choices=TYPES)
    has.add_argument("--number")
    has.add_argument("--date")
    has.add_argument("--date-tolerance", type=int, default=0, metavar="DAYS",
                     help="also match dates up to this many days before or after --date")
    has.add_argument("--currency")
    has.add_argument("--amount")
    has.set_defaults(func=cmd_has)

    latest = sub.add_parser("latest-download", help="print the newest matching PDF in the downloads folder")
    latest.add_argument("--pattern", required=True, help="file name pattern, e.g. 'Receipt-*.pdf'")
    latest.add_argument("--max-age", type=float, default=None, metavar="SECONDS",
                        help="only files modified within this many seconds")
    latest.add_argument("--wait", type=float, default=0, metavar="SECONDS",
                        help="keep looking for up to this many seconds")
    latest.set_defaults(func=cmd_latest_download)

    save = sub.add_parser("save", help="move a PDF into the vault and add it to the ledger")
    save.add_argument("pdf")
    save.add_argument("--source", required=True)
    save.add_argument("--vendor", required=True)
    save.add_argument("--type", required=True, choices=TYPES)
    save.add_argument("--number", required=True)
    save.add_argument("--date", required=True)
    save.add_argument("--currency", required=True)
    save.add_argument("--amount", required=True)
    save.set_defaults(func=cmd_save)

    lst = sub.add_parser("list", help="list saved documents as JSON lines")
    lst.add_argument("--source")
    lst.add_argument("--month", help="YYYY-MM")
    lst.set_defaults(func=cmd_list)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except VaultError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
