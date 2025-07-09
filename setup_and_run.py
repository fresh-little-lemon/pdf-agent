#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF论文分析助手 - 快速入门脚本
帮助用户快速设置环境并测试功能
"""

import os
import sys
import subprocess
import platform


def print_banner():
    """打印欢迎横幅"""
    print("=" * 70)
    print("📄 PDF论文分析助手 - 快速入门")
    print("=" * 70)
    print("🚀 智能PDF分析 + 论文问答助手")
    print("🔧 完整工作流: 边界框提取 → 布局分析 → HTML解析 → Markdown转换 → 智能问答")
    print("=" * 70)


def check_python_version():
    """检查Python版本"""
    print("\n🐍 检查Python版本...")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python版本过低: {version.major}.{version.minor}")
        print("请升级到Python 3.8或更高版本")
        return False
    else:
        print(f"✅ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True


def install_dependencies():
    """安装依赖项"""
    print("\n📦 安装依赖项...")
    
    try:
        # 检查requirements.txt是否存在
        if not os.path.exists("requirements.txt"):
            print("❌ 未找到requirements.txt文件")
            return False
        
        # 安装依赖
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 依赖项安装成功")
            return True
        else:
            print(f"❌ 依赖项安装失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 安装过程中出错: {str(e)}")
        return False


def check_api_configuration():
    """检查API配置"""
    print("\n🔑 检查API配置...")
    
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN") or os.getenv("DASHSCOPE_API_KEY")
    
    if api_key:
        print(f"✅ API密钥已配置 (长度: {len(api_key)})")
        return True
    else:
        print("⚠️ 未检测到API密钥配置")
        print("\n📝 请按以下步骤配置API密钥:")
        
        system = platform.system()
        if system == "Windows":
            print("Windows系统:")
            print('  set MODELSCOPE_SDK_TOKEN=your_token_here')
            print("或者:")
            print('  set DASHSCOPE_API_KEY=your_api_key_here')
        else:
            print("Linux/Mac系统:")
            print('  export MODELSCOPE_SDK_TOKEN="your_token_here"')
            print("或者:")
            print('  export DASHSCOPE_API_KEY="your_api_key_here"')
        
        print("\n💡 获取API密钥:")
        print("- ModelScope: https://www.modelscope.cn/")
        print("- DashScope: https://dashscope.aliyun.com/")
        
        return False


def create_directories():
    """创建必要的目录"""
    print("\n📁 创建工作目录...")
    
    directories = ["logs", "tmp"]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ 创建目录: {directory}")
        except Exception as e:
            print(f"❌ 创建目录 {directory} 失败: {str(e)}")
            return False
    
    return True


def check_test_file():
    """检查测试文件"""
    print("\n📄 检查测试文件...")
    
    test_pdf = "test.pdf"
    if os.path.exists(test_pdf):
        file_size = os.path.getsize(test_pdf) / (1024 * 1024)  # MB
        print(f"✅ 找到测试文件: {test_pdf} ({file_size:.1f} MB)")
        return True
    else:
        print(f"⚠️ 未找到测试文件: {test_pdf}")
        print("💡 请将测试PDF文件重命名为 'test.pdf' 并放在当前目录")
        print("   这样可以运行完整的工作流测试")
        return False


def run_dependency_test():
    """运行依赖项测试"""
    print("\n🔍 测试依赖项...")
    
    modules_to_test = [
        ("streamlit", "Streamlit Web框架"),
        ("fitz", "PyMuPDF PDF处理"),
        ("PIL", "Pillow 图像处理"),
        ("bs4", "BeautifulSoup HTML解析"),
        ("openai", "OpenAI API客户端")
    ]
    
    all_passed = True
    
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {description}")
        except ImportError:
            print(f"❌ {description}")
            all_passed = False
    
    return all_passed


def run_basic_test():
    """运行基础功能测试"""
    print("\n🧪 运行基础功能测试...")
    
    try:
        # 测试工具导入
        from utils.pdf_bbox_extractor import PDFBboxExtractor
        from utils.layout_analyzer import LayoutAnalyzer
        from utils.html_parser import get_api_status
        print("✅ 工具模块导入成功")
        
        # 测试API状态
        api_status = get_api_status()
        if api_status['api_key_configured']:
            print("✅ API状态检查通过")
        else:
            print("⚠️ API未配置，但核心功能可用")
        
        return True
        
    except Exception as e:
        print(f"❌ 基础功能测试失败: {str(e)}")
        return False


def suggest_next_steps(api_configured, test_file_exists):
    """建议下一步操作"""
    print("\n🎯 建议的下一步操作:")
    print("-" * 40)
    
    if not api_configured:
        print("1. 🔑 配置API密钥 (必须)")
        print("   - 获取ModelScope或DashScope API密钥")
        print("   - 设置环境变量")
        print()
    
    if api_configured and test_file_exists:
        print("2. 🧪 运行完整测试:")
        print("   python test_workflow.py")
        print()
    
    print("3. 🚀 启动应用:")
    print("   streamlit run app.py")
    print()
    
    if not test_file_exists:
        print("4. 📄 准备测试文件:")
        print("   - 将PDF文件重命名为 'test.pdf'")
        print("   - 放在当前目录下")
        print()
    
    print("5. 📖 查看详细文档:")
    print("   README_workflow.md")


def main():
    """主函数"""
    print_banner()
    
    # 检查Python版本
    if not check_python_version():
        return
    
    # 创建目录
    if not create_directories():
        return
    
    # 安装依赖项
    if not install_dependencies():
        print("\n💡 如果安装失败，请尝试:")
        print("pip install --upgrade pip")
        print("pip install -r requirements.txt")
        return
    
    # 测试依赖项
    if not run_dependency_test():
        print("\n❌ 部分依赖项未正确安装，请检查安装日志")
        return
    
    # 运行基础测试
    if not run_basic_test():
        return
    
    # 检查API配置
    api_configured = check_api_configuration()
    
    # 检查测试文件
    test_file_exists = check_test_file()
    
    # 总结和建议
    print("\n" + "=" * 70)
    print("📊 环境检查完成")
    print("=" * 70)
    
    if api_configured:
        print("✅ 环境配置完整，可以使用所有功能")
    else:
        print("⚠️ 环境基本就绪，需要配置API密钥以使用AI功能")
    
    # 建议下一步
    suggest_next_steps(api_configured, test_file_exists)
    
    print("\n🎉 设置完成！准备开始使用PDF论文分析助手")
    print("=" * 70)


if __name__ == "__main__":
    main() 