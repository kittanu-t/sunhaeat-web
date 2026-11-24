"""Data-gate spike: count Isan eateries in the Overture extract and draw a seeded sample.

Usage: python pipeline/spike_gate.py data/raw data/spike      (round 1 rules)
       python pipeline/spike_gate.py data/raw data/spike-v2 2 (round 2 rules, fresh seed)
Each round's rules are fixed before its sample is read. Round 2 was derived from round 1 failures,
so only its own fresh sample counts as evidence for it.
"""
import json
import os
import sys

import duckdb

# Places where people go to eat or drink coffee; bars, wineries and breweries stay out.
CATEGORIES = ("restaurant", "cafe", "coffee_shop", "casual_eatery", "fast_food_restaurant",
              "food_truck_stand", "smoothie_juice_bar", "non_alcoholic_beverage_venue")
MIN_CONFIDENCE = {1: 0.6, 2: 0.8}
# Round 2 only: drop names that signal another business unless the name also has a food word.
NON_FOOD = ("amulet|พระเครื่อง|พุทโธ|ร้านทอง|ห้างทอง|โรงสี|บิวตี้|beauty|คลินิก|clinic|โต๊ะจีน|ทุเรียน|ฟาร์ม|farm|"
            "โรงเรียน|school|เทศบาล|อบต|อะไหล่|มือถือ|เสริมสวย|ซ่อม|ขายส่ง|รีสอร์ท|resort|โรงแรม|hotel")
FOOD = ("อาหาร|ครัว|ก๋วยเตี๋ยว|ส้มตำ|ตำ|ข้าว|หมูกระทะ|หมูกะทะ|ปิ้งย่าง|ย่าง|ชาบู|กาแฟ|คาเฟ่|cafe|café|coffee|bakery|"
        "เบเกอรี่|โภชนา|ลาบ|ก้อย|แจ่ว|ปลาเผา|สเต็ก|steak|pizza|restaurant|kitchen|ซูชิ|sushi|โจ๊ก|ชา|นมสด")
SIMPLIFY_DEGREES = 0.0005  # about 50 m; full-resolution polygons make the join impractically slow
SAMPLE_SEED = {1: "sunhaeat-gate-1", 2: "sunhaeat-gate-2"}


def main(raw, out, round_no=1):
    sys.stdout.reconfigure(encoding="utf8")
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    os.chdir(raw)
    c = duckdb.connect()
    c.execute("load spatial")
    report = {}

    def put(key, sql):
        cur = c.execute(sql)
        cols = [d[0] for d in cur.description]
        report[key] = [dict(zip(cols, r)) for r in cur.fetchall()]
        print("##", key, flush=True)
        for row in report[key]:
            print("  ", row, flush=True)

    c.execute(f"""create table province as select region code, names.primary as name,
        ST_MakeValid(ST_Simplify(geometry, {SIMPLIFY_DEGREES})) g, bbox from 'provinces.parquet'
        where class='land' and try_cast(replace(region,'TH-','') as int) between 30 and 49""")
    c.execute(f"""create table food as select * from 'places.parquet'
        where taxonomy.hierarchy[1]='food_and_drink' and basic_category in {CATEGORIES}""")
    c.execute("""create table isan as select f.*, p.code province_code, p.name province_name
        from food f join province p
          on f.bbox.xmin between p.bbox.xmin and p.bbox.xmax and f.bbox.ymin between p.bbox.ymin and p.bbox.ymax
         and ST_Contains(p.g, f.geometry)""")
    extra = "" if round_no == 1 else (f"and not (regexp_matches(names.primary,'(?i){NON_FOOD}') "
                                      f"and not regexp_matches(names.primary,'(?i){FOOD}'))")
    c.execute(f"""create table usable as select * from isan where names.primary is not null and length(trim(names.primary))>=2
        and coalesce(operating_status,'open')='open' and confidence>={MIN_CONFIDENCE[round_no]}
        {extra}""")
    # Duplicate = same normalized name in the same ~110 m grid cell; keep the most confident record.
    c.execute("""create table final as select * from usable qualify row_number() over (
        partition by lower(regexp_replace(names.primary,'\\s+','','g')), round(bbox.xmin,3), round(bbox.ymin,3)
        order by confidence desc, id)=1""")

    put("funnel", "select (select count(*) from food) food_in_box, (select count(*) from isan) in_isan, "
                  "(select count(distinct id) from isan) in_isan_ids, (select count(*) from usable) usable, (select count(*) from final) deduped")
    put("operating_status", "select operating_status, count(*) n from isan group by 1 order by 2 desc")
    put("confidence", """select floor(confidence*10)/10 bucket, count(*) n from isan group by 1 order by 1""")
    put("sensitivity", """select t threshold, (select count(*) from isan where confidence>=t
        and coalesce(operating_status,'open')='open') n from (values (0.0),(0.4),(0.5),(0.6),(0.7),(0.8),(0.9)) v(t)""")
    put("by_province", """select province_code code, any_value(province_name) as name, count(*) n,
        round(100*avg((coalesce(len(phones),0)>0)::int),1) phone_pct from final group by 1 order by 3 desc""")
    put("category", "select basic_category, count(*) n from final group by 1 order by 2 desc")
    put("cuisine", "select taxonomy.primary as cuisine, count(*) n from final group by 1 order by 2 desc limit 25")
    put("completeness", """select count(*) n,
        round(100*avg((coalesce(len(phones),0)>0)::int),1) phone,
        round(100*avg((coalesce(len(websites),0)>0)::int),1) website,
        round(100*avg((coalesce(len(socials),0)>0)::int),1) social,
        round(100*avg((addresses[1].freeform is not null)::int),1) address,
        round(100*avg((regexp_matches(names.primary,'[ก-๙]'))::int),1) thai_name from final""")
    put("food_word_in_name", f"""select round(100*avg(regexp_matches(names.primary,'(?i){FOOD}')::int),1) pct,
        round(100*avg((taxonomy.primary='restaurant')::int),1) generic_cuisine_pct,
        sum(regexp_matches(names.primary,'0[0-9]{{8,9}}|0[0-9]{{1,2}}[- ][0-9]{{3}}')::int) phone_in_name from final""")
    put("ramen_named_noodle", """select count(*) ramen, sum((names.primary like '%ก๋วยเตี๋ยว%')::int) named_kuaitiao
        from final where taxonomy.primary='ramen_restaurant'""")
    put("sources", """select s.dataset, s.license, count(distinct id) n from (select id, unnest(sources) s from final) group by 1,2 order by 3 desc""")
    put("freshness", """select left(s.update_time,4) as year, count(distinct id) n from (select id, unnest(sources) s from final) group by 1 order by 1""")

    sample = c.execute(f"""select id, names.primary as name, basic_category, taxonomy.primary as cuisine, province_name,
        addresses[1].freeform address, addresses[1].locality locality, addresses[1].region region,
        websites[1] website, socials[1] social, round(confidence,2) confidence,
        bbox.ymin lat, bbox.xmin lon, sources[1].dataset dataset, sources[1].update_time updated
        from final order by md5('{SAMPLE_SEED[round_no]}'||id) limit 50""")
    cols = [d[0] for d in sample.description]
    rows = [dict(zip(cols, r)) for r in sample.fetchall()]
    with open(os.path.join(out, "gate-report.json"), "w", encoding="utf8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    with open(os.path.join(out, "sample50.json"), "w", encoding="utf8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    print("## sample")
    for i, r in enumerate(rows, 1):
        print(i, r["name"], r["basic_category"], r["cuisine"], r["province_name"], r["region"], r["locality"], r["address"],
              r["social"] or r["website"], r["confidence"], r["dataset"], (r["updated"] or "")[:10], sep=" | ")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
