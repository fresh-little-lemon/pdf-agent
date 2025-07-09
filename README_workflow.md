# PDF论文分析助手 - 完整工作流

这是一个基于 Streamlit 的 PDF 论文分析助手，能够自动处理 PDF 文档并提供智能问答功能。

## 🎯 功能特点

### 📋 完整的 PDF 分析工作流
1. **边界框提取** - 使用 Qwen2.5-VL 智能识别文本、图像、表格、矢量图
2. **布局分析** - 自动检测单栏/双栏/混合布局并进行智能切片
3. **内容解析** - 将切片转换为结构化 HTML 内容
4. **文档生成** - 转换为高质量 Markdown 文档
5. **智能总结** - AI 自动生成论文摘要和要点
6. **智能问答** - 基于论文内容的精准问答，支持多轮对话

### 🔧 技术特点
- **矢量图检测** - 30×30像素区域内密集元素自动识别和合并
- **小切片过滤** - 自动丢弃PDF中小于15px的无用切片
- **布局自适应** - 支持单栏、双栏、混合布局的智能识别
- **多线程处理** - 并行处理提高效率
- **日志管理** - 完整的日志记录和错误追踪

## 🚀 快速开始

### 1. 环境准备

#### 安装依赖
```bash
pip install -r requirements.txt
```

#### 配置 API 密钥
设置以下环境变量之一：
```bash
# 方法1: 使用 ModelScope API
export MODELSCOPE_SDK_TOKEN="your_token_here"

# 方法2: 使用 DashScope API  
export DASHSCOPE_API_KEY="your_api_key_here"
```

### 2. 运行测试

#### 测试工作流
```bash
# 将测试PDF文件放在当前目录并命名为 test.pdf
python test_workflow.py
```

#### 启动应用
```bash
streamlit run app.py
```

## 📁 项目结构

```
pdf-agent-qwenvl/
├── app.py                          # 主应用文件
├── test_workflow.py                # 工作流测试脚本
├── requirements.txt                # 依赖项列表
├── README_workflow.md              # 使用说明
├── utils/                          # 工具模块
│   ├── pdf_bbox_extractor.py       # PDF边界框提取
│   ├── layout_analyzer.py          # 布局分析和切片
│   ├── html_parser.py              # HTML解析
│   ├── html_to_markdown.py         # Markdown转换
│   ├── pdf_converter.py            # PDF转图片
│   └── image_extractor.py          # 图像提取
├── logs/                           # 日志文件目录
└── tmp/                            # 临时文件目录
```

## 🔄 工作流详解

### 步骤1: PDF边界框提取
- **功能**: 使用 `pdf_bbox_extractor.py` 识别PDF中的各种元素
- **检测内容**: 文本块、图像、表格、矢量图、原始框线
- **特殊功能**: 
  - 矢量图自动检测（30×30px区域内同时包含线条和图像）
  - 框线修正（根据PDF原始线条修正表格边框）
  - 多线程并行处理
- **输出**: 带标注的PDF文件 + JSON元数据

### 步骤2: 布局分析和切片
- **功能**: 使用 `layout_analyzer.py` 分析页面布局并切片
- **布局类型**: 
  - 单栏布局：内容跨越页面中轴线
  - 双栏布局：内容分布在左右两侧
  - 混合布局：包含单栏和双栏区域
- **特殊处理**:
  - 不规则双栏：元素与中轴线相交时，按元素边界独立切片
  - 小切片过滤：自动丢弃PDF中宽度或高度≤15px的切片
- **输出**: 切片图像（300dpi） + 切片信息JSON

### 步骤3: HTML解析
- **功能**: 使用 `html_parser.py` 将切片图像转换为HTML
- **解析引擎**: Qwen2.5-VL 多模态大语言模型
- **处理策略**: 串行处理确保稳定性和页码对应
- **输出**: 结构化HTML文件

### 步骤4: Markdown转换
- **功能**: 使用 `html_to_markdown.py` 将HTML转换为Markdown
- **转换内容**: 文本、表格、公式、图像、列表等
- **文档处理**: 自动合并、清理、格式化
- **输出**: 高质量Markdown文档

### 步骤5: 论文总结
- **功能**: 使用AI模型自动生成论文总结
- **总结内容**: 
  - 论文标题和作者
  - 研究背景和问题
  - 主要方法和技术
  - 核心贡献和创新点
  - 实验结果和数据
  - 结论和未来工作
- **输出**: 结构化论文总结

### 步骤6: 智能问答
- **功能**: 基于论文内容的智能问答
- **特点**:
  - 精准引用来源
  - 支持多轮对话
  - 理解表格、公式、图像
  - 保持上下文连贯性

## 💻 使用界面

### 主界面功能
- **文件上传**: 支持PDF格式文件拖拽上传
- **工作流控制**: 一键启动完整分析流程
- **状态监控**: 实时显示各步骤处理状态
- **进度追踪**: 可视化进度条和状态提示

### 侧边栏功能
- **API状态检查**: 自动检测API配置是否正确
- **处理状态**: 显示各步骤的成功/失败状态
- **数据管理**: 一键清除会话数据

### 聊天界面
- **论文总结展示**: 可折叠的详细总结内容
- **问答对话**: 类似ChatGPT的对话界面
- **历史记录**: 保存最近10轮对话历史
- **智能回答**: 基于论文内容的准确回答

## 📊 输出文件说明

### 边界框提取输出
- `{filename}_bbox.pdf`: 带标注的PDF文件
- `{filename}_bbox_metadata.json`: 详细的元素信息

### 布局分析输出
- `{filename}_slice/`: 切片图像目录
- `{filename}_slice_info.json`: 切片详细信息

### HTML解析输出
- `{filename}_slices_html/`: HTML文件目录
- `page_*.html`: 各页面的HTML文件

### Markdown转换输出
- `{filename}_slices_markdown/`: Markdown文件目录
- `{filename}_slices_clean_merged.md`: 最终合并文档

### 日志文件
- `logs/pdf_workflow_*.log`: 详细的处理日志

## ⚙️ 配置选项

### 边界框提取配置
```python
extract_pdf_bboxes(
    enable_table_detection=True,        # 启用表格检测
    show_original_lines=True,           # 显示原始框线（矢量图检测需要）
    max_workers=4,                      # 并行线程数
    show_original_qwen_tables=False     # 显示原始Qwen表格框线
)
```

### 布局分析配置
```python
analyze_and_slice_pdf(
    # 自动使用300dpi分辨率
    # 自动过滤≤15px的小切片
)
```

### HTML解析配置
```python
parse_all_images_to_html(
    parallel=False,                     # 使用串行处理
    max_workers=2,                      # 最大并行数
    enable_clean=False,                 # 是否清理HTML
    max_retries=3,                      # API重试次数
    retry_delay=2.0                     # 重试间隔
)
```

## 🐛 故障排除

### 常见问题

#### 1. API配置问题
```
❌ 请设置 MODELSCOPE_SDK_TOKEN 或 DASHSCOPE_API_KEY 环境变量
```
**解决方案**: 按照上述步骤配置API密钥

#### 2. 依赖项缺失
```
❌ ModuleNotFoundError: No module named 'xxx'
```
**解决方案**: 运行 `pip install -r requirements.txt`

#### 3. 内存不足
**症状**: 处理大PDF时程序崩溃
**解决方案**: 减少 `max_workers` 参数值

#### 4. API调用失败
**症状**: 网络错误或API限流
**解决方案**: 检查网络连接，等待后重试

### 调试技巧

#### 查看详细日志
```bash
tail -f logs/pdf_workflow_*.log
```

#### 测试单个步骤
```python
# 只测试前两个步骤（无需API）
python test_workflow.py
```

#### 检查临时文件
工作流会在临时目录生成中间文件，可用于调试：
- 查看切片图像质量
- 检查HTML解析结果
- 验证Markdown转换效果

## 📈 性能优化

### 推荐配置
- **小文档 (<10页)**: `max_workers=2-4`
- **中等文档 (10-50页)**: `max_workers=4-8`
- **大文档 (>50页)**: `max_workers=8-16`

### 处理时间估算
- **边界框提取**: ~10-30秒/页
- **布局分析**: ~1-5秒/页
- **HTML解析**: ~30-60秒/切片（取决于API响应）
- **Markdown转换**: ~1-3秒/页
- **论文总结**: ~10-30秒

## 🔒 安全注意事项

1. **API密钥安全**: 不要在代码中硬编码API密钥
2. **文件隐私**: 临时文件会自动清理，但建议定期检查
3. **网络安全**: API调用通过HTTPS加密传输
4. **本地处理**: 除AI推理外，所有处理都在本地进行

## 📞 技术支持

### 日志分析
所有操作都会记录详细日志，包括：
- 处理步骤和耗时
- 错误信息和堆栈跟踪
- API调用状态和重试信息
- 文件路径和统计信息

### 性能监控
- 内存使用情况
- 处理耗时统计
- API调用成功率
- 文件大小和质量指标

---

## 🎉 开始使用

1. **配置环境**: 安装依赖 + 设置API密钥
2. **测试功能**: 运行 `python test_workflow.py`
3. **启动应用**: 运行 `streamlit run app.py`
4. **上传PDF**: 在界面中上传PDF文件
5. **开始分析**: 点击"开始分析"按钮
6. **等待完成**: 观察处理进度
7. **开始问答**: 与论文内容进行对话

享受智能PDF分析的便利！🚀 