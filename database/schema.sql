CREATE DATABASE IF NOT EXISTS health_dashboard
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE health_dashboard;

-- 数据源注册表（扩展性的基础）
CREATE TABLE IF NOT EXISTS data_sources (
    id INT PRIMARY KEY AUTO_INCREMENT,
    source_key        VARCHAR(50)  UNIQUE NOT NULL,
    display_name      VARCHAR(100) NOT NULL,
    adapter_class     VARCHAR(200) NOT NULL,
    config_json       JSON,
    enabled           TINYINT DEFAULT 1,
    crawl_interval_seconds INT DEFAULT 3600,
    last_crawl_at     DATETIME,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 疾病统计数据主表
CREATE TABLE IF NOT EXISTS disease_stats (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    source_key    VARCHAR(50)  NOT NULL,
    disease_name  VARCHAR(200) NOT NULL,
    region        VARCHAR(100) NOT NULL,
    stat_date     DATE         NOT NULL,
    confirmed     INT DEFAULT 0,
    cured         INT DEFAULT 0,
    deaths        INT DEFAULT 0,
    extra_json    JSON,
    crawl_time    DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_src_dis_reg_date (source_key, disease_name, region, stat_date),
    INDEX idx_disease_date (disease_name, stat_date),
    INDEX idx_region_date  (region, stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 实时快照表（供 WebSocket 推送）
CREATE TABLE IF NOT EXISTS realtime_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    disease_name VARCHAR(200),
    region       VARCHAR(100),
    metric_name  VARCHAR(50),
    metric_value DECIMAL(12,2),
    snapshot_time DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;