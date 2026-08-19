{{ config(materialized='table', tags=['rankings']) }}
-- One row per poll CFBD publishes.
--
-- Derived from the data rather than hardcoded: the poll list is not stable across eras —
-- the CFP rankings did not exist before 2014, and the FCS polls appear only in seasons we
-- fetched FCS rankings for. A hardcoded list would silently drop a poll the API added.
--
-- `division` and `is_committee` are cfdb's classification, not CFBD's: the API returns only
-- the poll's display name, and the Rankings page needs to group FBS from FCS and to mark
-- the CFP committee ranking as the one that is not a vote.
with polls as (
    select distinct poll_name
    from {{ ref('stg_rankings') }}
    where poll_name is not null
)
select
    {{ surrogate_key(['poll_name']) }} as poll_sk,
    poll_name,
    -- `iii` is tested before `ii` because the latter is a substring of the former: reversed,
    -- the Division III poll matches the Division II branch and lands in the wrong division.
    case
        when lower(poll_name) like '%division iii%' then 'iii'
        when lower(poll_name) like '%division ii%'  then 'ii'
        when lower(poll_name) like 'fcs%'           then 'fcs'
        else 'fbs'
    end as division,
    -- The committee ranking is a selection decision, not a poll of voters, and the page
    -- presents it differently for that reason.
    case when lower(poll_name) like '%playoff committee%'
           or lower(poll_name) = 'playoff committee rankings'
         then true else false end as is_committee,
    case
        when lower(poll_name) like '%ap%'       then 1
        when lower(poll_name) like '%coaches%'  then 2
        when lower(poll_name) like '%committee%' then 0
        else 9
    end as display_order
from polls
