import requests
import os

# --- 配置区 ---
LLM_API_KEY = "你的_API_KEY"  # 支持 OpenAI 格式的 API (如 Claude, GPT, 或 DeepSeek)
LLM_BASE_URL = "https://api.openai.com/v1" # 或者你使用的中转地址
MODEL_NAME = "gpt-4o" # 建议使用长上下文模型

# Jina Reader 不需要 API Key 即可基础使用
JINA_READER_URL = "https://r.jina.ai/"

# --- 提示词库 ---
PROMPTS = {
    "cleaner": """你是一个专业的技术文档编辑，擅长从原始抓取文本中提取纯净的 Markdown 内容。
请处理以下内容：
1. 去除所有无关内容（Header, Footer, 社交按钮, 版权声明）。
2. 保留完整的技术代码块、数学公式和图片占位符。
3. 识别关键术语（如 MCP, ACI）并保留英文。""",

    "translator": """你是一位资深 AI 架构师和技术翻译专家。
请将提供的 Markdown 翻译成中文：
1. 技术术语：保持英文并在括号中备注中文，如 Agent-Computer Interface (ACI, 智能体-计算机接口)。
2. 风格：信达雅，主动语态，专业且干练。
3. 深度解读：在复杂模式段落后添加【深度解析】块。""",

    "rewriter": """你是一位顶尖技术博主。请对翻译后的内容进行重写：
1. 文首增加“核心速览 (TL;DR)”。
2. 使用粗体和列表优化视觉排版。
3. 文末增加“下一步行动计划”。"""
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
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        "temperature": 0.3
    }
    response = requests.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
    return response.json()['choices'][0]['message']['content']

def process_article(url, output_filename):
    """完整的流水线控制"""
    try:
        # 1. 抓取
        raw_md = fetch_markdown(url)
        
        # 2. 清洗
        print("正在进行信息清洗...")
        cleaned_md = call_llm(PROMPTS["cleaner"], raw_md)
        
        # 3. 翻译
        print("正在进行专家级翻译...")
        translated_md = call_llm(PROMPTS["translator"], cleaned_md)
        
        # 4. 重构排版
        print("正在进行最终排版重构...")
        final_md = call_llm(PROMPTS["rewriter"], translated_md)
        
        # 保存结果
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_md)
        
        print(f"✅ 处理完成！文件已保存至: {output_filename}")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

# --- 执行区 ---
if __name__ == "__main__":
    target_url = "https://www.anthropic.com/engineering/building-effective-agents"
    file_name = "Anthropic_Building_Effective_Agents_CN.md"
    
    process_article(target_url, file_name)