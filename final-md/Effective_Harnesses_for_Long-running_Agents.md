# Effective Harnesses for Long-running Agents

> 来源：https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents


## 核心速览 (TL;DR)
        - 降价内容：
随着人工智能代理的能力越来越强，开发人员越来越多地要求它们承担需要花费数小时甚至数天时间的复杂任务。
- 然而，让代理在多个上下文窗口中取得一致的进展仍然是一个悬而未决的问题。
- 长时间运行的代理的核心挑战是它们必须在离散的会话中工作，并且每个新会话开始时都不记得之前发生了什么。

降价内容：
随着人工智能代理的能力越来越强，开发人员越来越多地要求它们承担需要花费数小时甚至数天时间的复杂任务。然而，让代理在多个上下文窗口中取得一致的进展仍然是一个悬而未决的问题。

长时间运行的代理的核心挑战是它们必须在离散的会话中工作，并且每个新会话开始时都不记得之前发生了什么。想象一下一个软件项目，工程师轮班工作，每个新工程师到达时都不记得上一个班次发生了什么。由于上下文窗口是有限的，并且大多数复杂的项目无法在单个窗口内完成，因此代理需要一种方法来弥合编码会话之间的差距。

我们开发了一个两重解决方案，使 [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) 能够在多个上下文窗口中有效工作：一个在第一次运行时设置环境的**初始化代理**，以及一个**编码代理**，其任务是在每个会话中取得增量进展，同时为下一个会话留下清晰的工件。您可以在随附的[快速入门](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding)中找到代码示例

长期运行的代理问题
------------------------------------------

Claude Agent SDK 是一个功能强大的通用代理工具，擅长编码以及需要模型使用工具收集上下文、计划和执行的其他任务。它具有上下文管理功能，例如压缩，使代理能够在不耗尽上下文窗口的情况下处理任务。理论上，在这种设置下，代理应该可以在任意长时间内继续做有用的工作。

然而，仅仅压缩还不够。即使像 Opus 4.5 这样开箱即用的前沿编码模型在跨多个上下文窗口的 Claude Agent SDK 上循环运行，如果仅给出高级提示（例如“构建[claude.ai](http://claude.ai/redirect/website.v1.369200a8-3256-417c-ad34-892ce68ffdac)。”

克劳德的失败表现为两种模式。首先，代理倾向于尝试一次做太多事情——本质上是试图一次性完成应用程序。通常，这会导致模型在实现过程中脱离上下文，从而使下一个会话以半实现且未记录的功能开始。然后，代理必须猜测发生了什么，并花费大量时间尝试让基本应用程序再次运行。即使使用压缩也会发生这种情况，压缩并不总是能将完全清晰的指令传递给下一个代理。

第二种故障模式通常会在项目后期发生。在构建了一些功能之后，稍后的代理实例将环顾四周，查看是否已取得进展，并声明工作已完成。

这将问题分解为两部分。首先，我们需要设置一个初始环境，为给定提示所需的所有功能奠定基础，从而设置代理逐步、逐个功能地工作。其次，我们应该促使每个智能体朝着其目标逐步取得进展，同时在会话结束时使环境处于清洁状态。我们所说的“干净状态”是指适合合并到主分支的代码：没有重大错误，代码有序且文档齐全，一般来说，开发人员可以轻松地开始开发新功能，而无需首先清理不相关的混乱。

在内部实验时，我们使用两部分解决方案解决了这些问题：

1. 初始化代理：第一个代理会话使用专门的提示，要求模型设置初始环境：一个“init.sh”脚本、一个记录代理所做操作的日志的 claude-progress.txt 文件，以及显示添加的文件的初始 git 提交。2. 编码代理：每个后续会话都要求模型取得增量进展，然后留下结构化更新。1

这里的关键见解是找到一种方法，让代理在从新的上下文窗口开始时快速了解工作状态，这是通过 claude-progress.txt 文件和 git 历史记录来完成的。这些实践的灵感来自于了解有效的软件工程师每天所做的事情。

环境管理
----------------------

在更新的 [Claude 4 提示指南](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices#multi-context-window-workflows)中，我们分享了一些多上下文窗口工作流程的最佳实践，包括使用“为第一个上下文窗口使用不同提示”的线束结构。这种“不同的提示”要求初始化程序代理设置具有未来编码代理有效工作所需的所有必要上下文的环境。在这里，我们对此类环境的一些关键组件进行了更深入的探讨。

### 功能列表

为了解决代理一次性完成应用程序或过早地认为项目已完成的问题，我们提示初始化程序代理编写一份全面的功能需求文件，以扩展用户的初始提示。在 [claude.ai](http://claude.ai/redirect/website.v1.369200a8-3256-417c-ad34-892ce68ffdac) 克隆示例中，这意味着超过 200 个功能，例如“用户可以打开新聊天，输入查询，按 Enter 键，然后查看 AI 响应。”这些功能最初都被标记为“失败”，以便后来的编码代理能够清楚地了解完整功能的外观。```
{
    "category": "functional",
    "description": "New chat button creates a fresh conversation",
    "steps": [
      "Navigate to main interface",
      "Click the 'New Chat' button",
      "Verify a new conversation is created",
      "Check that chat area shows welcome state",
      "Verify conversation appears in sidebar"
    ],
    "passes": false
  }
```我们提示编码代理仅通过更改 pass 字段的状态来编辑此文件，并且我们使用措辞强硬的指令，例如“删除或编辑测试是不可接受的，因为这可能会导致功能缺失或有缺陷。”经过一些实验后，我们最终决定使用 JSON 来实现此目的，因为与 Markdown 文件相比，该模型不太可能不当更改或覆盖 JSON 文件。

### 渐进式进展

考虑到这个初始环境脚手架，编码代理的下一次迭代被要求一次仅处理一个功能。事实证明，这种增量方法对于解决代理一次性做太多事情的倾向至关重要。

一旦增量工作，模型在进行代码更改后使环境保持干净状态仍然很重要。在我们的实验中，我们发现引发此行为的最佳方法是要求模型使用描述性提交消息将其进度提交到 git，并将其进度摘要写入进度文件。这允许模型使用 git 来恢复错误的代码更改并恢复代码库的工作状态。

这些方法还提高了效率，因为它们消除了代理必须猜测发生了什么并花时间尝试让基本应用程序再次运行的需要。

### 测试

我们观察到的最后一个主要故障模式是克劳德倾向于在没有适当测试的情况下将功能标记为完整。如果没有明确的提示，Claude 倾向于更改代码，甚至使用单元测试或针对开发服务器的“curl”命令进行测试，但无法认识到该功能无法端到端运行。

在构建 Web 应用程序的情况下，一旦明确提示使用浏览器自动化工具并像人类用户一样进行所有测试，Claude 在端到端验证功能方面表现出色。

![图 1：Claude 在测试 claude.ai 克隆时通过 Puppeteer MCP 服务器拍摄的屏幕截图。 ](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages% 2F4zrzovbb%2F网站%2Ff94c2257964fb2d623f1e81f874977ebfc0986bc-1920x1080.gif&w=3840&q=75)

Claude 在测试 claude.ai 克隆时通过 Puppeteer MCP 服务器拍摄的屏幕截图。

为 Claude 提供此类测试工具极大地提高了性能，因为代理能够识别并修复仅从代码中并不明显的错误。

一些问题仍然存在，例如克劳德的愿景和浏览器自动化工具的限制，使得识别每种错误变得困难。例如，Claude 无法通过 Puppeteer MCP 查看浏览器本机警报模式，因此依赖这些模式的功能往往会出现更多错误。

加快步伐
-------------------

完成上述所有操作后，每个编码代理都会被提示执行一系列步骤来了解其方向，其中一些非常基本但仍然有用：

1. _运行 `pwd` 查看您正在工作的目录。您只能编辑此目录中的文件。_
2. _阅读 git 日志和进度文件以了解最近所做的工作。_
3. _阅读功能列表文件并选择尚未完成的最高优先级功能。_

这种方法可以在每次会话中为 Claude 节省一些令牌，因为它不必弄清楚如何测试代码。它还有助于要求初始化程序代理编写一个可以运行开发服务器的 init.sh 脚本，然后在实现新功能之前运行基本的端到端测试。

就 claude.ai 克隆而言，这意味着代理始终启动本地开发服务器并使用 Puppeteer MCP 启动新聊天、发送消息并接收响应。这确保了克劳德能够快速识别应用程序是否处于损坏状态，并立即修复任何现有的错误。如果代理开始实施新功能，则可能会使问题变得更糟。

鉴于所有这些，典型的会话以以下辅助消息开始：```
[Assistant] I'll start by getting my bearings and understanding the current state of the project.
[Tool Use] <bash - pwd>
[Tool Use] <read - claude-progress.txt>
[Tool Use] <read - feature_list.json>
[Assistant] Let me check the git log to see recent work.
[Tool Use] <bash - git log --oneline -20>
[Assistant] Now let me check if there's an init.sh script to restart the servers.
<Starts the development server>
[Assistant] Excellent! Now let me navigate to the application and verify that some fundamental features are still working.
<Tests basic functionality>
[Assistant] Based on my verification testing, I can see that the fundamental functionality is working well. The core chat features, theme switching, conversation loading, and error handling are all functioning correctly. Now let me review the tests.json file more comprehensively to understand what needs to be implemented next.
<Starts work on a new feature>
```Agent故障模式及解决方案

| **问题** | **初始化程序代理行为** | **编码代理行为** |
| --- | --- | --- |
|克劳德过早地宣布整个项目的胜利。 |设置功能列表文件：根据输入规范，设置包含端到端功能描述列表的结构化 JSON 文件。 |在会话开始时读取功能列表文件。选择一个功能来开始处理。 |
|克劳德让环境处于有错误或未记录进度的状态。 |编写了初始 git 存储库和进度注释文件。 |通过阅读进度说明文件和 git 提交日志来启动会话，并在开发服务器上运行基本测试以捕获任何未记录的错误。通过编写 git 提交和进度更新来结束会话。 |
|克劳德将功能标记为过早完成。 |设置功能列表文件。 |自我验证所有功能。仅在仔细测试后才将功能标记为“通过”。 |
|克劳德必须花时间弄清楚如何运行该应用程序。 |编写一个可以运行开发服务器的“init.sh”脚本。 |通过读取“init.sh”启动会话。 |

总结了长时间运行的人工智能代理的四种常见故障模式和解决方案。

未来的工作
------------

这项研究展示了长期运行的代理工具中的一组可能的解决方案，使模型能够在许多上下文窗口中取得增量进展。然而，仍有一些悬而未决的问题。

最值得注意的是，目前尚不清楚单个通用编码代理是否在跨上下文中表现最佳，或者是否可以通过多代理架构实现更好的性能。测试代理、质量保证代理或代码清理代理等专门代理可以在整个软件开发生命周期的子任务上做得更好，这似乎是合理的。

此外，该演示还针对全栈 Web 应用程序开发进行了优化。未来的方向是将这些发现推广到其他领域。这些经验教训中的部分或全部很可能可以应用于科学研究或金融建模等所需的长期运行的代理任务类型。

### 致谢

由贾斯汀·杨撰写。特别感谢 David Hershey、Prithvi Rajasakeran、Jeremy Hadfield、Naia Bouscal、Michael Tingley、Jesse Mu、Jake Eaton、Marius Buleandara、Maggie Vo、Pedram Navid、Nadine Yasser 和 Alex Notov 的贡献。

这项工作反映了 Anthropic 多个团队的集体努力，使 Claude 能够安全地进行长期自主软件工程，特别是代码 RL 和 Claude Code 团队。欢迎有兴趣做出贡献的候选人在 [anthropic.com/careers](http://anthropic.com/careers) 上申请。

### 脚注

1. 在本文中，我们将这些代理称为单独的代理，只是因为它们具有不同的初始用户提示。系统提示、工具集和整体代理工具在其他方面都是相同的。

## 下一步行动计划
- 选择一条思路在实践环境中试验，并记录结果。
- 将文中提到的最佳实践整理为团队规范。
- 对关键工具或接口进行 PoC 验证，确保集成可行性。