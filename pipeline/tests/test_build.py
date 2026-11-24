import duckdb
import pytest

from pipeline.build_dataset import extract, finalize

BASE = {
    "source_id": "a", "name": "ส้มตำแม่", "taxonomy": "restaurant", "province_code": "TH-40",
    "lat": 16.43, "lon": 102.83, "address": "1 ถนน โทร 0812345678", "locality": "ขอนแก่น",
    "websites": ["http://x.test", "https://ok.test/a"], "socials": ["https://www.facebook.com/123"], "confidence": 0.9,
    "sources": [{"dataset": "meta", "record_id": "1", "license": "CDLA-Permissive-2.0"}],
}


def row(**kw):
    return BASE | kw


def test_output_shape_has_no_phone_and_only_https():
    (r,) = finalize([row()])
    assert not {"phone", "phones", "emails"} & set(r)
    assert r["website"] == "https://ok.test/a" and r["facebook_url"] == "https://www.facebook.com/123"
    assert r["address"] == "1 ถนน" and r["price_min"] is None and r["price_max"] is None


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "https://user:pw@evil.test", "https://", "ftp://a.test", "https://a b.test"])
def test_unsafe_websites_are_dropped(url):
    assert finalize([row(websites=[url])])[0]["website"] is None


@pytest.mark.parametrize("url", [
    "https://facebook.com.evil.test/1", "https://www.facebook.com/a?b=<x>", "http://www.facebook.com/1"])
def test_only_plain_facebook_pages_are_kept(url):
    assert finalize([row(socials=[url])])[0]["facebook_url"] is None


def test_same_name_nearby_is_merged_keeping_best_confidence_and_far_one_stays():
    out = finalize([row(source_id="a", confidence=0.8), row(source_id="b", name="ส้ม ตำ แม่", lat=16.4309, confidence=0.95),
                    row(source_id="c", lat=16.5)])
    assert sorted(r["source_id"] for r in out) == ["b", "c"]


def test_source_in_two_simplified_provinces_gets_lowest_code_once():
    out = finalize([row(province_code="TH-41"), row(province_code="TH-40")])
    assert [r["province_code"] for r in out] == ["TH-40"]


def test_name_empty_after_cleaning_is_dropped():
    assert finalize([row(name="0812345678")]) == []


def test_order_and_ids_do_not_depend_on_input_order():
    rows = [row(source_id=s, lat=16 + i) for i, s in enumerate("abc")]
    assert finalize(rows) == finalize(rows[::-1])


PLACE = """select '{id}' id, ST_Point({lon}, 16.4) geometry, {conf}::double confidence, ['https://a.test'] websites,
  ['+66'] phones, ['https://www.facebook.com/1'] socials, [{{'freeform':'x','locality':'y','country':'TH'}}] addresses,
  {{'primary':'{name}'}} as names, [{{'dataset':'meta','license':'L','record_id':'r'}}] sources, {status} operating_status,
  '{cat}' basic_category, {{'primary':'restaurant','hierarchy':['{top}']}} taxonomy,
  {{'xmin':{lon}::double,'xmax':{lon}::double,'ymin':16.4::double,'ymax':16.4::double}} bbox"""
DEFAULT = {"id": "ok", "lon": 102.5, "conf": 0.8, "name": "ร้าน", "status": "null::varchar", "cat": "restaurant",
           "top": "food_and_drink"}


def test_extract_applies_gate_rules(tmp_path):
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    variants = [
        {}, {"id": "low", "conf": 0.79}, {"id": "closed", "status": "'permanently_closed'"}, {"id": "bar", "cat": "bar"},
        {"id": "shop", "top": "shopping"}, {"id": "outside", "lon": 105}, {"id": "gold", "name": "ร้านทองทวีชัย"},
        {"id": "farmcafe", "name": "ฟาร์มสุข คาเฟ่"},
    ]
    union = " union all ".join(PLACE.format(**(DEFAULT | v)) for v in variants)
    c.execute(f"copy ({union}) to '{(tmp_path / 'places.parquet').as_posix()}' (format parquet)")
    c.execute(f"""copy (select 'TH-40' region, 'land' class, {{'primary':'จังหวัดขอนแก่น'}} as names,
      ST_MakeEnvelope(102,16,103,17) geometry,
      {{'xmin':102.0::double,'xmax':103.0::double,'ymin':16.0::double,'ymax':17.0::double}} bbox)
      to '{(tmp_path / 'provinces.parquet').as_posix()}' (format parquet)""")
    rows, provinces = extract(tmp_path)
    assert sorted(r["source_id"] for r in rows) == ["farmcafe", "ok"]
    assert provinces == {"TH-40": "ขอนแก่น"} and "phones" not in rows[0]
