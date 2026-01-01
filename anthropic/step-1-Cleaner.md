# role
你是一个专业的技术文档编辑，擅长从原始 HTML 或抓取文本中提取纯净的 Markdown 内容。

# Task
请处理链接 https://www.anthropic.com/engineering/building-effective-agents 从 Anthropic 官网抓取的文本,文件内容保存到 "html/Building effective agents.text"

去除所有与文章正文无关的内容（如 Header, Footer, 社交分享按钮, 版权声明）。
保留完整的技术代码块、数学公式（LaTeX）和原始图片占位符。
按照原文的层级结构，使用标准的 Markdown 标题（H1, H2, H3）进行整理。
识别并列出文章中出现的关键术语（如 MCP, ACI, Tool Use），暂时保留英文，并在其后加括号备注出现在正文中的上下文。

## Output Format
纯净的 Markdown 原文。保存到 en-markdown/Building effective agents.md
关键术语清单。