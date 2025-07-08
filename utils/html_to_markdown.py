 #!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional


def convert_table_to_markdown(table_element) -> List[str]:
    """
    将HTML表格转换为Markdown表格格式，正确处理rowspan和colspan
    
    Args:
        table_element: BeautifulSoup表格元素
        
    Returns:
        Markdown表格行列表
    """
    try:
        markdown_lines = []
        
        # 查找所有行
        rows = table_element.find_all('tr')
        if not rows:
            return ["<!-- 表格为空 -->"]
        
        # 第一步：构建完整的表格矩阵
        table_matrix = []
        max_cols = 0
        
        # 遍历所有行，构建表格矩阵
        for row_idx, row in enumerate(rows):
            # 初始化当前行
            if len(table_matrix) <= row_idx:
                table_matrix.append([])
            
            # 获取所有单元格
            cells = row.find_all(['td', 'th'])
            col_idx = 0
            
            for cell in cells:
                # 找到下一个空位置
                while col_idx < len(table_matrix[row_idx]) and table_matrix[row_idx][col_idx] is not None:
                    col_idx += 1
                
                # 扩展当前行到足够长度
                while len(table_matrix[row_idx]) <= col_idx:
                    table_matrix[row_idx].append(None)
                
                cell_text = cell.get_text().strip()
                colspan = int(cell.get('colspan', 1))
                rowspan = int(cell.get('rowspan', 1))
                
                # 填充所有被这个单元格占据的位置
                for r in range(row_idx, row_idx + rowspan):
                    # 确保有足够的行
                    while len(table_matrix) <= r:
                        table_matrix.append([])
                    
                    for c in range(col_idx, col_idx + colspan):
                        # 确保当前行有足够的列
                        while len(table_matrix[r]) <= c:
                            table_matrix[r].append(None)
                        
                        # 填充单元格内容（对于跨行跨列的单元格，所有位置都填充相同内容）
                        table_matrix[r][c] = cell_text
                
                # 移动到下一个单元格位置
                col_idx += colspan
                max_cols = max(max_cols, col_idx)
        
        # 确保所有行都有相同的列数
        for row in table_matrix:
            while len(row) < max_cols:
                row.append("")
        
        # 第二步：生成markdown表格
        for row_idx, row_data in enumerate(table_matrix):
            # 添加行bbox注释（如果可获取）
            if row_idx < len(rows):
                row_bbox = rows[row_idx].get('data-bbox', '')
                if row_bbox:
                    markdown_lines.append(f"<!-- TABLE ROW bbox: {row_bbox} -->")
            
            # 构建markdown表格行
            markdown_row = "| " + " | ".join(str(cell) if cell is not None else "" for cell in row_data) + " |"
            markdown_lines.append(markdown_row)
            
            # 如果这是第一行，添加分隔符
            if row_idx == 0:
                separator = "| " + " | ".join(["---"] * len(row_data)) + " |"
                markdown_lines.append(separator)
        
        return markdown_lines
        
    except Exception as e:
        return [f"<!-- 表格转换错误: {str(e)} -->"]


def convert_list_to_markdown(list_element) -> List[str]:
    """
    将HTML列表转换为Markdown列表格式
    
    Args:
        list_element: BeautifulSoup列表元素
        
    Returns:
        Markdown列表行列表
    """
    try:
        markdown_lines = []
        
        # 获取列表项
        list_items = list_element.find_all('li', recursive=False)
        if not list_items:
            return ["<!-- 列表为空 -->"]
        
        # 确定列表类型
        is_ordered = list_element.name == 'ol'
        start_num = int(list_element.get('start', 1))
        
        for idx, item in enumerate(list_items):
            item_bbox = item.get('data-bbox', '')
            if item_bbox:
                markdown_lines.append(f"<!-- LIST ITEM bbox: {item_bbox} -->")
            
            # 获取列表项内容
            item_text = item.get_text().strip()
            
            # 构建列表项标记
            if is_ordered:
                marker = f"{start_num + idx}. "
            else:
                marker = "- "
            
            # 处理多行内容
            if '\n' in item_text:
                lines = item_text.split('\n')
                markdown_lines.append(f"{marker}{lines[0].strip()}")
                for line in lines[1:]:
                    if line.strip():
                        markdown_lines.append(f"   {line.strip()}")
            else:
                markdown_lines.append(f"{marker}{item_text}")
        
        return markdown_lines
        
    except Exception as e:
        return [f"<!-- 列表转换错误: {str(e)} -->"]


def clean_markdown_content(markdown_content: str) -> str:
    """
    清理markdown内容，删除所有注释和元数据，只保留纯文档内容
    
    Args:
        markdown_content: 原始markdown内容
        
    Returns:
        清理后的markdown内容
    """
    lines = markdown_content.split('\n')
    clean_lines = []
    
    for line in lines:
        # 跳过HTML注释行
        if line.strip().startswith('<!--') and line.strip().endswith('-->'):
            continue
        
        # 跳过页面分隔符
        if line.strip() == '---' and len(clean_lines) > 0 and clean_lines[-1].strip().startswith('<!-- PAGE'):
            continue
            
        # 跳过空行（但保留段落间的单个空行）
        if line.strip() == '':
            # 如果上一行不是空行，则保留这个空行
            if clean_lines and clean_lines[-1].strip() != '':
                clean_lines.append('')
            continue
            
        clean_lines.append(line)
    
    # 移除开头和结尾的多余空行
    while clean_lines and clean_lines[0].strip() == '':
        clean_lines.pop(0)
    while clean_lines and clean_lines[-1].strip() == '':
        clean_lines.pop()
    
    return '\n'.join(clean_lines)


def parse_html_to_markdown(html_content: str, page_num: int) -> str:
    """
    将HTML内容转换为Markdown格式
    
    Args:
        html_content: HTML内容字符串
        page_num: 页码
        
    Returns:
        转换后的Markdown内容
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    markdown_lines = []
    
    # 添加页码分隔符
    markdown_lines.append(f"<!-- PAGE {page_num} START -->")
    markdown_lines.append(f"---")
    markdown_lines.append(f"<!-- Page {page_num} -->")
    markdown_lines.append("")
    
    # 遍历所有元素，跳过表格和列表内部的元素
    processed_elements = set()
    
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'address', 'img', 'table', 'ol', 'ul']):
        # 跳过已处理的元素
        if element in processed_elements:
            continue
        
        # 如果元素在表格或列表内部，跳过
        if element.find_parent(['table', 'ol', 'ul']) and element.name not in ['table', 'ol', 'ul']:
            continue
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            # 处理标题
            level = int(element.name[1])
            title_text = element.get_text().strip()
            bbox = element.get('data-bbox', '')
            
            # 添加标题的bbox信息作为注释
            if bbox:
                markdown_lines.append(f"<!-- {element.name.upper()} bbox: {bbox} -->")
            
            markdown_lines.append(f"{'#' * level} {title_text}")
            markdown_lines.append("")
            
        elif element.name == 'p':
            # 处理段落
            text = element.get_text().strip()
            if text:  # 只处理非空段落
                bbox = element.get('data-bbox', '')
                parent_class = element.parent.get('class', []) if element.parent else []
                
                # 添加段落的bbox信息作为注释
                if bbox:
                    markdown_lines.append(f"<!-- PARAGRAPH bbox: {bbox} -->")
                
                # 检查是否为特殊类型的段落
                if element.parent and element.parent.name == 'address':
                    markdown_lines.append(f"*{text}*")
                else:
                    markdown_lines.append(text)
                
                markdown_lines.append("")
        
        elif element.name == 'div':
            # 处理div元素，特别是公式和特殊区块
            class_names = element.get('class', [])
            bbox = element.get('data-bbox', '')
            
            if 'formula' in class_names:
                # 处理公式
                formula_text = element.find('div')
                
                if bbox:
                    markdown_lines.append(f"<!-- FORMULA bbox: {bbox} -->")
                
                if formula_text:
                    # 提取LaTeX公式，直接显示为行间公式
                    latex_content = formula_text.get_text().strip()
                    markdown_lines.append(latex_content)
                else:
                    # 如果没有公式文本，标记为公式占位符
                    markdown_lines.append("<!-- Formula placeholder -->")
                
                markdown_lines.append("")
            
            elif 'abstract' in class_names:
                # 处理摘要区块
                abstract_text = element.get_text().strip()
                if bbox:
                    markdown_lines.append(f"<!-- ABSTRACT BLOCK bbox: {bbox} -->")
                markdown_lines.append(f"## Abstract")
                markdown_lines.append(abstract_text)
                
                # 标记摘要内部的所有元素为已处理
                for inner_element in element.find_all():
                    processed_elements.add(inner_element)
                
                markdown_lines.append("")
        
        elif element.name == 'img':
            # 处理图片，但跳过公式内的img元素
            parent_div = element.find_parent('div')
            if parent_div and 'formula' in parent_div.get('class', []):
                # 跳过公式内的img元素
                continue
            
            bbox = element.get('data-bbox', '')
            alt_text = element.get('alt', 'Image')
            src = element.get('src', '')
            
            if bbox:
                markdown_lines.append(f"<!-- IMAGE bbox: {bbox} -->")
            
            if src:
                markdown_lines.append(f"![{alt_text}]({src})")
            else:
                markdown_lines.append(f"![{alt_text}](image_placeholder)")
            
            markdown_lines.append("")
            
        elif element.name == 'table':
            # 处理表格
            bbox = element.get('data-bbox', '')
            class_names = element.get('class', [])
            
            if bbox:
                markdown_lines.append(f"<!-- TABLE bbox: {bbox} -->")
            if class_names:
                markdown_lines.append(f"<!-- TABLE class: {' '.join(class_names)} -->")
            
            # 转换表格为markdown格式
            table_markdown = convert_table_to_markdown(element)
            if table_markdown:
                markdown_lines.extend(table_markdown)
            
            # 标记表格内部的所有元素为已处理
            for inner_element in element.find_all():
                processed_elements.add(inner_element)
            
            markdown_lines.append("")
            
        elif element.name in ['ol', 'ul']:
            # 处理列表
            bbox = element.get('data-bbox', '')
            start_value = element.get('start', '')
            
            if bbox:
                markdown_lines.append(f"<!-- LIST {element.name.upper()} bbox: {bbox} -->")
            if start_value:
                markdown_lines.append(f"<!-- LIST start: {start_value} -->")
            
            # 转换列表为markdown格式
            list_markdown = convert_list_to_markdown(element)
            if list_markdown:
                markdown_lines.extend(list_markdown)
            
            # 标记列表内部的所有元素为已处理
            for inner_element in element.find_all():
                processed_elements.add(inner_element)
            
            markdown_lines.append("")
    
    # 添加页码结束标记
    markdown_lines.append(f"<!-- PAGE {page_num} END -->")
    markdown_lines.append("")
    
    return '\n'.join(markdown_lines)


def extract_metadata_from_html(html_content: str, page_num: int) -> Dict[str, Any]:
    """
    从HTML内容中提取元数据信息
    
    Args:
        html_content: HTML内容字符串
        page_num: 页码
        
    Returns:
        包含元数据的字典
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    metadata = {
        'page_number': page_num,
        'elements': [],
        'statistics': {
            'total_elements': 0,
            'headings': 0,
            'paragraphs': 0,
            'formulas': 0,
            'images': 0,
            'tables': 0,
            'lists': 0
        }
    }
    
    # 遍历所有元素并提取信息
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'img', 'table', 'ol', 'ul']):
        element_info = {
            'type': element.name,
            'bbox': element.get('data-bbox', ''),
            'text': element.get_text().strip()[:200] if element.get_text() else '',  # 限制长度
            'class': element.get('class', []),
            'parent_class': element.parent.get('class', []) if element.parent else []
        }
        
        metadata['elements'].append(element_info)
        metadata['statistics']['total_elements'] += 1
        
        # 统计不同类型的元素
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            metadata['statistics']['headings'] += 1
        elif element.name == 'p':
            metadata['statistics']['paragraphs'] += 1
        elif element.name == 'div' and 'formula' in element.get('class', []):
            metadata['statistics']['formulas'] += 1
        elif element.name == 'img':
            metadata['statistics']['images'] += 1
        elif element.name == 'table':
            metadata['statistics']['tables'] += 1
        elif element.name in ['ol', 'ul']:
            metadata['statistics']['lists'] += 1
    
    return metadata


def convert_html_files_to_markdown(html_dir: str, pdf_filename: str, output_dir: str = "tmp") -> Dict[str, Any]:
    """
    将HTML文件夹中的所有HTML文件转换为Markdown格式
    
    Args:
        html_dir: HTML文件所在目录
        pdf_filename: PDF文件名（不含扩展名）
        output_dir: 输出目录
        
    Returns:
        包含转换结果的字典
    """
    try:
        # 创建输出目录
        markdown_dir = os.path.join(output_dir, f"{pdf_filename}_markdown")
        os.makedirs(markdown_dir, exist_ok=True)
        
        # 获取所有HTML文件
        html_files = []
        for file in os.listdir(html_dir):
            if file.endswith('.html') and file.startswith('page_'):
                html_files.append(file)
        
        # 按页码排序
        html_files.sort(key=lambda x: int(re.search(r'page_(\d+)', x).group(1)))
        
        # 存储转换结果
        results = {
            'status': 'success',
            'message': '',
            'markdown_files': [],
            'clean_markdown_files': [],
            'merged_file': '',
            'clean_merged_file': '',
            'metadata': [],
            'statistics': {
                'total_pages': 0,
                'total_elements': 0,
                'total_headings': 0,
                'total_paragraphs': 0,
                'total_formulas': 0,
                'total_images': 0,
                'total_tables': 0,
                'total_lists': 0
            }
        }
        
        # 合并的markdown内容
        merged_content = []
        merged_content.append(f"# {pdf_filename} - Complete Document")
        merged_content.append("")
        merged_content.append(f"<!-- Generated from {len(html_files)} HTML pages -->")
        merged_content.append("")
        
        # 干净版本的合并内容
        clean_merged_content = []
        clean_merged_content.append(f"# {pdf_filename}")
        clean_merged_content.append("")
        
        # 处理每个HTML文件
        for html_file in html_files:
            html_path = os.path.join(html_dir, html_file)
            
            # 提取页码
            page_match = re.search(r'page_(\d+)', html_file)
            if not page_match:
                continue
                
            page_num = int(page_match.group(1))
            
            # 读取HTML内容
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 转换为Markdown
            markdown_content = parse_html_to_markdown(html_content, page_num)
            
            # 保存单独的页面markdown文件（完整版本）
            page_markdown_file = os.path.join(markdown_dir, f"page_{page_num}.md")
            with open(page_markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            results['markdown_files'].append(page_markdown_file)
            
            # 生成干净版本的markdown内容
            clean_markdown_content_text = clean_markdown_content(markdown_content)
            
            # 保存单独的页面markdown文件（干净版本）
            clean_page_markdown_file = os.path.join(markdown_dir, f"page_{page_num}_clean.md")
            with open(clean_page_markdown_file, 'w', encoding='utf-8') as f:
                f.write(clean_markdown_content_text)
            
            results['clean_markdown_files'].append(clean_page_markdown_file)
            
            # 添加到合并内容中
            merged_content.append(markdown_content)
            
            # 添加到干净版本合并内容中
            if clean_markdown_content_text.strip():  # 只添加非空内容
                clean_merged_content.append(clean_markdown_content_text)
            
            # 提取元数据
            metadata = extract_metadata_from_html(html_content, page_num)
            results['metadata'].append(metadata)
            
            # 更新统计信息
            results['statistics']['total_pages'] += 1
            results['statistics']['total_elements'] += metadata['statistics']['total_elements']
            results['statistics']['total_headings'] += metadata['statistics']['headings']
            results['statistics']['total_paragraphs'] += metadata['statistics']['paragraphs']
            results['statistics']['total_formulas'] += metadata['statistics']['formulas']
            results['statistics']['total_images'] += metadata['statistics']['images']
            results['statistics']['total_tables'] += metadata['statistics']['tables']
            results['statistics']['total_lists'] += metadata['statistics']['lists']
        
        # 保存合并的markdown文件（完整版本）
        merged_file = os.path.join(markdown_dir, f"{pdf_filename}_complete.md")
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(merged_content))
        
        results['merged_file'] = merged_file
        
        # 保存合并的markdown文件（干净版本）
        clean_merged_file = os.path.join(markdown_dir, f"{pdf_filename}_clean.md")
        with open(clean_merged_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(clean_merged_content))
        
        results['clean_merged_file'] = clean_merged_file
        
        # 保存元数据文件
        metadata_file = os.path.join(markdown_dir, f"{pdf_filename}_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(results['metadata'], f, indent=2, ensure_ascii=False)
        
        results['message'] = f"成功转换 {len(html_files)} 个HTML文件为Markdown格式（包含完整版和干净版）"
        
        return results
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'markdown_files': [],
            'clean_markdown_files': [],
            'merged_file': '',
            'clean_merged_file': '',
            'metadata': [],
            'statistics': {}
        }


def get_markdown_preview(markdown_file: str, max_lines: int = 50) -> str:
    """
    获取Markdown文件的预览内容
    
    Args:
        markdown_file: Markdown文件路径
        max_lines: 最大预览行数
        
    Returns:
        预览内容字符串
    """
    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) <= max_lines:
            return ''.join(lines)
        else:
            preview_lines = lines[:max_lines]
            preview_lines.append(f"\n... (还有 {len(lines) - max_lines} 行内容)")
            return ''.join(preview_lines)
            
    except Exception as e:
        return f"无法读取文件: {str(e)}"


def clean_markdown_files(output_dir: str, pdf_filename: str):
    """
    清理生成的Markdown文件
    
    Args:
        output_dir: 输出目录
        pdf_filename: PDF文件名
    """
    try:
        markdown_dir = os.path.join(output_dir, f"{pdf_filename}_markdown")
        if os.path.exists(markdown_dir):
            import shutil
            shutil.rmtree(markdown_dir)
            return True
    except Exception as e:
        print(f"清理文件时出错: {str(e)}")
        return False


def validate_html_directory(html_dir: str) -> Dict[str, Any]:
    """
    验证HTML目录是否有效
    
    Args:
        html_dir: HTML目录路径
        
    Returns:
        验证结果字典
    """
    try:
        if not os.path.exists(html_dir):
            return {
                'valid': False,
                'message': f"目录不存在: {html_dir}",
                'html_files': []
            }
        
        # 获取HTML文件
        html_files = []
        for file in os.listdir(html_dir):
            if file.endswith('.html') and file.startswith('page_'):
                html_files.append(file)
        
        if not html_files:
            return {
                'valid': False,
                'message': f"目录中没有找到page_*.html文件: {html_dir}",
                'html_files': []
            }
        
        # 按页码排序
        html_files.sort(key=lambda x: int(re.search(r'page_(\d+)', x).group(1)))
        
        return {
            'valid': True,
            'message': f"找到 {len(html_files)} 个HTML文件",
            'html_files': html_files
        }
        
    except Exception as e:
        return {
            'valid': False,
            'message': f"验证目录时出错: {str(e)}",
            'html_files': []
        }


if __name__ == "__main__":
    # 测试代码
    html_dir = "tmp/v9_html"
    pdf_filename = "v9"
    
    # 验证目录
    validation = validate_html_directory(html_dir)
    print(f"目录验证结果: {validation}")
    
    if validation['valid']:
        # 转换HTML文件
        results = convert_html_files_to_markdown(html_dir, pdf_filename)
        print(f"转换结果: {results['message']}")
        
        if results['status'] == 'success':
            print(f"生成的文件数量: {len(results['markdown_files'])}")
            print(f"合并文件: {results['merged_file']}")
            print(f"统计信息: {results['statistics']}")