#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import math
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image
import fitz  # PyMuPDF


class LayoutAnalyzer:
    """论文布局分析器，用于分析单栏、双栏、多栏布局并进行图片切片（自动过滤PDF中预测框小于等于15px的切片）"""
    
    def __init__(self):
        """初始化布局分析器"""
        self.layout_types = {
            'single': '单栏',
            'double': '双栏', 
            'mixed': '混合布局'
        }
    
    def analyze_page_layout(self, page_elements: List[Dict[str, Any]], page_width: float, 
                          page_height: float, center_tolerance: float = 100.0) -> Dict[str, Any]:
        """
        分析页面布局类型
        
        Args:
            page_elements: 页面元素列表（包含bbox信息）
            page_width: 页面宽度
            page_height: 页面高度
            center_tolerance: 中轴线两侧的容忍范围（像素，用于双栏区域的切分）
            
        Returns:
            布局分析结果
            
        布局判断逻辑：
            1. 双栏布局：中轴线未穿过任何元素
            2. 单栏布局：水平扫描线未发现多栏行（相同高度的元素都跨越中轴线）
            3. 混合布局：水平扫描线发现多栏行（相同高度存在不跨越中轴线的元素）
               - 规则双栏区域：按中轴线左右切分
               - 不规则双栏区域：按每个元素的边框独立切片
        """
        # 计算页面中轴线
        center_x = page_width / 2.0
        
        # 过滤出文本、图像、表格元素
        content_elements = [
            elem for elem in page_elements 
            if elem.get('type') in ['text', 'image', 'table']
        ]
        
        if not content_elements:
            return {
                'layout_type': 'single',
                'layout_name': self.layout_types['single'],
                'center_line': center_x,
                'intersecting_elements': [],
                'regions': [{'type': 'single', 'bbox': [0, 0, page_width, page_height]}],
                'analysis_details': '页面无内容元素'
            }
        
        # 检查哪些元素与中轴线相交
        intersecting_elements = []
        for elem in content_elements:
            bbox = elem['bbox']
            x1, y1, x2, y2 = bbox
            
            # 检查元素是否与中轴线相交
            if x1 <= center_x <= x2:
                intersecting_elements.append({
                    'element': elem,
                    'intersection_type': 'crosses_center'
                })
        
        # 步骤1：如果没有元素与中轴线相交，直接判断为双栏
        if not intersecting_elements:
            return {
                'layout_type': 'double',
                'layout_name': self.layout_types['double'],
                'center_line': center_x,
                'intersecting_elements': [],
                'regions': [
                    {'type': 'left_column', 'bbox': [0, 0, center_x, page_height]},
                    {'type': 'right_column', 'bbox': [center_x, 0, page_width, page_height]}
                ],
                'analysis_details': f'中轴线({center_x:.1f})未穿过任何元素，判断为双栏布局'
            }
        
        # 步骤2：使用水平扫描线检查布局类型
        has_multi_column_row = self._check_multi_column_rows(content_elements, center_x)
        
        if has_multi_column_row:
            # 步骤3：混合布局分析 - 找到单栏和双栏区域的边界
            return self._analyze_mixed_layout(
                content_elements, page_width, page_height, center_x, 
                center_tolerance, intersecting_elements
            )
        else:
            # 单栏布局
            return {
                'layout_type': 'single',
                'layout_name': self.layout_types['single'],
                'center_line': center_x,
                'intersecting_elements': intersecting_elements,
                'regions': [{'type': 'single', 'bbox': [0, 0, page_width, page_height]}],
                'analysis_details': '水平扫描未发现多栏行，判断为单栏布局'
            }
    
    def _check_multi_column_rows(self, content_elements: List[Dict[str, Any]], center_x: float) -> bool:
        """
        使用水平扫描线检查是否存在多栏行
        
        Args:
            content_elements: 内容元素列表
            center_x: 中轴线x坐标
            
        Returns:
            是否存在多栏行
        """
        # 检查每个元素是否与其他元素在相同高度有重叠
        for i, elem1 in enumerate(content_elements):
            bbox1 = elem1['bbox']
            x1_1, y1_1, x2_1, y2_1 = bbox1
            
            # 查找与elem1在Y坐标上有重叠的其他元素
            overlapping_elements = []
            for j, elem2 in enumerate(content_elements):
                if i == j:
                    continue
                    
                bbox2 = elem2['bbox']
                x1_2, y1_2, x2_2, y2_2 = bbox2
                
                # 检查Y坐标是否有重叠（相同高度）
                if not (y2_1 < y1_2 or y2_2 < y1_1):  # 有重叠
                    overlapping_elements.append(elem2)
            
            if overlapping_elements:
                # 如果有重叠元素，检查它们是否都跨越中轴线
                all_elements = [elem1] + overlapping_elements
                
                # 检查是否所有元素都跨越中轴线
                all_cross_center = all(
                    elem['bbox'][0] <= center_x <= elem['bbox'][2] 
                    for elem in all_elements
                )
                
                # 如果不是所有元素都跨越中轴线，说明存在多栏行
                if not all_cross_center:
                    return True
        
        return False
    
    def _check_irregular_double_column(self, content_elements: List[Dict[str, Any]], 
                                     y_start: float, y_end: float, center_x: float) -> List[Dict]:
        """
        检查双栏区域内是否存在不规则排列（元素与中轴线相交）
        
        Args:
            content_elements: 内容元素列表
            y_start: 区域起始Y坐标
            y_end: 区域结束Y坐标
            center_x: 中轴线x坐标
            
        Returns:
            如果是不规则双栏，返回每个元素的独立切片区域列表；否则返回空列表
        """
        # 找到在该Y区域内的所有元素
        region_elements = []
        for elem in content_elements:
            bbox = elem['bbox']
            x1, y1, x2, y2 = bbox
            
            # 检查元素是否在当前Y区域内（有重叠）
            if not (y2 < y_start or y1 > y_end):
                region_elements.append(elem)
        
        if not region_elements:
            return []
        
        # 检查区域内是否有元素与中轴线相交
        has_intersecting_elements = False
        for elem in region_elements:
            bbox = elem['bbox']
            x1, y1, x2, y2 = bbox
            
            # 如果元素与中轴线相交，说明是不规则双栏
            if x1 <= center_x <= x2:
                has_intersecting_elements = True
                break
        
        if has_intersecting_elements:
            # 不规则双栏，为每个元素创建独立的切片区域
            irregular_regions = []
            for i, elem in enumerate(region_elements):
                bbox = elem['bbox']
                x1, y1, x2, y2 = bbox
                
                # 将元素的实际边框范围限制在当前Y区域内
                actual_y1 = max(y1, y_start)
                actual_y2 = min(y2, y_end)
                
                irregular_regions.append({
                    'type': 'irregular_element',
                    'bbox': [x1, actual_y1, x2, actual_y2],
                    'element_type': elem.get('type', 'unknown'),
                    'element_index': i
                })
            
            return irregular_regions
        
        return []
    
    def _analyze_mixed_layout(self, content_elements: List[Dict[str, Any]], 
                            page_width: float, page_height: float, center_x: float,
                            center_tolerance: float, intersecting_elements: List[Dict]) -> Dict[str, Any]:
        """
        分析混合布局（单栏+双栏）
        
        Args:
            content_elements: 内容元素列表
            page_width: 页面宽度
            page_height: 页面高度
            center_x: 中轴线x坐标
            center_tolerance: 中轴线容忍范围
            intersecting_elements: 与中轴线相交的元素
            
        Returns:
            混合布局分析结果
        """
        # 按Y坐标排序所有元素
        sorted_elements = sorted(content_elements, key=lambda x: x['bbox'][1])
        
        regions = []
        current_y = 0
        
        # 分析每个元素，确定其所属区域类型
        y_positions = []
        for elem in sorted_elements:
            bbox = elem['bbox']
            x1, y1, x2, y2 = bbox
            elem_center_x = (x1 + x2) / 2.0
            
            # 判断元素类型
            if x1 <= center_x <= x2:
                # 跨越中轴线的元素，属于单栏
                region_type = 'single'
            elif abs(elem_center_x - center_x) <= center_tolerance:
                # 在中轴线附近的元素，检查是否跨越中轴线
                if x1 <= center_x <= x2:
                    region_type = 'single'
                else:
                    region_type = 'double'
            else:
                # 明确在左侧或右侧的元素，属于双栏
                region_type = 'double'
            
            y_positions.append({
                'y1': y1,
                'y2': y2,
                'type': region_type,
                'element': elem
            })
        
        # 合并相邻的相同类型区域
        if y_positions:
            merged_regions = []
            current_region = {
                'type': y_positions[0]['type'],
                'y1': y_positions[0]['y1'],
                'y2': y_positions[0]['y2']
            }
            
            for pos in y_positions[1:]:
                if pos['type'] == current_region['type'] and pos['y1'] <= current_region['y2'] + 20:
                    # 相同类型且Y坐标相近，合并
                    current_region['y2'] = max(current_region['y2'], pos['y2'])
                else:
                    # 不同类型或Y坐标间隔较大，添加当前区域并开始新区域
                    merged_regions.append(current_region)
                    current_region = {
                        'type': pos['type'],
                        'y1': pos['y1'],
                        'y2': pos['y2']
                    }
            
            merged_regions.append(current_region)
            
            # 生成切片区域
            slice_regions = []
            for region in merged_regions:
                if region['type'] == 'single':
                    slice_regions.append({
                        'type': 'single',
                        'bbox': [0, region['y1'], page_width, region['y2']]
                    })
                else:
                    # 双栏区域，检查是否为不规则双栏
                    irregular_regions = self._check_irregular_double_column(
                        content_elements, region['y1'], region['y2'], center_x
                    )
                    
                    if irregular_regions:
                        # 不规则双栏，为每个元素创建独立的切片区域
                        for elem_region in irregular_regions:
                            slice_regions.append(elem_region)
                    else:
                        # 规则双栏，分成左右两部分
                        slice_regions.append({
                            'type': 'left_column',
                            'bbox': [0, region['y1'], center_x, region['y2']]
                        })
                        slice_regions.append({
                            'type': 'right_column',
                            'bbox': [center_x, region['y1'], page_width, region['y2']]
                        })
        else:
            slice_regions = [{'type': 'single', 'bbox': [0, 0, page_width, page_height]}]
        
        return {
            'layout_type': 'mixed',
            'layout_name': self.layout_types['mixed'],
            'center_line': center_x,
            'intersecting_elements': intersecting_elements,
            'regions': slice_regions,
            'analysis_details': f'检测到混合布局，共{len(slice_regions)}个区域'
        }
    
    def slice_pdf_images(self, pdf_path: str, bbox_metadata_path: str, 
                        output_dir: str = "tmp") -> Dict[str, Any]:
        """
        根据布局分析结果对PDF图片进行切片
        
        Args:
            pdf_path: PDF文件路径
            bbox_metadata_path: bbox元数据文件路径
            output_dir: 输出目录
            
        Returns:
            切片结果
            
        Note:
            - 切片图像固定为300dpi分辨率
            - PDF中预测框宽度或高度小于等于15px的切片将被自动丢弃
        """
        try:
            # 读取bbox元数据
            with open(bbox_metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 获取PDF文件名
            pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
            
            # 创建输出目录
            slice_output_dir = os.path.join(output_dir, f"{pdf_filename}_slice")
            os.makedirs(slice_output_dir, exist_ok=True)
            
            # 打开PDF文档
            doc = fitz.open(pdf_path)
            
            all_results = {
                'pdf_filename': pdf_filename,
                'total_pages': len(doc),
                'slice_info': {},
                'output_directory': slice_output_dir,
                'slice_summary': {}
            }
            
            print(f"🔍 开始分析PDF布局并切片: {pdf_filename}")
            print(f"📄 总页数: {len(doc)}")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_rect = page.rect
                page_width = float(page_rect.width)
                page_height = float(page_rect.height)
                
                # 获取该页的元素信息
                page_key = str(page_num + 1)
                if page_key in metadata.get('pages', {}):
                    page_elements = metadata['pages'][page_key]['elements']
                else:
                    print(f"  ⚠️ 第{page_num + 1}页: 未找到元数据，跳过")
                    continue
                
                # 分析页面布局
                layout_result = self.analyze_page_layout(
                    page_elements, page_width, page_height
                )
                
                print(f"  📐 第{page_num + 1}页: {layout_result['layout_name']} - {layout_result['analysis_details']}")
                
                # 将页面转换为图片（300dpi分辨率）
                dpi = 300
                scale_factor = dpi / 72.0  # 72dpi为默认值，转换为300dpi
                mat = fitz.Matrix(scale_factor, scale_factor)
                pix = page.get_pixmap(matrix=mat)
                page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # 计算缩放比例
                scale_x = pix.width / page_width
                scale_y = pix.height / page_height
                
                # 根据布局结果进行切片
                page_slices = []
                discarded_slices = []
                slice_counter = 0
                
                for i, region in enumerate(layout_result['regions']):
                    bbox = region['bbox']
                    region_type = region['type']
                    
                    # 计算PDF中预测框尺寸
                    pdf_width = bbox[2] - bbox[0]
                    pdf_height = bbox[3] - bbox[1]
                    
                    # 检查PDF预测框尺寸，丢弃小于等于15px的切片
                    if pdf_width <= 15 or pdf_height <= 15:
                        discarded_slices.append({
                            'region_index': i + 1,
                            'region_type': region_type,
                            'pdf_bbox': bbox,
                            'pdf_width': pdf_width,
                            'pdf_height': pdf_height,
                            'reason': f'PDF预测框尺寸过小 ({pdf_width:.1f}x{pdf_height:.1f}px)'
                        })
                        continue
                    
                    # 将PDF坐标转换为图片坐标
                    img_x1 = int(bbox[0] * scale_x)
                    img_y1 = int(bbox[1] * scale_y)
                    img_x2 = int(bbox[2] * scale_x)
                    img_y2 = int(bbox[3] * scale_y)
                    
                    # 确保坐标在图片范围内
                    img_x1 = max(0, img_x1)
                    img_y1 = max(0, img_y1)
                    img_x2 = min(pix.width, img_x2)
                    img_y2 = min(pix.height, img_y2)
                    
                    # 计算最终图片切片尺寸
                    slice_width = img_x2 - img_x1
                    slice_height = img_y2 - img_y1
                    
                    # 切片图片
                    slice_image = page_image.crop((img_x1, img_y1, img_x2, img_y2))
                    
                    # 生成切片文件名（使用计数器确保连续编号）
                    slice_counter += 1
                    slice_filename = f"page_{page_num + 1}_slice_{slice_counter}.jpg"
                    slice_path = os.path.join(slice_output_dir, slice_filename)
                    
                    # 保存切片（高质量JPEG）
                    slice_image.save(slice_path, 'JPEG', quality=95, dpi=(300, 300))
                    
                    page_slices.append({
                        'slice_index': slice_counter,
                        'region_type': region_type,
                        'pdf_bbox': bbox,
                        'image_bbox': [img_x1, img_y1, img_x2, img_y2],
                        'filename': slice_filename,
                        'file_path': slice_path,
                        'width': slice_width,
                        'height': slice_height
                    })
                
                # 记录页面切片信息
                all_results['slice_info'][page_num + 1] = {
                    'page_number': page_num + 1,
                    'layout_analysis': layout_result,
                    'page_dimensions': {
                        'width': page_width,
                        'height': page_height
                    },
                    'image_dimensions': {
                        'width': pix.width,
                        'height': pix.height,
                        'dpi': 300
                    },
                    'scale_factors': {
                        'scale_x': scale_x,
                        'scale_y': scale_y,
                        'dpi_scale': scale_factor
                    },
                    'slices': page_slices,
                    'slice_count': len(page_slices),
                    'discarded_slices': discarded_slices,
                    'discarded_count': len(discarded_slices)
                }
                
                # 统计不同类型的切片
                regular_slices = len([s for s in page_slices if s['region_type'] != 'irregular_element'])
                irregular_slices = len([s for s in page_slices if s['region_type'] == 'irregular_element'])
                
                # 输出处理结果
                result_msg = f"    ✅ 第{page_num + 1}页切片完成，共{len(page_slices)}个切片"
                if irregular_slices > 0:
                    result_msg += f"（含{irregular_slices}个不规则元素切片）"
                if discarded_slices:
                    result_msg += f"，丢弃{len(discarded_slices)}个小尺寸切片"
                print(result_msg)
            
            doc.close()
            
            # 生成摘要统计
            total_slices = sum(
                page_info['slice_count'] 
                for page_info in all_results['slice_info'].values()
            )
            
            total_discarded = sum(
                page_info['discarded_count'] 
                for page_info in all_results['slice_info'].values()
            )
            
            layout_counts = {}
            for page_info in all_results['slice_info'].values():
                layout_type = page_info['layout_analysis']['layout_type']
                layout_counts[layout_type] = layout_counts.get(layout_type, 0) + 1
            
            # 统计不规则切片
            total_irregular = 0
            for page_info in all_results['slice_info'].values():
                for slice_data in page_info.get('slices', []):
                    if slice_data.get('region_type') == 'irregular_element':
                        total_irregular += 1
            
            all_results['slice_summary'] = {
                'total_slices': total_slices,
                'total_discarded': total_discarded,
                'total_irregular': total_irregular,
                'layout_distribution': layout_counts,
                'processed_pages': len(all_results['slice_info'])
            }
            
            # 保存切片信息到JSON文件
            json_path = os.path.join(slice_output_dir, f"{pdf_filename}_slice_info.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 切片完成!")
            print(f"📊 总切片数: {total_slices}")
            if total_discarded > 0:
                print(f"🗑️ 丢弃小尺寸切片: {total_discarded}")
            print(f"📐 布局分布: {layout_counts}")
            print(f"📁 输出目录: {slice_output_dir}")
            print(f"📋 切片信息: {json_path}")
            
            success_msg = f'成功处理{len(all_results["slice_info"])}页，生成{total_slices}个切片'
            if total_discarded > 0:
                success_msg += f'，丢弃{total_discarded}个小尺寸切片'
            
            return {
                'status': 'success',
                'message': success_msg,
                'results': all_results,
                'json_path': json_path
            }
            
        except Exception as e:
            error_msg = f"切片处理失败: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'status': 'error',
                'message': error_msg,
                'results': {},
                'json_path': ''
            }


def analyze_and_slice_pdf(pdf_path: str, bbox_metadata_path: str, 
                         output_dir: str = "tmp") -> Dict[str, Any]:
    """
    分析PDF布局并进行切片的主函数
    
    Args:
        pdf_path: PDF文件路径
        bbox_metadata_path: bbox元数据文件路径
        output_dir: 输出目录
        
    Returns:
        处理结果
        
            Note:
            - 切片图像固定为300dpi分辨率
            - PDF中预测框宽度或高度小于等于15px的切片将被自动丢弃
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(pdf_path):
            return {
                'status': 'error',
                'message': f'PDF文件不存在: {pdf_path}',
                'results': {},
                'json_path': ''
            }
        
        if not os.path.exists(bbox_metadata_path):
            return {
                'status': 'error',
                'message': f'bbox元数据文件不存在: {bbox_metadata_path}',
                'results': {},
                'json_path': ''
            }
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建布局分析器并处理
        analyzer = LayoutAnalyzer()
        result = analyzer.slice_pdf_images(pdf_path, bbox_metadata_path, output_dir)
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'布局分析和切片失败: {str(e)}',
            'results': {},
            'json_path': ''
        }


if __name__ == "__main__":
    # 测试代码
    test_pdf = "test.pdf"
    test_metadata = "test_bbox_metadata.json"
    
    if os.path.exists(test_pdf) and os.path.exists(test_metadata):
        result = analyze_and_slice_pdf(test_pdf, test_metadata)
        print(f"处理结果: {result}")
    else:
        print("请提供测试文件: test.pdf 和 test_bbox_metadata.json") 