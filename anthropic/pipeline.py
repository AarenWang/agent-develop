import argparse
import csv
import re
from pathlib import Path

import requests

# --- 配置区 ---
LLM_API_KEY = "你的_API_KEY"  # 支持 OpenAI 格式的 API (如 Claude, GPT, 或 DeepSeek)
LLM_BASE_URL = "https://api.openai.com/v1"  # 或者你使用的中转地址
MODEL_NAME = "gpt-4o"  # 建议使用长上下文模型

# Jina Reader 不需要 API Key 即可基础使用
JINA_READER_URL = "https://r.jina.ai/"

# --- 提示词库 ---
PROMPTS = {
    "cleaner": """你是一个专业的技术文档编辑，擅长从原始抓取文本中提取纯净的 Markdown 内容。
处理文章标题《{article_title}》，来源 URL: {source_url}
请严格执行：
1. 仅保留正文内容，去除 Header/Footer、社交按钮、版权声明等噪声。
2. 保留所有技术代码块、数学公式和图片占位符。
3. 识别关键术语（如 MCP、ACI）并保留英文原文。""",

    "translator": """你是一位资深 AI 架构师和技术翻译专家。
当前文章标题《{article_title}》，来源 URL: {source_url}
请将提供的 Markdown 翻译成中文并满足：
1. 技术术语保持英文，并在括号中备注中文，例如 Agent-Computer Interface (ACI, 智能体-计算机接口)。
2. 风格为信达雅，主动语态，专业且干练。
3. 在复杂模式或关键设计段落后添加【深度解析】块，补充解释。""",

    "rewriter": """你是一位顶尖技术博主。请对翻译后的内容进行重写和排版：
文章标题：《{article_title}》
来源 URL: {source_url}
1. 文首增加“核心速览 (TL;DR)”，用要点概括全文。
2. 使用粗体、列表、引用等 Markdown 语法优化视觉排版，保持信息层次清晰。
3. 文末增加“下一步行动计划”，给出读者可执行的后续步骤。"""
}


def fetch_markdown(url):
    """使用 Jina Reader 抓取网页并转为 Markdown"""
    print(f"正在抓取网页: {url}")
    response = requests.get(f"{JINA_READER_URL}{url}")
    return response.text


def call_llm(prompt, content):
    """通用的 LLM 调用函数"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.3,
    }
    response = requests.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]


def slugify(title):
    """将标题转换为安全的文件名"""
    safe_title = re.sub(r"[^\w\-]+", "_", title, flags=re.UNICODE)
    return safe_title.strip("_") or "article"


def load_articles(list_file):
    """从文件中读取 URL 和标题列表，支持 CSV（url,title）或无表头两列格式"""
    articles = []
    with open(list_file, newline="", encoding="utf-8") as f:
        f.seek(0)
        reader = csv.DictReader(f)
        if reader.fieldnames and {"url", "title"}.issubset({fn.lower() for fn in reader.fieldnames}):
            for row in reader:
                url = row.get("url") or row.get("URL")
                title = row.get("title") or row.get("TITLE")
                if url and title:
                    articles.append({"url": url.strip(), "title": title.strip()})
        else:
            f.seek(0)
            simple_reader = csv.reader(f)
            for row in simple_reader:
                if not row or row[0].startswith("#"):
                    continue
                if len(row) < 2:
                    raise ValueError("每行需要提供 URL 和标题，两列以逗号分隔")
                articles.append({"url": row[0].strip(), "title": row[1].strip()})

    return articles


def process_article(url, title, output_dir):
    """完整的流水线控制"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 抓取
        raw_md = fetch_markdown(url)

        # 2. 清洗
        print("正在进行信息清洗...")
        cleaned_md = call_llm(PROMPTS["cleaner"].format(article_title=title, source_url=url), raw_md)

        # 3. 翻译
        print("正在进行专家级翻译...")
        translated_md = call_llm(PROMPTS["translator"].format(article_title=title, source_url=url), cleaned_md)

        # 4. 重构排版
        print("正在进行最终排版重构...")
        final_md = call_llm(PROMPTS["rewriter"].format(article_title=title, source_url=url), translated_md)

        # 保存结果
        output_filename = output_path / f"{slugify(title)}.md"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_md)

        print(f"✅ 处理完成！文件已保存至: {output_filename}")

    except Exception as e:
        print(f"❌ 发生错误: {e}")


def main():
    parser = argparse.ArgumentParser(description="批量抓取并翻译文章")
    parser.add_argument(
        "list_file",
        help="包含 URL 和标题的文件，支持 CSV，列名为 url,title 或无表头两列格式",
    )
    parser.add_argument(
        "--output-dir",
        default="final-md",
        help="输出 Markdown 文件夹，默认 final-md",
    )

    args = parser.parse_args()
    articles = load_articles(args.list_file)

    if not articles:
        raise SystemExit("未从列表中读取到任何文章，请检查文件内容")

    for article in articles:
        print(f"\n开始处理: {article['title']} ({article['url']})")
        process_article(article["url"], article["title"], args.output_dir)


# --- 执行区 ---
if __name__ == "__main__":
    main()
