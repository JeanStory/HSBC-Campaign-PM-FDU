import os
import argparse
from typing import List
from pdf2image import convert_from_path
import dashscope
import openai
import json

# dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
# dashscope.api_key = "sk-6872f42e65cd47f9a8157f1a60444601"


def pdf2image(input_file: str) -> List[str]:
    """
    Convert a PDF file to a series of images.

    Args:
        input_file (str): The path to the input PDF file.

    Returns:
        None
    """
    # check if input_file path is a absolute path
    if not os.path.isabs(input_file):
        input_file = os.path.abspath(input_file)
    image_dir = os.path.join(os.path.dirname(input_file), "images")
    os.makedirs(image_dir, exist_ok=True)
    ret = []
    # 创建临时目录存放图片
    images = convert_from_path(input_file)
    for i, image in enumerate(images):
        img_path = os.path.join(image_dir, f"page_{i}.jpg")
        image.save(img_path, "JPEG")
        ret.append(img_path)

    return ret

def ocr_parse(input_file: str) -> str:
    """
    Parse the OCR text from the images.

    Args:
        input_file (str): The path to the input PDF file.

    Returns:
        None
    """
    
    client = dashscope.MultiModalConversation()
    client.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
    client.api_key = "sk-6872f42e65cd47f9a8157f1a60444601"
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "image": f"{input_file}",
                    "min_pixels": 28 * 28 * 4,
                    "max_pixels": 28 * 28 * 8192,
                },
                {
                    "text": "请解析出图片中的文本"
                }
            ]
        }
    ]

    response = client.call(
        messages=messages,
        api_key=client.api_key,
        model="qwen-vl-ocr")
    if response.status_code == 200:
        return response["output"]["choices"][0]["message"].content[0]["text"]
    return ""

def content_structure(content: str) -> str:
    """
    Structure the OCR text.

    Args:
        content (str): The OCR text.

    Returns:
        None
    """
    try:
        client = openai.OpenAI(
            api_key="sk-6872f42e65cd47f9a8157f1a60444601",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        fields_description = """
        包含以下字段：
        - title: 文档标题
        - id: 文档编号
        - customer_name: 客户名称
        - sign_date: 签署日期（YYYY-MM-DD格式）
        - deadline: 截止日期（YYYY-MM-DD格式）
        """
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的文本结构化助手，负责解析文档中的文本，并按照指定的JSON格式返回。最终只返回JSON数据，不返回其他任何内容。"
            },
            {
                "role": "user",
                "content": f"""
请将以下内容解析为JSON结构，{fields_description}。输出应严格遵循该结构。

示例：
输入：项目名称为XX合同，编号为123456，客户名称为客户A，签署于2023年1月1日，截止日期为2023年1月31日
输出：
{{
    "title": "XX合同",
    "id": "123456",
    "customer_name": "客户A",
    "sign_date": "2023-01-01",
    "deadline": "2023-01-31"
}}

现在请解析以下内容：
{content}
                """
            }
        ]
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
        )
        result = completion.choices[0].message.content
        if result:
            json.loads(result)
        return result
    except Exception as e:
        print(e)
        return ""


def parse_pdf(input_file: str) -> str:
    """
    Parse the OCR text from the images.

    Args:
        input_file (str): The path to the input PDF file.

    Returns:
        None
    """
    content = ""
    images = pdf2image(input_file)
    if not images:
        return ""
    images_dir = os.path.dirname(images[0])
    for image in images:
        content += ocr_parse(image) + "\n"
        # os.remove(image)
    # os.rmdir(images_dir)

    ret = content_structure(content)
    return ret
