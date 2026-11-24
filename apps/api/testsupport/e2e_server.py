"""API with a throwaway database for browser tests: python -m testsupport.e2e_server PORT

The real pipeline importer loads a small catalog plus the demo restaurants, so browser tests see production-shaped data.
"""
import hashlib
import json
import sys

import psycopg
import uvicorn

from app.main import create_app
from app.settings import Settings
from pipeline.build_dataset import finalize
from pipeline.import_dataset import DEMO_PATH, import_rows
from testsupport.db import migrate, postgres

SECRET = "e2e-hmac-secret"
NAMES = ["ร้านส้มตำระเบิด", "ลาบนัวหลังมอ", "ก๋วยเตี๋ยวเรือริมบึง", "กาแฟดอกคูน", "หมูกระทะทุ่งสร้าง", "<img src=x onerror=alert(1)> ส้มตำ"]
PROVINCES = {f"TH-{n}": name for n, name in zip(range(30, 50), [
    "นครราชสีมา", "บุรีรัมย์", "สุรินทร์", "ศรีสะเกษ", "อุบลราชธานี", "ยโสธร", "ชัยภูมิ", "อำนาจเจริญ", "บึงกาฬ", "หนองบัวลำภู",
    "ขอนแก่น", "อุดรธานี", "เลย", "หนองคาย", "มหาสารคาม", "ร้อยเอ็ด", "กาฬสินธุ์", "สกลนคร", "นครพนม", "มุกดาหาร"], strict=True)}


def catalog() -> list[dict]:
    def row(i, name, province="TH-40", lat=16.43, lon=102.83):
        return {"source_id": f"e2e-{i}", "name": name, "taxonomy": "restaurant", "province_code": province,
                "lat": lat + i * 0.004, "lon": lon + i * 0.003, "address": f"{i} ถนนทดสอบ", "locality": "ในเมือง",
                "websites": [], "socials": ["https://www.facebook.com/100"], "confidence": 0.95 - i / 100,
                "sources": [{"dataset": "meta", "record_id": str(i), "license": "CDLA-Permissive-2.0"}]}
    rows = [row(i, n) for i, n in enumerate(NAMES)]
    rows += [row(20 + i, f"ส้มตำโคราช {i}", "TH-30", 14.95, 102.05) for i in range(3)]
    return finalize(rows)


def main(port: int) -> None:
    with postgres() as url:
        migrate(url)
        password = hashlib.sha256(b"e2e").hexdigest()
        with psycopg.connect(url, autocommit=True) as conn:
            import_rows(conn, catalog(), json.loads(DEMO_PATH.read_text(encoding="utf8")), PROVINCES, "e2e-release")
            conn.execute(f"alter role api_runtime login password '{password}'")
            runtime = f"postgresql://api_runtime:{password}@{conn.info.host}:{conn.info.port}/{conn.info.dbname}"
        app = create_app(Settings(_env_file=None, database_url=runtime, api_hmac_secret=SECRET))
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main(int(sys.argv[1]))
