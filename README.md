# PDF处理工具

一个功能强大的PDF处理工具，集成了PDF转图片、图片提取和AI文档解析功能，使用Streamlit构建用户界面。

## 🎯 功能特性

### 1. 📄➡️🖼️ PDF页面转JPG
- 将PDF每页转换为高质量JPG图片
- 可调节图片质量(DPI：72-300)
- 自动生成唯一文件名，避免冲突
- 支持批量下载ZIP文件

### 2. 🖼️📤 提取PDF中的图片
- 从PDF文档中提取所有嵌入的图片
- 按照 `{pdf文件名}_page_{页码}_{图片序号}.{格式}` 命名
- 支持多种图片格式（JPG、PNG、GIF等）
- 可选择统一转换为JPG格式

### 3. 📄➡️📝 PDF解析为HTML（新功能）
- 使用Qwen2.5-VL模型进行文档解析
- 生成QwenVL HTML格式，包含文档结构信息
- 按页面保存为 `page_{页码}.html` 格式
- 支持高质量文档识别和内容提取

## 📁 项目结构

```
pdf-agent-qwenvl/
├── app.py                          # Streamlit主应用
├── utils/
│   ├── __init__.py                # Python包初始化
│   ├── pdf_converter.py          # PDF转JPG工具
│   ├── image_extractor.py         # PDF图片提取工具
│   └── html_parser.py             # Qwen2.5-VL HTML解析工具
├── tmp/                           # 临时文件存储目录
│   ├── {pdf文件名}_converted_to_img/  # PDF转换的图片
│   ├── {pdf文件名}_figure/           # 提取的图片
│   └── {pdf文件名}_html/             # 解析的HTML文件
├── requirements.txt               # 项目依赖
└── README.md                     # 项目说明
```

## 🚀 安装与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置API密钥（HTML解析功能需要）
```bash
# 设置ModelScope API密钥
export MODELSCOPE_SDK_TOKEN=your_api_key

# 或者设置阿里云DashScope API密钥
export DASHSCOPE_API_KEY=your_api_key
```

### 3. 启动应用
```bash
streamlit run app.py
```

## 📖 使用说明

### PDF页面转JPG
1. 选择"📄➡️🖼️ PDF页面转JPG"功能
2. 在侧边栏调整图片质量设置
3. 上传PDF文件
4. 点击"开始转换"按钮
5. 预览和下载转换结果

### 提取PDF中的图片
1. 选择"🖼️📤 提取PDF中的图片"功能
2. 上传PDF文件，查看图片信息
3. 选择是否统一转换为JPG格式
4. 点击"开始提取图片"按钮
5. 下载提取的图片

### PDF解析为HTML
1. 选择"📄➡️📝 PDF解析为HTML"功能
2. 确保已配置API密钥
3. 上传PDF文件
4. 点击"开始解析为HTML"按钮
5. 等待AI解析完成
6. 预览和下载HTML文件

## 🔧 技术栈

- **Streamlit**: Web应用框架
- **PyMuPDF**: PDF处理库
- **Pillow**: 图像处理库
- **BeautifulSoup4**: HTML解析库
- **OpenAI**: API客户端
- **Qwen2.5-VL**: 多模态AI模型

## 📝 文件命名规则

### PDF转JPG
- 格式：`{pdf文件名}_page_{页码}.jpg`
- 示例：`document_page_1.jpg`, `document_page_2.jpg`

### 图片提取
- 格式：`{pdf文件名}_page_{页码}_{图片序号}.{原格式}`
- 示例：`document_page_1_1.jpg`, `document_page_1_2.png`

### HTML解析
- 格式：`page_{页码}.html`
- 示例：`page_1.html`, `page_2.html`

## ⚠️ 注意事项

1. **API密钥**: HTML解析功能需要配置有效的API密钥
2. **网络连接**: HTML解析功能需要稳定的网络连接
3. **文件大小**: 建议上传的PDF文件大小不超过50MB
4. **图片质量**: DPI设置越高，生成的图片质量越好，但文件也会越大

## 🔗 相关链接

- [ModelScope](https://modelscope.cn/)
- [Qwen2.5-VL模型](https://github.com/QwenLM/Qwen2.5-VL)
- [PyMuPDF文档](https://pymupdf.readthedocs.io/)
- [Streamlit文档](https://docs.streamlit.io/)