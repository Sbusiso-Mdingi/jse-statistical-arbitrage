SELECT
  DATE(PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING))) AS day,
  EXTRACT(HOUR FROM PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING))) < 15 AS before_close,
  REGEXP_CONTAINS(LOWER(V2Organizations), r'(^|;)standard bank') AS sbk,
  REGEXP_CONTAINS(LOWER(V2Organizations), r'(^|;)nedbank') AS ned,
  COUNT(*) AS articles,
  AVG(CAST(SPLIT(V2Tone, ',')[OFFSET(0)] AS FLOAT64)) AS tone
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP('2015-02-18')
  AND REGEXP_CONTAINS(LOWER(V2Organizations), r'(^|;)(standard bank|nedbank)')
GROUP BY 1, 2, 3, 4
