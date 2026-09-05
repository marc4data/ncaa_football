-- drive_number should run 1..n within a game with no gaps and no repeats. A gap is either a
-- missing possession or a chart that silently skips one; a repeat puts two bars on one row.
--
-- SEVERITY IS WARN, AND THE MEASURED COUNT IS 4 GAMES OF 3,343 in the raw layer: one with a
-- gap (401752740) and three with a duplicated drive_number. That is a CFBD defect this repo
-- cannot fix, and four games is not a reason to fail every build — but it is a reason to know
-- when it becomes forty.
--
-- The chart's own protection is different and lives upstream: rows are ordered by
-- drive_number, so a gap shortens the sequence rather than misplacing a bar.
{{ config(severity='warn') }}

select
    game_id,
    season,
    count(*)                     as drive_rows,
    count(distinct drive_number) as distinct_numbers,
    min(drive_number)            as first_number,
    max(drive_number)            as last_number
from {{ ref('fct_drive') }}
where drive_number is not null
group by game_id, season
having count(*) <> count(distinct drive_number)
    or count(distinct drive_number) <> max(drive_number) - min(drive_number) + 1
