CREATE TABLE IF NOT EXISTS statistics_expanded (
    id SERIAL PRIMARY KEY,
    totalamount INTEGER,
    lastyearamount INTEGER,
    lastmonthamount INTEGER
);

CREATE TABLE IF NOT EXISTS statistics_by_keyword_expanded (
    keyword VARCHAR(50) PRIMARY KEY,
    totalamount INTEGER,
    lastyearamount INTEGER,
    lastmonthamount INTEGER
);

CREATE OR REPLACE FUNCTION public.updatestat()
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
    keyword_ VARCHAR(50);
    type_cursor CURSOR FOR SELECT DISTINCT keyword FROM keywords;
BEGIN
    -- 遍历所有类型
    FOR keyword_ IN SELECT DISTINCT keyword FROM keywords
    LOOP
        -- 使用 INSERT ... ON CONFLICT 替代 REPLACE INTO
        INSERT INTO statistics_by_keyword (keyword, totalamount, lastyearamount, lastmonthamount)
        VALUES (
            keyword_,
            (SELECT COUNT(*) FROM pictures WHERE href IN (SELECT href FROM keywords WHERE keyword = keyword_)),
            (SELECT COUNT(*) FROM pictures WHERE href IN (SELECT href FROM keywords WHERE keyword = keyword_) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)),
            (SELECT COUNT(*) FROM pictures WHERE href IN (SELECT href FROM keywords WHERE keyword = keyword_) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE))
        )
        ON CONFLICT (keyword) DO UPDATE SET
            totalamount = EXCLUDED.totalamount,
            lastyearamount = EXCLUDED.lastyearamount,
            lastmonthamount = EXCLUDED.lastmonthamount;
    END LOOP;

    -- 更新统计表
    UPDATE statistics
    SET totalamount = (SELECT COUNT(*) FROM pictures),
        lastyearamount = (SELECT COUNT(*) FROM pictures WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE)),
        lastmonthamount = (SELECT COUNT(*) FROM pictures WHERE EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE));
    delete from statistics_by_keyword where keyword not in (SELECT DISTINCT keyword FROM keywords);
END;
$function$;

-- ============================================================================
-- Expanded statistics: collections are expanded so each collection_item counts
-- as a separate picture (non-collection pictures still count as 1 each).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.updatestat_expanded()
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
    keyword_ VARCHAR(50);
BEGIN
    FOR keyword_ IN SELECT DISTINCT keyword FROM keywords
    LOOP
        INSERT INTO statistics_by_keyword_expanded (keyword, totalamount, lastyearamount, lastmonthamount)
        VALUES (
            keyword_,
            (SELECT
                (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE AND href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_))
                +
                (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE AND p.href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_))
            ),
            (SELECT
                (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE AND href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE))
                +
                (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE AND p.href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_) AND EXTRACT(YEAR FROM p.date) = EXTRACT(YEAR FROM CURRENT_DATE))
            ),
            (SELECT
                (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE AND href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_) AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE))
                +
                (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE AND p.href IN (SELECT k.href FROM keywords k WHERE k.keyword = keyword_) AND EXTRACT(YEAR FROM p.date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM p.date) = EXTRACT(MONTH FROM CURRENT_DATE))
            )
        )
        ON CONFLICT (keyword) DO UPDATE SET
            totalamount = EXCLUDED.totalamount,
            lastyearamount = EXCLUDED.lastyearamount,
            lastmonthamount = EXCLUDED.lastmonthamount;
    END LOOP;

    DELETE FROM statistics_expanded;
    INSERT INTO statistics_expanded (totalamount, lastyearamount, lastmonthamount)
    VALUES (
        (SELECT
            (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE)
            +
            (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE)
        ),
        (SELECT
            (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE))
            +
            (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE AND EXTRACT(YEAR FROM p.date) = EXTRACT(YEAR FROM CURRENT_DATE))
        ),
        (SELECT
            (SELECT COUNT(*) FROM pictures WHERE is_collection = FALSE AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM CURRENT_DATE))
            +
            (SELECT COUNT(*) FROM collection_items ci INNER JOIN pictures p ON ci.collection_href = p.href WHERE p.is_collection = TRUE AND EXTRACT(YEAR FROM p.date) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM p.date) = EXTRACT(MONTH FROM CURRENT_DATE))
        )
    );

    DELETE FROM statistics_by_keyword_expanded WHERE keyword NOT IN (SELECT DISTINCT keyword FROM keywords);
END;
$function$;
