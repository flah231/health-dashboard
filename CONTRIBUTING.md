# 贡献指南

感谢你愿意为这个项目做贡献！本文档说明如何参与开发。

## 🐛 报告 Bug

在 [Issues](../../issues) 提交时请包含：

1. **环境信息**：操作系统、Python/Node.js 版本
2. **复现步骤**：越具体越好
3. **期望行为 vs 实际行为**
4. **错误日志**：`%APPDATA%\HealthDashboard\logs\` 下的日志文件
5. **截图**（如适用）

## ✨ 提交新功能

建议先在 [Issues](../../issues) 讨论，避免重复劳动。

## 📝 贡献数据源适配器

这是**最受欢迎的贡献**！添加新省份数据源：

### 步骤

1. **侦察目标网站**：
   - 找到月报列表页（通常是 `/col/colXXX/index.html`）
   - 找到详情页的 HTML 结构
   - 判断数据在 HTML 表格、docx 附件还是正文文字里

2. **创建适配器**：复制 `collector/adapters/gd_province.py` 作为模板

3. **实现 3 个方法**：
   ```python
   class YourProvinceAdapter(BaseAdapter):
       source_key = "xx_cn"           # 唯一标识
       province_name = "某某省"
       
       def _discover_report_urls(self): ...   # 抓取所有月报 URL
       def _process_report(self, ...): ...    # 解析单个月报
       def _normalize(self, raw): ...         # 疾病名标准化

注册：在 backend/init_db.py 的 DEFAULT_SOURCES 里加一行

测试：

bash
cd collector
python run_once.py xx_cn
提交 PR

🔀 Pull Request 规范
分支命名：feature/xxx 或 fix/xxx

Commit 信息：清晰描述改动（如 feat: 新增四川省数据源适配器）

代码风格：

Python：PEP 8

JavaScript/Vue：ESLint 默认配置

测试：确保本地跑通再提交

📋 开发环境搭建
见 README.md。

🎯 待办事项
欢迎认领以下方向：

□ 新增更多省份数据源（四川、河南、湖北等）
□ 支持导出数据为 CSV/Excel
□ 添加"同比/环比"分析
□ 前端主题切换（浅色/深色）
□ Docker 部署方案
📜 行为准则
尊重所有贡献者

建设性反馈

不讨论政治敏感话题