{{ config(materialized='table') }}

-- Broadcast outlets, normalised, abbreviated and ranked. R-080.
--
-- AUTHORED, NOT DERIVED. Three things this fixes, none of which a display trim in Streamlit
-- could reach — a trim would fix one surface and leave the Excel workbook saying something
-- else, and the warehouse would still hold the duplicates.
--
-- 1. THE SAME CHANNEL APPEARS UNDER SEVERAL NAMES. Measured across 1,781 TV rows:
--        ACC Network (95) / ACC NETWORK (7)      SEC Network (87) / SEC NETWORK (4)
--        BTN (100) / BIG10 (10)                  The CW Network (78) / CW (29)
--    Casing and abbreviation both, so neither upper() nor a rename map alone is enough.
--
-- 2. THE PRIMARY OUTLET WAS PICKED ALPHABETICALLY. fct_game ordered by outlet, so on the 49
--    games carrying more than one TV outlet, ABC beat ESPN because A sorts before E. That is
--    not a precedence rule, it is the absence of one. `precedence_rank` is the rule.
--
-- 3. THE LONG STRINGS ARE UNRENDERABLE IN A TABLE CELL. Marc named them: NEC Front Row,
--    Midco Sports Net, The Spot - MTN, USA Net. `display_abbreviation` is a COLUMN, not
--    string surgery in a view, so the site and the workbook agree by construction.
--
-- PRECEDENCE IS A JUDGEMENT AND IT IS WRITTEN DOWN HERE RATHER THAN INFERRED:
--        1  national over-the-air     ABC, CBS, FOX, NBC, CW — largest audience
--        2  national cable, primary   ESPN and the general-entertainment channels
--        3  national cable, secondary the numbered and niche sports tiers
--        4  conference networks       BTN, SEC, ACC — national carriage, single-conference
--        5  regional and local        one-market stations and regional sports networks
--        9  unmapped                  see below
--
-- AN UNMAPPED OUTLET STILL RESOLVES. Anything absent from this list keeps its raw name, gets
-- rank 9 and `is_mapped = false`. A new channel next season must appear on the site rather
-- than vanish because nobody updated a dimension, and the flag is what makes the gap
-- countable instead of invisible.

with authored as (

    select * from (values
        -- raw                  key             display            abbrev    rank  media
        ('ABC',                 'abc',          'ABC',             'ABC',       1, 'tv'),
        ('CBS',                 'cbs',          'CBS',             'CBS',       1, 'tv'),
        ('FOX',                 'fox',          'FOX',             'FOX',       1, 'tv'),
        ('NBC',                 'nbc',          'NBC',             'NBC',       1, 'tv'),
        ('The CW Network',      'cw',           'The CW Network',  'CW',        1, 'tv'),
        ('CW',                  'cw',           'The CW Network',  'CW',        1, 'tv'),

        ('ESPN',                'espn',         'ESPN',            'ESPN',      2, 'tv'),
        ('TNT',                 'tnt',          'TNT',             'TNT',       2, 'tv'),
        ('USA Net',             'usa',          'USA Network',     'USA',       2, 'tv'),
        ('truTV',               'trutv',        'truTV',           'truTV',     2, 'tv'),
        ('CNBC',                'cnbc',         'CNBC',            'CNBC',      2, 'tv'),
        ('NFL Net',             'nfl_network',  'NFL Network',     'NFL',       2, 'tv'),

        ('ESPN2',               'espn2',        'ESPN2',           'ESPN2',     3, 'tv'),
        ('ESPNU',               'espnu',        'ESPNU',           'ESPNU',     3, 'tv'),
        ('CBSSN',               'cbssn',        'CBS Sports Net',  'CBSSN',     3, 'tv'),
        ('FS1',                 'fs1',          'FS1',             'FS1',       3, 'tv'),
        ('FS2',                 'fs2',          'FS2',             'FS2',       3, 'tv'),

        -- Marc's two named abbreviations, and the pattern the rest follow.
        ('ACC Network',         'accn',         'ACC Network',     'ACC',       4, 'tv'),
        ('ACC NETWORK',         'accn',         'ACC Network',     'ACC',       4, 'tv'),
        ('SEC Network',         'secn',         'SEC Network',     'SEC',       4, 'tv'),
        ('SEC NETWORK',         'secn',         'SEC Network',     'SEC',       4, 'tv'),
        ('BTN',                 'btn',          'Big Ten Network', 'BTN',       4, 'tv'),
        ('BIG10',               'btn',          'Big Ten Network', 'BTN',       4, 'tv'),

        ('Midco Sports Net',    'midco',        'Midco Sports',    'Midco',     5, 'tv'),
        ('NEC Front Row',       'nec_front_row','NEC Front Row',   'NEC',       5, 'tv'),
        ('The Spot - MTN',      'the_spot_mtn', 'The Spot - MTN',  'MTN',       5, 'tv'),
        ('MNMT',                'mnmt',         'MNMT',            'MNMT',      5, 'tv'),
        ('MVC',                 'mvc',          'MVC',             'MVC',       5, 'tv'),
        ('NCN',                 'ncn',          'NCN',             'NCN',       5, 'tv'),
        ('KELO-TV',             'kelo',         'KELO-TV',         'KELO',      5, 'tv'),
        ('KMCI-TV',             'kmci',         'KMCI-TV',         'KMCI',      5, 'tv')
    ) as t(outlet_raw, outlet_key, display_name, display_abbreviation,
           precedence_rank, media_type)

),

observed as (

    -- Every outlet the feed has actually carried, TV and web alike. Driven off the data so
    -- an unmapped channel gets a row rather than disappearing at the join.
    select distinct outlet as outlet_raw, media_type
    from {{ ref('stg_game_media') }}
    where outlet is not null

)

select
    {{ surrogate_key(['o.outlet_raw', 'o.media_type']) }}      as broadcast_outlet_sk,
    o.outlet_raw,
    o.media_type,
    coalesce(a.outlet_key, {{ to_slug('o.outlet_raw') }})      as outlet_key,
    coalesce(a.display_name, o.outlet_raw)                     as display_name,
    -- Falls back to the RAW string, not to a truncation. A name we have not shortened should
    -- render in full and look long, which is a visible prompt to add it here — a silently
    -- clipped one is not.
    coalesce(a.display_abbreviation, o.outlet_raw)             as display_abbreviation,
    coalesce(a.precedence_rank, 9)                             as precedence_rank,
    a.outlet_raw is not null                                   as is_mapped
from observed o
left join authored a
    on a.outlet_raw = o.outlet_raw and a.media_type = o.media_type
