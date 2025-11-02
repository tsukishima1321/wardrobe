-- DROP FUNCTION public.updatestat();

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
END;
$function$
;
