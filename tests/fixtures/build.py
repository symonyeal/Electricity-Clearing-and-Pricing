# Rebuild the committed price fixtures from the downloaded archive.
# The fixtures keep the published header, quoting and row order, for two zones only,
# so the tests parse the same text the archive publishes. Run from the repository root:
#   python tests/fixtures/build.py
#
# LEGEND
#   DAYS,ZONES : the local days and zone names kept; every other row is dropped
#   src,dst    : the downloaded monthly archive and the fixture written beside the tests

import io
import zipfile
from pathlib import Path

DAYS = ["2025-03-08", "2025-03-09", "2025-03-10", "2025-06-01", "2025-09-19",
        "2025-09-20", "2025-10-25", "2025-10-26", "2025-10-27", "2025-10-28",
        "2025-10-29", "2025-10-30", "2025-10-31", "2025-11-01", "2025-11-02",
        "2025-11-03"]
ZONES = ("N.Y.C.", "WEST")
SRC, DST = Path("data/nyiso"), Path("tests/fixtures/nyiso")


def keep(line, head):
    return head or any(f'"{z}"' in line or f",{z}," in line for z in ZONES)


def main():
    n = 0
    for k in ("damlbmp", "realtime"):
        for m in sorted({d[:7].replace("-", "") + "01" for d in DAYS}):
            src = SRC / k / f"{m}{k}_zone_csv.zip"
            out = io.BytesIO()
            with zipfile.ZipFile(src) as z, zipfile.ZipFile(out, "w",
                                                            zipfile.ZIP_DEFLATED) as w:
                for d in DAYS:
                    name = f"{d.replace('-', '')}{k}_zone.csv"
                    if d[:7].replace("-", "") + "01" != m or name not in z.namelist():
                        continue
                    t = z.read(name).decode("utf-8-sig").splitlines()
                    w.writestr(name, "\n".join(
                        x for i, x in enumerate(t) if keep(x, i == 0)) + "\n")
                    n += 1
            p = DST / k / f"{m}{k}_zone_csv.zip"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(out.getvalue())
    print(f"wrote {n} day files under {DST}")


if __name__ == "__main__":
    main()
