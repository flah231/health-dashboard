USE health_dashboard;

INSERT INTO data_sources (source_key, display_name, adapter_class, enabled, crawl_interval_seconds)
VALUES
  ('openfda',    'OpenFDA 公开数据',  'adapters.openfda_adapter.OpenFDAAdapter',    1, 3600),
  ('disease_sh', 'disease.sh 疫情数据', 'adapters.disease_sh_adapter.DiseaseShAdapter', 1, 1800)
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);

-- 生成近 7 天的模拟数据（3 个疾病 × 3 个区域）
INSERT INTO disease_stats
  (source_key, disease_name, region, stat_date, confirmed, cured, deaths)
SELECT 'disease_sh', d.name, r.region,
       CURDATE() - INTERVAL n.d DAY,
       FLOOR(80 + RAND() * 200),
       FLOOR(60 + RAND() * 150),
       FLOOR(1  + RAND() * 5)
FROM
  (SELECT '流感' AS name UNION ALL SELECT '肺结核' UNION ALL SELECT '手足口病') d
  CROSS JOIN
  (SELECT '全国' AS region UNION ALL SELECT '广东省' UNION ALL SELECT '浙江省') r
  CROSS JOIN
  (SELECT 0 AS d UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
   UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6) n;