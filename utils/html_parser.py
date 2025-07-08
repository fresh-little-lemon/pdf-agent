import os
import base64
from typing import List
from openai import OpenAI
from bs4 import BeautifulSoup
import re


def encode_image(image_path: str) -> str:
    """将图片转换为base64编码"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def inference_with_api(image_path: str, prompt: str, sys_prompt: str = "You are a helpful assistant.", 
                      model_id: str = "Qwen/Qwen2.5-VL-72B-Instruct", 
                      min_pixels: int = 512*28*28, max_pixels: int = 2048*28*28) -> str:
    """
    使用API调用Qwen2.5-VL模型进行图片解析
    
    Args:
        image_path: 图片路径
        prompt: 提示词
        sys_prompt: 系统提示词
        model_id: 模型ID
        min_pixels: 最小像素数
        max_pixels: 最大像素数
    
    Returns:
        模型输出的HTML内容
    """
    base64_image = encode_image(image_path)
    
    # 从环境变量获取API密钥
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise Exception("请设置 MODELSCOPE_SDK_TOKEN 或 DASHSCOPE_API_KEY 环境变量")
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://api-inference.modelscope.cn/v1/"
    )

    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": sys_prompt}]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "min_pixels": min_pixels,
                    "max_pixels": max_pixels,
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]
    
    completion = client.chat.completions.create(
        model=model_id,
        messages=messages,
    )
    
    return completion.choices[0].message.content


def clean_and_format_html(full_predict: str) -> str:
    """
    清理和格式化HTML内容
    
    Args:
        full_predict: 原始HTML预测结果
    
    Returns:
        清理后的HTML内容
    """
    soup = BeautifulSoup(full_predict, 'html.parser')
    
    # 正则表达式模式匹配颜色样式
    color_pattern = re.compile(r'\bcolor:[^;]+;?')

    # 查找所有带有style属性的标签并移除颜色样式
    for tag in soup.find_all(style=True):
        original_style = tag.get('style', '')
        new_style = color_pattern.sub('', original_style)
        if not new_style.strip():
            del tag['style']
        else:
            new_style = new_style.rstrip(';')
            tag['style'] = new_style
            
    # 移除data-bbox和data-polygon属性
    for attr in ["data-bbox", "data-polygon"]:
        for tag in soup.find_all(attrs={attr: True}):
            del tag[attr]

    classes_to_update = ['formula.machine_printed', 'formula.handwritten']
    # 更新特定的类名
    for tag in soup.find_all(class_=True):
        if hasattr(tag, 'attrs') and 'class' in tag.attrs:
            new_classes = [cls if cls not in classes_to_update else 'formula' for cls in tag.get('class', [])]
            tag['class'] = list(dict.fromkeys(new_classes))  # 去重并更新类名

    # 清理特定类名的div内容
    for div in soup.find_all('div', class_='image caption'):
        div.clear()
        div['class'] = ['image']

    classes_to_clean = ['music sheet', 'chemical formula', 'chart']
    # 清理特定类名的标签内容并移除format属性
    for class_name in classes_to_clean:
        for tag in soup.find_all(class_=class_name):
            if hasattr(tag, 'clear'):
                tag.clear()
                if 'format' in tag.attrs:
                    del tag['format']

    # 手动构建输出字符串
    output = []
    if soup.body:
        for child in soup.body.children:
            if hasattr(child, 'name'):  # Tag object
                output.append(str(child))
                output.append('\n')
            elif isinstance(child, str) and not child.strip():
                continue  # 忽略空白文本节点
    
    complete_html = f"""```html\n<html><body>\n{" ".join(output)}</body></html>\n```"""
    return complete_html


def parse_images_to_html(image_paths: List[str], pdf_filename: str, output_dir: str = "tmp", start_page: int = 1, enable_clean: bool = False) -> List[str]:
    """
    将图片列表解析为HTML格式并保存
    
    Args:
        image_paths: 图片路径列表
        pdf_filename: PDF文件名（不含扩展名）
        output_dir: 输出目录
        start_page: 起始页码，默认为1
        enable_clean: 是否启用HTML清理功能，默认为False
    
    Returns:
        生成的HTML文件路径列表
    """
    # 创建HTML输出目录
    html_output_dir = os.path.join(output_dir, f"{pdf_filename}_html")
    if not os.path.exists(html_output_dir):
        os.makedirs(html_output_dir)
    
    system_prompt = "You are an AI specialized in recognizing and extracting text from images. Your mission is to analyze the image document and generate the result in QwenVL Document Parser HTML format using specified tags while maintaining user privacy and data integrity."
    prompt = "QwenVL HTML"
    
    html_files = []
    
    for i, image_path in enumerate(image_paths):
        page_number = start_page + i
        try:
            print(f"正在解析第 {page_number} 页图片...")
            
            # 调用API进行解析
            raw_html = inference_with_api(
                image_path=image_path,
                prompt=prompt,
                sys_prompt=system_prompt
            )
            
            # 根据设置决定是否清理和格式化HTML
            if enable_clean:
                final_html = clean_and_format_html(raw_html)
            else:
                final_html = raw_html
            
            # 生成HTML文件名
            html_filename = f"page_{page_number}.html"
            html_path = os.path.join(html_output_dir, html_filename)
            
            # 保存HTML文件
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            html_files.append(html_path)
            print(f"第 {page_number} 页解析完成，保存到: {html_path}")
            
        except Exception as e:
            print(f"解析第 {page_number} 页时出错: {str(e)}")
            continue
    
    return html_files


def get_api_status() -> dict:
    """
    检查API状态和配置
    
    Returns:
        API状态信息
    """
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN") or os.getenv("DASHSCOPE_API_KEY")
    
    return {
        "api_key_configured": bool(api_key),
        "api_key_length": len(api_key) if api_key else 0,
        "base_url": "https://api-inference.modelscope.cn/v1/"
    }


def sequential_parse_images_to_html(image_paths: List[str], pdf_filename: str, output_dir: str = "tmp", enable_clean: bool = False) -> List[str]:
    """
    顺序解析图片为HTML（推荐方式，页码对齐且不会覆盖）
    
    Args:
        image_paths: 图片路径列表
        pdf_filename: PDF文件名
        output_dir: 输出目录
        enable_clean: 是否启用HTML清理功能
    
    Returns:
        生成的HTML文件路径列表
    """
    return parse_images_to_html(image_paths, pdf_filename, output_dir, start_page=1, enable_clean=enable_clean)


def parallel_parse_images_to_html(image_paths: List[str], pdf_filename: str, output_dir: str = "tmp", 
                                  max_workers: int = 3, enable_clean: bool = False) -> List[str]:
    """
    并行解析图片为HTML（注意：需要确保API支持并发调用）
    
    Args:
        image_paths: 图片路径列表
        pdf_filename: PDF文件名
        output_dir: 输出目录
        max_workers: 最大并行工作数
        enable_clean: 是否启用HTML清理功能
    
    Returns:
        生成的HTML文件路径列表
    """
    import concurrent.futures
    import time
    
    # 创建HTML输出目录
    html_output_dir = os.path.join(output_dir, f"{pdf_filename}_html")
    if not os.path.exists(html_output_dir):
        os.makedirs(html_output_dir)
    
    system_prompt = "You are an AI specialized in recognizing and extracting text from images. Your mission is to analyze the image document and generate the result in QwenVL Document Parser HTML format using specified tags while maintaining user privacy and data integrity. "
    prompt = "QwenVL HTML"
    
    def process_single_image(args):
        image_path, page_number = args
        try:
            print(f"正在解析第 {page_number} 页图片...")
            
            # 调用API进行解析
            raw_html = inference_with_api(
                image_path=image_path,
                prompt=prompt,
                sys_prompt=system_prompt
            )
            
            # 根据设置决定是否清理和格式化HTML
            if enable_clean:
                final_html = clean_and_format_html(raw_html)
            else:
                final_html = raw_html
            
            # 生成HTML文件名
            html_filename = f"page_{page_number}.html"
            html_path = os.path.join(html_output_dir, html_filename)
            
            # 保存HTML文件
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            print(f"第 {page_number} 页解析完成，保存到: {html_path}")
            return html_path
            
        except Exception as e:
            print(f"解析第 {page_number} 页时出错: {str(e)}")
            return None
    
    # 准备参数：(image_path, page_number)
    args_list = [(image_path, i + 1) for i, image_path in enumerate(image_paths)]
    
    html_files = []
    
    # 使用线程池进行并行处理
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_page = {executor.submit(process_single_image, args): args[1] for args in args_list}
        
        # 获取结果
        for future in concurrent.futures.as_completed(future_to_page):
            page_number = future_to_page[future]
            try:
                html_path = future.result()
                if html_path:
                    html_files.append(html_path)
            except Exception as e:
                print(f"第 {page_number} 页处理异常: {str(e)}")
    
    # 按页码排序
    html_files.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
    
    return html_files


def parse_all_images_to_html(image_paths: List[str], pdf_filename: str, output_dir: str = "tmp", 
                            parallel: bool = False, max_workers: int = 3, enable_clean: bool = False) -> List[str]:
    """
    解析所有图片为HTML格式（支持串行和并行处理）
    
    Args:
        image_paths: 图片路径列表
        pdf_filename: PDF文件名
        output_dir: 输出目录
        parallel: 是否使用并行处理
        max_workers: 并行处理的最大工作线程数
        enable_clean: 是否启用HTML清理功能
    
    Returns:
        生成的HTML文件路径列表
    """
    if parallel:
        print(f"使用并行处理模式，{max_workers}个线程...")
        return parallel_parse_images_to_html(image_paths, pdf_filename, output_dir, max_workers, enable_clean)
    else:
        print("使用串行处理模式...")
        return sequential_parse_images_to_html(image_paths, pdf_filename, output_dir, enable_clean)


def insert_extracted_images_to_html(html_files: List[str], extracted_images_dir: str, pdf_filename: str) -> List[str]:
    """
    将提取的图片插入到对应页的HTML中的img元素位置
    
    Args:
        html_files: HTML文件路径列表
        extracted_images_dir: 提取图片的目录路径
        pdf_filename: PDF文件名
    
    Returns:
        更新后的HTML文件路径列表
    """
    import re
    
    updated_html_files = []
    
    # 获取提取图片的文件夹路径
    figure_dir = os.path.join(extracted_images_dir, f"{pdf_filename}_figure")
    
    if not os.path.exists(figure_dir):
        print(f"警告：图片文件夹 {figure_dir} 不存在")
        return html_files
    
    # 获取所有提取的图片
    extracted_images = {}
    if os.path.exists(figure_dir):
        for img_file in os.listdir(figure_dir):
            if img_file.startswith(pdf_filename):
                # 解析文件名：{pdf文件名}_page_{页码}_{图片序号}.{扩展名}
                pattern = rf"{re.escape(pdf_filename)}_page_(\d+)_(\d+)\.(jpg|jpeg|png|gif|bmp)"
                match = re.match(pattern, img_file)
                if match:
                    page_num = int(match.group(1))
                    img_index = int(match.group(2))
                    img_path = os.path.abspath(os.path.join(figure_dir, img_file))
                    
                    if page_num not in extracted_images:
                        extracted_images[page_num] = {}
                    extracted_images[page_num][img_index] = img_path
    
    # 处理每个HTML文件
    for html_file in html_files:
        try:
            # 从文件名中提取页码
            html_filename = os.path.basename(html_file)
            page_match = re.match(r'page_(\d+)\.html', html_filename)
            if not page_match:
                updated_html_files.append(html_file)
                continue
            
            page_num = int(page_match.group(1))
            
            # 读取HTML文件
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找所有img元素
            img_tags = soup.find_all('img')
            
            if page_num in extracted_images and img_tags:
                # 为每个img标签添加src属性
                available_images = extracted_images[page_num]
                img_index = 1
                
                for img_tag in img_tags:
                    if img_index in available_images:
                        # 添加src属性，使用绝对路径
                        img_path = available_images[img_index]
                        img_tag['src'] = img_path
                        print(f"为第{page_num}页第{img_index}张图片添加路径: {img_path}")
                        img_index += 1
                    else:
                        print(f"警告：第{page_num}页第{img_index}张图片未找到对应的提取图片")
                        img_index += 1
            
            # 保存更新后的HTML文件
            updated_html = str(soup)
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(updated_html)
            
            updated_html_files.append(html_file)
            print(f"✅ 更新HTML文件: {html_file}")
            
        except Exception as e:
            print(f"❌ 更新HTML文件 {html_file} 时出错: {str(e)}")
            updated_html_files.append(html_file)
    
    return updated_html_files


def parse_and_insert_images(pdf_file_bytes: bytes, pdf_filename: str, output_dir: str = "tmp", 
                           parallel: bool = False, max_workers: int = 3, enable_clean: bool = False,
                           insert_extracted_images: bool = False) -> dict:
    """
    完整的PDF解析流程：转换为图片、解析为HTML、可选插入提取的图片
    
    Args:
        pdf_file_bytes: PDF文件字节数据
        pdf_filename: PDF文件名
        output_dir: 输出目录
        parallel: 是否使用并行处理
        max_workers: 工作线程数
        enable_clean: 是否启用HTML清理
        insert_extracted_images: 是否插入提取的图片到HTML中
    
    Returns:
        包含所有结果路径的字典
    """
    from utils.pdf_converter import pdf_to_jpg
    from utils.image_extractor import extract_images_from_pdf
    
    results = {
        'converted_images': [],
        'extracted_images': [],
        'html_files': [],
        'status': 'success',
        'message': ''
    }
    
    try:
        # 步骤1: 转换PDF为图片
        print("步骤1/4: 转换PDF为图片...")
        converted_images = pdf_to_jpg(
            pdf_file_bytes,
            pdf_filename=pdf_filename,
            output_dir=output_dir,
            dpi=150
        )
        results['converted_images'] = converted_images
        print(f"✅ PDF转换完成，共生成 {len(converted_images)} 张图片")
        
        # 步骤2: 解析图片为HTML
        print("步骤2/4: 解析图片为HTML...")
        html_files = parse_all_images_to_html(
            image_paths=converted_images,
            pdf_filename=pdf_filename,
            output_dir=output_dir,
            parallel=parallel,
            max_workers=max_workers,
            enable_clean=enable_clean
        )
        results['html_files'] = html_files
        print(f"✅ HTML解析完成，共生成 {len(html_files)} 个HTML文件")
        
        # 步骤3: 提取PDF中的图片（如果需要）
        if insert_extracted_images:
            print("步骤3/4: 提取PDF中的图片...")
            extracted_images = extract_images_from_pdf(
                pdf_file_bytes,
                pdf_filename,
                output_dir
            )
            results['extracted_images'] = extracted_images
            print(f"✅ 图片提取完成，共提取 {len(extracted_images)} 张图片")
            
            # 步骤4: 将提取的图片插入到HTML中
            print("步骤4/4: 将提取的图片插入到HTML中...")
            updated_html_files = insert_extracted_images_to_html(
                html_files,
                output_dir,
                pdf_filename
            )
            results['html_files'] = updated_html_files
            print(f"✅ 图片插入完成，更新了 {len(updated_html_files)} 个HTML文件")
        else:
            print("跳过图片提取和插入步骤")
        
        results['message'] = "所有步骤完成成功"
        
    except Exception as e:
        results['status'] = 'error'
        results['message'] = f"处理过程中出现错误: {str(e)}"
        print(f"❌ 错误: {str(e)}")
    
    return results


def batch_parse_images_to_html(image_paths: List[str], pdf_filename: str, output_dir: str = "tmp", 
                               batch_size: int = 5, use_parallel: bool = False, enable_clean: bool = False) -> List[str]:
    """
    批量解析图片为HTML（兼容性函数，现在使用顺序处理确保页码正确）
    
    Args:
        image_paths: 图片路径列表
        pdf_filename: PDF文件名
        output_dir: 输出目录
        batch_size: 已废弃，保留兼容性
        use_parallel: 是否使用并行处理
        enable_clean: 是否启用HTML清理功能
    
    Returns:
        生成的HTML文件路径列表
    """
    if use_parallel:
        print("使用并行处理模式...")
        return parallel_parse_images_to_html(image_paths, pdf_filename, output_dir, max_workers=3, enable_clean=enable_clean)
    else:
        print("使用顺序处理模式...")
        return sequential_parse_images_to_html(image_paths, pdf_filename, output_dir, enable_clean=enable_clean) 