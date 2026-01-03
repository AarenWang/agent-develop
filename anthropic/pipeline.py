import argparse
import csv
import re
from pathlib import Path
from textwrap import dedent

import time

import requests
from deep_translator import GoogleTranslator

# Jina Reader 不需要 API Key 即可基础使用
JINA_READER_URL = "https://r.jina.ai/"


def fetch_markdown(url):
    """使用 Jina Reader 抓取网页并转为 Markdown"""
    print(f"正在抓取网页: {url}")
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(f"{JINA_READER_URL}{url}")
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            wait_time = 2 ** attempt
            print(f"⚠️ 抓取失败（{exc}），{wait_time}s 后重试...")
            time.sleep(wait_time)
    raise last_error


def clean_markdown(content: str) -> str:
    """进行轻量清洗，移除冗余头信息并压缩空行"""
    lines = []
    for line in content.splitlines():
        if line.startswith("Title:") or line.startswith("URL Source:"):
            continue
        lines.append(line.rstrip())

    cleaned = []
    for line in lines:
        if line.strip() == "" and (cleaned and cleaned[-1] == ""):
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def translate_markdown(content: str) -> str:
    """翻译 Markdown 文本，保留代码块内容"""
    translator = GoogleTranslator(source="auto", target="zh-CN")
    segments = re.split(r"(```[\s\S]*?```)", content)
    translated_parts = []

    def _translate_chunk(text: str) -> str:
        if len(text) <= 4500:
            return translator.translate(text)
        pieces = []
        buffer = ""
        for sentence in re.split(r"(?<=[。！!？?\n])", text):
            if len(buffer) + len(sentence) > 4000 and buffer:
                pieces.append(translator.translate(buffer))
                buffer = ""
            buffer += sentence
        if buffer:
            pieces.append(translator.translate(buffer))
        return "".join(pieces)

    for segment in segments:
        if segment.startswith("```"):
            translated_parts.append(segment)
        elif segment.strip():
            try:
                translated_parts.append(_translate_chunk(segment))
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ 翻译失败，保留英文原文：{exc}")
                translated_parts.append(segment)
        else:
            translated_parts.append(segment)

    return "".join(translated_parts)


def build_tldr(content: str, sentences: int = 3) -> str:
    """从译文前几句生成简要 TL;DR"""
    plain_text = re.sub(r"```[\s\S]*?```", "", content)
    plain_text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", plain_text)
    first_sentences = re.split(r"(?<=[。！!？?])", plain_text)
    bullets = [s.strip() for s in first_sentences if s.strip()][:sentences]
    if not bullets:
        return "- 文章概览暂不可用"
    return "\n".join(f"- {item}" for item in bullets)


def rewrite_markdown(content: str, title: str, source_url: str) -> str:
    """按照提示词要求进行重写排版"""
    tldr_block = dedent(
        f"""
        ## 核心速览 (TL;DR)
        {build_tldr(content)}
        """
    ).strip()

    next_steps = dedent(
        """
        ## 下一步行动计划
        - 选择一条思路在实践环境中试验，并记录结果。
        - 将文中提到的最佳实践整理为团队规范。
        - 对关键工具或接口进行 PoC 验证，确保集成可行性。
        """
    ).strip()

    header = f"# {title}\n\n> 来源：{source_url}\n"
    return "\n\n".join([header, tldr_block, content.strip(), next_steps])


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
        cleaned_md = clean_markdown(raw_md)

        # 3. 翻译
        print("正在进行专家级翻译...")
        translated_md = translate_markdown(cleaned_md)

        # 4. 重构排版
        print("正在进行最终排版重构...")
        final_md = rewrite_markdown(translated_md, title, url)

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
