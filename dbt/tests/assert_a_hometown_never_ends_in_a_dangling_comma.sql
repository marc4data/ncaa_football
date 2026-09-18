-- A hometown is "City, ST" or it is just the one part — never a part and a separator.
--
-- A172 (cfdb-main-R-1655). `dim_athlete.hometown_display` has carried a comment since it was
-- written promising "Null rather than a lone comma when the city is missing, so the page renders
-- an em dash (AC-G.32) instead of stray punctuation." The INTENT was right and the GUARD was
-- incomplete: it tested `is not null`, and the source publishes EMPTY STRINGS.
--
-- 📊 So an international player with a city and no state published `'Pori, '` — city, comma,
-- trailing space. MEASURED BEFORE THE FIX: 834 of 83,985 roster rows, 0.99%.
--
-- 🚨 AND IT WAS FOUND BY RASTERISING THE PAGE AND READING IT, not by reading the SQL — which
-- looked correct, and said so in a comment. That is the fourth time a picture has caught what
-- code review could not (B103's invisible mark_rule, B108's 2:1 squash, B109's black-on-black
-- accent, this).
--
-- The test is on the SERVING column because that is what a reader meets, and it is cheap: a
-- trailing separator is always a defect, in either direction, whatever produced it.
select
    athlete_sk,
    full_name,
    hometown_display,
    home_city,
    home_state
from {{ ref('dim_athlete') }}
where hometown_display is not null
  and (trim(hometown_display) like '%,'
       or trim(hometown_display) like ',%')
