#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF分析工作流测试脚本
用于验证完整工作流的各个步骤是否正常工作
"""

import os
import sys
import tempfile
from datetime import datetime
from app import PDFAnalysisWorkflow, WorkflowLogger


def test_workflow():
    """测试完整的PDF分析工作流"""
    
    print("=" * 70)
    print("PDF分析工作流测试")
    print("=" * 70)
    
    # 检查测试文件
    test_pdf = "test.pdf"
    if not os.path.exists(test_pdf):
        print(f"❌ 测试文件 {test_pdf} 不存在")
        print("请将测试PDF文件命名为 'test.pdf' 并放在当前目录")
        return False
    
    print(f"✅ 找到测试文件: {test_pdf}")
    
    # 检查API配置
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("⚠️ 警告: 未配置API密钥，HTML解析和论文总结步骤将跳过")
        print("请设置 MODELSCOPE_SDK_TOKEN 或 DASHSCOPE_API_KEY 环境变量")
        api_configured = False
    else:
        print(f"✅ API密钥已配置 (长度: {len(api_key)})")
        api_configured = True
    
    try:
        # 创建日志器和工作流
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger = WorkflowLogger(f"test_workflow_{timestamp}.log")
        workflow = PDFAnalysisWorkflow(logger)
        
        print(f"\n📁 工作目录: {workflow.create_temp_directory()}")
        
        # 步骤1: 边界框提取
        print("\n" + "="*50)
        print("测试步骤1: PDF边界框提取")
        print("="*50)
        
        bbox_result = workflow.step1_extract_bboxes(test_pdf)
        if bbox_result['status'] != 'success':
            print(f"❌ 步骤1失败: {bbox_result['message']}")
            return False
        
        print("✅ 步骤1成功: PDF边界框提取完成")
        print(f"📊 统计: {bbox_result['statistics']}")
        
        # 步骤2: 布局分析和切片
        print("\n" + "="*50)
        print("测试步骤2: 布局分析和切片")
        print("="*50)
        
        metadata_path = bbox_result['metadata_path']
        slice_result = workflow.step2_analyze_layout_and_slice(test_pdf, metadata_path)
        if slice_result['status'] != 'success':
            print(f"❌ 步骤2失败: {slice_result['message']}")
            return False
        
        print("✅ 步骤2成功: 布局分析和切片完成")
        if 'results' in slice_result and 'slice_summary' in slice_result['results']:
            summary = slice_result['results']['slice_summary']
            print(f"📊 切片统计: 总={summary['total_slices']}, 丢弃={summary['total_discarded']}, 不规则={summary['total_irregular']}")
        
        # 获取切片目录
        slice_output_dir = slice_result['results']['output_directory']
        pdf_filename = os.path.splitext(os.path.basename(test_pdf))[0]
        
        if not api_configured:
            print("\n⚠️ 跳过HTML解析和后续步骤（需要API配置）")
            print(f"✅ 前两个步骤测试成功！")
            print(f"📁 切片输出目录: {slice_output_dir}")
            return True
        
        # 步骤3: HTML解析
        print("\n" + "="*50)
        print("测试步骤3: HTML解析")
        print("="*50)
        
        html_result = workflow.step3_parse_slices_to_html(slice_output_dir, pdf_filename)
        if html_result['status'] != 'success':
            print(f"❌ 步骤3失败: {html_result['message']}")
            return False
        
        print("✅ 步骤3成功: HTML解析完成")
        print(f"📊 解析了 {html_result['slice_count']} 个切片")
        
        # 步骤4: Markdown转换
        print("\n" + "="*50)
        print("测试步骤4: Markdown转换")
        print("="*50)
        
        html_dir = os.path.join(workflow.temp_dir, f"{pdf_filename}_slices_html")
        markdown_result = workflow.step4_convert_html_to_markdown(html_dir, pdf_filename)
        if markdown_result['status'] != 'success':
            print(f"❌ 步骤4失败: {markdown_result['message']}")
            return False
        
        print("✅ 步骤4成功: Markdown转换完成")
        print(f"📊 文档统计: {markdown_result['statistics']}")
        
        # 步骤5: 论文总结
        print("\n" + "="*50)
        print("测试步骤5: 论文总结")
        print("="*50)
        
        clean_markdown_file = markdown_result['clean_merged_file']
        summary_result = workflow.step5_summarize_paper(clean_markdown_file)
        if summary_result['status'] != 'success':
            print(f"❌ 步骤5失败: {summary_result['message']}")
            return False
        
        print("✅ 步骤5成功: 论文总结完成")
        print(f"📝 总结长度: {len(summary_result['summary'])} 字符")
        
        # 测试问答功能
        print("\n" + "="*50)
        print("测试问答功能")
        print("="*50)
        
        test_question = "这篇论文的主要贡献是什么？"
        answer = workflow.answer_question(
            question=test_question,
            markdown_content=summary_result['markdown_content']
        )
        
        print(f"✅ 问答测试成功")
        print(f"❓ 测试问题: {test_question}")
        print(f"💬 回答长度: {len(answer)} 字符")
        
        # 所有测试通过
        print("\n" + "="*70)
        print("🎉 所有测试步骤完成！工作流运行正常")
        print("="*70)
        print(f"📁 工作目录: {workflow.temp_dir}")
        print(f"📄 日志文件: logs/{logger.log_file}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {str(e)}")
        return False


def check_dependencies():
    """检查依赖项"""
    print("🔍 检查依赖项...")
    
    required_modules = [
        'streamlit',
        'fitz',  # PyMuPDF
        'PIL',   # Pillow
        'bs4',   # BeautifulSoup4
        'openai'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module}")
    
    if missing_modules:
        print(f"\n⚠️ 缺少以下依赖项: {', '.join(missing_modules)}")
        print("请运行: pip install -r requirements.txt")
        return False
    else:
        print("✅ 所有依赖项已安装")
        return True


def main():
    """主函数"""
    print("PDF分析工作流测试脚本")
    print("="*70)
    
    # 检查依赖项
    if not check_dependencies():
        return
    
    print()
    
    # 运行工作流测试
    success = test_workflow()
    
    if success:
        print("\n🚀 测试完成！您可以运行以下命令启动Streamlit应用:")
        print("streamlit run app.py")
    else:
        print("\n❌ 测试失败，请检查错误信息并修复问题")


if __name__ == "__main__":
    main() 