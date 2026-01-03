# Advanced Tool Use: Powering Agents with Code

> 来源：https://www.anthropic.com/engineering/advanced-tool-use


## 核心速览 (TL;DR)
        - 降价内容：
人工智能代理的未来是模型可以跨数百或数千种工具无缝工作。
- 集成了 git 操作、文件操作、包管理器、测试框架和部署管道的 IDE 助手。
- 一个运营协调器，可同时连接 Slack、GitHub、Google Drive、Jira、公司数据库和数十个 MCP 服务器。

降价内容：
人工智能代理的未来是模型可以跨数百或数千种工具无缝工作。集成了 git 操作、文件操作、包管理器、测试框架和部署管道的 IDE 助手。一个运营协调器，可同时连接 Slack、GitHub、Google Drive、Jira、公司数据库和数十个 MCP 服务器。

为了[构建有效的代理](https://www.anthropic.com/research/building- effective-agents)，他们需要使用无限的工具库，而不需要预先将每个定义填充到上下文中。我们关于使用 [MCP 代码执行](https://www.anthropic.com/engineering/code-execution-with-mcp) 的博客文章讨论了工具结果和定义有时会在代理读取请求之前消耗 50,000 多个令牌。代理应该按需发现和加载工具，只保留与当前任务相关的工具。

代理还需要能够从代码调用工具。使用自然语言工具调用时，每次调用都需要完整的推理过程，中间结果会在上下文中堆积，无论它们是否有用。代码非常适合编排逻辑，例如循环、条件和数据转换。代理需要根据手头的任务灵活地在代码执行和推理之间进行选择。

代理还需要从示例中学习正确的工具用法，而不仅仅是模式定义。 JSON 模式定义了结构上有效的内容，但无法表达使用模式：何时包含可选参数、哪些组合有意义，或者您的 API 期望什么约定。

今天，我们发布了三项使这成为可能的功能：

* **工具搜索工具，**允许 Claude 使用搜索工具访问数千种工具，而无需消耗其上下文窗口
* **编程工具调用**，允许 Claude 在代码执行环境中调用工具，减少对模型上下文窗口的影响
* **工具使用示例**，它提供了演示如何有效使用给定工具的通用标准

在内部测试中，我们发现这些功能帮助我们构建了传统工具使用模式无法实现的东西。例如，**[Claude for Excel](https://www.claude.com/claude-for-excel)**使用编程工具调用来读取和修改具有数千行的电子表格，而不会使模型的上下文窗口过载。

根据我们的经验，我们相信这些功能为您与 Claude 一起构建内容开辟了新的可能性。

工具搜索工具
----------------

### 挑战

MCP 工具定义提供了重要的上下文，但随着更多服务器连接，这些令牌会不断增加。考虑五台服务器的设置：

* GitHub：35 个工具（约 26K 代币）
* Slack：11 个工具（约 21K 代币）
* Sentry：5 个工具（~3K 代币）
* Grafana：5 个工具（~3K 代币）
* Splunk：2 个工具（~2K 代币）

在对话开始之前，这 58 个工具消耗了大约 55K 令牌。添加更多像 Jira 这样的服务器（仅使用约 17K 令牌），您很快就会接近 100K+ 令牌开销。在 Anthropic，我们看到工具定义在优化之前消耗了 134K 令牌。

但代币成本并不是唯一的问题。最常见的故障是错误的工具选择和不正确的参数，特别是当工具具有类似名称（例如“notification-send-user”与“notification-send-channel”）时。

### 我们的解决方案

工具搜索工具不是预先加载所有工具定义，而是按需发现工具。 Claude 只看到当前任务实际需要的工具。

![图1：工具搜索工具图](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimag es%2F4zrzovbb%2Fwebsite%2Ff359296f770706608901eadaffbff4ca0b67874c-1999x1125.png&w=3840&q=75)

_工具搜索工具保留了 191,300 个上下文标记，而 Claude 的传统方法保留了 122,800 个。_

传统方法：* 预先加载所有工具定义（50 多个 MCP 工具约 72K 令牌）
* 通话记录与系统提示争夺剩余空间
* 总上下文消耗：在任何工作开始之前约 77K 令牌

使用工具搜索工具：

* 仅预先加载工具搜索工具（约 500 个令牌）
* 根据需要按需发现工具（3-5 个相关工具，约 3K 代币）
* 总上下文消耗：约 8.7K 个令牌，保留 95% 的上下文窗口

这意味着令牌使用量减少了 85%，同时保持对完整工具库的访问。内部测试表明，使用大型工具库时，MCP 评估的准确性显着提高。启用工具搜索工具后，Opus 4 从 49% 提高到 74%，Opus 4.5 从 79.5% 提高到 88.1%。

### 工具搜索工具的工作原理

工具搜索工具可让 Claude 动态发现工具，而不是预先加载所有定义。您向 API 提供所有工具定义，但使用“defer_loading: true”标记工具，以便按需发现它们。延迟工具最初不会加载到 Claude 的上下文中。 Claude 只能看到工具搜索工具本身以及带有“defer_loading: false”的任何工具（您最关键、最常用的工具）。

当 Claude 需要特定功能时，它会搜索相关工具。工具搜索工具返回对匹配工具的引用，这些工​​具在 Claude 的上下文中扩展为完整的定义。

例如，如果 Claude 需要与 GitHub 交互，它会搜索“github”，并且只会加载 `github.createPullRequest` 和 `github.listIssues`，而不加载来自 Slack、Jira 和 Google Drive 的其他 50 多个工具。

这样，Claude 就可以访问您的完整工具库，而只需支付其实际需要的工具的代币成本。

**提示缓存注意：**工具搜索工具不会破坏提示缓存，因为延迟工具完全从初始提示中排除。它们仅在 Claude 搜索后才会添加到上下文中，因此您的系统提示和核心工具定义仍然可缓存。

**执行：**```
{
  "tools": [
    // Include a tool search tool (regex, BM25, or custom)
    {"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"},

    // Mark tools for on-demand discovery
    {
      "name": "github.createPullRequest",
      "description": "Create a pull request",
      "input_schema": {...},
      "defer_loading": true
    }
    // ... hundreds more deferred tools with defer_loading: true
  ]
}
```对于 MCP 服务器，您可以推迟加载整个服务器，同时保持加载特定的高使用率工具：```
{
  "type": "mcp_toolset",
  "mcp_server_name": "google-drive",
  "default_config": {"defer_loading": true}, # defer loading the entire server
  "configs": {
    "search_files": {
"defer_loading": false
    }  // Keep most used tool loaded
  }
}
```Claude 开发者平台提供开箱即用的基于正则表达式和基于 BM25 的搜索工具，但您也可以使用嵌入或其他策略来实现自定义搜索工具。

### 何时使用工具搜索工具

与任何架构决策一样，启用工具搜索工具需要权衡。该功能在工具调用之前添加了一个搜索步骤，因此当上下文节省和准确性改进超过额外的延迟时，它可以提供最佳的投资回报率。

**在以下情况下使用它：**

* 工具定义消耗 >10K 代币
* 遇到刀具选择精度问题
* 使用多台服务器构建 MCP 驱动的系统
* 10+ 可用工具

**在以下情况下效果较差：**

* 小型工具库（<10 个工具）
* 每个会话中经常使用的所有工具
* 工具定义紧凑

程序化工具调用
------------------------

### 挑战

随着工作流程变得更加复杂，传统的工具调用会产生两个基本问题：

* **来自中间结果的上下文污染**：当 Claude 分析 10MB 日志文件中的错误模式时，整个文件都会进入其上下文窗口，即使 Claude 只需要错误频率的摘要。当跨多个表获取客户数据时，每条记录都会在上下文中累积，无论相关性如何。这些中间结果消耗大量的代币预算，并且可以将重要信息完全推出上下文窗口。
* **推理开销和手动综合**：每个工具调用都需要完整的模型推理过程。收到结果后，克劳德必须“观察”数据以提取相关信息，推理各个部分如何组合在一起，并决定下一步做什么——所有这些都是通过自然语言处理进行的。五工具工作流程意味着五次推理过程加上 Claude 解析每个结果、比较值并综合结论。这既缓慢又容易出错。

### 我们的解决方案

编程工具调用使 Claude 能够通过代码而不是通过单独的 API 往返来编排工具。 Claude 不是每次请求一个工具并将每个结果返回到其上下文，而是编写调用多个工具、处理其输出并控制实际进入其上下文窗口的信息的代码。

Claude 擅长编写代码，通过让它用 Python 表达编排逻辑，而不是通过自然语言工具调用，您可以获得更可靠、更精确的控制流。循环、条件、数据转换和错误处理在代码中都是显式的，而不是在 Claude 的推理中隐式的。

#### 示例：预算合规性检查

考虑一个常见的业务任务：“哪些团队成员超出了第三季度的差旅预算？”

您可以使用三种工具：

* `get_team_members(department)` - 返回带有 ID 和级别的团队成员列表
* `get_expenses(user_id,quarter)` - 返回用户的费用行项目
* `get_budget_by_level(level)` - 返回员工级别的预算限制

**传统方法**：

* 获取团队成员 → 20 人
* 对于每个人，获取他们的第三季度支出 → 20 次工具调用，每次返回 50-100 个行项目（航班、酒店、餐饮、收据）
* 按员工级别获取预算限制
* 所有这些都进入 Claude 的上下文：2,000 多个费用行项目 (50 KB+)
* Claude 手动汇总每个人的费用，查找他们的预算，将费用与预算限制进行比较
* 模型的往返次数更多，上下文消耗显着

**通过编程工具调用**：

Claude 没有将每个工具结果返回给 Claude，而是编写了一个 Python 脚本来协调整个工作流程。该脚本在代码执行工具（沙盒环境）中运行，在需要工具的结果时暂停。当您通过 API 返回工具结果时，它们将由脚本处理，而不是由模型使用。脚本继续执行，克劳德只看到最终的输出。

![图2：编程工具调用流](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimage s%2F4zrzovbb%2F网站%2F65737d69a3290ed5c1f3c3b8dc873645a9dcc2eb-1999x1491.png&w=3840&q=75)

编程工具调用使 Claude 能够通过代码而不是通过单独的 API 往返来编排工具，从而允许并行工具执行。

以下是克劳德针对预算合规任务的编排代码：```
team = await get_team_members("engineering")

# Fetch budgets for each unique level
levels = list(set(m["level"] for m in team))
budget_results = await asyncio.gather(*[
    get_budget_by_level(level) for level in levels
])

# Create a lookup dictionary: {"junior": budget1, "senior": budget2, ...}
budgets = {level: budget for level, budget in zip(levels, budget_results)}

# Fetch all expenses in parallel
expenses = await asyncio.gather(*[
    get_expenses(m["id"], "Q3") for m in team
])

# Find employees who exceeded their travel budget
exceeded = []
for member, exp in zip(team, expenses):
    budget = budgets[member["level"]]
    total = sum(e["amount"] for e in exp)
    if total > budget["travel_limit"]:
        exceeded.append({
            "name": member["name"],
            "spent": total,
            "limit": budget["travel_limit"]
        })

print(json.dumps(exceeded))
```克劳德的上下文只收到最终结果：超出预算的两到三个人。 2,000 多个行项目、中间金额和预算查找不会影响 Claude 的上下文，从而将消耗从 200KB 的原始费用数据减少到仅 1KB 的结果。

效率提升是巨大的：

* **节省代币**：通过将中间结果排除在 Claude 的上下文之外，PTC 极大地减少了代币消耗。平均使用量从 43,588 个令牌下降到 27,297 个令牌，复杂研究任务减少了 37%。
* **减少延迟**：每个 API 往返都需要模型推理（数百毫秒到秒）。当 Claude 在单个代码块中协调 20 多个工具调用时，您可以消除 19 多个推理过程。 API 处理工具执行，而无需每次都返回模型。
* **提高准确性**：通过编写明确的编排逻辑，Claude 比用自然语言处理多个工具结果时犯的错误更少。内部知识检索从25.6%提高到28.5%； [GIA 基准](https://arxiv.org/abs/2311.12983) 从 46.5% 降至 51.2%。

生产工作流程涉及混乱的数据、条件逻辑和需要扩展的操作。编程工具调用让 Claude 以编程方式处理这种复杂性，同时将重点放在可操作的结果而不是原始数据处理上。

### 编程工具调用的工作原理

#### 1. 将工具标记为可从代码调用

将 code_execution 添加到工具中，并将 allowed_callers 设置为选择加入工具以进行编程执行：```
{
  "tools": [
    {
      "type": "code_execution_20250825",
      "name": "code_execution"
    },
    {
      "name": "get_team_members",
      "description": "Get all members of a department...",
      "input_schema": {...},
      "allowed_callers": ["code_execution_20250825"] # opt-in to programmatic tool calling
    },
    {
      "name": "get_expenses",
 	...
    },
    {
      "name": "get_budget_by_level",
	...
    }
  ]
}
```API 将这些工具定义转换为 Claude 可以调用的 Python 函数。

#### 2. Claude 编写编排代码

Claude 不是一次请求一个工具，而是生成 Python 代码：```
{
  "type": "server_tool_use",
  "id": "srvtoolu_abc",
  "name": "code_execution",
  "input": {
    "code": "team = get_team_members('engineering')\n..." # the code example above
  }
}
```#### 3. 工具在不影响 Claude 上下文的情况下执行

当代码调用 get_expenses() 时，您会收到带有调用者字段的工具请求：```
{
  "type": "tool_use",
  "id": "toolu_xyz",
  "name": "get_expenses",
  "input": {"user_id": "emp_123", "quarter": "Q3"},
  "caller": {
    "type": "code_execution_20250825",
    "tool_id": "srvtoolu_abc"
  }
}
```您提供结果，该结果在代码执行环境而不是 Claude 的上下文中进行处理。对于代码中的每个工具调用，都会重复此请求-响应循环。

#### 4. 只有最终输出进入上下文

当代码运行完毕后，只将代码的结果返回给Claude：```
{
  "type": "code_execution_tool_result",
  "tool_use_id": "srvtoolu_abc",
  "content": {
    "stdout": "[{\"name\": \"Alice\", \"spent\": 12500, \"limit\": 10000}...]"
  }
}
```这就是 Claude 看到的全部内容，而不是一路上处理的 2000 多个费用行项目。

### 何时使用编程工具调用

编程工具调用向您的工作流程添加了代码执行步骤。当令牌节省、延迟改进和准确性提升显着时，这种额外的开销就会得到回报。

**最有益的时候：**

* 处理只需要聚合或摘要的大型数据集
* 通过三个或更多相关工具调用运行多步骤工作流程
* 在克劳德看到工具结果之前对其进行过滤、排序或转换
* 处理中间数据不应影响克劳德推理的任务
* 跨多个项目运行并行操作（例如，检查 50 个端点）

**在以下情况下效果较差：**

* 进行简单的单一工具调用
* 从事克劳德应该看到并推理所有中间结果的任务
* 以较小的响应运行快速查找

工具使用示例
-----------------

### 挑战

JSON Schema 擅长定义结构（类型、必填字段、允许的枚举），但它无法表达使用模式：何时包含可选参数、哪些组合有意义或您的 API 期望什么约定。

考虑一个支持票证 API：```
{
  "name": "create_ticket",
  "input_schema": {
    "properties": {
      "title": {"type": "string"},
      "priority": {"enum": ["low", "medium", "high", "critical"]},
      "labels": {"type": "array", "items": {"type": "string"}},
      "reporter": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "name": {"type": "string"},
          "contact": {
            "type": "object",
            "properties": {
              "email": {"type": "string"},
              "phone": {"type": "string"}
            }
          }
        }
      },
      "due_date": {"type": "string"},
      "escalation": {
        "type": "object",
        "properties": {
          "level": {"type": "integer"},
          "notify_manager": {"type": "boolean"},
          "sla_hours": {"type": "integer"}
        }
      }
    },
    "required": ["title"]
  }
}
```该模式定义了什么是有效的，但没有回答关键问题：

* **格式歧义：** `due_date` 应该使用“2024-11-06”、“2024 年 11 月 6 日”还是“2024-11-06T00:00:00Z”？
* **ID 约定：** `reporter.id` 是 UUID、“USR-12345”还是只是“12345”？
* **嵌套结构用法：**Claude 何时应该填充`reporter.contact`？
* **参数相关性：** `escalation.level` 和 `escalation.sla_hours` 与优先级有何关系？

这些歧义可能导致格式错误的工具调用和不一致的参数使用。

### 我们的解决方案

工具使用示例让您可以直接在工具定义中提供示例工具调用。您不是仅仅依赖于模式，而是向 Claude 展示了具体的使用模式：```
{
    "name": "create_ticket",
    "input_schema": { /* same schema as above */ },
    "input_examples": [
      {
        "title": "Login page returns 500 error",
        "priority": "critical",
        "labels": ["bug", "authentication", "production"],
        "reporter": {
          "id": "USR-12345",
          "name": "Jane Smith",
          "contact": {
            "email": "jane@acme.com",
            "phone": "+1-555-0123"
          }
        },
        "due_date": "2024-11-06",
        "escalation": {
          "level": 2,
          "notify_manager": true,
          "sla_hours": 4
        }
      },
      {
        "title": "Add dark mode support",
        "labels": ["feature-request", "ui"],
        "reporter": {
          "id": "USR-67890",
          "name": "Alex Chen"
        }
      },
      {
        "title": "Update API documentation"
      }
    ]
  }
```从这三个例子中，克劳德了解到：

* **格式约定**：日期使用 YYYY-MM-DD，用户 ID 遵循 USR-XXXXX，标签使用短横线大小写
* **嵌套结构模式**：如何用其嵌套的联系对象构造报告者对象
* **可选参数相关性**：关键错误具有完整的联系信息 + 具有严格 SLA 的升级；功能请求有记者但没有联系/升级；内部任务只有标题

在我们自己的内部测试中，工具使用示例将复杂参数处理的准确性从 72% 提高到 90%。

### 何时使用工具使用示例

工具使用示例将标记添加到您的工具定义中，因此当准确性改进超过额外成本时，它们是最有价值的。

**最有益的时候：**

* 复杂的嵌套结构，其中有效的 JSON 并不意味着正确的用法
* 具有许多可选参数和包含模式的工具很重要
* 具有特定领域约定的 API 未在模式中捕获
* 类似的工具，其中的示例阐明了要使用哪一个（例如，“create_ticket”与“create_incident”）

**在以下情况下效果较差：**

* 简单的单参数工具，用法一目了然
* Claude 已经理解的标准格式，如 URL 或电子邮件
* JSON Schema 约束可以更好地处理验证问题

最佳实践
--------------

构建采取现实世界行动的代理意味着同时处理规模、复杂性和精度。这三个功能共同解决工具使用工作流程中的不同瓶颈。以下是如何有效地将它们结合起来。

### 策略性地分层功能

并非每个代理都需要使用所有三个功能来完成给定的任务。从你最大的瓶颈开始：

* 工具定义中的上下文膨胀 → 工具搜索工具
* 大量中间结果污染上下文 → 编程工具调用
* 参数错误和畸形调用 → 工具使用示例

这种集中的方法可以让您解决限制代理性能的特定约束，而不是预先增加复杂性。

然后根据需要分层附加功能。它们是互补的：工具搜索工具确保找到正确的工具，编程工具调用确保高效执行，工具使用示例确保正确调用。

### 设置工具搜索工具以便更好地发现

工具搜索与名称和描述相匹配，因此清晰的描述性定义可以提高发现的准确性。```
// Good
{
    "name": "search_customer_orders",
    "description": "Search for customer orders by date range, status, or total amount. Returns order details including items, shipping, and payment info."
}

// Bad
{
    "name": "query_db_orders",
    "description": "Execute order query"
}
```添加系统提示指导，以便 Claude 知道可用的内容：```
You have access to tools for Slack messaging, Google Drive file management,
Jira ticket tracking, and GitHub repository operations. Use the tool search
to find specific capabilities.
```始终加载三到五个最常用的工具，推迟其余的。这可以平衡常见操作的即时访问与其他所有内容的按需发现。

### 设置编程工具调用以正确执行

由于 Claude 编写代码来解析工具输出，因此文档返回格式清晰。这有助于 Claude 编写正确的解析逻辑：```
{
    "name": "get_orders",
    "description": "Retrieve orders for a customer.
Returns:
    List of order objects, each containing:
    - id (str): Order identifier
    - total (float): Order total in USD
    - status (str): One of 'pending', 'shipped', 'delivered'
    - items (list): Array of {sku, quantity, price}
    - created_at (str): ISO 8601 timestamp"
}
```请参阅下文，了解受益于程序化编排的选择加入工具：

* 可以并行运行的工具（独立运行）
* 操作可以安全重试（幂等）

### 设置工具使用示例以确保参数准确性

行为清晰的工艺示例：

* 使用真实的数据（真实的城市名称、合理的价格，而不是“字符串”或“值”）
* 以最小、部分和完整规格模式显示多样性
* 保持简洁：每个工具 1-5 个示例
* 关注歧义（仅添加模式中正确用法不明显的示例）

开始使用
----------------

这些功能在测试版中可用。要启用它们，请添加 beta 标头并包含您需要的工具：```
client.beta.messages.create(
    betas=["advanced-tool-use-2025-11-20"],
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    tools=[
        {"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"},
        {"type": "code_execution_20250825", "name": "code_execution"},
        # Your tools with defer_loading, allowed_callers, and input_examples
    ]
)
```有关详细的 API 文档和 SDK 示例，请参阅我们的：

* 工具搜索工具的[文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)和[cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/tool_search_with_embeddings.ipynb)
* 用于编程工具调用的[文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)和[cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/programmatic_tool_calling_ptc.ipynb)
* [文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use#providing-tool-use-examples) 工具使用示例

这些功能将工具的使用从简单的函数调用转向智能编排。随着代理处理涉及数十种工具和大型数据集的更复杂的工作流程，动态发现、高效执行和可靠调用成为基础。

我们很高兴看到您所构建的内容。

致谢
----------------

由 Bin Wu 编写，Adam Jones、Artur Renault、Henry Tay、Jake Noble、Nathan McCandlish、Noah Picard、Sam Jiang 和 Claude 开发者平台团队的贡献。这项工作建立在 Chris Gorgolewski、Daniel Jiang、Jeremy Fox 和 Mike Lambert 的基础研究的基础上。我们还从整个 AI 生态系统中汲取灵感，包括 [Joel Pobar 的 LLMVM](https://github.com/9600dev/llmvm)、[Cloudflare 的代码模式](https://blog.cloudflare.com/code-mode/) 和 [Code Execution as MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)。特别感谢 Andy Schumeister、Hamish Kerr、Keir Bradwell、Matt Bleifer 和 Molly Vorwerck 的支持。

## 下一步行动计划
- 选择一条思路在实践环境中试验，并记录结果。
- 将文中提到的最佳实践整理为团队规范。
- 对关键工具或接口进行 PoC 验证，确保集成可行性。