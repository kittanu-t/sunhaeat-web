# ruff: noqa: S608 -- SQL is built from constants in this file
"""Download Overture places and Thai province polygons for the Isan bounding box."""
import os
import sys

import duckdb

RELEASE = "2026-11-18.0"
ROOT = f"s3://overturemaps-us-west-2/release/{RELEASE}"
BOX = "bbox.xmin BETWEEN 100.7 AND 105.8 AND bbox.ymin BETWEEN 14.0 AND 18.6"


def main(out):
    os.makedirs(out, exist_ok=True)
    os.chdir(out)  # relative COPY targets avoid quoting non-ASCII paths
    c = duckdb.connect()
    c.execute("install httpfs;load httpfs;install spatial;load spatial;set s3_region='us-west-2'")
    c.execute(f"""COPY (SELECT * EXCLUDE (theme, type) FROM read_parquet('{ROOT}/theme=places/type=place/*')
        WHERE {BOX}) TO 'places.parquet' (FORMAT parquet)""")
    print("places", c.execute("select count(*) from 'places.parquet'").fetchone(), flush=True)
    c.execute(f"""COPY (SELECT * EXCLUDE (theme, type) FROM read_parquet('{ROOT}/theme=divisions/type=division_area/*')
        WHERE country='TH' AND subtype='region') TO 'provinces.parquet' (FORMAT parquet)""")
    print("provinces", c.execute("select count(*) from 'provinces.parquet'").fetchone())


if __name__ == "__main__":
    main(sys.argv[1])
