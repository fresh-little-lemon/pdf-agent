# 📄 PDF论文分析助手 - Agent架构

## 🎯 最新更新

### 🧠 智能Agent架构重构

为了降低代码耦合度并提高功能模块化，我们将论文分析功能重构为独立的Agent模块：

#### 📝 PaperSummaryAgent（论文总结代理）
- **功能**: 智能分析和总结学术论文内容
- **模型**: Qwen/Qwen2.5-14B-Instruct-1M
- **特点**: 结构化总结，包含标题、作者、背景、方法、贡献、结果、结论

#### 🤖 PaperQAAgent（智能问答代理）
- **功能**: 基于论文内容的智能问答系统
- **路由模型**: Qwen/Qwen3-235B-A22B（智能判断问题类型）
- **文本模型**: Qwen/Qwen2.5-14B-Instruct-1M（纯文本问答）
- **视觉模型**: Qwen/Qwen2.5-VL-72B-Instruct（图像内容分析）

### 🔄 智能路由系统

#### 路由逻辑
```python
# 自动判断问题类型
question = "论文中的第二张图片说了什么？"
# 路由agent判断 → 需要视觉功能
# 自动选择视觉模型进行分析

question = "这篇论文的主要贡献是什么？"  
# 路由agent判断 → 纯文本问题
# 使用文本模型进行回答
```

#### 支持的视觉问题类型
- 📊 **图表分析**: "图1显示了什么数据？"
- 🖼️ **图片描述**: "第三张图片的内容是什么？"
- 📈 **趋势分析**: "图表中的趋势说明了什么？"
- 🔍 **细节查询**: "示意图中的流程是怎样的？"

## 🏗️ 架构说明

### 文件结构
```
agent/
├── __init__.py                 # Agent模块入口
├── paper_summary_agent.py      # 论文总结代理
└── paper_qa_agent.py          # 智能问答代理（含路由）

app.py                         # 主应用（简化后）
```

### 🧩 模块化设计

#### 1. PaperSummaryAgent
```python
from agent.paper_summary_agent import PaperSummaryAgent

agent = PaperSummaryAgent(logger)
result = agent.summarize_paper(markdown_file)
```

**核心功能**:
- ✅ Markdown内容验证
- 📋 智能提示词生成
- 🎯 结构化论文总结
- 🔧 错误处理和重试

#### 2. PaperQAAgent
```python
from agent.paper_qa_agent import PaperQAAgent

agent = PaperQAAgent(logger)
answer = agent.answer_question(
    question="用户问题",
    markdown_content="论文内容", 
    slice_images_dir="切片图像目录",  # 支持视觉功能
    conversation_history=[...]       # 对话历史
)
```

**核心功能**:
- 🤖 **智能路由**: 自动判断问题是否需要视觉分析
- 👁️ **视觉问答**: 分析图片、图表、示意图等
- 📝 **文本问答**: 基于论文文本内容回答
- 🎯 **图片选择**: 根据问题自动选择相关图片
- 💬 **对话历史**: 支持多轮对话

## 🚀 性能优化

### 并行处理配置
- **HTML解析**: 并行模式，10个工作线程
- **边界框提取**: 10个工作线程
- **临时数据**: 统一存储在 `/tmp` 目录

### 智能降级机制
```python
# 视觉分析失败时自动降级为文本回答
try:
    vision_answer = analyze_image(question, image)
except Exception:
    text_answer = analyze_text(question, markdown_content)
    return f"无法分析图片，基于文本回答：\n{text_answer}"
```

## 🔍 使用示例

### 文本问题
```
用户: "这篇论文的主要方法是什么？"
系统: [路由判断: 文本问题] → [文本模型回答]
```

### 视觉问题  
```
用户: "论文中的第二张图显示了什么？"
系统: [路由判断: 视觉问题] → [图片选择] → [视觉模型分析]
```

### 图片选择逻辑
- 🔢 **序数识别**: "第二张图" → 选择第2张图片
- 🔤 **中文数字**: "第三幅图" → 转换为数字3
- 🎯 **关键词匹配**: "图表数据" → 选择前几张相关图片

## 🛠️ 开发指南

### 扩展新的Agent
1. 在 `agent/` 目录下创建新的agent文件
2. 继承或参考现有agent的结构
3. 在 `__init__.py` 中注册新agent
4. 在 `app.py` 中集成调用

### 自定义路由规则
编辑 `paper_qa_agent.py` 中的 `_route_question` 方法：
```python
def _route_question(self, question: str) -> bool:
    # 添加自定义判断逻辑
    if "新的视觉关键词" in question:
        return True
    return existing_logic(question)
```

## 📋 API接口

### PaperSummaryAgent
```python
# 总结论文
result = agent.summarize_paper(markdown_file)
# 返回: {'status': 'success', 'summary': '...', 'markdown_content': '...'}

# 验证文件
validation = agent.validate_markdown_content(markdown_file)  
# 返回: {'valid': True, 'message': '...', 'content_length': 1234}
```

### PaperQAAgent
```python
# 智能问答
answer = agent.answer_question(
    question="问题",
    markdown_content="内容",
    conversation_history=[],      # 可选：对话历史
    slice_images_dir="/path"      # 可选：图片目录
)
# 返回: "智能回答内容"

# 手动路由判断
needs_vision = agent._route_question("问题")
# 返回: True/False
```

## 🔧 配置要求

### 环境变量
```bash
# 必须配置其中一个API密钥
export MODELSCOPE_SDK_TOKEN="your_token"
# 或
export DASHSCOPE_API_KEY="your_key"
```

### 模型配置
- **路由模型**: Qwen/Qwen3-235B-A22B
- **文本模型**: Qwen/Qwen2.5-14B-Instruct-1M  
- **视觉模型**: Qwen/Qwen2.5-VL-72B-Instruct

## 🎉 优势特点

### 🧠 智能化
- 自动判断问题类型，无需人工指定
- 智能选择合适的模型进行处理
- 自动降级机制保证系统稳定性

### 🔧 模块化
- Agent独立开发和测试
- 便于功能扩展和维护
- 降低代码耦合度

### 🚀 高性能
- 并行处理提高速度
- 智能路由减少不必要计算
- 临时数据统一管理

### 💬 用户友好
- 支持多轮对话
- 自然语言交互
- 图文并茂的回答

---

**🔗 相关文档**:
- [PDF工作流文档](README_workflow.md)
- [布局分析文档](README_layout_analyzer.md)
- [主要README](README.md) 