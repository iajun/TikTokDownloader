"""
AI总结服务模块
负责使用DeepSeek AI进行内容总结
"""

from typing import Optional
from openai import OpenAI


class AISummarizer:
    """AI总结服务"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化AI总结服务"""
        self.deepseek_client = None
        
        if api_key:
            self.deepseek_client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            print("DeepSeek客户端初始化成功")
        else:
            print("警告: 未提供DeepSeek API密钥，将跳过AI总结功能")
    
    def summarize_with_ai(self, text: str) -> Optional[str]:
        """使用DeepSeek AI进行内容总结"""
        if not self.deepseek_client:
            print("未配置DeepSeek API，跳过AI总结")
            return None
        
        try:
            print("正在使用AI进行内容总结...")
            
            prompt = f"""
清单体笔记法的常见技巧包括：
1. 简洁备忘：省略无关信息，只记录关键点。
2. 条理清晰：使用有序和无序列表进行逻辑分点。
3. 层级分明：最多分三层，确保信息结构清晰。
4. 高信息密度：每行只表达一个含义，避免多行叙述。
5. 标题明确：每个要点附上简短标题，方便快速浏览。
6. 产品化思维：结构清晰，注意排班、总分总、目录式结构。
7. 视觉优化：使用加粗、斜体、底色、颜色、表情符号等方式进行适当美化。
8. 理清脉络：按时间顺序、操作步骤、事实认知、STAR原则等方式理清思路。


请对以下抖音视频的文字内容进行总结，要求总结分为3部分：

第一部分：知识点列表（这里要求尽可能全，不要有任何遗漏，不要太过简陋，每个知识点下面有对应的说明）

第二部分：核心观点和要点
1. 提取核心观点和要点
2. 分析内容的主要价值

第三部分：你的客观辩证性思考和引发思考的问题

视频文字内容：
{text}
"""
            
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个有上进心爱思考的年轻人，你习惯在抖音视频中学习知识，并擅长总结和分析视频内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            print("AI总结完成")
            return summary
            
        except Exception as e:
            print(f"AI总结失败: {str(e)}")
            return None
