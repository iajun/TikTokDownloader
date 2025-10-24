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
**请对以下抖音视频的文字内容进行总结，要求总结分为3部分：**

---

### **第一部分：知识点列表**

* **要求**：列出视频中的所有知识点，尽量详细，不遗漏任何关键点。
* **每个知识点下面包含以下内容**：

  1. **定义**：该知识点的基本概念或定义。
  2. **应用场景**：该知识点在实际中的应用情况。
  3. **关键步骤**：如果涉及操作或流程，列出实现该知识点的关键步骤或流程。
  4. **实际案例**：如果可能，列出一个实际案例或示例来说明该知识点的应用。

---

### **第二部分：核心观点和要点**

* **要求**：提炼出视频中的核心观点和要点，并进行深入分析。

  1. **核心观点**：视频中的核心思想或核心观点。
  2. **关键要点**：每个核心观点下的具体要点，简洁明了。
  3. **价值分析**：分析视频内容的主要价值所在，例如：它能解决什么问题、提升哪些能力、应用到哪些领域等。

---

### **第三部分：思考感悟和疑问**

* **要求**：根据视频内容，提出自己的思考和感悟，并提出一些问题或疑问。

  1. **思考感悟**：

     * 如何将视频中的知识点应用到实际生活或工作中？
     * 是否与自己目前的学习或工作有直接关联？能否优化已有的工作方式或认知？
  2. **疑问**：

     * 在理解视频内容时，是否有不清楚的地方？
     * 有没有深层次的问题或争议？是否有对该知识点的不同解释或观点？
     * 是否有相关领域中的其他观点或实践方法可以对比或补充？

---

### **目标**：

* 高效学习，提升认知。
* 清晰、条理地总结视频中的内容，便于后续回顾和思考。
* 通过总结与思考，深化对内容的理解与应用。

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
