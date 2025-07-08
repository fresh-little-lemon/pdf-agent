#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup, Tag
import json


class BboxLayoutAnalyzer:
    """基于bbox坐标的布局分析器"""
    
    def __init__(self, column_threshold: float = 50.0):
        """
        初始化布局分析器
        
        Args:
            column_threshold: 判断双栏的阈值，x坐标差异小于此值认为是同一栏
        """
        self.column_threshold = column_threshold
    
    def parse_bbox(self, bbox_str: str) -> Optional[Tuple[float, float, float, float]]:
        """
        解析bbox字符串为坐标
        
        Args:
            bbox_str: bbox字符串，格式为 "x1,y1,x2,y2" 或 "x1 y1 x2 y2"
            
        Returns:
            (x1, y1, x2, y2) 坐标元组，失败返回None
        """
        try:
            # 清理字符串并分割
            coords = re.findall(r'[\d.]+', bbox_str.strip())
            if len(coords) >= 4:
                x1, y1, x2, y2 = map(float, coords[:4])
                return (x1, y1, x2, y2)
            return None
        except (ValueError, TypeError):
            return None
    
    def extract_elements_with_bbox(self, html_content: str) -> List[Dict[str, Any]]:
        """
        提取HTML中所有带bbox的元素
        
        Args:
            html_content: HTML内容
            
        Returns:
            包含元素信息的列表
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = []
        
        # 查找所有带data-bbox属性的元素
        for element in soup.find_all(attrs={'data-bbox': True}):
            bbox_str = element.get('data-bbox', '')
            bbox = self.parse_bbox(bbox_str)
            
            if bbox:
                elements.append({
                    'element': element,
                    'bbox': bbox,
                    'bbox_str': bbox_str,
                    'tag_name': element.name,
                    'text': element.get_text().strip()[:100],  # 限制文本长度
                    'original_index': len(elements)
                })
        
        return elements
    
    def detect_column_layout(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检测元素的分栏布局
        
        Args:
            elements: 元素列表
            
        Returns:
            布局检测结果
        """
        if not elements:
            return {
                'is_multi_column': False,
                'column_count': 1,
                'columns': [],
                'confidence': 0.0
            }
        
        # 按y坐标分组，找到可能的行
        rows = {}
        for elem in elements:
            x1, y1, x2, y2 = elem['bbox']
            # 使用y1作为行的标识，允许一定的误差
            row_key = round(y1 / 10) * 10  # 10像素精度
            if row_key not in rows:
                rows[row_key] = []
            rows[row_key].append(elem)
        
        # 分析每行的x坐标分布
        x_positions = []
        for row_elements in rows.values():
            if len(row_elements) >= 2:  # 至少需要2个元素才能判断分栏
                x_starts = [elem['bbox'][0] for elem in row_elements]
                x_starts.sort()
                x_positions.extend(x_starts)
        
        if not x_positions:
            return {
                'is_multi_column': False,
                'column_count': 1,
                'columns': [],
                'confidence': 0.0
            }
        
        # 聚类x坐标，找到不同的栏
        x_positions.sort()
        columns = []
        current_column = [x_positions[0]]
        
        for x in x_positions[1:]:
            if abs(x - current_column[-1]) <= self.column_threshold:
                current_column.append(x)
            else:
                columns.append(current_column)
                current_column = [x]
        
        if current_column:
            columns.append(current_column)
        
        # 计算每栏的平均x坐标
        column_centers = []
        for column in columns:
            center = sum(column) / len(column)
            column_centers.append(center)
        
        # 判断是否为多栏布局
        is_multi_column = len(column_centers) >= 2
        confidence = len([col for col in columns if len(col) >= 2]) / len(columns) if columns else 0.0
        
        return {
            'is_multi_column': is_multi_column,
            'column_count': len(column_centers),
            'columns': column_centers,
            'confidence': confidence
        }
    
    def sort_elements_reading_order(self, elements: List[Dict[str, Any]], 
                                   layout_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        按照阅读顺序排序元素（从上到下，从左到右）
        
        Args:
            elements: 元素列表
            layout_info: 布局信息
            
        Returns:
            排序后的元素列表
        """
        if not elements:
            return elements
        
        if not layout_info['is_multi_column']:
            # 单栏布局：简单按y坐标排序
            return sorted(elements, key=lambda elem: (elem['bbox'][1], elem['bbox'][0]))
        
        # 多栏布局：更复杂的排序逻辑
        columns = layout_info['columns']
        
        # 为每个元素分配栏位
        for elem in elements:
            x1, y1, x2, y2 = elem['bbox']
            # 找到最接近的栏
            distances = [abs(x1 - col_center) for col_center in columns]
            elem['column_index'] = distances.index(min(distances))
        
        # 按行分组
        row_groups = {}
        for elem in elements:
            y1 = elem['bbox'][1]
            # 使用较粗的粒度分组行
            row_key = round(y1 / 20) * 20  # 20像素精度
            if row_key not in row_groups:
                row_groups[row_key] = []
            row_groups[row_key].append(elem)
        
        # 排序逻辑
        sorted_elements = []
        
        # 按行排序
        for row_y in sorted(row_groups.keys()):
            row_elements = row_groups[row_y]
            
            # 检查这一行是否跨多栏
            columns_in_row = set(elem['column_index'] for elem in row_elements)
            
            if len(columns_in_row) == 1:
                # 单栏行：按x坐标排序
                row_elements.sort(key=lambda elem: elem['bbox'][0])
                sorted_elements.extend(row_elements)
            else:
                # 多栏行：按栏位和x坐标排序
                row_elements.sort(key=lambda elem: (elem['column_index'], elem['bbox'][0]))
                sorted_elements.extend(row_elements)
        
        return sorted_elements


class HtmlLayoutReorder:
    """HTML布局重排序工具"""
    
    def __init__(self, column_threshold: float = 50.0):
        """
        初始化重排序工具
        
        Args:
            column_threshold: 双栏检测阈值
        """
        self.analyzer = BboxLayoutAnalyzer(column_threshold)
    
    def backup_html_files(self, html_dir: str) -> str:
        """
        备份HTML文件到origin目录
        
        Args:
            html_dir: HTML目录路径
            
        Returns:
            备份目录路径
        """
        origin_dir = html_dir + "_origin"
        
        # 如果备份目录已存在，先删除
        if os.path.exists(origin_dir):
            shutil.rmtree(origin_dir)
        
        # 复制整个目录
        shutil.copytree(html_dir, origin_dir)
        
        return origin_dir
    
    def reorder_html_file(self, html_file_path: str) -> Dict[str, Any]:
        """
        重排序单个HTML文件
        
        Args:
            html_file_path: HTML文件路径
            
        Returns:
            处理结果
        """
        try:
            # 读取HTML文件
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取带bbox的元素
            elements = self.analyzer.extract_elements_with_bbox(html_content)
            
            if not elements:
                return {
                    'status': 'skipped',
                    'message': '未找到带bbox的元素',
                    'layout_info': None,
                    'reordered': False
                }
            
            # 检测布局
            layout_info = self.analyzer.detect_column_layout(elements)
            
            if not layout_info['is_multi_column']:
                return {
                    'status': 'skipped',
                    'message': '检测到单栏布局，无需重排序',
                    'layout_info': layout_info,
                    'reordered': False
                }
            
            # 排序元素
            sorted_elements = self.analyzer.sort_elements_reading_order(elements, layout_info)
            
            # 重建HTML结构
            # 获取所有元素的父容器
            root_container = soup.find('body') or soup
            
            # 移除原有的带bbox元素
            for elem_info in elements:
                elem_info['element'].extract()
            
            # 按新顺序添加元素
            for elem_info in sorted_elements:
                root_container.append(elem_info['element'])
            
            # 保存重排序后的HTML
            with open(html_file_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            return {
                'status': 'success',
                'message': f'成功重排序 {len(sorted_elements)} 个元素',
                'layout_info': layout_info,
                'reordered': True,
                'element_count': len(sorted_elements)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'处理文件时出错: {str(e)}',
                'layout_info': None,
                'reordered': False
            }
    
    def process_html_directory(self, pdf_filename: str, base_dir: str = "tmp") -> Dict[str, Any]:
        """
        处理整个HTML目录
        
        Args:
            pdf_filename: PDF文件名（不含扩展名）
            base_dir: 基础目录
            
        Returns:
            处理结果
        """
        html_dir = os.path.join(base_dir, f"{pdf_filename}_html")
        
        if not os.path.exists(html_dir):
            return {
                'status': 'error',
                'message': f'HTML目录不存在: {html_dir}',
                'processed_files': [],
                'skipped_files': [],
                'error_files': [],
                'layout_analysis': {}
            }
        
        # 获取所有HTML文件
        html_files = [f for f in os.listdir(html_dir) 
                     if f.endswith('.html') and f.startswith('page_')]
        
        if not html_files:
            return {
                'status': 'error',
                'message': f'未找到HTML文件: {html_dir}',
                'processed_files': [],
                'skipped_files': [],
                'error_files': [],
                'layout_analysis': {}
            }
        
        # 先检测是否需要重排序（检查第一个文件的布局）
        first_file = os.path.join(html_dir, html_files[0])
        
        with open(first_file, 'r', encoding='utf-8') as f:
            sample_content = f.read()
        
        sample_elements = self.analyzer.extract_elements_with_bbox(sample_content)
        sample_layout = self.analyzer.detect_column_layout(sample_elements)
        
        if not sample_layout['is_multi_column']:
            return {
                'status': 'skipped',
                'message': '检测到单栏布局，无需重排序',
                'processed_files': [],
                'skipped_files': html_files,
                'error_files': [],
                'layout_analysis': sample_layout
            }
        
        # 备份文件
        try:
            backup_dir = self.backup_html_files(html_dir)
            print(f"✅ 已备份文件到: {backup_dir}")
        except Exception as e:
            return {
                'status': 'error',
                'message': f'备份文件失败: {str(e)}',
                'processed_files': [],
                'skipped_files': [],
                'error_files': [],
                'layout_analysis': {}
            }
        
        # 处理每个文件
        results = {
            'status': 'success',
            'message': '',
            'processed_files': [],
            'skipped_files': [],
            'error_files': [],
            'layout_analysis': sample_layout
        }
        
        for html_file in sorted(html_files):
            html_file_path = os.path.join(html_dir, html_file)
            file_result = self.reorder_html_file(html_file_path)
            
            if file_result['status'] == 'success' and file_result['reordered']:
                results['processed_files'].append(html_file)
            elif file_result['status'] == 'skipped':
                results['skipped_files'].append(html_file)
            else:
                results['error_files'].append(html_file)
            
            print(f"📄 {html_file}: {file_result['message']}")
        
        # 生成总结信息
        total_files = len(html_files)
        processed_count = len(results['processed_files'])
        skipped_count = len(results['skipped_files'])
        error_count = len(results['error_files'])
        
        results['message'] = (
            f"处理完成! 总文件数: {total_files}, "
            f"重排序: {processed_count}, "
            f"跳过: {skipped_count}, "
            f"错误: {error_count}"
        )
        
        return results


def create_layout_reorder_tool(column_threshold: float = 50.0) -> HtmlLayoutReorder:
    """
    创建布局重排序工具实例
    
    Args:
        column_threshold: 双栏检测阈值
        
    Returns:
        布局重排序工具实例
    """
    return HtmlLayoutReorder(column_threshold)


if __name__ == "__main__":
    # 测试代码
    tool = create_layout_reorder_tool()
    
    # 示例：处理v9的HTML文件
    result = tool.process_html_directory("v9", "tmp")
    
    print("\n📊 处理结果:")
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    
    if result['layout_analysis']:
        layout = result['layout_analysis']
        print(f"布局分析: {layout['column_count']}栏布局, 置信度: {layout['confidence']:.2f}")
    
    if result['processed_files']:
        print(f"重排序文件: {result['processed_files']}")
    
    if result['error_files']:
        print(f"错误文件: {result['error_files']}") 