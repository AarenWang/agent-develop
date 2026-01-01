# agent-develop

## 批量翻译流水线快速开始

1. 准备包含 `url,title` 的列表文件（可为 CSV 或无表头的两列逗号分隔格式）：
   ```csv
   url,title
   https://www.anthropic.com/engineering/building-effective-agents,Anthropic - Building effective agents
   https://example.com/article-2,Example Article 2
   ```

2. 运行流水线（结果默认保存在 `final-md/`）：
   ```bash
   python anthropic/pipeline.py articles.csv --output-dir final-md
   ```

提示词会自动填入每篇文章的标题和来源 URL，确保清洗、翻译和重写阶段都围绕指定文章进行。
