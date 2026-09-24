-- A224 (cfdb-main-R-3010). THE OFFENSE'S END IS WHERE IT STARTED PLUS WHAT IT GAINED.
--
-- 🚨 THIS IS THE INVARIANT THAT SEPARATES THE NEW COLUMN FROM `end_yards_from_own_goal`,
-- WHICH SINCE 2026 IS A DIFFERENT FACT — the possession-CHANGE spot, not the offense's last
-- spot. 📊 The two agree on 90.3% of 2024 drives, 81.3% of 2025 and 40.9% of 2026, and on
-- 2026 punts on 0.9%. **A test that asserted the two were equal would be asserting the defect
-- this column exists to route around.**
--
-- ⚠️ AND IT IS AN IDENTITY, NOT A BOUND (R-2260). `offense_end` is DEFINED as start plus the
-- gain, so this fires the moment anyone clamps it, rounds it, or swaps in the end coordinate.
--
-- ⚠️ THE TWO SPELLINGS ARE CHECKED AGAINST EACH OTHER IN THE SAME PASS, which is R-306's whole
-- point: two spellings of one number that can disagree are two numbers. The absolute frame
-- flips with the side in possession, so the check flips with it too.
--
-- ⚠️ IT `ref()`s ITS SUBJECT (§3.6), so it is ordered after the model rather than free to run
-- before the table exists — and it is a PROPERTY, naming no drive and no season, so it says
-- the same true thing about CI's fixture as about the warehouse (§2.3.3).
select
    drive_id,
    season,
    start_yards_from_own_goal,
    yards,
    offense_end_yards_from_own_goal,
    offense_end_yardline,
    is_home_offense
from {{ ref('fct_drive') }}
where
    -- the definition itself
    offense_end_yards_from_own_goal <> start_yards_from_own_goal + yards
    -- the twin, in the absolute frame, must be the same position
 or offense_end_yardline <> case when is_home_offense
                                 then 100 - (100 - offense_end_yards_from_own_goal)
                                 else 100 - offense_end_yards_from_own_goal end
    -- 🚨 THE FLAG IS ASSERTED NON-NULL AND THE VALUES ARE NOT, AND THE ASYMMETRY IS THE
    -- POINT. The values inherit the feed's nulls honestly; the flag is `coalesce`d in the
    -- model, so this clause tests the MODEL's own guarantee rather than the feed's weather.
    -- ⚠️ Asserting the values non-null would put a missing snapshot on the critical path of a
    -- gated `dbt_test`, which is a stopped publish rather than a finding (§2.3).
 or is_offense_end_on_field is null
    -- the flag must say what it means
 or is_offense_end_on_field
        <> (offense_end_yards_from_own_goal between 0 and 100)
